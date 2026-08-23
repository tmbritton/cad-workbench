"""Bearing on an M10 stud — 6 x 28 x 8 mm, 14 mm boss.

The same feature as threaded_boss.py the other way round: the thread is cut on
the outside of the boss, making a stud that screws into a tapped hole.

A printed thread is not a machined one. It will take a nut, but treat the load
rating as unknown until you have pulled one apart.

Every number is in parameters.py — this file is the contract and nothing else.

    mise dev   ball-bearing threaded_stud
    mise build ball-bearing threaded_stud
"""

from __future__ import annotations

from _bearing import check_bearing, solid
from build123d import Part
from parameters import MATERIAL
from parameters import THREADED_STUD as SPEC

__all__ = ["MATERIAL"]  # re-exported so the build driver reports mass


def build() -> Part:
    return solid(SPEC)


def check(part) -> None:
    check_bearing(part, SPEC)


if __name__ == "__main__":
    from cadkit import cli

    raise SystemExit(cli(build, check))
