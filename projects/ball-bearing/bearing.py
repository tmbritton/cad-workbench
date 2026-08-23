"""6000 in dumbbells — 10 x 26 x 8 mm, 13 elements.

The one to print. A dumbbell is a cylinder with a 45 degree V round its waist;
the race fills that V with a matching rib, which is what holds it in. Nothing
overhangs past 45 degrees, so it needs no support and no breakaway anything.

Every number is in parameters.py — this file is the contract and nothing else.

    mise dev   ball-bearing bearing
    mise build ball-bearing bearing
"""

from __future__ import annotations

from _bearing import check_bearing, solid
from build123d import Part
from parameters import BEARING as SPEC
from parameters import MATERIAL

__all__ = ["MATERIAL"]  # re-exported so the build driver reports mass


def build() -> Part:
    return solid(SPEC)


def check(part) -> None:
    check_bearing(part, SPEC)


if __name__ == "__main__":
    from cadkit import cli

    raise SystemExit(cli(build, check))
