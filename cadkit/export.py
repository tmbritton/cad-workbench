"""Building one model and writing it out.

The single place that turns a model's `build()` into files, shared by the build
driver and by a model's own `__main__`, so `mise build` and
`python projects/x/thing.py` cannot drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from build123d import export_step, export_stl

from cadkit.checks import bed_fit
from cadkit.materials import Material
from cadkit.select import shape

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / "projects"
EXPORTS = ROOT / "exports"

GREY, GREEN, YELLOW, RED, OFF = (
    "\033[90m",
    "\033[32m",
    "\033[33m",
    "\033[31m",
    "\033[0m",
)


@dataclass
class Result:
    project: str
    name: str
    part: object
    stl: Path
    step: Path
    material: Material | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def solids(self) -> int:
        return len(self.part.solids())

    @property
    def volume(self) -> float:
        """Cubic millimetres."""
        return self.part.volume

    def line(self, width: int = 0) -> str:
        """One row of the build report."""
        size = self.part.bounding_box().size
        mass = ""
        if self.material is not None:
            mass = f"   {self.material.mass(self.volume):,.0f} g {self.material.name}"
        solids = f"{self.solids} solid" + ("" if self.solids == 1 else "s")
        return (
            f"{self.name:<{width}}  {solids:<9}  "
            f"{size.X:>6.1f} x {size.Y:>6.1f} x {size.Z:>6.1f} mm   "
            f"{self.volume / 1000:>7,.1f} cm3{mass}"
        ).rstrip()


def build_model(
    project: str,
    name: str,
    build_fn,
    check_fn=None,
    material: Material | None = None,
    write: bool = True,
) -> Result:
    """Build, check, then export. In that order, deliberately.

    `check_fn` runs before anything is written, so a failed assertion leaves
    the previous export in place rather than replacing it with geometry that is
    wrong in a way nobody noticed. A stale STL announces itself when the print
    does not match; a fresh wrong one does not.
    """
    part = shape(build_fn())

    if check_fn is not None:
        check_fn(part)

    out = EXPORTS / project
    result = Result(
        project=project,
        name=name,
        part=part,
        stl=out / f"{name}.stl",
        step=out / f"{name}.step",
        material=material,
    )

    ok, message = bed_fit(part)
    if not ok:
        result.warnings.append(message)

    if write:
        out.mkdir(parents=True, exist_ok=True)
        export_stl(part, str(result.stl))
        export_step(part, str(result.step))

    return result


def material_of(module) -> Material | None:
    """Read a model's declared material, accepting either spelling.

    `MATERIAL = ASA` is preferred because it also carries the name and Tg;
    `DENSITY = 1.07` is accepted for a one-off where naming a material would be
    more ceremony than it is worth.
    """
    mat = getattr(module, "MATERIAL", None)
    if isinstance(mat, Material):
        return mat
    if isinstance(mat, str):
        from cadkit.materials import BY_NAME

        return BY_NAME.get(mat)
    density = getattr(module, "DENSITY", None)
    if isinstance(density, (int, float)):
        return Material("", float(density))
    return None
