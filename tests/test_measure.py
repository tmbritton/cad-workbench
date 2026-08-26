"""Measurements, and the guesses they exist to stop.

Every test here is about a refusal. `measured()` returning the right number for
a well-formed entry is the easy half and one test covers it; the reason the
module exists is that a number with no account of where it came from should not
be usable, and that is what the rest of these pin down.
"""

from __future__ import annotations

import pytest

from cadkit.measure import MeasurementError, load, measured, provisional

GOOD = """
[bore]
value = 12.7
unit = "mm"
how = "calipers, three readings across the mouth"

[wall]
value = 2.0
how = "scan, provisional"
provisional = true
"""


@pytest.fixture
def project(tmp_path):
    """A project folder with a measurements.toml and nothing else."""
    (tmp_path / "measurements.toml").write_text(GOOD)
    return tmp_path


def test_a_well_formed_measurement_reads_back(project) -> None:
    assert measured("bore", project) == 12.7
    assert measured("wall", project) == 2.0


def test_the_unit_defaults_to_millimetres_and_nothing_else_is_allowed(tmp_path) -> None:
    (tmp_path / "measurements.toml").write_text(
        '[bore]\nvalue = 0.5\nunit = "in"\nhow = "calipers"\n'
    )
    with pytest.raises(MeasurementError, match="millimetres"):
        measured("bore", tmp_path)


def test_a_number_with_no_provenance_is_refused(tmp_path) -> None:
    """The whole point. Without this the file is a dict with extra ceremony."""
    (tmp_path / "measurements.toml").write_text("[bore]\nvalue = 12.7\n")
    with pytest.raises(MeasurementError, match="no `how`"):
        measured("bore", tmp_path)


def test_an_empty_provenance_is_refused_too(tmp_path) -> None:
    (tmp_path / "measurements.toml").write_text('[bore]\nvalue = 12.7\nhow = "  "\n')
    with pytest.raises(MeasurementError, match="no `how`"):
        measured("bore", tmp_path)


def test_a_missing_value_is_refused(tmp_path) -> None:
    (tmp_path / "measurements.toml").write_text('[bore]\nhow = "calipers"\n')
    with pytest.raises(MeasurementError, match="no `value`"):
        measured("bore", tmp_path)


def test_a_bare_number_is_refused(tmp_path) -> None:
    """`bore = 12.7` is the shape somebody will reach for. It has no provenance."""
    (tmp_path / "measurements.toml").write_text("bore = 12.7\n")
    with pytest.raises(MeasurementError, match="must be a table"):
        measured("bore", tmp_path)


def test_an_unknown_name_lists_the_known_ones(project) -> None:
    with pytest.raises(MeasurementError, match="bore, wall"):
        measured("boer", project)


def test_a_missing_file_is_an_error_not_a_default(tmp_path) -> None:
    """Returning a plausible number is how a guess gets into a part."""
    (tmp_path / "projects").mkdir()  # stands in for the workspace root
    with pytest.raises(MeasurementError, match="no measurements.toml"):
        measured("bore", tmp_path)


def test_provisional_is_reported_and_the_rest_is_not(project) -> None:
    assert [m.name for m in provisional(project)] == ["wall"]
    assert len(load(project)) == 2


def test_a_project_with_no_measurements_file_is_not_an_error(tmp_path) -> None:
    """Most projects keep their numbers in the model, and are right to."""
    (tmp_path / "projects").mkdir()
    assert load(tmp_path) == []
    assert provisional(tmp_path) == []


def test_the_workspaces_own_measurements_are_all_well_formed() -> None:
    """Guards the real files against a typo that would only show up on a build."""
    from cadkit.discover import projects

    for folder in projects():
        for entry in load(folder):  # raises if any entry is malformed
            assert entry.how
