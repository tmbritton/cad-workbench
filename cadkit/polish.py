"""Chamfering every edge that will take one, and none of the ones that will not.

`chamfer(part.edges(), 1.0)` is the line everybody writes first, and on any part
with real features it raises. OCCT refuses the whole operation when one edge in
the set has no room — two chamfers meeting on a narrow land, a fillet that
leaves nothing to cut into — and it does not say which edge. What follows is
half an hour of commenting out selectors.

`polish` answers the question the kernel would not: it tries the batch, and on
failure splits it and tries each half, down to single edges. What comes back is
the largest set that lands together, and what is left out is named.

Two things matter more than they look:

  * every attempt chamfers the **original** solid with the whole accepted set,
    never the result of the last attempt. Building up incrementally would
    re-chamfer edges that moved under an earlier cut, and the second pass on a
    moved edge is a different operation with a different answer.
  * an edge is also rejected when its chamfer *succeeds* but leaves a face
    thinner than a bead. That is not a kernel failure — OCCT is happy — but the
    slicer will drop the sliver, so the part is worse for having tried.

Sizes are the workspace default from REFERENCE.md: a chamfer rather than a
fillet at the plate, because a fillet leaves a horizontal tangent at z=0.
"""

from __future__ import annotations

from build123d import GeomType
from build123d import chamfer as _chamfer

from cadkit import printer
from cadkit.select import shape

# Edge shapes a chamfer can run along. Everything else — the b-spline an ISO
# thread's helix comes out as, the free curve an imported mesh leaves behind —
# OCCT will not chamfer at any size, and asking it edge by edge is how a
# finishing pass on a threaded boss comes to take a minute and a half. Three
# hundred and sixteen of that part's four hundred and fifty-three edges are
# helices, and all three hundred and sixteen of them were going to fail.
CHAMFERABLE = (GeomType.LINE, GeomType.CIRCLE, GeomType.ELLIPSE)

# The area below which a face is a sliver the slicer will not print as drawn.
# Three chamfers meeting at a convex corner leave about 0.87 x size squared, so
# the floor has to sit under that or every corner on the part vetoes itself.
FLOOR = 0.8


class Unpolished(RuntimeError):
    """Not one edge in the set could take a chamfer of this size."""


def _small(part, floor: float) -> int:
    return sum(1 for face in part.faces() if face.area < floor)


def _try(part, edges, size: float, floor: float, before: int):
    """Chamfer `edges` onto `part`, or return None if it will not do.

    Returns None both when the kernel refuses and when it agrees but leaves
    more sliver faces than it found, which is the same answer for the caller
    and a different one for the part.
    """
    if not edges:
        return None
    try:
        out = _chamfer(edges, size)
    except Exception:  # noqa: BLE001 — OCCT raises a dozen unrelated types
        return None
    return None if _small(out, floor) > before else out


class _Budget:
    """A count of kernel calls left to spend, and what went untested.

    Bisection is cheap when most edges work — one attempt for a clean part,
    a handful when one edge is bad. It is linear when most edges *fail*, and
    that is not hypothetical: a part with an ISO thread on it has three hundred
    helical edges that will not take a chamfer at any size, and finding that
    out one edge at a time costs a minute and a half.

    So the search is bounded. Running out is not an error and not silent: what
    was not reached is reported as untested, and the fix is to hand `polish` the
    edges you actually meant rather than every edge on the part.
    """

    def __init__(self, attempts: int):
        self.left = attempts
        self.untested: list = []

    def spend(self) -> bool:
        self.left -= 1
        return self.left >= 0


def _accept(part, edges, size: float, floor: float, before: int, budget) -> list:
    """The largest subset of `edges` that chamfers cleanly, by bisection."""
    if not edges:
        return []
    if not budget.spend():
        budget.untested.extend(edges)
        return []
    if _try(part, edges, size, floor, before) is not None:
        return list(edges)
    if len(edges) == 1:
        return []  # tried alone and still no: this edge genuinely has no room

    half = len(edges) // 2
    left = _accept(part, edges[:half], size, floor, before, budget)
    right = _accept(part, edges[half:], size, floor, before, budget)
    if not (left and right):
        return left + right

    # Each half landed on its own; they may still collide with each other.
    both = left + right
    if budget.spend() and _try(part, both, size, floor, before) is None:
        return left if len(left) >= len(right) else right
    return both


def polish(
    obj,
    size: float = 1.0,
    edges=None,
    floor: float | None = None,
    report: list | None = None,
    attempts: int = 500,
):
    """Chamfer as many of `edges` as will take it, and say which would not.

    `edges` defaults to every edge on the part, which is the useful default for
    a finishing pass: the caller narrows it when only some edges are exposed.
    Order is deterministic — longest first, ties broken on position — so the
    same part polishes the same way whatever order its edges came out in, and a
    rebuild does not silently chamfer a different set.

    Pass a list as `report` to be told what was skipped; the edges are appended
    to it. Skipping is normal on a part with tight geometry and is not by
    itself a fault, which is why it is not an exception.

    `attempts` bounds the search, as a backstop rather than as a knob. The
    parts in this tree use between one and 264 of them: a part whose edges all
    work costs exactly one, and the print-in-place bearing — every raceway a
    curve, half its edges hopeless — costs 264. Reaching the default means
    something is unusual, and the message says so rather than quietly returning
    half a pass.
    """
    part = shape(obj)
    candidates = list(part.edges() if edges is None else edges)
    if not candidates:
        return part

    # Two free filters before the kernel is asked anything. An edge shorter
    # than the chamfer cannot take it; an edge that is neither straight nor a
    # circular arc will not take one either. Both are cheap and certain, and
    # between them they clear the thread off a threaded part.
    candidates = [
        e for e in candidates if e.length >= size and e.geom_type in CHAMFERABLE
    ]
    if not candidates:
        raise Unpolished(
            f"no edge on this part is a straight or circular one at least "
            f"{size:.2f} mm long, so there is nothing a chamfer could run along"
        )

    candidates.sort(
        key=lambda e: (-e.length, tuple(round(c, 6) for c in tuple(e.center())))
    )
    floor = FLOOR * size**2 if floor is None else floor
    before = _small(part, floor)

    budget = _Budget(attempts)
    accepted = _accept(part, candidates, size, floor, before, budget)
    if not accepted:
        raise Unpolished(
            f"no edge of this part will take a {size:.2f} mm chamfer "
            f"({len(candidates)} tried) — the size is larger than the features"
        )
    if report is not None:
        kept = {id(e) for e in accepted}
        report.extend(e for e in candidates if id(e) not in kept)
    if budget.untested and report is None:
        # Nobody asked to be told, so say it once rather than let a partial
        # result pass for a complete one.
        import warnings

        warnings.warn(
            f"polish ran out of attempts with {len(budget.untested)} edges "
            f"untested; pass the edges you meant, or raise attempts=",
            stacklevel=2,
        )

    # The whole accepted set at once, against the original solid — build123d
    # takes the parent from the edges themselves, and every edge here came from
    # `part` before anything was cut. Never the result of the last attempt
    # inside the bisection: an edge that moved under an earlier chamfer is a
    # different edge, and chamfering it again is a different operation.
    return _chamfer(accepted, size)


def bed_chamfer(obj, size: float = 1.0, tol: float = 1e-6):
    """Chamfer only the edges sitting on the build plate.

    The one chamfer REFERENCE.md argues for by name: at z=0 a fillet leaves a
    horizontal tangent, which is a severe overhang exactly where adhesion
    matters most and there is nothing underneath but glass. Also the cheapest
    fix for the elephant's foot the first layer squashes out.
    """
    part = shape(obj)
    z = part.bounding_box().min.Z
    on_bed = [e for e in part.edges() if abs(e.center().Z - z) < tol]
    if not on_bed:
        raise Unpolished("no edge sits on the plate; is the part above z=0?")
    return polish(part, size, edges=on_bed)


def cosmetic(obj, size: float | None = None, **kwargs):
    """A finishing pass at the workspace's default size.

    One extrusion width, doubled: small enough to fit almost anywhere, large
    enough to catch the light and stop a part looking like it came out of a
    nozzle rather than out of a design.
    """
    return polish(obj, 2 * printer.LINE_W if size is None else size, **kwargs)
