"""Filament properties, for mass estimates and thermal sanity checks.

Nominal figures. Density varies a few percent between brands and pigments, and
Tg varies more than that between formulations of the same nominal polymer, so
treat these as good enough to decide "does this need an enclosure" and "is this
a 40 g print or a 400 g print" — not as datasheet values for a specific spool.

A model declares its material so the build driver can report mass:

    from cadkit.materials import ASA
    MATERIAL = ASA
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Material:
    """A filament.

    density: g/cm3, solid. Multiply by infill and wall fraction for a real
             print estimate — the number the driver reports is the solid mass,
             which is an upper bound.
    tg:      glass transition, degrees C. The temperature at which the part
             starts to soften and creep. Relevant twice over here: once for
             what the finished part must survive in service, and once for what
             the filament must survive sitting in a heated chamber.
    """

    name: str
    density: float
    tg: float | None = None

    def mass(self, volume_mm3: float) -> float:
        """Solid mass in grams for a volume in cubic millimetres."""
        return volume_mm3 / 1000.0 * self.density


PLA = Material("PLA", 1.24, tg=60.0)
PETG = Material("PETG", 1.27, tg=80.0)
ABS = Material("ABS", 1.04, tg=105.0)
ASA = Material("ASA", 1.07, tg=105.0)
PC = Material("PC", 1.20, tg=147.0)
PA = Material("PA", 1.14, tg=50.0)  # nylon; drops sharply once it absorbs water
TPU = Material("TPU", 1.21)  # elastomer, no useful single Tg

BY_NAME = {m.name: m for m in (PLA, PETG, ABS, ASA, PC, PA, TPU)}
