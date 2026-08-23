"""Standard bearing trade sizes, and the lookup that turns a name into numbers.

A helper, not a model: no `build()`, and the leading underscore keeps it out of
the export sweep entirely.

Every row is bore / outside diameter / width in millimetres, plus the flange
for the F-series. The inch series is stored as its fractions rather than as
decimals so the source of each number stays visible — `9 / 8 * IN` is a
1-1/8 inch outside diameter, `1.125` is a number somebody typed.

Widths in the inch series are the **open** ones. Most R sizes are also sold
shielded (ZZ) or sealed (2RS) in a wider shell — R8 is 1/4 open and 5/16
shielded — so a printed copy of an "R8" is only a drop-in for the open one.
"""

from __future__ import annotations

from dataclasses import dataclass

IN = 25.4


@dataclass(frozen=True)
class Size:
    """One row of the trade table, in millimetres.

    `bore`, not `id`: `id` is a Python builtin, and shadowing a name that is
    also a parameter is the exact mistake the OpenSCAD original made — see the
    header of bearing.py.
    """

    name: str
    bore: float
    od: float
    width: float
    flange: bool = False
    flange_d: float = 0.0
    flange_w: float = 0.0


TABLE: tuple[Size, ...] = (
    # ---- inch series ------------------------------------------------------
    Size("R2", 1 / 8 * IN, 3 / 8 * IN, 5 / 32 * IN),
    Size("R3", 3 / 16 * IN, 1 / 2 * IN, 5 / 32 * IN),
    Size("R4", 1 / 4 * IN, 5 / 8 * IN, 0.196 * IN),
    Size("R6", 3 / 8 * IN, 7 / 8 * IN, 7 / 32 * IN),
    Size("R8", 1 / 2 * IN, 9 / 8 * IN, 1 / 4 * IN),
    Size("R10", 5 / 8 * IN, 11 / 8 * IN, 9 / 32 * IN),
    Size("R12", 3 / 4 * IN, 13 / 8 * IN, 5 / 16 * IN),
    Size("R14", 7 / 8 * IN, 15 / 8 * IN, 3 / 8 * IN),
    Size("R16", 8 / 8 * IN, 16 / 8 * IN, 3 / 8 * IN),
    Size("R18", 9 / 8 * IN, 17 / 8 * IN, 3 / 8 * IN),
    Size("R20", 10 / 8 * IN, 18 / 8 * IN, 3 / 8 * IN),
    Size("R22", 11 / 8 * IN, 20 / 8 * IN, 7 / 16 * IN),
    Size("R24", 12 / 8 * IN, 21 / 8 * IN, 7 / 16 * IN),
    # ---- metric, deep groove ----------------------------------------------
    Size("605", 5, 14, 5),
    Size("608", 8, 22, 7),
    Size("629", 9, 26, 8),
    Size("635", 5, 19, 6),
    Size("6000", 10, 26, 8),
    Size("6001", 12, 28, 8),
    Size("6002", 15, 32, 9),
    Size("6003", 17, 35, 10),
    Size("6007", 35, 62, 14),
    Size("6200", 10, 30, 9),
    Size("6201", 12, 32, 10),
    Size("6202", 15, 35, 11),
    Size("6203", 17, 40, 12),
    Size("6204", 20, 47, 14),
    Size("6205", 25, 52, 15),
    Size("6206", 30, 62, 16),
    Size("6207", 35, 72, 17),
    Size("6208", 40, 80, 18),
    Size("6209", 45, 85, 19),
    Size("6210", 50, 90, 20),
    Size("6211", 55, 100, 21),
    Size("6212", 60, 110, 22),
    Size("6301", 12, 37, 12),
    Size("6302", 15, 42, 13),
    Size("6303", 17, 47, 14),
    Size("6304", 20, 52, 15),
    Size("6305", 25, 62, 17),
    Size("6306", 30, 72, 19),
    Size("6307", 35, 80, 21),
    Size("6308", 40, 90, 23),
    Size("6309", 45, 100, 25),
    Size("6310", 50, 110, 27),
    Size("6311", 55, 120, 29),
    Size("6312", 60, 130, 31),
    Size("6403", 17, 62, 17),
    Size("6800", 10, 19, 5),
    Size("6801", 12, 21, 5),
    Size("6802", 15, 24, 5),
    Size("6803", 17, 26, 5),
    Size("6804", 20, 32, 7),
    Size("6805", 25, 37, 7),
    Size("6806", 30, 42, 7),
    Size("6900", 10, 22, 6),
    Size("6901", 12, 24, 6),
    Size("6902", 15, 28, 7),
    Size("6903", 17, 30, 7),
    Size("6904", 20, 37, 9),
    Size("6905", 25, 42, 9),
    Size("6906", 30, 47, 9),
    Size("6907", 35, 55, 10),
    Size("6908", 40, 62, 12),
    Size("16004", 20, 42, 8),
    Size("16005", 25, 47, 8),
    Size("16100", 10, 28, 8),
    Size("16101", 12, 30, 8),
    # ---- flanged ----------------------------------------------------------
    Size("F686ZZ", 6, 13, 5, True, 15, 1),
    Size("F687ZZ", 7, 14, 5, True, 16, 1),
    Size("F688ZZ", 8, 16, 5, True, 18, 1),
    Size("F689ZZ", 9, 17, 5, True, 19, 1),
    Size("F6900ZZ", 10, 22, 6, True, 25, 1.5),
    Size("F6901ZZ", 12, 24, 6, True, 26.5, 1.5),
    Size("F6902ZZ", 15, 28, 7, True, 31.5, 1.5),
    Size("F6903ZZ", 17, 30, 7, True, 33.5, 1.5),
    Size("F6904ZZ", 20, 37, 9, True, 40.5, 1.5),
    Size("F6905ZZ", 25, 42, 9, True, 45.5, 1.5),
    Size("F6000ZZ", 10, 26, 8, True, 28.5, 1.5),
    Size("F6001ZZ", 12, 28, 8, True, 30.5, 1.5),
    Size("F6002ZZ", 15, 32, 9, True, 34.5, 1.5),
    Size("F6003ZZ", 17, 35, 10, True, 37.5, 1.5),
    Size("F6004ZZ", 20, 42, 12, True, 44.5, 1.5),
    Size("F6005ZZ", 25, 47, 12, True, 49.5, 1.5),
    Size("F6006ZZ", 30, 55, 13, True, 57.5, 1.5),
)

BY_NAME: dict[str, Size] = {s.name: s for s in TABLE}


def lookup(name: str) -> Size:
    """The row for a trade size, or a message naming the near misses.

    The OpenSCAD original leaned on `search()`, which answers "not found" with
    an empty list and then indexes the table with it. Failing here, by name,
    is the whole reason this is a function.
    """
    try:
        return BY_NAME[name]
    except KeyError:
        near = [n for n in BY_NAME if n.startswith(name[:2])] or list(BY_NAME)
        raise KeyError(
            f"unknown bearing trade size {name!r}; "
            f"{len(BY_NAME)} are known, closest by prefix: {', '.join(near[:8])}"
        ) from None


def _self_check() -> None:
    """The table has to be consistent before any geometry is built from it.

    Cheap enough to run at import: a typo'd column here is a silently wrong
    part, and every model in this project reads the table before it draws
    anything.
    """
    seen: set[str] = set()
    for s in TABLE:
        assert s.name not in seen, f"{s.name} appears twice in the trade table"
        seen.add(s.name)
        assert 0 < s.bore < s.od, f"{s.name}: bore {s.bore} is not inside OD {s.od}"
        assert s.width > 0, f"{s.name}: width {s.width} is not positive"
        # A race needs somewhere to be. The generator splits the radial gap
        # three ways — inner race, rolling element, outer race — so a section
        # thinner than the width is a bearing whose races are foil.
        assert s.od - s.bore >= 4, f"{s.name}: only {s.od - s.bore:.2f} mm of radial gap"
        if s.flange:
            assert s.flange_d > s.od, (
                f"{s.name}: flange {s.flange_d} does not clear OD {s.od}"
            )
            assert 0 < s.flange_w < s.width, (
                f"{s.name}: flange width {s.flange_w} does not fit in {s.width}"
            )
        else:
            assert s.flange_d == s.flange_w == 0, f"{s.name}: unflanged but has a flange"


_self_check()
