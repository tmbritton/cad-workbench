"""Right-angle structural connector for two 14.6 mm OD PVC pipes.

The two 30 mm sockets are blind: this is a frame joint, not a fluid fitting.
Each has one radial screw opening on the upper side. The underside is flattened
slightly so both legs can sit on the print bed without rolling. A solid
triangular gusset fills the inside corner and ties the two legs together.
"""

from __future__ import annotations

import math

from build123d import Box, Cylinder, Part, Polygon, Pos, Rot, extrude

from cadkit import fits_bed, single_solid
from cadkit.materials import ASA
from cadkit.measure import measured

MATERIAL = ASA
DEFAULT = True

# ---- measured -----------------------------------------------------------
PIPE_OD = 14.6  # calipers, supplied by the user; measure both pipes if different
SOCKET_DEPTH = 30.0  # requested insertion length, per leg

# ---- decided ------------------------------------------------------------
# Clearance is radial. 0.25 and 0.50 mm/side would not admit the pipe; an ASA
# coupon at 0.90 mm/side (16.4 mm ID) was printed and confirmed to fit.
CLEARANCE = measured("clearance")
WALL = 4.0  # requested radial thickness around the sockets
SCREW_D = measured("screw_hole_d")  # provisional M3 clearance opening
SCREW_FROM_MOUTH = 12.0  # keeps 18 mm of pipe behind each screw
CORE_MARGIN = 1.0  # separates the two blind pocket floors from the other arm
FLAT_CUT = 0.8  # plane off the bottom: 3.2 mm of wall remains below each bore

# ---- derived ------------------------------------------------------------
SOCKET_D = PIPE_OD + 2 * CLEARANCE
OUTER_D = SOCKET_D + 2 * WALL
OUTER_R = OUTER_D / 2
SOCKET_R = SOCKET_D / 2
# At the floor of one socket, the other leg's outside ends at OUTER_R;
# leave a whole wall plus a little extra before starting either pocket.
SOCKET_ROOT = OUTER_R + WALL + CORE_MARGIN
REACH = SOCKET_ROOT + SOCKET_DEPTH
CENTER_Z = OUTER_R - FLAT_CUT
TOP_Z = CENTER_Z + OUTER_R
# A triangular fill runs between both legs. Each end reaches into one collar,
# while its diagonal side bridges the otherwise empty inside corner. The bores
# are removed *after* the union so the full 30 mm insertion survives.
GUSSET_REACH = 2 * OUTER_R + 2 * WALL

# Horizontal bores need accessible supports under their ceilings. Both blind
# sockets open at the mouth, so support can be removed after printing.
SUPPORT = True
ALLOW = {
    "unsupported": (
        "both horizontal, blind sockets use slicer supports accessible from "
        "their mouths; not yet verified by a print"
    )
}


def _along_x(radius: float, start: float, end: float) -> Part:
    return (
        Pos((start + end) / 2, 0, CENTER_Z)
        * Rot(0, 90, 0)
        * Cylinder(radius, end - start)
    )


def _along_y(radius: float, start: float, end: float) -> Part:
    return (
        Pos(0, (start + end) / 2, CENTER_Z)
        * Rot(90, 0, 0)
        * Cylinder(radius, end - start)
    )


def build() -> Part:
    """Gusseted 90-degree collars with blind pockets and top screw holes."""
    assert WALL > FLAT_CUT > 0
    assert 0 < SCREW_FROM_MOUTH < SOCKET_DEPTH
    assert 0 < SCREW_D < SOCKET_D

    gusset = extrude(
        Polygon((0, 0), (GUSSET_REACH, 0), (0, GUSSET_REACH), align=None),
        amount=TOP_Z,
    )
    arms = _along_x(OUTER_R, 0, REACH) + _along_y(OUTER_R, 0, REACH) + gusset
    # Clip less than one millimetre off the bottom of both round collars. The
    # intersection supplies two broad coplanar contact strips on the bed.
    bed_half_space = Pos(REACH / 2, REACH / 2, 25) * Box(
        REACH + 2 * OUTER_D, REACH + 2 * OUTER_D, 50
    )
    part = arms & bed_half_space

    # Extend the cutters beyond the mouths, but start exactly at the measured
    # floor position. The sockets cannot collide inside the solid elbow core.
    part -= _along_x(SOCKET_R, SOCKET_ROOT, REACH + 1)
    part -= _along_y(SOCKET_R, SOCKET_ROOT, REACH + 1)

    # One opening per leg, through only the TOP wall and into its pipe pocket.
    # The holes are clearance for the screw shaft: screw into the PVC itself,
    # not into an undersized hole in the printed collar.
    screw_at = REACH - SCREW_FROM_MOUTH
    for x, y in ((screw_at, 0), (0, screw_at)):
        part -= Pos(x, y, TOP_Z - WALL / 2) * Cylinder(SCREW_D / 2, WALL + 2)
    return part


def check(part: Part) -> None:
    single_solid(part)
    fits_bed(part)
    box = part.bounding_box()
    assert abs(box.min.Z) < 1e-3, f"base at {box.min.Z:.2f} mm, wanted 0"
    assert abs(box.max.X - REACH) < 1e-3 and abs(box.max.Y - REACH) < 1e-3, (
        f"socket mouths at X={box.max.X:.2f}, Y={box.max.Y:.2f} mm, wanted {REACH:.2f} mm"
    )
    inside_corner = OUTER_R + WALL / 4
    assert part.is_inside((inside_corner, inside_corner, CENTER_Z)), (
        f"inside corner at ({inside_corner:.2f}, {inside_corner:.2f}) mm is empty; "
        "the reinforcing gusset must join both legs"
    )

    for axis in ("X", "Y"):
        # Both the mouth and the blind floor are re-measured on the finished
        # solid, rather than trusting the length of a cutter before booleans.
        faces = [
            f
            for f in part.faces()
            if abs(getattr(f.center(), axis) - REACH) < 1e-3 and len(f.wires()) == 2
        ]
        assert len(faces) == 1, f"{axis} mouth is not one open annulus"
        # Circle lengths directly measure diameters without assuming an
        # extrusion's nominal size. The outer contour has a tiny bottom flat,
        # so measure the inner circle and the top radial thickness instead.
        inner = min(faces[0].wires(), key=lambda wire: wire.length)
        actual_socket_d = inner.length / math.pi
        assert abs(actual_socket_d - SOCKET_D) < 1e-2, (
            f"{axis} socket ID {actual_socket_d:.2f} mm, wanted {SOCKET_D:.2f} "
            f"for {PIPE_OD:.2f} mm pipe"
        )
        outer = max(faces[0].wires(), key=lambda wire: wire.length)
        actual_wall = outer.bounding_box().max.Z - inner.bounding_box().max.Z
        assert abs(actual_wall - WALL) < 1e-2, (
            f"{axis} socket top wall is {actual_wall:.2f} mm, wanted {WALL:.2f} mm"
        )
        floors = [
            f
            for f in part.faces()
            if abs(getattr(f.center(), axis) - SOCKET_ROOT) < 1e-3
            and abs(f.area - math.pi * SOCKET_R**2) < 1e-2
        ]
        assert len(floors) == 1, (
            f"{axis} socket floor missing at {SOCKET_ROOT:.2f} mm; "
            f"expected {SOCKET_DEPTH:.2f} mm insertion"
        )
        depth = getattr(faces[0].center(), axis) - getattr(floors[0].center(), axis)
        assert abs(depth - SOCKET_DEPTH) < 1e-3, (
            f"{axis} pocket depth {depth:.2f} mm, wanted {SOCKET_DEPTH:.2f} mm"
        )

    # A hole must pierce the top of *each* pocket, not the far wall or just
    # one of the two legs. Test the resulting solid at each screw's axis.
    at = REACH - SCREW_FROM_MOUTH
    for x, y in ((at, 0), (0, at)):
        assert not part.is_inside((x, y, TOP_Z - WALL / 2)), (
            f"screw opening at ({x:.2f}, {y:.2f}) does not pierce the wall"
        )
        assert part.is_inside((x + SCREW_D, y, TOP_Z - WALL / 2)) or part.is_inside(
            (x, y + SCREW_D, TOP_Z - WALL / 2)
        ), f"no solid wall beside screw opening at ({x:.2f}, {y:.2f})"


if __name__ == "__main__":
    from cadkit import cli

    raise SystemExit(cli(build, check))
