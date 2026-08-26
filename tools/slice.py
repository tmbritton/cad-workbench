#!/usr/bin/env python
"""Ask the slicer what a part will cost, and optionally write it a 3MF.

    mise slice                              # every project
    mise slice dehydrator-riser             # one project
    mise slice dehydrator-riser collar      # one model
    mise slice dehydrator-riser collar --3mf

The build report's mass is density times solid volume — an upper bound that
assumes the part is solid through. This is the real number, from the program
that will actually print it: minutes and grams, with the layer height, wall
count and infill it used to get there so the figure can be read in context.

`--3mf` writes `exports/<project>/<model>.3mf` with those settings already
embedded, so the slicer opens on a plate that needs no setting up. It is the
same run either way — the 3MF is what slicing produced, not a second act — so
there is one command rather than two.

A model that must be printed with support, or with a brim, says so in its own
file next to its material — those are facts about the part, learned on a test
print, and they belong where the rest of its dimensions are:

    SUPPORT = True  # the seat ring hangs over its own cavity; validated 13 Aug
    BRIM = 5.0      # 90 mm tall on 17.5 cm2 of bed contact
"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from cadkit import dfm, slicing
from cadkit.discover import is_model, load, model_files, project_path, projects
from cadkit.export import (
    EXPORTS,
    GREEN,
    GREY,
    OFF,
    PROJECTS,
    RED,
    ROOT,
    YELLOW,
    build_model,
    material_of,
)
from cadkit.materials import BY_NAME


def slice_project(project: Path, only: list[str], args) -> tuple[int, int]:
    """Returns (sliced, failed). A model with no declared filament is skipped."""
    candidates = model_files(project)
    if only:
        wanted = {name.removesuffix(".py") for name in only}
        missing = wanted - {p.stem for p in candidates}
        if missing:
            names = ", ".join(sorted(missing))
            print(f"{RED}no such model in {project.name}: {names}{OFF}", file=sys.stderr)
            return 0, len(missing)
        candidates = [p for p in candidates if p.stem in wanted]

    print(f"{GREY}{project.name}{OFF}")
    sliced = failed = 0

    with project_path(project):
        for path in candidates:
            try:
                module = load(path.stem)
            except Exception:
                print(f"  {RED}FAIL{OFF} {path.stem}: import failed")
                traceback.print_exc()
                failed += 1
                continue
            if not is_model(module):
                continue

            material = BY_NAME[args.material] if args.material else material_of(module)
            if material is None or not material.filament:
                # Not a failure. A project may not have chosen its filament yet
                # and be right not to — pvc-6-way-converter says so in its
                # README, because the choice depends on where the frame lives
                # and what load it takes. Same treatment as a model whose
                # third-party geometry is absent: say what is missing, move on.
                print(
                    f"  {GREY}skip{OFF} {path.stem}: no material declared, so there "
                    f"is nothing to weigh (set MATERIAL, or pass --material)"
                )
                continue

            support = args.support or bool(getattr(module, "SUPPORT", False))
            width = args.brim if args.brim is not None else getattr(module, "BRIM", 0)
            extra = slicing.brim(width) if width else None

            try:
                # Built and exported first: the slicer takes an STL, and the
                # one on disk may be older than the model. Findings come along
                # because a brim is the answer to two of them.
                result = build_model(
                    project=project.name,
                    name=path.stem,
                    build_fn=module.build,
                    check_fn=getattr(module, "check", None),
                    material=material,
                    rules=("warp_risk", "stability"),
                    allow=getattr(module, "ALLOW", None),
                )
                cut = slicing.slice_stl(
                    result.stl,
                    material,
                    slicing.workdir_for(project.name, path.stem),
                    layer_h=args.layer,
                    support=support,
                    findings=result.findings,
                    extra=extra,
                    export_3mf=f"{path.stem}.3mf" if args.three_mf else None,
                )
            except FileNotFoundError as missing:
                print(f"  {GREY}skip{OFF} {path.stem}: needs {missing}")
                continue
            except slicing.SlicerError as exc:
                print(f"  {RED}FAIL{OFF} {path.stem}: {exc}")
                failed += 1
                continue
            except AssertionError as exc:
                print(f"  {RED}FAIL{OFF} {path.stem}: {exc}")
                failed += 1
                continue
            except Exception:
                print(f"  {RED}FAIL{OFF} {path.stem}: build raised")
                traceback.print_exc()
                failed += 1
                continue

            sliced += 1
            name = material.name if material else "?"
            print(f"  {GREEN}ok{OFF}   {path.stem:<14} {cut.line()}  {GREY}{name}{OFF}")

            if args.three_mf:
                out = EXPORTS / project.name / f"{path.stem}.3mf"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes((cut.gcode.parent / f"{path.stem}.3mf").read_bytes())
                print(f"       {GREY}-> {out.relative_to(ROOT)}{OFF}")

            # Said plainly rather than folded into the number, because a
            # reader who does not know support was on will believe the grams.
            declared = []
            if support:
                declared.append("support everywhere")
            if width:
                declared.append(f"a {width:g} mm brim")
            if declared:
                how = " and ".join(declared)
                print(f"  {YELLOW}note{OFF} {path.stem}: sliced with {how}")

    return sliced, failed


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join(__doc__.splitlines()[2:]),
    )
    ap.add_argument("project", nargs="?", help="project folder name; omit to slice all")
    ap.add_argument("models", nargs="*", help="model names; omit to slice the project")
    ap.add_argument(
        "--3mf",
        dest="three_mf",
        action="store_true",
        help="also write exports/<project>/<model>.3mf with the settings embedded",
    )
    ap.add_argument(
        "--support",
        action="store_true",
        help="slice with support everywhere, whatever the model declares",
    )
    ap.add_argument(
        "--brim",
        type=float,
        metavar="MM",
        help="brim width, overriding the model's own BRIM; 0 for none",
    )
    ap.add_argument(
        "--material",
        choices=sorted(BY_NAME),
        help="override the model's declared filament",
    )
    ap.add_argument(
        "--layer",
        type=float,
        default=dfm.printer.LAYER_H,
        help="layer height in mm (default %(default)s)",
    )
    args = ap.parse_args()

    try:
        print(f"{GREY}{' '.join(slicing.find_slicer())}{OFF}")
    except slicing.SlicerError as exc:
        print(f"{RED}{exc}{OFF}", file=sys.stderr)
        return 1

    available = projects()
    if not available:
        print(f"{RED}no projects found in {PROJECTS}{OFF}", file=sys.stderr)
        return 1
    if args.project:
        chosen = [p for p in available if p.name == args.project]
        if not chosen:
            names = ", ".join(p.name for p in available)
            print(f"{RED}no such project: {args.project}{OFF}", file=sys.stderr)
            print(f"{GREY}available: {names}{OFF}", file=sys.stderr)
            return 1
    else:
        chosen = available

    sliced = failed = 0
    for project in chosen:
        s, f = slice_project(project, args.models, args)
        sliced += s
        failed += f

    if failed:
        print(f"\n{RED}{failed} failed{OFF}, {sliced} sliced")
        return 1
    print(f"\n{GREEN}{sliced} model(s) sliced{OFF}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
