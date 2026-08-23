"""ISO metric screw threads, by designation.

A helper, not a model. Turns `"M12"` or `"M12x1.5"` into the major diameter and
pitch the geometry needs, and refuses anything that is not a real thread — the
point of a designation is that `M12` means one specific thing, so a generator
that accepts `M12` with a pitch of 1.3 is not producing an M12.

Pitches are ISO 261: the coarse series below, and for the fine series only the
pitches that standard actually lists against each diameter. `bd_warehouse`
draws the form itself, to the ISO 68-1 profile — 60 degree flanks, crest
truncated at H/8, root at H/4 — so nothing here has to approximate it.

    >>> parse("M12")
    Thread(name='M12', major_d=12.0, pitch=1.75, series='coarse')
    >>> parse("M12x1.5").minor_d
    10.376
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from cadkit.printer import LINE_W

# ISO 261 coarse pitch series. First and second choice diameters together;
# picking between them is the caller's business, not this table's.
COARSE: dict[float, float] = {
    1.6: 0.35,
    2: 0.4,
    2.5: 0.45,
    3: 0.5,
    3.5: 0.6,
    4: 0.7,
    5: 0.8,
    6: 1.0,
    7: 1.0,
    8: 1.25,
    10: 1.5,
    12: 1.75,
    14: 2.0,
    16: 2.0,
    18: 2.5,
    20: 2.5,
    22: 2.5,
    24: 3.0,
    27: 3.0,
    30: 3.5,
    33: 3.5,
    36: 4.0,
    39: 4.0,
    42: 4.5,
    45: 4.5,
    48: 5.0,
    52: 5.0,
    56: 5.5,
    60: 5.5,
    64: 6.0,
}

# ISO 261 fine series, as the pitches listed against each diameter. Not every
# combination someone might write down: M12x1.5 and M12x1.25 exist, M12x1.6
# does not.
FINE: dict[float, tuple[float, ...]] = {
    4: (0.5,),
    5: (0.5,),
    6: (0.75,),
    8: (1.0, 0.75),
    10: (1.25, 1.0, 0.75),
    12: (1.5, 1.25, 1.0),
    14: (1.5,),
    16: (1.5,),
    18: (2.0, 1.5),
    20: (2.0, 1.5),
    22: (2.0, 1.5),
    24: (2.0,),
    27: (2.0,),
    30: (3.0, 2.0, 1.5),
    33: (3.0, 2.0),
    36: (3.0, 2.0),
    39: (3.0, 2.0),
    42: (4.0, 3.0, 2.0),
    45: (4.0, 3.0, 2.0),
    48: (4.0, 3.0, 2.0),
    52: (4.0, 3.0, 2.0),
    56: (4.0, 3.0, 2.0),
    60: (4.0, 3.0, 2.0),
    64: (4.0, 3.0, 2.0),
}

# A 0.4 mm nozzle lays a bead about this wide, and a thread flank needs to be
# at least one bead or the crest never forms and the thread is a knurl. M5
# coarse is the smallest that clears it; below that, print a plain boss and
# tap it, or use a heat-set insert.
MIN_PITCH = 0.8

_DESIGNATION = re.compile(r"^M(\d+(?:\.\d+)?)(?:[x×](\d+(?:\.\d+)?))?$", re.IGNORECASE)


@dataclass(frozen=True)
class Thread:
    """One thread, resolved from its designation."""

    name: str
    major_d: float
    pitch: float
    series: str

    @property
    def height(self) -> float:
        """H, the height of the sharp ISO triangle. `sqrt(3) / 2 * pitch`."""
        return 0.8660254037844386 * self.pitch

    @property
    def minor_d(self) -> float:
        """Minor diameter of the internal thread — the tapped hole's own bore.

        `D - 5/4 * H`, which is where the ISO profile puts the internal root.
        """
        return round(self.major_d - 1.25 * self.height, 3)

    @property
    def tap_drill(self) -> float:
        """Drill size for tapping this by hand, if you print the boss plain.

        `D - P`, the shop rule of thumb, which lands near 75% engagement.
        """
        return round(self.major_d - self.pitch, 2)

    @property
    def wall(self) -> float:
        """Least material a tapped boss needs around the thread.

        The thread cuts to `major_d`, so the boss has to carry two perimeters
        outside that before it is a wall at all.
        """
        return 2 * LINE_W


def parse(designation: str) -> Thread:
    """Resolve `"M12"` (coarse) or `"M12x1.5"` (fine) against ISO 261.

    An unlisted pitch is an error rather than a thread nobody can buy a bolt
    for. The message names the pitches that diameter does have.
    """
    match = _DESIGNATION.match(designation.strip())
    if match is None:
        raise ValueError(
            f"{designation!r} is not a metric thread designation; "
            "write M12 for the coarse pitch or M12x1.5 for a fine one"
        )

    major = float(match.group(1))
    if major not in COARSE:
        near = sorted(COARSE, key=lambda d: abs(d - major))[:4]
        raise ValueError(
            f"M{major:g} is not an ISO 261 diameter; nearest are "
            + ", ".join(f"M{d:g}" for d in sorted(near))
        )

    if match.group(2) is None:
        thread = Thread(f"M{major:g}", major, COARSE[major], "coarse")
    else:
        pitch = float(match.group(2))
        allowed = FINE.get(major, ())
        if pitch == COARSE[major]:
            thread = Thread(f"M{major:g}x{pitch:g}", major, pitch, "coarse")
        elif pitch in allowed:
            thread = Thread(f"M{major:g}x{pitch:g}", major, pitch, "fine")
        else:
            options = [COARSE[major], *allowed]
            raise ValueError(
                f"M{major:g} has no {pitch:g} mm pitch in ISO 261; it is "
                + ", ".join(f"{p:g}" for p in options)
                + f" (coarse is {COARSE[major]:g})"
            )

    if thread.pitch < MIN_PITCH:
        raise ValueError(
            f"{thread.name} has a {thread.pitch:g} mm pitch, under the "
            f"{MIN_PITCH:g} mm a {2 * LINE_W:.2f} mm bead can form — print a "
            f"plain boss and tap it {thread.tap_drill:g} mm instead"
        )
    return thread


def _self_check() -> None:
    """The tables have to agree with the standard before anything is cut."""
    for diameter, pitches in FINE.items():
        assert diameter in COARSE, f"M{diameter:g} is fine-only, which ISO 261 is not"
        assert COARSE[diameter] not in pitches, (
            f"M{diameter:g}: {COARSE[diameter]:g} is its coarse pitch, "
            "so it does not belong in the fine list too"
        )
        assert list(pitches) == sorted(pitches, reverse=True), (
            f"M{diameter:g} fine pitches should read coarsest first"
        )
    # Spot-checks against ISO 261 proper, so a typo in the bulk of the table
    # has something to fail against.
    for name, pitch in (
        ("M3", 0.5),
        ("M6", 1.0),
        ("M8", 1.25),
        ("M12", 1.75),
        ("M16", 2.0),
        ("M20", 2.5),
        ("M24", 3.0),
        ("M36", 4.0),
    ):
        assert COARSE[float(name[1:])] == pitch, f"{name} coarse pitch is not {pitch}"


_self_check()
