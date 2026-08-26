"""The design-for-FDM rules, against shapes built to trip exactly one of them.

`tests/test_projects.py` runs these rules over the real tree, which proves they
do not fire on parts that print. It cannot prove they fire on parts that do
not: every model in the workspace is meant to be printable, so a rule that
silently never fires would pass that suite forever.

So each case here is the smallest solid that is wrong in one particular way,
and each asserts the rule that should catch it *and* that the part is otherwise
quiet — a rule that reports everything is no more useful than one that reports
nothing.
"""

from __future__ import annotations

import pytest
from build123d import Box, Cone, Cylinder, Pos, chamfer

from cadkit.dfm import Limits, inspect_part, validate_allow
from cadkit.materials import ASA, PLA

# Fewer samples than the default: these solids are a few hundred triangles and
# the wall-thickness rule converges immediately on them.
FAST = Limits(samples=600)


def rules_fired(part, **kwargs) -> set[str]:
    report = inspect_part(part, limits=FAST, **kwargs)
    return {f.rule for f in report.findings if f.severity != "allowed"}


def test_a_plain_block_trips_nothing() -> None:
    """The control. Without this, every assertion below could be vacuous."""
    assert rules_fired(Box(30, 30, 10)) == set()


def test_a_chamfered_block_trips_nothing() -> None:
    """REFERENCE.md recommends a chamfer at the plate; it must not be a finding.

    45 degrees tessellates to 45.0000-something, so a rule written as
    "steeper than 45" flags the one feature the reference tells you to add.
    """
    block = Box(30, 30, 10)
    assert rules_fired(chamfer(block.edges().group_by()[0], 1.0)) == set()


def test_thin_wall_catches_a_wall_under_two_beads() -> None:
    tube = Cylinder(10, 30) - Cylinder(9.6, 30)  # 0.4 mm wall
    report = inspect_part(tube, limits=FAST)
    thin = [f for f in report.findings if f.rule == "thin_wall"]
    assert thin and thin[0].severity == "fail"
    assert thin[0].value == pytest.approx(0.4, abs=0.15)


def test_thin_wall_ignores_a_sound_wall() -> None:
    assert "thin_wall" not in rules_fired(Cylinder(10, 30) - Cylinder(7, 30))


def test_unsupported_fails_a_cantilever_and_measures_its_reach() -> None:
    """Held at one end only, so the reach is the whole arm and then some."""
    part = Box(10, 10, 60) + Pos(20, 0, 25) * Box(50, 10, 10)
    found = [
        f for f in inspect_part(part, limits=FAST).findings if f.rule == "unsupported"
    ]
    assert found and found[0].severity == "fail"
    assert found[0].value > 50


def test_unsupported_stays_quiet_on_a_short_hole_ceiling() -> None:
    """A 10 mm bore roofed over is a bridge nobody thinks about."""
    part = Box(60, 60, 20) - Pos(0, 0, -4) * Cylinder(5, 12)
    assert "unsupported" not in rules_fired(part)


def test_unsupported_warns_on_a_wide_hole_ceiling() -> None:
    part = Box(80, 80, 20) - Pos(0, 0, -4) * Cylinder(15, 12)
    found = [
        f for f in inspect_part(part, limits=FAST).findings if f.rule == "unsupported"
    ]
    assert found and found[0].severity == "warn"
    assert found[0].value > FAST.bridge_mm


def test_overhang_catches_a_flaring_cone() -> None:
    """Widening upward: the lateral surface is the underside."""
    assert "overhang" in rules_fired(Cylinder(4, 20) + Pos(0, 0, 15) * Cone(4, 16, 10))


def test_overhang_ignores_a_narrowing_cone() -> None:
    """The same shape point-up supports itself all the way."""
    assert "overhang" not in rules_fired(Cone(20, 0, 30))


def test_thin_pin_catches_an_upright_post() -> None:
    assert "thin_pin" in rules_fired(Box(20, 20, 4) + Pos(0, 0, 17) * Cylinder(1.5, 30))


def test_thin_pin_ignores_a_hole_of_the_same_diameter() -> None:
    """Concave is a hole, which has its own rules and none of them are this."""
    assert "thin_pin" not in rules_fired(Box(20, 20, 30) - Cylinder(1.5, 30))


def test_warp_risk_depends_on_the_material() -> None:
    """The same footprint is a certainty in ASA and a non-event in PLA."""
    slab = Box(140, 110, 6)
    assert "warp_risk" in rules_fired(slab, material=ASA)
    assert "warp_risk" not in rules_fired(slab, material=PLA)


def test_warp_risk_ignores_a_rounded_footprint() -> None:
    assert "warp_risk" not in rules_fired(Cylinder(70, 6), material=ASA)


def test_stability_fails_a_part_whose_mass_hangs_past_its_base() -> None:
    part = Box(6, 6, 80) + Pos(30, 0, 35) * Box(50, 20, 10)
    found = [f for f in inspect_part(part, limits=FAST).findings if f.rule == "stability"]
    assert found and found[0].severity == "fail"


def test_allow_downgrades_a_finding_and_keeps_its_reason() -> None:
    tube = Cylinder(10, 30) - Cylinder(9.6, 30)
    report = inspect_part(tube, limits=FAST, allow={"thin_wall": "a test coupon"})
    assert not report.failures
    assert [f.reason for f in report.allowed] == ["a test coupon"]


@pytest.mark.parametrize(
    ("allow", "message"),
    [
        ({"overhung": "typo"}, "no such rule"),
        ({"overhang": "   "}, "needs a reason"),
    ],
)
def test_allow_refuses_to_silence_anything_by_accident(allow, message) -> None:
    """A mistyped rule name would otherwise mute nothing, quietly."""
    with pytest.raises(ValueError, match=message):
        validate_allow(allow)


def test_every_rule_has_an_implementation_and_a_docstring() -> None:
    from cadkit import dfm

    assert set(dfm.RULES) == set(dfm._IMPLEMENTATIONS)
    assert set(dfm.CHEAP) <= set(dfm.RULES)
    for name in dfm.RULES:
        assert (dfm._IMPLEMENTATIONS[name].__doc__ or "").strip(), name
