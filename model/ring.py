"""Full-perimeter fit test: the whole collar, male section cut to its engaged length.

Second gate, after the corner coupon passed. Same footprint as the real part —
298.6 x 214.6 — but the male section stops once it has reached the depth the
socket above actually swallows, so everything that determines fit is present and
everything that is merely tall is not.

What this proves that the corner coupon could not:

  1. **All four corners engage at once.** One corner fitting does not mean four
     do. This is the first time the part has to drop onto the tray as a closed
     loop, with no freedom to twist into place.
  2. **It does not rock.** A full-perimeter seat either sits flat or it does not.
  3. **Warping over the real footprint.** The genuine ASA risk on this part.
     ~300 x 215 mm is a large closed rectangle, and corners lifting off the plate
     would show here rather than after four hours of printing the tall version.
  4. **First-layer adhesion at full scale.** The coupon's footprint was a
     fortieth of this one.

If this seats flat and square, the only thing left untested in the full collar
is wall height — which affects nothing that mates.

    mise run ring
"""

from pathlib import Path

from build123d import Axis, Plane, export_step, export_stl

from collar import MALE_H, SOCKET_D, STEP_Z, build

# The male section only ever engages SOCKET_D. Above that it is plain wall, and
# plain wall is exactly what this test is not about.
MALE_KEEP = SOCKET_D

ASA_DENSITY = 1.07  # g/cm3


if __name__ == "__main__":
    part = build(male_h=MALE_KEEP).part
    full = build().part

    solids = part.solids()
    assert len(solids) == 1, f"expected one connected solid, got {len(solids)}"

    ceiling = next(
        f.center().Z
        for f in part.faces().filter_by(Plane.XY).sort_by(Axis.Z)
        if f.center().Z > 1e-6
    )
    assert abs(ceiling - SOCKET_D) < 1e-6, (
        f"cavity is {ceiling:.2f} mm deep, wanted {SOCKET_D:.2f}"
    )

    size = part.bounding_box().size
    full_size = full.bounding_box().size
    assert abs(size.X - full_size.X) < 1e-6 and abs(size.Y - full_size.Y) < 1e-6, (
        "footprint must match the real collar exactly, or it tests the wrong thing"
    )

    vol = part.volume / 1000
    full_vol = full.volume / 1000

    print(f"solids       : {len(solids)}")
    print(f"bounding box : {size.X:.1f} x {size.Y:.1f} x {size.Z:.1f} mm")
    print(f"footprint    : matches the full collar exactly")
    print(f"male kept    : {MALE_KEEP:.0f} mm of {MALE_H:.0f} mm")
    print(f"socket cavity: {ceiling:.1f} mm deep  (must seat flush)")
    print(f"volume       : {vol:,.1f} cm3   ({vol / full_vol:.0%} of the full collar)")
    print(f"ASA mass     : {vol * ASA_DENSITY:.0f} g   (full collar {full_vol * ASA_DENSITY:.0f} g)")

    out = Path(__file__).parent
    export_stl(part, str(out / "ring.stl"))
    export_step(part, str(out / "ring.step"))
    print(f"exported     : {out / 'ring.stl'}")
    print(f"               {out / 'ring.step'}")
