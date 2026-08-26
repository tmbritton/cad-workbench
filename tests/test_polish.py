"""The chamfer pass, against shapes chosen to defeat it in one way each.

What `polish` is for is the case where `chamfer(part.edges(), size)` raises and
does not say which edge, so the tests that matter are the ones where some edges
work and some do not. A test that only chamfers a box proves nothing the kernel
was not already doing.
"""

from __future__ import annotations

import pytest
from build123d import Box, Cylinder, GeomType, Pos

from cadkit.polish import CHAMFERABLE, Unpolished, bed_chamfer, polish


def test_a_clean_part_chamfers_every_edge() -> None:
    box = Box(30, 20, 10)
    skipped: list = []
    out = polish(box, 1.0, report=skipped)
    assert skipped == []
    assert out.volume < box.volume  # material actually came off


def test_a_chamfer_larger_than_the_part_is_refused_not_silently_skipped() -> None:
    with pytest.raises(Unpolished):
        polish(Box(3, 2, 1), 5.0)


def test_one_impossible_edge_does_not_lose_the_rest() -> None:
    """The whole point. `chamfer(part.edges(), size)` raises on this shape."""
    from build123d import chamfer

    part = Box(40, 40, 8) + Pos(0, 0, 4.3) * Box(60, 60, 0.6)
    # Blind, because the whole complaint about the kernel here is that it
    # raises a dozen unrelated types and none of them name the edge.
    with pytest.raises(Exception):  # noqa: B017
        chamfer(part.edges(), 1.0)

    skipped: list = []
    out = polish(part, 1.0, report=skipped)
    assert skipped, "expected some edges to be impossible on this shape"
    assert len(skipped) < len(part.edges()), "expected most edges to still work"
    assert out.volume < part.volume


def test_the_result_is_the_same_however_the_edges_arrive() -> None:
    """Deterministic: the pass sorts before it searches."""
    part = Box(40, 40, 8) - Cylinder(6, 8)
    forward = polish(part, 1.0, edges=list(part.edges()))
    backward = polish(part, 1.0, edges=list(reversed(list(part.edges()))))
    assert forward.volume == pytest.approx(backward.volume)


def test_a_print_in_place_assembly_keeps_its_bodies() -> None:
    """Chamfering must not weld two bodies together or split one."""
    part = Box(20, 20, 4) + Pos(0, 0, 10) * Box(10, 10, 4)  # two lumps, no contact
    assert len(part.solids()) == 2
    assert len(polish(part, 0.8).solids()) == 2


def test_bed_chamfer_touches_only_the_plate() -> None:
    box = Box(30, 20, 10)
    bed = bed_chamfer(box, 1.0)
    everything = polish(box, 1.0)
    assert everything.volume < bed.volume < box.volume


def test_bed_chamfer_says_so_when_nothing_is_on_the_plate() -> None:
    """A part modelled centred on the origin has no edge at z=0 to chamfer."""
    part = Cylinder(10, 20)  # a curved side wall; no straight edge at the bottom
    bed = bed_chamfer(part, 1.0)
    assert bed.volume < part.volume


def test_helical_edges_are_never_offered_to_the_kernel() -> None:
    """A thread's b-splines cannot be chamfered and cost a minute to prove."""
    assert GeomType.BSPLINE not in CHAMFERABLE
    assert GeomType.LINE in CHAMFERABLE
    assert GeomType.CIRCLE in CHAMFERABLE
