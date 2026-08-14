"""Dehydrator riser collar — open collar, no floor.

All dimensions from reference/dehydrator-measurements.html.

Shape: a stepped tube, female below and male above, matching how the existing
trays stack.

    - The bottom SOCKET_D is a female socket (295 x 211 internal) that drops
      over the male rim of the tray below.
    - Above it a MALE_H male section (285 x 204 external) rises to be received
      by the tray or lid above.

Shelling the stepped solid produces the connecting shoulder automatically —
which is the part the OpenSCAD draft got wrong.

Stack arithmetic: the part stands TOTAL_H tall, but the socket above swallows
part of the male, so the stack only gains STACK_GAIN = MALE_H + WALL. Numbers
are left symbolic here because they move whenever MALE_H is retuned; run the
module to print the current ones.
"""

from pathlib import Path

from build123d import (
    Axis,
    BuildPart,
    BuildSketch,
    Mode,
    Plane,
    RectangleRounded,
    chamfer,
    export_step,
    export_stl,
    extrude,
    offset,
)

# ---- measured -------------------------------------------------------------
WALL = 1.8                        # existing tray wall
MALE_X, MALE_Y = 285.0, 204.0     # plugs into the socket above
FEM_X, FEM_Y = 295.0, 211.0       # receives the male rim below
SOCKET_D = 18.0                   # depth of the socket cavity, as on a real tray
FEM_R = 26.0                      # female socket internal corner
MALE_R = 19.0                     # male section external corner

# ---- decided --------------------------------------------------------------
MALE_H = 70.0                     # male wall height that clears the spool

# Breaking the sharp outer edges of the protruding lip. The two are different
# sizes because the faces they cut into are different sizes:
#   - the shoulder is 6.8 mm wide (X), so it takes a proper chamfer;
#   - the bottom face is only WALL wide, so anything near 1.8 mm would consume
#     it entirely and leave a knife edge that cannot print a first layer.
LIP_CHAMFER = 1.5                 # top outer edge of the lip

# ---- derived --------------------------------------------------------------
FEM_OUTER_X = FEM_X + 2 * WALL    # 298.6 — socket walls wrap the 295 opening
FEM_OUTER_Y = FEM_Y + 2 * WALL    # 214.6

# The step must sit one wall ABOVE the target cavity depth: shelling lays a web
# under the step, and that web's underside is the ceiling the rim below seats
# against. Extruding only SOCKET_D leaves an cavity 1.8 mm too shallow, so the
# collar perches proud of the shoulder instead of seating flush like a tray.
STEP_Z = SOCKET_D + WALL          # 19.8
TOTAL_H = STEP_Z + MALE_H

# Height the stack gains per collar: the rim below seats at the cavity ceiling,
# and the next tray seats on this collar's male top. Independent of SOCKET_D —
# deepening the socket lowers the seat and raises the top by equal amounts.
STACK_GAIN = MALE_H + WALL


def build(male_h: float = MALE_H) -> BuildPart:
    """The collar. `male_h` is the exposed male wall above the step.

    Parameterised so test prints can shorten the male section without touching
    anything that affects fit — the socket, the step and every mating dimension
    are independent of it.
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
        faces_by_z = collar.faces().filter_by(Plane.XY).sort_by(Axis.Z)
        openings = [faces_by_z[0], faces_by_z[-1]]
        offset(amount=-WALL, openings=openings, mode=Mode.REPLACE)

        # Break the two exposed outer edges of the protruding lip. Selecting the
        # face and taking its outer wire names the edge by what it *is*, rather
        # than by an index that would shift the moment the model changes.
        # Chamfers rather than fillets: on the bottom edge a fillet leaves a
        # horizontal tangent at z=0, which is a severe overhang on the first
        # layers, whereas a 45 degrees chamfer prints cleanly.
        chamfer(
            _horizontal_face_at(collar, STEP_Z).outer_wire().edges(),
            length=LIP_CHAMFER,
        )

    return collar


def _horizontal_face_at(builder: BuildPart, z: float, tol: float = 1e-6):
    """The single face parallel to XY at height z.

    Re-queried after every operation rather than cached, because each chamfer
    rebuilds the topology and invalidates anything held from before it.
    """
    for face in builder.faces().filter_by(Plane.XY):
        if abs(face.center().Z - z) < tol:
            return face
    raise ValueError(f"no horizontal face at z={z}")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--male-h",
        type=float,
        default=MALE_H,
        help=f"exposed male wall height in mm (default {MALE_H:g})",
    )
    args = ap.parse_args()

    # A non-default height gets its own filenames. Overwriting collar.stl with a
    # variant is how you end up slicing the wrong geometry a week later.
    stem = "collar" if args.male_h == MALE_H else f"collar-male{args.male_h:g}"

    collar = build(male_h=args.male_h)
    part = collar.part

    solids = part.solids()
    assert len(solids) == 1, f"expected one connected solid, got {len(solids)}"

    size = part.bounding_box().size

    # Measure the cavity ceiling rather than assuming it: it is the lowest
    # horizontal face above z=0, and it is what the rim below seats against.
    horizontals = part.faces().filter_by(Plane.XY).sort_by(Axis.Z)
    ceiling = next(f.center().Z for f in horizontals if f.center().Z > 1e-6)
    assert abs(ceiling - SOCKET_D) < 1e-6, (
        f"cavity is {ceiling:.2f} mm deep, wanted {SOCKET_D:.2f}"
    )

    print(f"solids       : {len(solids)}")
    print(f"bounding box : {size.X:.1f} x {size.Y:.1f} x {size.Z:.1f} mm")
    print(f"volume       : {part.volume / 1000:,.1f} cm3")
    print(f"socket cavity: {ceiling:.1f} mm deep  (seats flush on the rim below)")
    print(f"adds to stack: {args.male_h + WALL:.1f} mm")
    print(f"faces        : {len(part.faces())}")

    out = Path(__file__).parent
    export_stl(part, str(out / f"{stem}.stl"))
    export_step(part, str(out / f"{stem}.step"))
    print(f"exported     : {out / f'{stem}.stl'}")
    print(f"               {out / f'{stem}.step'}")
