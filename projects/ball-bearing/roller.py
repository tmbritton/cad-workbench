"""Parametric bearing, 6000, cylindrical rollers.

Same generator as bearing.py at a different element setting — a variant is a
model here, not a flag, so the file is the name and the STL cannot be produced
under an ambiguous one.

A roller has more contact area than a ball and no overhang worth the name: it
is a cylinder standing on the plate, chamfered back at both ends to a narrower
stub that carries on to the bearing's faces. The chamfer is the shoulder the
raceway grips, and it is at 45 degrees so the race's matching roof prints
without support. Nothing needs a breakaway skirt.

The cost is stiction — a cylinder is a line contact where a ball is a point —
so this one turns less freely than either of the others, and is the right
choice when the load matters more than the spin.

    mise build ball-bearing roller
"""

from __future__ import annotations

import bearing
from bearing import MATERIAL, Bearing, check_bearing, solid
from build123d import Part

__all__ = ["MATERIAL"]  # re-exported so the driver reports mass

SPEC = Bearing.of("6000", element="roller")


def build() -> Part:
    return solid(SPEC)


def check(part) -> None:
    check_bearing(part, SPEC)

    # The stub has to reach both faces, or the race has to bridge over the
    # roller in mid-air. Measured on a roller rather than assumed from the
    # profile, because the boolean that cuts the raceway could have taken it.
    _, _, rollers = bearing._bodies(part, SPEC)
    height = rollers[0].bounding_box().size.Z
    assert abs(height - SPEC.width) < bearing.TOL, (
        f"roller stands {height:.3f} mm in an {SPEC.width:.3f} mm bearing — its "
        "ends do not reach the faces, so the race must bridge over it"
    )


if __name__ == "__main__":
    from cadkit import cli

    raise SystemExit(cli(build, check))
