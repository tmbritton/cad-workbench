"""Boat trim holder: a Bézier arch with drilled shoulders and downturned ends.

Look down Z to compare to the side-profile photo. XY is the 102 × 42 mm
section; extrusion along Z supplies the 37 mm width. There are no bottom feet.
"""

from __future__ import annotations

from math import sqrt

from build123d import Cylinder, Edge, Face, Part, Pos, Rot, Side, Wire, extrude

from cadkit import fits_bed, single_solid
from cadkit.materials import ASA
from cadkit.measure import measured

MATERIAL = ASA
DEFAULT = True

# ---- measured -----------------------------------------------------------
LENGTH = 102.0
WIDTH = 37.0
HEIGHT = 42.0  # open end tips to the outside crown
REFERENCE_RADIUS = 46.0  # original sketch; user now says this may be inaccurate
ARCH_WALL = 4.5  # normal thickness, including the drilled shoulder regions
LEG_WALL = 3.2
LEG_HEIGHT = 20.0  # sketch: end tips to the underside of the level shoulders
HOLE_D = 4.5
HOLE_EDGE_OFFSET = 12.4  # projected X distance to the NEAREST hole edge

# ---- decided ------------------------------------------------------------
# The photo supplies topology, not extra measurements. These unmeasured
# transitions are explicitly provisional and can be tuned after comparison.
CORNER_REACH = measured("corner_reach")
SHOULDER_END = measured("shoulder_end")
SHOULDER_HANDLE = measured("shoulder_handle")
CROWN_HANDLE = measured("crown_handle")

# ---- derived ------------------------------------------------------------
MID = LENGTH / 2
SHOULDER_Y = LEG_HEIGHT + ARCH_WALL
CORNER_START_Y = SHOULDER_Y - CORNER_REACH
HOLE_X = HOLE_EDGE_OFFSET + HOLE_D / 2


def _mirror(points):
    """Mirror and reverse to continue walking from left to right."""
    return [(LENGTH - x, y) for x, y in reversed(points)]


def _upper_profile() -> Wire:
    """Outer shoulder/arch path, traversed left to right with tangent joins."""
    shoulder = [
        (CORNER_REACH, SHOULDER_Y),
        (SHOULDER_END, SHOULDER_Y),
    ]
    # One quintic Bézier per half replaces the shoulder-to-circle join. The
    # first three poles share Y: zero slope AND zero curvature where the arch
    # leaves the level shoulder. The final two share Y: horizontal at the
    # crown. Mirroring gives the same crown curvature on both sides.
    # The intermediate pole lets the curve rise gradually, rather than making
    # a steep shoulder then suddenly flattening onto a prescribed circle.
    arch = [
        shoulder[-1],
        (SHOULDER_END + SHOULDER_HANDLE / 2, SHOULDER_Y),
        (SHOULDER_END + SHOULDER_HANDLE, SHOULDER_Y),
        (
            MID - 5 * CROWN_HANDLE / 3,
            HEIGHT - (HEIGHT - SHOULDER_Y) / 4,
        ),
        (MID - CROWN_HANDLE, HEIGHT),
        (MID, HEIGHT),
    ]
    return Wire(
        [
            Edge.make_bezier(*shoulder),
            Edge.make_bezier(*arch),
            Edge.make_bezier(*_mirror(arch)),
            Edge.make_bezier(*_mirror(shoulder)),
        ]
    )


def _section() -> Face:
    upper = _upper_profile()
    # Offset the actual curve: independently drawn inner and outer Béziers
    # can cross or pinch, which caused missing STL faces in the first attempt.
    inner = upper.offset_2d(ARCH_WALL, side=Side.RIGHT, closed=False)

    # Cubic quarter-ellipse blends have vertical tangents at the straight ends
    # and horizontal tangents at the shoulders. The inner ellipse is smaller,
    # transitioning from the 3.2 mm straight wall to the 4.5 mm upper strip.
    handle = 4 * (sqrt(2) - 1) / 3  # standard cubic quarter-circle handle ratio
    outer_corner = [
        (0, CORNER_START_Y),
        (0, CORNER_START_Y + handle * CORNER_REACH),
        (CORNER_REACH * (1 - handle), SHOULDER_Y),
        (CORNER_REACH, SHOULDER_Y),
    ]
    inner_corner = [
        (LEG_WALL, CORNER_START_Y),
        (LEG_WALL, CORNER_START_Y + handle * (LEG_HEIGHT - CORNER_START_Y)),
        (CORNER_REACH - handle * (CORNER_REACH - LEG_WALL), LEG_HEIGHT),
        (CORNER_REACH, LEG_HEIGHT),
    ]
    edges = [*upper.edges(), *inner.edges()]
    for outer, inside, x in (
        (outer_corner, inner_corner, 0),
        (_mirror(outer_corner), _mirror(inner_corner), LENGTH),
    ):
        inside_x = LEG_WALL if x == 0 else LENGTH - LEG_WALL
        edges.extend(
            [
                Edge.make_bezier(*outer),
                Edge.make_bezier(*inside),
                Edge.make_line((x, 0), (x, CORNER_START_Y)),
                Edge.make_line((inside_x, 0), (inside_x, CORNER_START_Y)),
                Edge.make_line((x, 0), (inside_x, 0)),
            ]
        )
    return Face(Wire(edges))


def build() -> Part:
    """Extrude one continuous profile, then drill through its upper shoulders."""
    assert LEG_WALL < ARCH_WALL < CORNER_REACH < SHOULDER_END < MID
    assert SHOULDER_END + SHOULDER_HANDLE < MID - 5 * CROWN_HANDLE / 3
    assert 0 < CORNER_START_Y < LEG_HEIGHT < SHOULDER_Y < HEIGHT
    assert CORNER_REACH < HOLE_EDGE_OFFSET
    assert HOLE_X + HOLE_D / 2 < SHOULDER_END, "hole must stay within the shoulder"

    # Explicit direction keeps the print face at Z=0 regardless of wire order.
    part = extrude(_section(), amount=WIDTH, dir=(0, 0, 1))
    for x in (HOLE_X, LENGTH - HOLE_X):
        # Axes run along Y, through the 4.5 mm strip, not along Z through the
        # extrusion width and not through the thin downturned end walls.
        part -= (
            Pos(x, LEG_HEIGHT + ARCH_WALL / 2, WIDTH / 2)
            * Rot(90, 0, 0)
            * Cylinder(HOLE_D / 2, ARCH_WALL + 2)
        )
    return part


def _crossing(part, x, z):
    """Measure material intervals along Y on the finished solid."""
    return part.intersect(Edge.make_line((x, -1, z), (x, HEIGHT + 1, z)))


def check(part: Part) -> None:
    single_solid(part)
    fits_bed(part)
    assert part.is_valid, "holder B-rep is invalid"
    bounds = part.bounding_box()
    for name, got, wanted in (
        ("end-to-end length", bounds.size.X, LENGTH),
        ("arch height", bounds.size.Y, HEIGHT),
        ("width", bounds.size.Z, WIDTH),
        ("plate height", bounds.min.Z, 0),
    ):
        assert abs(got - wanted) < 0.01, f"{name} {got:.3f} mm, wanted {wanted:.3f} mm"

    # Measure the crown and shoulders on the resulting solid. This catches a
    # wrong offset side, an interior cap, or a mounting shelf at the wrong Y.
    for x, bottom in ((HOLE_X, LEG_HEIGHT), (MID, HEIGHT - ARCH_WALL)):
        section = _crossing(part, x, WIDTH / 4)
        assert section is not None and len(section.edges()) == 1, (
            f"expected one material interval at x={x:.2f} mm"
        )
        band = section.edges()[0].bounding_box()  # sole material interval above
        assert abs(band.min.Y - bottom) < 0.01, (
            f"inside surface at x={x:.2f}: {band.min.Y:.3f} mm, wanted {bottom:.3f}"
        )
        assert abs(band.size.Y - ARCH_WALL) < 0.01, (
            f"strip at x={x:.2f}: {band.size.Y:.3f} mm, wanted {ARCH_WALL:.3f}"
        )

    # Bottom contact faces are only the two narrow end tips. Their X extents
    # measure end thickness and prevent the erroneous inward feet returning.
    tips = [f for f in part.faces() if abs(f.bounding_box().max.Y) < 0.01]
    assert len(tips) == 2, f"found {len(tips)} end tips, wanted 2"
    for tip in tips:
        assert abs(tip.bounding_box().size.X - LEG_WALL) < 0.01, (
            f"end tip {tip.bounding_box().size.X:.3f} mm, wanted {LEG_WALL:.3f}; "
            "bottom foot?"
        )

    for x in (HOLE_X, LENGTH - HOLE_X):
        bore = _crossing(part, x, WIDTH / 2)
        assert bore is None or not bore.edges(), (
            f"mounting hole at x={x:.2f} mm does not pass through the upper strip"
        )
        for side in (-1, 1):
            # Probe either side of the required 4.5 mm opening on the actual
            # part: verifies diameter/edge offset, not just an empty centre.
            for delta, material in ((-0.05, False), (0.05, True)):
                probe_x = x + side * (HOLE_D / 2 + delta)
                assert (
                    part.is_inside((probe_x, LEG_HEIGHT + ARCH_WALL / 2, WIDTH / 2))
                    == material
                ), (
                    f"hole edge near x={probe_x:.3f} mm; wanted diameter {HOLE_D} mm, "
                    f"near-edge end offset {HOLE_EDGE_OFFSET} mm"
                )


if __name__ == "__main__":
    from cadkit import cli

    raise SystemExit(cli(build, check))
