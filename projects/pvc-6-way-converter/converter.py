"""Six-way PVC converter — the blind arm drilled through.

The part itself comes from an external OpenSCAD generator, not from here; the
STL in `inputs/` is its output and every dimension in it was checked against
the pipe with calipers. Five of the six arms are open sockets. The large one is
not: its bore stops 2.95 mm short of the mouth, leaving a solid disc where the
pipe has to go. That is the generator's bug, and everything else about the mesh
is right, so this model repairs the output rather than reproducing the part.

The repair is a single subtraction, and it is chosen so that no number has to
be invented. The cap is exactly the bore's own floor swept out to the mouth, so
extruding that face and removing it continues the bore it was blocking — same
diameter, same facets, nothing else touched. The wall left behind is therefore
the arm's own, and the arm's own wall is 2.0 mm, the same as the other five.

    mise build pvc-6-way-converter
"""

from __future__ import annotations

import math
from pathlib import Path

from build123d import Mesher, Part, Plane, Vector, extrude

from cadkit import fits_bed, single_solid

# The generator's output. Untracked: it is an input to this workspace, not
# something this workspace produces. Path is relative to this file so the model
# runs the same directly as it does under `mise build`.
SOURCE = (
    Path(__file__).resolve().parents[2]
    / "inputs"
    / "quarter-inch-6-way-half-inch-converter.stl"
)

# ---- measured (off the source mesh, mm) -----------------------------------
# The five good arms, and the large one. Both wall figures are the same 2.0,
# which is what makes the repair below need no dimension of its own.
SMALL_OD, SMALL_ID = 13.7, 9.7
LARGE_OD, LARGE_ID = 19.8, 15.8
WALL = 2.0  # (OD - ID) / 2, and equal on both sizes
REACH = 16.85  # centre of the part to the mouth of any arm

# The bug: material between the large arm's bore floor and its mouth.
CAP_T = 2.95

# ---- geometry helpers ------------------------------------------------------
# An arm runs along one of the three axes, so anything square to that axis is a
# face on the plane of the other two.
AXES = ("X", "Y", "Z")
SQUARE_TO = {"X": Plane.YZ, "Y": Plane.XZ, "Z": Plane.XY}


def _radius(point, axis: str) -> float:
    """How far a point sits off an arm's axis, mm."""
    return math.hypot(*(getattr(point, a) for a in AXES if a != axis))


def blind_floors(part, tol: float = 1e-3) -> list:
    """Discs that block an arm's bore. There should be none.

    Named by what such a face *is* rather than by where this particular file
    happens to put it: flat, square to an arm's axis, concentric with it, and
    set back inside the part. The set-back is the whole of the test — every arm
    has a face matching the first three conditions at its mouth, out on the
    bounding box, and on a healthy arm that mouth is the only one. So this
    keeps finding the bug if the generator is rerun and caps a different arm.
    """
    box = part.bounding_box()
    found = []
    for axis in AXES:
        mouths = (getattr(box.min, axis), getattr(box.max, axis))
        for face in part.faces().filter_by(SQUARE_TO[axis]):
            centre = face.center()
            on_axis = _radius(centre, axis) < tol
            at_mouth = min(abs(getattr(centre, axis) - m) for m in mouths) < tol
            if on_axis and not at_mouth:
                found.append(face)
    return found


def arm_mouths(part, tol: float = 1e-3) -> dict[str, list[float]]:
    """The opening at the end of each arm, as its wire radii, largest first.

    A healthy mouth is an annulus: two wires, one wall of pipe between them.
    The capped arm's is a single disc. Measuring the opening rather than
    trusting it is the check that would have caught this in the first place.
    """
    box = part.bounding_box()
    found = {}
    for axis in AXES:
        for sign, mouth in (("-", getattr(box.min, axis)), ("+", getattr(box.max, axis))):
            for face in part.faces().filter_by(SQUARE_TO[axis]):
                centre = face.center()
                if _radius(centre, axis) > tol:
                    continue
                if abs(getattr(centre, axis) - mouth) > tol:
                    continue
                found[f"{sign}{axis}"] = sorted(
                    (
                        max(_radius(v, axis) for v in wire.vertices())
                        for wire in face.wires()
                    ),
                    reverse=True,
                )
    return found


def build() -> Part:
    """The generator's part with the blind arm opened out."""
    if not SOURCE.exists():
        raise FileNotFoundError(
            f"{SOURCE} is missing — this model repairs the generator's output, "
            "so the STL has to be there to repair"
        )

    # The source is a mesh, so every facet arrives as its own triangular face.
    # clean() fuses the coplanar ones, which is what turns the bore floor from
    # 164 triangles into the single disc the repair extrudes.
    part = Mesher().read(str(SOURCE))[0].clean()

    floors = blind_floors(part)
    assert len(floors) == 1, (
        f"expected exactly one blocked bore to open, found {len(floors)} "
        f"at {[tuple(round(c, 2) for c in f.center()) for f in floors]} — "
        "the source is not the part this model was written against"
    )
    floor = floors[0]

    # A face's normal points out of the material behind it, so the floor's
    # points up the empty bore. The cap is everything the other way, from the
    # floor out to the mouth.
    towards_mouth = -floor.normal_at()
    box = part.bounding_box()
    mouth = Vector(
        *(getattr(box.max if getattr(towards_mouth, a) > 0 else box.min, a) for a in AXES)
    )
    depth = (mouth - floor.center()).dot(towards_mouth)
    assert abs(depth - CAP_T) < 1e-3, (
        f"cap is {depth:.2f} mm thick, expected {CAP_T:.2f} — the source has "
        "changed and the measurements above no longer describe it"
    )

    return part - extrude(floor, amount=depth, dir=towards_mouth)


def check(part) -> None:
    single_solid(part)
    fits_bed(part)

    left = blind_floors(part)
    assert not left, (
        f"{len(left)} bore(s) still blocked at "
        f"{[tuple(round(c, 2) for c in f.center()) for f in left]}"
    )

    # Every arm open, and every wall the same 2.0 mm — which is the thing that
    # was actually asked of the repaired arm, so it is asserted on all six
    # rather than on the one that was wrong.
    mouths = arm_mouths(part)
    assert len(mouths) == 6, f"expected 6 arm mouths, measured {len(mouths)}"
    for name, radii in sorted(mouths.items()):
        assert len(radii) == 2, (
            f"{name} arm does not open: its mouth is a solid disc of radius "
            f"{radii[0]:.2f}, not a ring"
        )
        outer, inner = radii
        assert abs((outer - inner) - WALL) < 1e-3, (
            f"{name} arm wall is {outer - inner:.2f} mm, wanted {WALL:.2f} "
            f"(mouth OD {2 * outer:.2f}, ID {2 * inner:.2f})"
        )

    # Five of one pipe size and one of the other, which is what the part is
    # for. Diameters rather than radii because that is how the pipe was
    # measured and how the generator was asked for it.
    sockets = sorted((2 * outer, 2 * inner) for outer, inner in mouths.values())
    wanted = sorted([(SMALL_OD, SMALL_ID)] * 5 + [(LARGE_OD, LARGE_ID)])
    assert all(
        abs(got_od - want_od) < 1e-2 and abs(got_bore - want_bore) < 1e-2
        for (got_od, got_bore), (want_od, want_bore) in zip(sockets, wanted, strict=True)
    ), (
        "sockets measure "
        + ", ".join(f"{od:.2f}/{bore:.2f}" for od, bore in sockets)
        + " (OD/bore), wanted "
        + ", ".join(f"{od:.2f}/{bore:.2f}" for od, bore in wanted)
    )

    # Nothing but the cap should have gone. It was interior material, so the
    # envelope is untouched.
    size = part.bounding_box().size
    for axis, across in zip(AXES, (size.X, size.Y, size.Z), strict=True):
        assert abs(across - 2 * REACH) < 1e-3, (
            f"{axis} is {across:.2f} mm across, wanted {2 * REACH:.2f} — the "
            "cut removed more than the cap"
        )


if __name__ == "__main__":
    from cadkit import cli

    raise SystemExit(cli(build, check))
