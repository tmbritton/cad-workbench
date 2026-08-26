#!/usr/bin/env python
"""Judge every model in a project against the design-for-FDM rules.

    mise check                        # every project
    mise check ball-bearing           # one project
    mise check ball-bearing flanged   # one model

`mise test` asks whether a model is what it says it is. This asks the different
question of whether it can be printed: overhangs with nothing under them, walls
thinner than a pair of beads, a footprint that will lift, a base too narrow for
what stands on it. Nothing here is fatal on its own — every rule has a
legitimate exception, and a model declares its own in an ALLOW dict:

    ALLOW = {"overhang": "the seat ring, printed on support; ring test, 13 Aug 2026"}

Allowed findings are still reported, dimmed, with their reason. They are the
part of the design that somebody decided about, which makes them the part most
worth being able to read later.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from cadkit import dfm, measure
from cadkit.discover import is_model, load, model_files, project_path, projects
from cadkit.export import GREEN, GREY, OFF, PROJECTS, RED, YELLOW, material_of
from cadkit.select import shape

SEVERITY = {
    "fail": (RED, "FAIL"),
    "warn": (YELLOW, "warn"),
    "allowed": (GREY, "ok  "),
}


def check_project(project: Path, only: list[str], limits: dfm.Limits, show_allowed: bool):
    """Returns (models checked, models with a surviving failure)."""
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
    checked = failed = 0

    # Before any geometry: a dimension nobody has verified is a fault in the
    # part that no amount of measuring the geometry can find, because the
    # geometry is a faithful model of the wrong number.
    for entry in measure.provisional(project):
        print(
            f"  {YELLOW}warn{OFF} {entry.name} = {entry.value:g} mm is still "
            f"provisional: {entry.how}"
        )

    # Same tolerance as the build driver: one model that will not build is not
    # a reason to learn nothing about the rest of the project.
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

            try:
                part = shape(module.build())
                report = dfm.inspect_part(
                    part,
                    material=material_of(module),
                    allow=getattr(module, "ALLOW", None),
                    limits=limits,
                )
            except FileNotFoundError as missing:
                print(f"  {GREY}skip{OFF} {path.stem}: needs {missing}")
                continue
            except (TypeError, ValueError) as exc:  # a malformed ALLOW
                print(f"  {RED}FAIL{OFF} {path.stem}: {exc}")
                failed += 1
                continue
            except Exception:
                print(f"  {RED}FAIL{OFF} {path.stem}: build raised")
                traceback.print_exc()
                failed += 1
                continue

            checked += 1
            if report.failures:
                failed += 1

            shown = [
                f
                for f in report.findings
                if f.severity != "allowed" or show_allowed or f.reason
            ]
            if not shown:
                print(f"  {GREEN}ok{OFF}   {path.stem}")
                continue
            print(f"  {GREY}{path.stem}{OFF}")
            for finding in shown:
                colour, label = SEVERITY[finding.severity]
                print(f"    {colour}{label}{OFF} {finding.line()}")

    return checked, failed


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join(__doc__.splitlines()[2:]),
    )
    ap.add_argument("project", nargs="?", help="project folder name; omit to check all")
    ap.add_argument("models", nargs="*", help="model names; omit to check the project")
    ap.add_argument(
        "--samples",
        type=int,
        default=dfm.Limits.samples,
        help="surface points used by the wall-thickness rule (default %(default)s)",
    )
    ap.add_argument(
        "--rules",
        action="store_true",
        help="list the rules and their thresholds, and check nothing",
    )
    args = ap.parse_args()

    if args.rules:
        limits = dfm.Limits()
        print(dfm.Limits.__doc__)
        for name in dfm.RULES:
            summary = (dfm._IMPLEMENTATIONS[name].__doc__ or "").strip().splitlines()[0]
            print(f"  {name:<14} {summary}")
        print(f"\nthresholds: {limits}")
        return 0

    limits = dfm.Limits(samples=args.samples)

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

    checked = failed = 0
    for project in chosen:
        c, f = check_project(project, args.models, limits, show_allowed=True)
        checked += c
        failed += f

    if failed:
        print(
            f"\n{RED}{failed} model(s) with something unprintable{OFF}, {checked} checked"
        )
        return 1
    print(f"\n{GREEN}{checked} model(s) checked{OFF}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
