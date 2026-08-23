"""Parametric bearing, F6000ZZ, balls — the flanged and the awkward case at once.

Two things this exercises that the other models do not. The flange is drawn as
part of the outer race's own section rather than stacked on it as a second
ring, so it cannot come off the printer as its own body; and the balls need
breakaway skirts, because a sphere touches the plate at a point and overhangs
90 degrees above it.

Snap the skirts off before turning it. They are deliberately grown 0.12 mm into
the underside of each ball — a gap there would be a sphere printing onto air —
so the bearing comes off the plate locked and is freed by hand.

Balls also mean the raceway roof is a full circle of near-horizontal overhang
where the groove closes. It bridges, but not beautifully: prefer bearing.py's
dumbbells unless something about the application actually wants point contact.

F6000ZZ rather than one of the smaller flanged sizes because it is the 6000
the other two models use, with a flange on it — so all three are the same
bearing — and because it clears the face-lip rule by 1.18 mm. An F6900ZZ
passes that rule by 0.01 mm, which is not a margin, it is a coincidence.

    mise build ball-bearing flanged
"""

from __future__ import annotations

import bearing
from bearing import MATERIAL, Bearing, check_bearing, solid
from build123d import Part

__all__ = ["MATERIAL"]

SPEC = Bearing.of("F6000ZZ", element="ball")


def build() -> Part:
    return solid(SPEC)


def check(part) -> None:
    check_bearing(part, SPEC)

    # The flange is part of the outer race, not a ring resting on it. If the
    # union had failed it would still export, as a loose collar around a
    # bearing that is now one body short.
    _, outer, _ = bearing._bodies(part, SPEC)
    assert abs(outer.bounding_box().size.X - SPEC.flange_d) < bearing.TOL, (
        f"the outer race measures {outer.bounding_box().size.X:.2f} mm across, "
        f"not {SPEC.flange_d:.2f} — the flange is a separate body"
    )

    # Each ball leaves the plate wearing its own skirt, and the skirts are
    # separate from one another: one continuous ring under all of them is the
    # bug this model exists to keep out, and it looks like a correct part
    # everywhere except that the bearing will not turn.
    _, _, balls = bearing._bodies(part, SPEC)
    plate = min(b.bounding_box().min.Z for b in balls)
    assert abs(plate + SPEC.width / 2) < bearing.TOL, (
        f"the balls' skirts stop at z={plate:.3f}, not at the plate "
        f"({-SPEC.width / 2:.3f}) — they cannot be printed onto anything"
    )


if __name__ == "__main__":
    from cadkit import cli

    raise SystemExit(cli(build, check))
