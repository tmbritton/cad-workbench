"""6000 in rollers — 10 x 26 x 8 mm, 10 elements.

A roller is a cylinder standing on the plate, chamfered back at both ends to a
narrower stub that carries on to the bearing's faces. The chamfer is the
shoulder the raceway grips; the stub means the race never has to bridge over
the roller. Line contact where a ball is point contact: more load, less spin.

Every number is in parameters.py — this file is the contract and nothing else.

    mise dev   ball-bearing roller
    mise build ball-bearing roller
"""

from __future__ import annotations

import _bearing
from _bearing import check_bearing, solid
from build123d import Part
from parameters import MATERIAL
from parameters import ROLLER as SPEC

__all__ = ["MATERIAL"]  # re-exported so the build driver reports mass


def build() -> Part:
    return solid(SPEC)


def check(part) -> None:
    check_bearing(part, SPEC)

    # The stub has to reach both faces, or the race has to bridge over the
    # roller in mid-air. Measured on a roller rather than assumed from the
    # profile, because the boolean that cuts the raceway could have taken it.
    _, _, rollers = _bearing._bodies(part, SPEC)
    height = rollers[0].bounding_box().size.Z
    assert abs(height - SPEC.width) < _bearing.TOL, (
        f"roller stands {height:.3f} mm in an {SPEC.width:.3f} mm bearing — its "
        "ends do not reach the faces, so the race must bridge over it"
    )


if __name__ == "__main__":
    from cadkit import cli

    raise SystemExit(cli(build, check))
