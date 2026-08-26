"""Dehydrator riser collar — open collar, no floor.

All dimensions from README.md in this folder.

Shape: a stepped tube, female below and male above, matching how the existing
trays stack.

    - The bottom SOCKET_D is a female socket (295 x 211 internal) that drops
      over the male rim of the tray below.
    - Above it a MALE_H male section (285 x 204 external) rises to be received
      by the tray or lid above.

Shelling the stepped solid produces the connecting shoulder automatically —
which is the part the abandoned OpenSCAD draft got wrong, leaving two
disconnected rings that still exported a "valid" STL.

Stack arithmetic: the part stands TOTAL_H tall, but the socket above swallows
part of the male, so the stack only gains STACK_GAIN = MALE_H + WALL.
"""

from build123d import (
    Axis,
    BuildPart,
    BuildSketch,
    Mode,
    Plane,
    RectangleRounded,
    chamfer,
    extrude,
    offset,
)

from cadkit import cavity_ceiling, fits_bed, horizontal_face_at, single_solid
from cadkit.materials import ASA

MATERIAL = ASA

# Both validated on the ring test, 13 Aug 2026, and written down here so
# `mise slice` costs the print that will actually happen rather than an
# idealised one. The seat ring at z = SOCKET_D hangs inward over the socket
# cavity and does not bridge; the brim is for 89.8 mm of height standing on
# 17.5 cm2 of bed contact. Both are argued in full in README.md.
SUPPORT = True
BRIM = 5.0

# The seat ring is the overhang the rules find, and support is the answer that
# was chosen for it rather than a redesign — so the finding is not news, and
# leaving it shouting drowns out the next one. README.md carries the argument.
ALLOW = {"overhang": "the seat ring, printed on support; ring test, 13 Aug 2026"}

# ---- measured -------------------------------------------------------------
WALL = 1.8  # existing tray wall
MALE_X, MALE_Y = 285.0, 204.0  # plugs into the socket above
FEM_X, FEM_Y = 295.0, 211.0  # receives the male rim below
SOCKET_D = 18.0  # depth of the socket cavity, as on a real tray
FEM_R = 26.0  # female socket internal corner
MALE_R = 19.0  # male section external corner

# ---- decided --------------------------------------------------------------
MALE_H = 70.0  # male wall height that clears the spool

# Breaking the sharp outer edges of the protruding lip. Chamfers rather than
# fillets: on the bottom edge a fillet leaves a horizontal tangent at z=0,
# which is a severe overhang on the first layers, whereas a 45 degree chamfer
# prints cleanly. 1.5 mm because the bottom face is only WALL wide, and
# anything near 1.8 would consume it entirely and leave a knife edge.
LIP_CHAMFER = 1.5

# ---- derived --------------------------------------------------------------
FEM_OUTER_X = FEM_X + 2 * WALL  # 298.6 — socket walls wrap the 295 opening
FEM_OUTER_Y = FEM_Y + 2 * WALL  # 214.6

# The step must sit one wall ABOVE the target cavity depth: shelling lays a web
# under the step, and that web's underside is the ceiling the rim below seats
# against. Extruding only SOCKET_D leaves a cavity 1.8 mm too shallow, so the
# collar perches proud of the shoulder instead of seating flush like a tray.
STEP_Z = SOCKET_D + WALL  # 19.8
TOTAL_H = STEP_Z + MALE_H

# Height the stack gains per collar: the rim below seats at the cavity ceiling,
# and the next tray seats on this collar's male top. Independent of SOCKET_D —
# deepening the socket lowers the seat and raises the top by equal amounts.
STACK_GAIN = MALE_H + WALL


def build(male_h: float = MALE_H) -> BuildPart:
    """The collar. `male_h` is the exposed male wall above the step.

    Parameterised so test prints can shorten the male section without touching
    anything that affects fit — the socket, the step and every mating dimension
    are independent of it. See ring.py and coupon.py, which are exactly this
    function with material removed.
    """
    with BuildPart() as collar:
        # Lower female socket: drops over the male rim of the tray below.
        # Outer radius is the internal one plus the wall, so shelling leaves the
        # cavity at exactly FEM_R.
        with BuildSketch(Plane.XY):
            RectangleRounded(FEM_OUTER_X, FEM_OUTER_Y, FEM_R + WALL)
        extrude(amount=STEP_Z)

        # Upper male section: received by the tray or lid above.
        with BuildSketch(Plane.XY.offset(STEP_Z)):
            RectangleRounded(MALE_X, MALE_Y, MALE_R)
        extrude(amount=male_h)

        # Hollow it. Opening the top and bottom faces makes it a true collar,
        # and the step between the two extrusions becomes a real shoulder.
        horizontals = collar.faces().filter_by(Plane.XY).sort_by(Axis.Z)
        offset(
            amount=-WALL,
            openings=[horizontals[0], horizontals[-1]],
            mode=Mode.REPLACE,
        )

        # Break the two exposed outer edges of the protruding lip. Selecting the
        # face and taking its outer wire names the edge by what it *is*, rather
        # than by an index that would shift the moment the model changes.
        chamfer(
            horizontal_face_at(collar, STEP_Z).outer_wire().edges(),
            length=LIP_CHAMFER,
        )

    return collar


def check(part) -> None:
    single_solid(part)
    fits_bed(part)

    # Measured, not assumed: this is the surface the tray below seats against,
    # and getting it wrong by one wall thickness is the mistake that produced a
    # collar perching 1.8 mm proud of the shoulder.
    ceiling = cavity_ceiling(part)
    assert abs(ceiling - SOCKET_D) < 1e-6, (
        f"socket cavity is {ceiling:.2f} mm deep, wanted {SOCKET_D:.2f}"
    )

    size = part.bounding_box().size
    assert abs(size.Z - TOTAL_H) < 1e-6, (
        f"stands {size.Z:.2f} mm tall, wanted {TOTAL_H:.2f}"
    )


if __name__ == "__main__":
    from cadkit import cli

    raise SystemExit(cli(build, check))
