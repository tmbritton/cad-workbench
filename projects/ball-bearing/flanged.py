"""F6000ZZ in balls — 10 x 26 x 8 mm with a 28.5 x 1.5 flange, 9 elements.

The flanged and the awkward case at once, so nothing else has to cover either.
The flange is drawn as part of the outer race's own section, so it cannot come
off the printer as a loose collar. The balls need breakaway skirts, because a
sphere touches the plate at a point and overhangs 90 degrees above it — snap
them off before turning it.

Every number is in parameters.py — this file is the contract and nothing else.

    mise dev   ball-bearing flanged
    mise build ball-bearing flanged
"""

from __future__ import annotations

import _bearing
from _bearing import check_bearing, solid
from build123d import Part
from parameters import FLANGED as SPEC
from parameters import MATERIAL

__all__ = ["MATERIAL"]  # re-exported so the build driver reports mass


def build() -> Part:
    return solid(SPEC)


def check(part) -> None:
    check_bearing(part, SPEC)

    # The flange is part of the outer race, not a ring resting on it. If the
    # union had failed it would still export, as a loose collar around a
    # bearing that is now one body short.
    _, outer, balls = _bearing._bodies(part, SPEC)
    assert abs(outer.bounding_box().size.X - SPEC.plate.diameter) < _bearing.TOL, (
        f"the outer race measures {outer.bounding_box().size.X:.2f} mm across, "
        f"not {SPEC.plate.diameter:.2f} — the flange is a separate body"
    )

    # Each ball leaves the plate wearing its own skirt. One continuous ring
    # under all of them is the bug this model exists to keep out, and it looks
    # correct everywhere except that the bearing will not turn.
    plate = min(b.bounding_box().min.Z for b in balls)
    assert abs(plate + SPEC.width / 2) < _bearing.TOL, (
        f"the balls skirts stop at z={plate:.3f}, not at the plate "
        f"({-SPEC.width / 2:.3f}) — they cannot be printed onto anything"
    )


if __name__ == "__main__":
    from cadkit import cli

    raise SystemExit(cli(build, check))
