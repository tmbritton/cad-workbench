"""The parts of the slicer interface that can be tested without a slicer.

Actually slicing takes twenty seconds to four minutes and needs a working
OrcaSlicer, so it is not something to put in a suite that should run on every
save. What *is* worth pinning down is everything around it: the profile
flattening, the plate rule, the header parsing, and the promise that a finding
drives exactly one setting and no others.

The profile tests skip rather than fail when no slicer is installed. A checkout
on a machine without one is not a regression, and the same argument applies
here as to the models built from `inputs/` — a suite that is permanently red is
a suite nobody reads.
"""

from __future__ import annotations

import pytest

from cadkit import slicing
from cadkit.dfm import Finding
from cadkit.materials import ASA, PLA, Material


def _have_profiles() -> bool:
    try:
        slicing.profiles()
    except slicing.SlicerError:
        return False
    return True


needs_profiles = pytest.mark.skipif(
    not _have_profiles(),
    reason="no slicer profiles installed on this machine",
)


@pytest.mark.parametrize(
    ("text", "minutes"),
    [
        ("4h 8m 28s", pytest.approx(248.47, abs=0.01)),
        ("59m 12s", pytest.approx(59.2, abs=0.01)),
        ("1d 2h 3m 4s", pytest.approx(1563.07, abs=0.01)),
    ],
)
def test_slicer_times_are_read_as_minutes(text, minutes) -> None:
    assert slicing._parse_time(text) == minutes


def test_duration_reads_as_hours_and_minutes() -> None:
    made = slicing.Slice(248.5, 172.0, 0.2, 2, 15.0, None, {})
    assert made.duration == "4h 08m"
    assert slicing.Slice(59.2, 8.0, 0.2, 2, 15.0, None, {}).duration == "59m"


def test_a_brim_is_the_only_thing_a_finding_changes() -> None:
    """Growing this list is a decision, not a refactor — see AGENTS.md."""
    warp = Finding("warp_risk", "warn", "sharp corner")
    assert set(slicing.tuned([warp])) == {"brim_type", "brim_width"}
    assert slicing.tuned([Finding("overhang", "warn", "steep")]) == {}
    assert slicing.tuned([]) == {}


def test_an_allowed_finding_does_not_change_settings() -> None:
    """It was overruled with a reason; acting on it anyway ignores the reason."""
    allowed = Finding("warp_risk", "allowed", "sharp corner", reason="printed fine")
    assert slicing.tuned([allowed]) == {}


def test_a_material_with_no_filament_name_says_so_rather_than_guessing() -> None:
    with pytest.raises(slicing.SlicerError, match="declares no material"):
        slicing.filament_profile(None)
    with pytest.raises(slicing.SlicerError, match="declares no material"):
        slicing.filament_profile(Material("mystery", 1.0))


@needs_profiles
def test_the_machine_profile_flattens_to_something_complete() -> None:
    """A leaf profile is a handful of keys; the merged one is the whole machine."""
    from cadkit import printer

    machine = slicing.flatten("machine", printer.SLICER_MACHINE)
    assert machine["printer_model"] == printer.NAME
    assert float(machine["nozzle_diameter"][0]) == printer.NOZZLE_D
    assert "inherits" not in machine
    # Kept on purpose: without these the slicer calls the process incompatible.
    assert machine["from"] == "system"
    assert machine["instantiation"] == "true"


@needs_profiles
def test_the_process_is_chosen_by_layer_height() -> None:
    assert "0.20mm" in slicing.process_profile(0.2)
    assert "0.08mm" in slicing.process_profile(0.08)


@needs_profiles
def test_an_unavailable_layer_height_is_refused_not_rounded() -> None:
    """Slicing at 0.16 because 0.15 was asked for changes every number below."""
    with pytest.raises(slicing.SlicerError, match="Available layer heights"):
        slicing.process_profile(0.15)


@needs_profiles
def test_asa_is_not_offered_the_cool_plate() -> None:
    """The rule reads bed temperatures, so it holds for filaments unknown here."""
    asa = slicing.flatten("filament", slicing.filament_profile(ASA))
    assert float(asa["cool_plate_temp"][0]) == 0
    assert slicing.plate_for(asa) != "Cool Plate"
    pla = slicing.flatten("filament", slicing.filament_profile(PLA))
    assert slicing.plate_for(pla) != "Cool Plate"  # textured suits it better


@needs_profiles
def test_every_material_resolves_to_a_real_filament_profile() -> None:
    """Guards the names in cadkit/materials.py against a slicer update."""
    from cadkit.materials import BY_NAME

    for material in BY_NAME.values():
        assert slicing.filament_profile(material)
