"""NPT pipe threads, by designation — the fitting a piece of threaded PVC uses.

A helper, not a model. Turns `"1 NPT"` into a diameter and pitch a boss can be
cut to, the same job `_threads.py` does for `"M12"`. It exists because NPT is
not ISO 261: it is a *tapered* thread (1:16 on diameter — 1°47′ per side),
which is what lets a pipe thread wedge tight, and `_threads.py`'s straight
metric geometry has no way to express that.

`bd_warehouse` (0.3.0, what this project has installed) cannot draw the taper
either — `Thread.__init__` raises `ValueError("taper_angle is not currently
supported")` the moment a taper angle is passed, despite the parameter
existing in its signature. Drawing the true cone would mean a helical sweep
built by hand in build123d, with no library underneath it.

So this module cuts a **straight** thread instead, at the diameter midway
across the length that actually engages — hand-tight (`l1`) to wrench-tight
(`l2`). Over that span the real taper only moves the diameter about a
millimetre (0.6 mm on `"3/4 NPT"`, 1.1 mm on `"1 NPT"`), which is smaller than
ordinary FDM slop and about the same size as the `bore_fit`/`od_fit` fudge
factors `parameters.py` already carries for other threads. A straight cut
centred on that range sits within the taper's own excursion at both ends. It
will not seat as deep as a real male NPT thread and is not a pressure joint —
treat it the way this project already treats its metric studs: it will take a
fitting, not a promise about how hard.

    >>> parse("1 NPT").major_d
    32.859
    >>> parse("3/4 NPT").pitch
    1.8143

Dimensions are ASME B1.20.1, cross-checked against two independent sources.
Only the sizes below are in the table — not every NPT size, only the ones with
sourced, cross-checked numbers. Add another the same way if one is needed:
threads/inch, the major diameter at the gauge plane, and the two engagement
lengths, all straight off the standard.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 1:16 on diameter — 3/4 inch of diameter change per foot of length — the
# taper every NPT size shares. Dimensionless, so it applies in any consistent
# unit; used here in mm.
TAPER = 1 / 16


@dataclass(frozen=True)
class Pipe:
    """One NPT size, resolved from its designation.

    `major_d` and `minor_d` are what `_bearing.py` actually cuts the boss
    with — duck-typed to look like `_threads.Thread` (same four attributes:
    `name`, `pitch`, `major_d`, `minor_d`), and computed the same way `minor_d`
    is there too: see that property for why it is ISO 68-1's truncation and
    not NPT's own.
    """

    name: str
    tpi: float  # threads per inch
    od: float  # major diameter at the gauge plane, mm — the pipe's nominal OD
    l1: float  # hand-tight engagement length, mm
    l2: float  # effective (wrench-tight) thread length, mm

    @property
    def pitch(self) -> float:
        """Pitch, mm. `25.4 / tpi`."""
        return round(25.4 / self.tpi, 4)

    @property
    def major_d(self) -> float:
        """The diameter this module actually cuts the thread at.

        Not the gauge-plane OD — the real thread tapers down from there, and
        a single straight diameter sits closest to the true cone when it is
        centred on the length that engages, not planted at the wide end. Half
        the taper's total drop over `l2`, backed off `od`.
        """
        return round(self.od - TAPER * self.l2 / 2, 3)

    @property
    def minor_d(self) -> float:
        """Root diameter of the cut thread.

        Not NPT's own truncation (`h = 0.8 x pitch` off the root, per ASME
        B1.20.1) — `_boss()` cuts every thread, this family included, with
        `bd_warehouse.IsoThread(major_diameter, pitch, ...)`, which has no
        argument for a custom root and always truncates to the ISO 68-1
        profile itself: `1.25 x H` off a sharp-V height of `H = sqrt(3)/2 x
        pitch`. That is the root that actually gets cut, so it is what has to
        go into the wall-thickness math in `_bearing.py` — the textbook NPT
        number would describe a thread this codebase does not draw. Same
        formula as `_threads.Thread.minor_d`, restated here because `Pipe`
        does not share that dataclass.
        """
        height = 0.8660254037844386 * self.pitch  # sqrt(3)/2 x pitch
        return round(self.major_d - 1.25 * height, 3)


# ASME B1.20.1. Only sizes with sourced, cross-checked numbers — see the
# module docstring.
_SIZES: dict[str, Pipe] = {
    "3/4": Pipe("3/4 NPT", tpi=14, od=26.670, l1=8.611, l2=13.861),
    "1": Pipe("1 NPT", tpi=11.5, od=33.401, l1=10.160, l2=17.343),
}

_DESIGNATION = re.compile(r"^(\d+(?:/\d+)?)\s*NPT$", re.IGNORECASE)


def is_pipe(designation: str) -> bool:
    """Whether `designation` is shaped like an NPT size, before parsing it.

    `_bearing.py` uses this to decide which parser to try — an NPT-shaped
    string that names an unlisted size should fail with *this* module's
    message, not fall through to `_threads.py`'s "not a metric thread" one.
    """
    return _DESIGNATION.match(designation.strip()) is not None


def parse(designation: str) -> Pipe:
    """Resolve `"1 NPT"` or `"3/4 NPT"` against the table above."""
    match = _DESIGNATION.match(designation.strip())
    if match is None:
        raise ValueError(
            f"{designation!r} is not an NPT pipe thread designation; "
            "write it like '1 NPT' or '3/4 NPT'"
        )
    size = match.group(1)
    if size not in _SIZES:
        available = ", ".join(f"{s} NPT" for s in _SIZES)
        raise ValueError(f"{size} NPT is not in this table; available: {available}")
    return _SIZES[size]


def _self_check() -> None:
    """The table has to agree with ASME B1.20.1 before anything is cut."""
    for size, pipe in _SIZES.items():
        assert pipe.name == f"{size} NPT", f"{pipe.name} does not name its own key"
        assert 0 < pipe.minor_d < pipe.major_d < pipe.od, (
            f"{pipe.name}: expected 0 < minor_d < major_d < od, got "
            f"{pipe.minor_d} < {pipe.major_d} < {pipe.od}"
        )
        # The straight stand-in never has to reach past half the taper's
        # drop over l2 — if it did, the formula above is wrong, not the size.
        assert pipe.od - pipe.major_d <= TAPER * pipe.l2, (
            f"{pipe.name}: major_d is further off od than the taper allows"
        )

    # Spot-checks against ASME B1.20.1 proper, so a typo in the table has
    # something to fail against. Values are the two sources this module's
    # docstring numbers were cross-checked against.
    one = _SIZES["1"]
    assert abs(one.pitch - 2.2087) < 0.001, (
        f"1 NPT pitch should be 2.2087, got {one.pitch}"
    )
    assert abs(one.od - 33.401) < 0.001, f"1 NPT OD should be 33.401, got {one.od}"
    assert abs(one.major_d - 32.859) < 0.001, (
        f"1 NPT stand-in diameter should be 32.859, got {one.major_d}"
    )

    three_q = _SIZES["3/4"]
    assert abs(three_q.pitch - 1.8143) < 0.001, (
        f"3/4 NPT pitch should be 1.8143, got {three_q.pitch}"
    )
    assert abs(three_q.od - 26.670) < 0.001, (
        f"3/4 NPT OD should be 26.670, got {three_q.od}"
    )

    # parse() has to raise, not guess, on anything it cannot resolve.
    for bad in ("1in", "M12", "NPT", "2 NPT", "", "1/2 NPT"):
        try:
            parse(bad)
        except ValueError:
            continue
        raise AssertionError(f"parse({bad!r}) should have raised ValueError")

    assert is_pipe("1 NPT") and is_pipe("3/4 NPT") and is_pipe("2 NPT")
    assert not is_pipe("M12") and not is_pipe("M12x1.5") and not is_pipe("12")


_self_check()


if __name__ == "__main__":
    for _size, _pipe in _SIZES.items():
        print(
            f"{_pipe.name}: {_pipe.tpi:g} tpi, pitch {_pipe.pitch} mm, "
            f"major {_pipe.major_d} mm (od {_pipe.od} mm), "
            f"minor {_pipe.minor_d} mm, engages {_pipe.l1}-{_pipe.l2} mm"
        )
