"""Bearing on a tapped M12 socket — 8 x 40 x 10 mm, 18 mm boss.

The inner race carries a tube with an ISO M12 coarse thread cut in its bore,
so a standard M12 bolt screws into it. In use the part is the other way up
from how it prints, and the boss hangs below the inner ring.

check_bearing measures the thread itself: over one whole pitch, the minor
diameter has to be M12's 10.106 and not merely something near it.

Every number is in parameters.py — this file is the contract and nothing else.

    mise dev   ball-bearing threaded_boss
    mise build ball-bearing threaded_boss
"""

from __future__ import annotations

from _bearing import check_bearing, solid
from build123d import Part
from parameters import MATERIAL
from parameters import THREADED_BOSS as SPEC

__all__ = ["MATERIAL"]  # re-exported so the build driver reports mass


def build() -> Part:
    return solid(SPEC)


def check(part) -> None:
    check_bearing(part, SPEC)


if __name__ == "__main__":
    from cadkit import cli

    raise SystemExit(cli(build, check))
