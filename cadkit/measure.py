"""Dimensions that came from somewhere, and the ones that only look like they did.

Most numbers in this workspace belong in the model, next to the comment that
says why they are what they are. That is the house style and it is right: the
script is the explanation, and moving a dimension into a data file to be
looked up by name puts the number and its reason on different pages.

This is for the other case. A number that is a *guess* builds, checks clean,
slices, and prints — and produces a perfect model of the wrong object. Nothing
downstream catches it, because there is nothing wrong with it except that it is
not true. The only place it can be caught is where it was written down, and
only if it was written down as a guess.

So: an optional `measurements.toml` beside the models, holding the dimensions
whose provenance is the interesting part.

    [clearance]
    value = 0.15
    unit = "mm"
    how = "reasoned from a 0.42 mm line width; no print has tested it"
    provisional = true

`how` is required. A measurement with no account of where it came from is a
guess with better manners, and this refuses to serve one. `provisional = true`
says so out loud: the value builds normally and `mise check` keeps mentioning
it until a test print settles it and the flag comes off.

Reach for this when a number is provisional, when it came from a scan or a
published standard rather than from calipers, or when two projects have to
agree on it. Leave everything else in the model where it can be read.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import cache
from pathlib import Path

FILENAME = "measurements.toml"


class MeasurementError(LookupError):
    """A measurement is missing, unusable, or was never really taken."""


@dataclass(frozen=True)
class Measurement:
    name: str
    value: float
    how: str
    provisional: bool
    source: Path

    def __float__(self) -> float:
        return self.value


def _find(start: Path) -> Path:
    """Walk up from `start` to the measurements.toml that governs it."""
    for folder in [start, *start.parents]:
        candidate = folder / FILENAME
        if candidate.is_file():
            return candidate
        if (folder / "projects").is_dir():  # reached the workspace root
            break
    raise MeasurementError(
        f"no {FILENAME} above {start}. Create one beside the models, with a "
        f'`value`, a `unit` of "mm", and a `how` saying where the number came from.'
    )


@cache
def _read(path: Path) -> dict:
    return tomllib.loads(path.read_text())


def load(start: Path) -> list[Measurement]:
    """Every measurement governing `start`, validated. Empty if there is no file."""
    try:
        path = _find(Path(start).resolve())
    except MeasurementError:
        return []
    return [_build(path, name) for name in sorted(_read(path))]


def _build(path: Path, name: str) -> Measurement:
    entry = _read(path)[name]
    if not isinstance(entry, dict):
        raise MeasurementError(
            f"{path.name}: [{name}] must be a table with value, unit and how, "
            f"not a bare {type(entry).__name__}"
        )
    if "value" not in entry:
        raise MeasurementError(f"{path.name}: [{name}] has no `value`")

    unit = entry.get("unit", "mm")
    if unit != "mm":
        raise MeasurementError(
            f"{path.name}: [{name}] is in {unit!r}; everything here is millimetres"
        )

    how = str(entry.get("how", "")).strip()
    if not how:
        # The whole point of the file. Without this it is a dict of numbers
        # with extra ceremony, and a guess reads exactly like a measurement.
        raise MeasurementError(
            f"{path.name}: [{name}] has no `how`. Say where the number came from — "
            f'"calipers, three readings", "ISO 261", "phone scan, provisional". '
            f"If there is no answer, it is a guess, and a guess should say so."
        )
    return Measurement(
        name=name,
        value=float(entry["value"]),
        how=how,
        provisional=bool(entry.get("provisional", False)),
        source=path,
    )


def measured(name: str, start: str | Path | None = None) -> float:
    """The named dimension, in millimetres, or an error saying what is wrong.

    Never a default. A missing measurement has to stop the build: returning a
    plausible number is how a guess gets into a part in the first place.

    `start` defaults to the file that called this, so a model finds its own
    project's measurements without naming a path.
    """
    if start is None:
        import inspect

        frame = inspect.stack()[1]
        start = Path(frame.filename).resolve().parent
    path = _find(Path(start).resolve())

    if name not in _read(path):
        known = ", ".join(sorted(_read(path))) or "none"
        raise MeasurementError(
            f"{path.name} has no measurement called {name!r}. Known: {known}"
        )
    return _build(path, name).value


def provisional(start: str | Path) -> list[Measurement]:
    """Measurements still flagged as unverified. What `mise check` reports."""
    return [m for m in load(start) if m.provisional]
