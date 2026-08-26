"""NPT pipe-thread designations, and `_bearing.py` picking the right parser.

`_threads.py` (the ISO 261 counterpart) has no test file of its own — its
only coverage is the `_self_check()` that runs at import — but this module's
`parse()` is new logic, not just a data table, and the straight-vs-taper
tradeoff it encodes is exactly the kind of thing that should stay pinned down
by an assertion rather than a comment. So this one gets a real test file.

Reference numbers (pitch, OD, the two engagement lengths) are ASME B1.20.1,
cross-checked against two independent sources — see `_pipe.py`'s docstring
for where they came from and why the cut diameter is not simply the OD.
"""

from __future__ import annotations

import pytest

from cadkit.discover import find_project, load, project_path

PROJECT = find_project("ball-bearing")


@pytest.fixture
def pipe():
    with project_path(PROJECT):
        yield load("_pipe")


@pytest.fixture
def bearing():
    with project_path(PROJECT):
        yield load("_bearing")


def test_1_npt_matches_the_standard(pipe) -> None:
    thread = pipe.parse("1 NPT")
    assert thread.name == "1 NPT"
    assert thread.tpi == 11.5
    assert abs(thread.pitch - 2.2087) < 0.001
    assert abs(thread.od - 33.401) < 0.001
    # The cut diameter is centred on the engagement span, not planted at the
    # gauge-plane OD — see _pipe.py's Pipe.major_d docstring.
    assert abs(thread.major_d - 32.859) < 0.001
    assert thread.minor_d < thread.major_d


def test_three_quarter_npt_matches_the_standard(pipe) -> None:
    thread = pipe.parse("3/4 NPT")
    assert thread.name == "3/4 NPT"
    assert thread.tpi == 14
    assert abs(thread.pitch - 1.8143) < 0.001
    assert abs(thread.od - 26.670) < 0.001
    assert abs(thread.major_d - 26.237) < 0.001


def test_minor_diameter_matches_what_iso_thread_actually_cuts(pipe) -> None:
    """`_boss()` cuts every thread with `IsoThread`, which has no argument for
    a custom root — it always truncates to ISO 68-1, regardless of which
    parser resolved the designation. `minor_d` has to predict *that* geometry
    for the wall-thickness math in `_bearing.py` to mean anything, not the
    textbook NPT root (`h = 0.8 x pitch`) that nothing here draws.
    """
    thread = pipe.parse("1 NPT")
    height = 0.8660254037844386 * thread.pitch  # sqrt(3)/2 x pitch, ISO 68-1
    iso_minor = round(thread.major_d - 1.25 * height, 3)
    assert thread.minor_d == iso_minor

    # And explicitly not the ASME truncation, so a regression back to it
    # (an easy mistake — it is the number the standard actually quotes) fails
    # loudly rather than silently reintroducing the mismatch.
    npt_minor = round(thread.major_d - 2 * 0.8 * thread.pitch, 3)
    assert thread.minor_d != npt_minor


def test_an_unlisted_size_names_whats_available(pipe) -> None:
    with pytest.raises(ValueError, match="1 NPT|3/4 NPT"):
        pipe.parse("2 NPT")


@pytest.mark.parametrize("bad", ["1in", "M12", "NPT", "", "1 in NPT", "-1 NPT"])
def test_a_malformed_designation_is_refused(pipe, bad: str) -> None:
    with pytest.raises(ValueError):
        pipe.parse(bad)


def test_is_pipe_tells_an_npt_shaped_string_from_a_metric_one(pipe) -> None:
    assert pipe.is_pipe("1 NPT")
    assert pipe.is_pipe("3/4 NPT")
    assert pipe.is_pipe("2 NPT")  # shaped right even though 2" is not tabled
    assert not pipe.is_pipe("M12")
    assert not pipe.is_pipe("M12x1.5")
    assert not pipe.is_pipe("12")


def test_boss_thread_dispatches_npt_designations_to_pipe(bearing) -> None:
    spec = bearing.Bearing(
        bore=10,
        od=120,
        width=16,
        race_t=22,
        element_d=12,
        boss=bearing.Boss(length=24, thread="1 NPT", external=True),
    )
    thread = spec.boss_thread
    assert thread.name == "1 NPT"
    assert abs(thread.major_d - 32.859) < 0.001


def test_boss_thread_still_dispatches_metric_designations_to_threads(bearing) -> None:
    spec = bearing.Bearing(
        bore=6,
        od=44,
        width=10,
        race_t=6,
        element_d=8,
        boss=bearing.Boss(length=18, thread="M12", external=True),
    )
    thread = spec.boss_thread
    assert thread.name == "M12"
    assert thread.major_d == 12.0


def test_boss_thread_is_none_without_a_thread(bearing) -> None:
    spec = bearing.Bearing(bore=6, od=44, width=10)
    assert spec.boss_thread is None


def test_an_npt_shaped_size_not_in_the_table_fails_through_boss_thread(bearing) -> None:
    """A size `is_pipe` recognises the shape of but `_pipe.parse` does not
    have data for must fail with `_pipe.py`'s message, not fall through to
    `_threads.py`'s "not a metric thread" one — that would name the wrong
    problem.
    """
    spec = bearing.Bearing(
        bore=10,
        od=120,
        width=16,
        boss=bearing.Boss(length=24, thread="2 NPT", external=True),
    )
    with pytest.raises(ValueError, match="not in this table"):
        _ = spec.boss_thread


def test_the_pvc_turntable_post_spec_resolves_and_validates() -> None:
    """The actual spec this project ships, exercised end to end: dispatch,
    the wall-thickness math against the real minor diameter, and every other
    `validate()` rule, together.
    """
    with project_path(PROJECT):
        parameters = load("parameters")
    parameters.PVC_TURNTABLE_POST.validate()  # raises on any violation
