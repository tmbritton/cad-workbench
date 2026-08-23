"""Turntable — 100 mm across the top, on a 72 mm bearing, 12 dumbbells.

100 mm is the whole part: the top plate is the widest thing on it, so the
bearing underneath has to be smaller than that. 72 mm leaves a 14 mm ring of
plate outside the bearing for the bolt holes to sit in.

A lazy susan is a thin-section bearing with a big bore and a disc on the outer
race. The plate is drawn as part of that race and sits on the build plate, so
it needs no support at any diameter. Turn the finished part over and it is the
top: plate and outer race turn together on the inner race, which you screw down.

Every number is in parameters.py — this file is the contract and nothing else.

    mise dev   ball-bearing lazy_susan
    mise build ball-bearing lazy_susan
"""

from __future__ import annotations

import _bearing
from _bearing import check_bearing, solid
from build123d import Part
from parameters import LAZY_SUSAN as SPEC
from parameters import MATERIAL

__all__ = ["MATERIAL"]  # re-exported so the build driver reports mass


def build() -> Part:
    return solid(SPEC)


def check(part) -> None:
    check_bearing(part, SPEC)

    # The plate has to be part of the outer race. If the union had failed it
    # would still export — as a loose disc around a bearing, which is a thing
    # you find out on the plate.
    _, outer, _ = _bearing._bodies(part, SPEC)
    assert abs(outer.bounding_box().size.X - SPEC.plate.diameter) < _bearing.TOL, (
        f"the outer race measures {outer.bounding_box().size.X:.2f} mm across, "
        f"not {SPEC.plate.diameter:.2f} — the plate is a separate body"
    )

    # Flat on the plate, one face, nothing to support. The whole reason the top
    # goes on the build plate rather than at the other end.
    assert abs(part.bounding_box().min.Z + SPEC.width / 2) < _bearing.TOL, (
        f"the plate is not on the build-plate face, so it would print as a "
        f"{SPEC.plate.diameter:.0f} mm horizontal overhang"
    )


if __name__ == "__main__":
    from cadkit import cli

    raise SystemExit(cli(build, check))
