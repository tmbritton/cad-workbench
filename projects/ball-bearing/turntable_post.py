"""Everything at once — a 100 mm turntable top on an M12 stud.

The part to preview if you want to see how the pieces sit together: a disc on
the outer race, a threaded stud on the inner race, and the bearing between
them, printed as one piece.

It prints the way it is drawn — plate flat on the build plate, stud rising, no
support anywhere. In use it is the other way up: the stud screws into a base
and stays put, and the top turns on it.

The other models each show one feature on its own. `lazy_susan.py` is the
turntable, and it cannot also carry a stud: its inner race is 57 mm across and
ISO 261 stops at M64, so there is no thread that would fit. That is why the
combined part is a smaller bearing with fatter races.

Every number is in parameters.py — this file is the contract and nothing else.

    mise dev   ball-bearing turntable_post
    mise build ball-bearing turntable_post
"""

from __future__ import annotations

import _bearing
from _bearing import check_bearing, solid
from build123d import Part
from parameters import MATERIAL
from parameters import TURNTABLE_POST as SPEC

__all__ = ["MATERIAL"]  # re-exported so the build driver reports mass

# `mise dev ball-bearing` with no model name shows this one. It is the only
# model with both features on it, so it is the one worth looking at; without
# the marker the viewer would pick whatever sorts first, which is the plain
# 26 mm bearing.
DEFAULT = True


def build() -> Part:
    return solid(SPEC)


def check(part) -> None:
    # check_bearing does the rest: the raceway gaps, the thread against ISO,
    # every bolt hole open, and two perimeters left under both raceways.
    check_bearing(part, SPEC)

    # Both features on the same part, on opposite races. The point of the
    # model is that they coexist, so that is what is asserted: the plate has
    # to have fused to the outer race and the stud to the inner one, and each
    # has to have stayed clear of the other.
    inner, outer, _ = _bearing._bodies(part, SPEC)
    assert abs(outer.bounding_box().size.X - SPEC.plate.diameter) < _bearing.TOL, (
        f"the outer race measures {outer.bounding_box().size.X:.2f} mm across, "
        f"not {SPEC.plate.diameter:.2f} — the plate is a separate body"
    )
    stud = inner.bounding_box().max.Z - SPEC.width / 2
    assert abs(stud - SPEC.boss.length) < _bearing.TOL, (
        f"the inner race stands {stud:.2f} mm proud of the bearing, not "
        f"{SPEC.boss.length:.2f} — the stud is not on it"
    )


if __name__ == "__main__":
    from cadkit import cli

    raise SystemExit(cli(build, check))
