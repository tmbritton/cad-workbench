"""A 10 in turntable top on a stud that screws into 1" threaded PVC.

`turntable_post.py`'s idea, scaled to a real base: instead of an M12 bolt, the
stud threads into a piece of 1" Schedule 40 PVC — glue a 1" FNPT female
adapter onto a length of 1" pipe, and this screws straight into it.

It prints the way it is drawn — plate flat on the build plate, stud rising, no
support anywhere. In use it is the other way up: the stud screws into the PVC
base and stays put, and the 254 mm top turns on it.

The stud is a straight thread standing in for 1" NPT, not the true 1:16 taper
— `_pipe.py` has the full reasoning for why, and what that trades away.

Every number is in parameters.py — this file is the contract and nothing else.

    mise dev   ball-bearing pvc_turntable_post
    mise build ball-bearing pvc_turntable_post
"""

from __future__ import annotations

import _bearing
from _bearing import check_bearing, solid
from build123d import Part
from parameters import MATERIAL
from parameters import PVC_TURNTABLE_POST as SPEC

__all__ = ["MATERIAL"]  # re-exported so the build driver reports mass


def build() -> Part:
    return solid(SPEC)


def check(part) -> None:
    # check_bearing does the rest: the raceway gaps, the thread against its
    # designation (including the "1 NPT" stand-in — _pipe.py resolves it to
    # the diameter and pitch that actually got cut, and this measures the
    # built solid against exactly that), every bolt hole open, and two
    # perimeters left under both raceways.
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
