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
    filament: the slicer's own name for this stuff, minus the "@vendor machine"
             suffix, so `cadkit.slicing` can find a real vendor profile and get
             a real weight instead of density times volume. Lives here rather
             than in the slicing module because it is a fact about the
             material, and a material should carry everything about itself in
             one place.
    warp:    relative tendency to lift a first layer off the plate, 0 to 1.
             Deliberately a *ranking* and not a shrinkage percentage: no source
             in REFERENCE.md gives a hard figure for ASA, and inventing one
             would put a number nobody measured into a check that then reads as
             authoritative. It scales one threshold — how large a flat footprint
             may get before a sharp corner on it is worth flagging — so its
             ordering matters and its absolute value does not.
    """

    name: str
    density: float
    tg: float | None = None
    warp: float = 0.5
    filament: str | None = None

    def mass(self, volume_mm3: float) -> float:
        """Solid mass in grams for a volume in cubic millimetres."""
        return volume_mm3 / 1000.0 * self.density


# The filament names are Bambu's own, as they appear in the slicer's profile
# tree. Generic where one exists, because the brand on the spool is not this
# file's business; branded where it does not.
PLA = Material("PLA", 1.24, tg=60.0, warp=0.1, filament="Generic PLA")
PETG = Material("PETG", 1.27, tg=80.0, warp=0.3, filament="Generic PETG")
ABS = Material("ABS", 1.04, tg=105.0, warp=1.0, filament="Bambu ABS")
# ASA warp: "lower than ABS", unquantified anywhere in REFERENCE.md.
ASA = Material("ASA", 1.07, tg=105.0, warp=0.9, filament="Bambu ASA")
PC = Material("PC", 1.20, tg=147.0, warp=1.0, filament="Generic PC")
# Nylon: the vendor tree has no unfilled profile for this machine, so the
# nearest thing is a carbon-filled one. Its weight will be a few percent out.
PA = Material("PA", 1.14, tg=50.0, warp=0.8, filament="Bambu PA6-CF")
TPU = Material("TPU", 1.21, warp=0.1, filament="Generic TPU")  # no useful Tg

BY_NAME = {m.name: m for m in (PLA, PETG, ABS, ASA, PC, PA, TPU)}
