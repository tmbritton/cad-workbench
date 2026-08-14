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

    mise build dehydrator-riser ring
"""

import collar

from cadkit import cavity_ceiling, single_solid
from cadkit.materials import ASA

MATERIAL = ASA

# The male section only ever engages SOCKET_D. Above that it is plain wall, and
# plain wall is exactly what this test is not about.
MALE_KEEP = collar.SOCKET_D


def build():
    """The collar with the male section truncated. Nothing else changes.

    Every dimension comes from collar.py, so this test cannot drift from the
    part it tests — the only difference between them is one argument.
    """
    return collar.build(male_h=MALE_KEEP)


def check(part) -> None:
    single_solid(part)

    ceiling = cavity_ceiling(part)
    assert abs(ceiling - collar.SOCKET_D) < 1e-6, (
        f"socket cavity is {ceiling:.2f} mm deep, wanted {collar.SOCKET_D:.2f}"
    )

    # The whole point of this gate is the real footprint. If it differs from the
    # collar's by any amount, the test is measuring a different part.
    size = part.bounding_box().size
    full = collar.build().part.bounding_box().size
    assert abs(size.X - full.X) < 1e-6 and abs(size.Y - full.Y) < 1e-6, (
        f"footprint {size.X:.2f} x {size.Y:.2f} must match the collar's "
        f"{full.X:.2f} x {full.Y:.2f}, or it tests the wrong thing"
    )

    assert abs(size.Z - (collar.STEP_Z + MALE_KEEP)) < 1e-6, (
        f"stands {size.Z:.2f} mm tall, wanted {collar.STEP_Z + MALE_KEEP:.2f}"
    )


if __name__ == "__main__":
    from cadkit import cli

    raise SystemExit(cli(build, check))
