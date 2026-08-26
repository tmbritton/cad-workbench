#!/usr/bin/env python
"""Look at what a built part is actually made of, so a selector can name it.

    mise inspect ball-bearing flanged        # faces, edges, what touches the plate
    mise inspect ball-bearing flanged --faces
    mise inspect pvc-6-way-converter --against inputs/original.stl

The file is `probe.py` and the task is `inspect` because a `tools/inspect.py`
shadows the standard library's `inspect` for everything under this repo, and
what breaks is `typing_extensions` at import time, two libraries away, with a
traceback that mentions neither this file nor build123d.

AGENTS.md says to select geometry by meaning rather than by list position, and
means it: an index into `faces()` is stable only until the next operation. But
naming a face by what it is requires knowing what is there, and until now the
only way to find out was to print things from inside `build()` and delete them
afterwards.

This is that, kept. It answers three questions:

  * **what the part is** — bodies, faces, edges by kind, size, volume, mass;
  * **where the flat faces are** — the horizontal ones by height, which is what
    `horizontal_face_at` and `cavity_ceiling` are looking for, and the largest
    faces by area, which is usually what you meant by "the top";
  * **how far it has drifted** — against the mesh it was rebuilt from, if the
    model declares a `TARGET` or one is named with `--against`.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from collections import Counter
from pathlib import Path

from build123d import Axis, CenterOf, Plane

from cadkit.compare import compare
from cadkit.discover import find_project, is_model, load, model_files, project_path
from cadkit.export import GREEN, GREY, OFF, RED, ROOT, YELLOW, material_of
from cadkit.select import shape


def overview(part, material) -> list[str]:
    """Bodies, faces, edges, size, mass — the shape of the thing in six lines."""
    box = part.bounding_box()
    faces, edges = part.faces(), part.edges()
    com = part.center(CenterOf.MASS)

    lines = [
        f"size     {box.size.X:.2f} x {box.size.Y:.2f} x {box.size.Z:.2f} mm",
        f"origin   x {box.min.X:.2f}..{box.max.X:.2f}   "
        f"y {box.min.Y:.2f}..{box.max.Y:.2f}   z {box.min.Z:.2f}..{box.max.Z:.2f}",
        f"volume   {part.volume / 1000:.2f} cm3"
        + (f"   {material.mass(part.volume):.0f} g {material.name}" if material else ""),
        f"mass at  {com.X:.2f}, {com.Y:.2f}, {com.Z:.2f}",
        f"bodies   {len(part.solids())}",
        f"faces    {len(faces)}  ({_kinds(faces)})",
        f"edges    {len(edges)}  ({_kinds(edges)})",
    ]
    return lines


def _kinds(shapes) -> str:
    """ "98 circle, 81 line" -- what the geometry is made of, commonest first."""
    counted = Counter(str(s.geom_type).removeprefix("GeomType.").lower() for s in shapes)
    return ", ".join(f"{n} {kind}" for kind, n in counted.most_common())


def horizontals(part, limit: int) -> list[str]:
    """Flat faces by height — what `horizontal_face_at` is indexed on.

    Grouped by height rather than listed one per line: a shelled part has
    dozens of coplanar faces at the same z, and thirty lines saying 18.00 mm
    tell you less than one line saying there are thirty of them there.
    """
    flat = part.faces().filter_by(Plane.XY).sort_by(Axis.Z)
    if not flat:
        return ["(no faces parallel to the plate)"]

    at: dict[float, list] = {}
    for face in flat:
        at.setdefault(round(face.center().Z, 3), []).append(face)

    base = min(at)
    lines = []
    for z in sorted(at)[:limit]:
        group = at[z]
        area = sum(f.area for f in group)
        facing = "down" if group[0].normal_at().Z < 0 else "up"
        note = "  <- on the plate" if z == base and facing == "down" else ""
        count = f"{len(group)} faces" if len(group) > 1 else "1 face"
        lines.append(
            f"  z {z:>9.3f}   {count:<9}  {area:>10.1f} mm2  facing {facing}{note}"
        )
    if len(at) > limit:
        lines.append(f"  {GREY}... and {len(at) - limit} more heights{OFF}")
    return lines


def biggest(part, limit: int) -> list[str]:
    """The largest faces by area — usually what somebody means by "the top"."""
    faces = sorted(part.faces(), key=lambda f: -f.area)[:limit]
    lines = []
    for face in faces:
        centre, normal = face.center(), face.normal_at()
        kind = str(face.geom_type).removeprefix("GeomType.").lower()
        lines.append(
            f"  {face.area:>10.1f} mm2  {kind:<9} at "
            f"{centre.X:>8.2f}, {centre.Y:>8.2f}, {centre.Z:>8.2f}  "
            f"facing {normal.X:>5.2f}, {normal.Y:>5.2f}, {normal.Z:>5.2f}"
        )
    return lines


def inspect_model(project: Path, name: str, args) -> int:
    with project_path(project):
        module = load(name)
        if not is_model(module):
            print(f"{RED}{name}.py defines no build(){OFF}", file=sys.stderr)
            return 1
        try:
            part = shape(module.build())
        except FileNotFoundError as missing:
            print(f"{GREY}skip{OFF} {name}: needs {missing}")
            return 0
        material = material_of(module)
        target = args.against or getattr(module, "TARGET", None)

    print(f"{GREEN}{project.name}/{name}{OFF}")
    for line in overview(part, material):
        print(f"  {line}")

    print(f"\n{GREY}flat faces, by height{OFF}")
    for line in horizontals(part, args.limit):
        print(line)

    if args.faces:
        print(f"\n{GREY}largest faces{OFF}")
        for line in biggest(part, args.limit):
            print(line)

    if target:
        path = Path(target)
        if not path.is_absolute():
            path = ROOT / path
        print(f"\n{GREY}against {Path(target)}{OFF}")
        try:
            drift = compare(part, path, samples=args.samples)
        except FileNotFoundError:
            print(f"  {YELLOW}not found{OFF} — {path}")
            return 0
        print(f"  ours -> theirs   {drift.ours_to_theirs.line()}")
        print(f"  theirs -> ours   {drift.theirs_to_ours.line()}")
        print(
            f"  {GREY}the second is the one to read for a feature that went "
            f"missing; the first for material we added{OFF}"
        )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join(__doc__.splitlines()[2:]),
    )
    ap.add_argument("project", help="project folder name")
    ap.add_argument("model", nargs="?", help="model name; omit for the project's default")
    ap.add_argument("--faces", action="store_true", help="also list the largest faces")
    ap.add_argument(
        "--against", metavar="MESH", help="compare against a mesh, overriding TARGET"
    )
    ap.add_argument(
        "--limit", type=int, default=15, help="rows per section (default %(default)s)"
    )
    ap.add_argument(
        "--samples", type=int, default=4000, help="surface points used by --against"
    )
    args = ap.parse_args()

    project = find_project(args.project)
    if args.model:
        name = args.model.removesuffix(".py")
        if name not in {p.stem for p in model_files(project)}:
            names = ", ".join(p.stem for p in model_files(project))
            print(f"{RED}no such model: {name}{OFF}", file=sys.stderr)
            print(f"{GREY}available: {names}{OFF}", file=sys.stderr)
            return 1
    else:
        # Same rule as `mise dev`: the model that claims DEFAULT, else the
        # first alphabetically. Reaching for a family and getting whichever
        # sorts first is a papercut every time.
        name = _default(project)

    try:
        return inspect_model(project, name, args)
    except Exception:
        print(f"{RED}build failed{OFF}", file=sys.stderr)
        traceback.print_exc()
        return 1


def _default(project: Path) -> str:
    with project_path(project):
        claimed = []
        first = None
        for path in model_files(project):
            try:
                module = load(path.stem)
            except Exception:
                continue
            if not is_model(module):
                continue
            first = first or path.stem
            if getattr(module, "DEFAULT", False):
                claimed.append(path.stem)
    if len(claimed) > 1:
        raise SystemExit(
            f"two models claim DEFAULT in {project.name}: {', '.join(claimed)}"
        )
    if not first:
        raise SystemExit(f"{project.name} has no models")
    return claimed[0] if claimed else first


if __name__ == "__main__":
    raise SystemExit(main())
