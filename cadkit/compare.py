"""How far a rebuilt part has drifted from the geometry it was rebuilt from.

One project here reads somebody else's generator output, repairs a fault in it,
and exports the result. Nothing measures whether the repair left the rest of it
alone — `check()` asserts the dimensions the model knows to assert, and a
surface that quietly moved two millimetres between them passes.

Deviation is two questions, not one, and they have different answers:

  * how far our surface sits from theirs — where we added material or moved it;
  * how much of theirs we did not reproduce — where we lost a feature.

A single "average error" hides the second behind the first. A rebuild that
drops a boss entirely can have a fine average, because every point we *did*
model is right where it should be. Both directions are reported, always.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Drift:
    """Distances, in mm, from one surface to another."""

    worst: float
    typical: float  # median
    p95: float
    samples: int

    def line(self) -> str:
        return (
            f"worst {self.worst:.2f}, typical {self.typical:.2f}, 95th {self.p95:.2f} mm"
        )


@dataclass(frozen=True)
class Comparison:
    ours_to_theirs: Drift  # material we put where they had none
    theirs_to_ours: Drift  # material they had that we did not model
    target: Path

    def line(self) -> str:
        return (
            f"ours -> theirs: {self.ours_to_theirs.line()}\n"
            f"theirs -> ours: {self.theirs_to_ours.line()}"
        )


# Fixed, for the same reason `cadkit.dfm` fixes its own: a drift figure that
# moves between runs cannot answer "is the rebuild closer than it was".
SEED = 20260813


def _drift(source, against, samples: int) -> Drift:
    import numpy as np
    import trimesh

    points, _ = trimesh.sample.sample_surface(source, samples, seed=SEED)
    distance = against.nearest.on_surface(points)[1]
    return Drift(
        worst=float(distance.max()),
        typical=float(np.median(distance)),
        p95=float(np.percentile(distance, 95)),
        samples=len(distance),
    )


def compare(part, target: str | Path, samples: int = 4000) -> Comparison:
    """Measure a built part against the mesh it was rebuilt from.

    Sampled rather than exhaustive, and by area, so a large flat face is not
    out-voted by a corner somebody tessellated finely. Four thousand points is
    enough that the 95th percentile is stable between runs and the worst case
    is not; read the worst as "there is something at least this bad", not as a
    number to compare between runs.
    """
    from cadkit.mesh import from_part, from_stl

    target = Path(target)
    if not target.is_file():
        raise FileNotFoundError(target)

    ours = from_part(part)
    theirs = from_stl(target)
    return Comparison(
        ours_to_theirs=_drift(ours, theirs, samples),
        theirs_to_ours=_drift(theirs, ours, samples),
        target=target,
    )
