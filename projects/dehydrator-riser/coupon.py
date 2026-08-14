"""Corner test coupon for the riser collar.

One corner of the real part, cut out and truncated, so the fit can be checked
before committing ~170 g of ASA and several hours to the full collar.

Trimmed in two directions. In plan it keeps one corner plus a straight run either
side; in height it stops once the male section has reached its engaged length,
since the socket above never swallows more than SOCKET_D and the rest is plain
wall. Together those take the test piece to about 8 g.

Every dimension is imported from collar.py — nothing is redefined here. If the
collar changes, this changes with it, so the test can never drift from the part
it is testing.

What a successful coupon proves:
  1. It seats FLUSH on the tray's rim, with no gap under the lip.
     (Tests the 18 mm cavity, i.e. the STEP_Z = SOCKET_D + WALL correction.)
  2. The corner does not bind — R19 male into the R26 socket, 2.97 mm at the
     tightest point, which is the smallest clearance anywhere on the profile.
  3. The straight runs sit against the tray with the expected slop:
     5.0 mm per side in X, 3.5 mm in Y.
  4. The seat ring printed flat. It is a horizontal cantilever — 5.0 mm wide in
     X, 3.5 mm in Y — hanging inward off the socket wall with nothing beneath it.
     Slicers manage this by anchoring each concentric loop to the one outside it,
     but any droop lands directly on the surface the collar seats on, so it is
     worth a straightedge.

    mise build dehydrator-riser coupon
"""

import collar
from build123d import Align, Box, Pos

from cadkit import cavity_ceiling, single_solid
from cadkit.materials import ASA

MATERIAL = ASA

# Straight run to keep on each side, measured inward from the outer corner.
# Enough to register flat against the tray on both axes; the corner arc itself
# only spans about 19 mm, so this leaves a generous tail either side of it.
LENGTH = 60.0

# How much of the male section to keep. The socket above only ever swallows
# SOCKET_D of it, so that is the entire engaged length and everything above is
# plain wall that tests nothing. Truncating there is exact, not an
# approximation: the cut face is the same 1.8 mm annulus as the real top.
MALE_KEEP = collar.SOCKET_D
COUPON_H = collar.STEP_Z + MALE_KEEP


def build():
    """The collar, intersected with a box over one corner.

    Algebra mode: solids are values, so `&` is just intersection. Same kernel as
    the builder-mode code in collar.py, and the two mix freely.
    """
    part = collar.build(male_h=MALE_KEEP).part

    x0 = collar.FEM_OUTER_X / 2 - LENGTH
    y0 = collar.FEM_OUTER_Y / 2 - LENGTH

    # Oversized in +X/+Y so those cuts land outside the part; in Z it clears the
    # already-truncated top, so height comes from MALE_KEEP alone.
    window = Pos(x0, y0, -1) * Box(
        LENGTH + 20,
        LENGTH + 20,
        COUPON_H + 2,
        align=(Align.MIN, Align.MIN, Align.MIN),
    )

    return part & window


def check(part) -> None:
    single_solid(part)

    # The cavity must survive the cut at its full depth, or the coupon proves
    # nothing about the seat — the whole reason it exists.
    ceiling = cavity_ceiling(part)
    assert abs(ceiling - collar.SOCKET_D) < 1e-6, (
        f"coupon cavity is {ceiling:.2f} mm, expected {collar.SOCKET_D:.2f}"
    )

    size = part.bounding_box().size
    assert abs(size.Z - COUPON_H) < 1e-6, (
        f"stands {size.Z:.2f} mm tall, wanted {COUPON_H:.2f}"
    )
    assert abs(size.X - LENGTH) < 1e-6 and abs(size.Y - LENGTH) < 1e-6, (
        f"footprint {size.X:.2f} x {size.Y:.2f}, wanted {LENGTH:.2f} square"
    )


if __name__ == "__main__":
    from cadkit import cli

    raise SystemExit(cli(build, check))
