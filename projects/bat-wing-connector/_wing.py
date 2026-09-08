"""The bat-wing connector generator. A helper, not a model — `connector.py` is
the thin file that says which spec to draw.

One 1/2" PVC "arm" and four 1/4" PVC "fingers" emerge as short collars
from a broad circular palm, matching the connector's top-view sketch. See
`_envelope()` for that hub-and-collars construction. Every socket is a blind pocket, not a
through-bore: sockets used to share one open, connected interior so
something could be threaded from the trunk into any finger, but at a wide
enough fan that means support material trapped inside a sealed cavity with
no way back out, so blind sockets and a solid joint replaced it — see
`solid()` and `check_wing()`.

    from _wing import Wing, check_wing, solid

    SPEC = Wing()

    python projects/bat-wing-connector/_wing.py    # prints reach and validate()'s verdict
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import cast

from build123d import Compound, Cylinder, Location, Part, Pos, Rot, Vector

from cadkit.measure import measured
from cadkit.select import shape

# ---- measured ---------------------------------------------------------------
# 1/2" and 1/4" PVC, caliper-measured against this same stock in
# projects/pvc-6-way-converter/converter.py — not re-measured here.
TRUNK_OD, TRUNK_ID = 19.8, 15.8  # 1/2" PVC
FINGER_OD, FINGER_ID = 13.7, 9.7  # 1/4" PVC

# ---- decided ------------------------------------------------------------
# Radial gap so a socket's bore clears the pipe's own OD. REFERENCE.md's
# generic clearance-hole figure, untried against a printed socket at this
# diameter — see measurements.toml.
CLEARANCE = measured("clearance")

# How deep a socket's blind pocket reaches in from the mouth — how much pipe
# it can take. Reasoned from typical PVC slip-fit practice, not dry-fitted —
# see measurements.toml.
SOCKET_DEPTH = measured("socket_depth")

# Tolerance for measuring the built part back. Loose next to OCCT's own
# precision, tight next to anything a 0.4 mm nozzle can express.
TOL = 1e-3


@dataclass(frozen=True)
class Socket:
    """One pipe's mouth: its own OD, and its angle off the trunk axis.

    All angles are measured in the palm's XY plane, trunk at 0.
    """

    od: float
    angle: float


def _adjacent_pairs(sockets: list[Socket]):
    """Every socket paired with its nearest neighbour going round the pivot.

    `sockets` is sorted by angle already (trunk at 0, increasing), so
    consecutive pairs cover every gap but one: the last socket back round to
    the trunk, the empty side of the fan. That pair's gap is `360 -
    sockets[-1].angle` — a real neighbour relationship (both axes still meet
    at the same pivot), included as a `Socket` standing in for the trunk at
    its wrapped-around angle so callers don't have to special-case it.
    """
    yield from zip(sockets, sockets[1:], strict=False)
    wrapped = Socket(sockets[0].od, sockets[0].angle + 360)
    yield sockets[-1], wrapped


@dataclass(frozen=True)
class Wing:
    """Every dimension of the connector, given or derived, in one place.

    `solid()` draws from this and `check_wing()` measures back against it, so
    there is no second copy of the arithmetic to drift.
    """

    wall: float = 2.0
    finger_angle_step: float = 40.0  # degrees between adjacent fingers
    finger_count: int = 4
    # Degrees from the trunk to the first, nearest finger. The top-view sketch
    # puts that gap at about 50 degrees, then the four fingers continue around
    # the same side of the palm at 40-degree steps. This is intentionally not
    # the symmetric 120-degree gap used by the previous model: that wrapped
    # the sockets around 240 degrees and did not match the drawing.
    wrist_angle: float = 50.0

    # ---- derived -------------------------------------------------------
    @property
    def sockets(self) -> list[Socket]:
        """Trunk first, at angle 0, then each finger fanning out from it.

        The first finger sits `wrist_angle` off the trunk; every finger
        after that is another `finger_angle_step` further round.
        """
        fingers = [
            Socket(FINGER_OD, self.wrist_angle + i * self.finger_angle_step)
            for i in range(self.finger_count)
        ]
        return [Socket(TRUNK_OD, 0.0), *fingers]

    def id_hole(self, pipe_od: float) -> float:
        """The bore a pipe of this OD slides into."""
        return pipe_od + 2 * CLEARANCE

    def od_stub(self, pipe_od: float) -> float:
        """Outside of the stub around that bore, one `wall` of material thick."""
        return self.id_hole(pipe_od) + 2 * self.wall

    @property
    def joint_r(self) -> float:
        """Radius of the broad circular palm shown in the top-view sketch.

        `min_reach` is where adjacent collars have completely separated. The
        palm continues one radius of the largest collar beyond that point, so
        it hides the converging tubes and leaves only short socket collars
        visible outside its perimeter. This is a derived proportion rather
        than a dimension read from the photograph.
        """
        return self.min_reach + self.od_stub(TRUNK_OD) / 2

    @property
    def collar_root(self) -> float:
        """Distance from the centre where each collar begins.

        Starting one wall inside the palm perimeter gives the collar and palm
        a real lap joint without carrying the tube through the centre or out
        through the palm's opposite edge.
        """
        return self.joint_r - self.wall

    @property
    def joint_h(self) -> float:
        """Thickness of the circular palm in Z, normal to its flat faces.

        Every socket axis lies in the palm's XY midplane, so the palm only has
        to be as thick as the biggest collar crossing it — the trunk's — with
        two walls of margin around its surface.
        """
        return self.od_stub(TRUNK_OD) + 2 * self.wall

    @property
    def min_reach(self) -> float:
        """Shortest reach at which every socket has pulled clear of its
        neighbours — the point where a mouth stops being fused to the tube
        next to it and becomes its own free-standing opening.

        Two cylinders (radii Rs, Ro) through a common point at angle theta:
        the closest a point on one's disk, at range r along its own axis,
        comes to the other's axis is `r*sin(theta) - Rs*cos(theta)`, and it
        has to clear the other's own radius. Solved for r:

            r >= (Ro + Rs*cos(theta)) / sin(theta)

        Checked both directions for every adjacent pair — near/far is not
        symmetric, since one tube can clear the other without the other
        clearing it back, if the second one's own reach runs out first — and
        the worst of all of them is what every socket is drawn to, since
        `reach` is one number shared by the whole fan.

        "Adjacent" is circular, not just consecutive in the list: every axis
        meets every other one at the same pivot, so the gap from the last
        finger back round to the trunk is a neighbour pair too, and at a wide
        enough spread it can be the tightest one — a fan wrapping most of the
        way around a full circle leaves less on the empty side than between
        two fingers on the crowded side.
        """
        worst = 0.0
        for a, b in _adjacent_pairs(self.sockets):
            gap = b.angle - a.angle
            # The wrapped empty-side gap may exceed 180 degrees. Cylinder-axis
            # separation uses the smaller angle between the two rays.
            diff = math.radians(min(gap, 360 - gap))
            for near, far in ((a, b), (b, a)):
                rs, ro = self.od_stub(near.od) / 2, self.od_stub(far.od) / 2
                need = (ro + rs * math.cos(diff)) / math.sin(diff)
                worst = max(worst, need)
        return worst

    @property
    def reach(self) -> float:
        """Pivot to mouth, along any socket's axis.

        `min_reach` plus `wall`: the margin isn't `socket_depth` alone,
        because `min_reach` is the point where two neighbours are *exactly*
        tangent — zero wall between them — and OCCT does not reliably resolve
        a boolean at exact tangency. Rounding that up by a wall's worth before
        `socket_depth`'s own engagement length is added keeps every mouth's
        annulus a couple of tenths clear of its neighbour rather than sitting
        on the edge of the same tolerance `validate()` refuses geometry at.
        """
        return self.min_reach + self.wall + SOCKET_DEPTH

    @property
    def plan_rotation(self) -> float:
        """Rotate the fan in XY to match the drawing's top-view orientation.

        The trunk points left, the last finger points right, and the sockets
        between them sweep around the lower half of the palm. This rotation
        has no printability effect because the palm lies flat on the plate.
        """
        bisector = self.sockets[-1].angle / 2
        return -(90 + bisector)

    def validate(self) -> None:
        """Everything that has to hold before any geometry is drawn.

        Not `check_wing()` — these are preconditions on the numbers, and a
        violated one produces geometry that is nonsense rather than merely
        wrong, so it is worth refusing before OCCT is asked to do the boolean.
        """
        if self.wall <= 0:
            raise ValueError(f"wall {self.wall} must be positive")
        if not 0 < self.finger_angle_step < 180:
            raise ValueError(
                f"finger_angle_step {self.finger_angle_step} must be between "
                "0 and 180 degrees — two sockets 0 or 180 degrees apart don't "
                "describe a direction between them"
            )
        if not 0 < self.wrist_angle < 180:
            raise ValueError(
                f"wrist_angle {self.wrist_angle} must be between 0 and 180 "
                "degrees, the same reason as finger_angle_step above"
            )
        if self.finger_count < 1:
            raise ValueError(f"finger_count {self.finger_count} must be at least 1")
        if SOCKET_DEPTH <= 0:
            raise ValueError(f"socket_depth {SOCKET_DEPTH} must be positive")
        span = self.sockets[-1].angle
        if span >= 360:
            raise ValueError(
                f"trunk to the last finger spans {span:g} degrees, which wraps "
                "past the trunk itself — narrow finger_angle_step, wrist_angle "
                "or finger_count"
            )


# ---- geometry ----------------------------------------------------------
# The circular palm lies flat in XY. Socket cylinders begin Z-standing, rotate
# into an intermediate XZ fan, then the outer 90-degree X rotation lays that
# fan into XY. The resulting top view has the trunk on the left and the four
# fingers sweeping below the palm to the right, as drawn.


def direction(angle_deg: float, rotation: float) -> Vector:
    """Unit vector a socket at this angle points along in the palm's XY plane."""
    theta = math.radians(90 + angle_deg + rotation)
    return Vector(math.sin(theta), -math.cos(theta), 0)


def _axis_location(angle_deg: float, axial_offset: float, rotation: float) -> Location:
    """Lay a Z-standing shape along one radial axis in the palm's XY plane."""
    return Rot(90, 0, 0) * Rot(0, 90 + angle_deg + rotation, 0) * Pos(0, 0, axial_offset)


def _collar(radius: float, w: Wing, angle: float) -> Part:
    """A short cylinder from just inside the palm edge to the socket mouth."""
    height = w.reach - w.collar_root
    z_offset = (w.reach + w.collar_root) / 2
    return _axis_location(angle, z_offset, w.plan_rotation) * Cylinder(radius, height)


def _bore(radius: float, w: Wing, angle: float) -> Part:
    """A blind pocket on one socket's axis: `SOCKET_DEPTH` deep, starting
    right at the mouth and stopping well short of the pivot — nowhere near
    the joint or any other socket's own pocket."""
    z_offset = w.reach - SOCKET_DEPTH / 2
    return _axis_location(angle, z_offset, w.plan_rotation) * Cylinder(
        radius, SOCKET_DEPTH
    )


def _envelope(w: Wing) -> Part:
    """The hull: the broad circular palm plus five short socket collars.

    The palm is a Z-axis cylinder through the pivot (`Wing.joint_r`,
    `Wing.joint_h`), square to every radial socket axis. Its lower circular
    face sits on the print bed; only the collars need support.
    """
    part = Cylinder(w.joint_r, w.joint_h)
    for s in w.sockets:
        part = cast(Part, part + _collar(w.od_stub(s.od) / 2, w, s.angle))
    return part


def _pockets(w: Wing) -> Part | Compound:
    """Every socket's blind pocket, unioned into one piece purely so there
    is one shape to subtract — each pocket is nowhere near any other, so
    this is a union of separate pieces, not a connected cavity. See
    `check_wing()`, which measures that they stay that way.
    """
    part: Part | Compound | None = None
    for s in w.sockets:
        pocket = _bore(w.id_hole(s.od) / 2, w, s.angle)
        part = pocket if part is None else cast(Part | Compound, part + pocket)
    assert part is not None
    return part


def solid(w: Wing) -> Part:
    """The whole connector: hull minus every socket's blind pocket."""
    w.validate()
    return cast(Part, _envelope(w) - _pockets(w))


# ---- checks --------------------------------------------------------------


def _radius_from_axis(point, axis: Vector) -> float:
    """How far a point sits off a socket's axis line, mm.

    The axis passes through the pivot at the origin, so this is the point's
    component perpendicular to `axis` — the same idea as
    `pvc-6-way-converter/converter.py`'s `_radius`, generalised from a
    coordinate axis to an arbitrary direction through the origin.
    """
    p = Vector(point.X, point.Y, point.Z)
    along = p.dot(axis)
    return (p - axis * along).length


def mouth(part, socket: Socket, w: Wing) -> tuple[float, float]:
    """(outer diameter, inner diameter) measured at one socket's mouth face.

    Located by where that socket's axis says the mouth has to be — `reach`
    along its `direction` — rather than trusted from the code that drew it.
    """
    axis = direction(socket.angle, w.plan_rotation)
    target = axis * w.reach
    face = None
    for candidate in shape(part).faces():
        if (candidate.center() - target).length < 1e-2:
            face = candidate
            break
    if face is None:
        raise AssertionError(
            f"no face found at the {socket.od:g} mm socket's mouth "
            f"({tuple(round(c, 2) for c in target)}) — the geometry does not "
            "match the spec it was drawn from"
        )

    wires = face.wires()
    if len(wires) != 2:
        raise AssertionError(
            f"the {socket.od:g} mm socket's mouth has {len(wires)} wire(s), "
            "not 2 — it is not an open annulus (a blind floor, or a mouth "
            "that merged into a neighbour)"
        )
    radii = sorted(
        (max(_radius_from_axis(v, axis) for v in wire.vertices()) for wire in wires),
        reverse=True,
    )
    return 2 * radii[0], 2 * radii[1]


def _axial_extent(part, axis: Vector) -> tuple[float, float]:
    """(nearest, farthest) a shape reaches along `axis`, from the pivot."""
    projections = [Vector(v.X, v.Y, v.Z).dot(axis) for v in shape(part).vertices()]
    return min(projections), max(projections)


def check_wing(part, w: Wing) -> None:
    """Measure the built connector against the numbers it was drawn from."""
    from cadkit import fits_bed, single_solid

    single_solid(part)
    fits_bed(part)

    # Every socket's pocket is meant to be its own separate hole — blind,
    # not threading into a shared interior — so the union should be exactly
    # as many solids as there are sockets, never fewer. Fewer would mean two
    # pockets that were supposed to stay apart have actually merged.
    pockets = _pockets(w)
    solids = shape(pockets).solids()
    assert len(solids) == len(w.sockets), (
        f"the {len(w.sockets)} sockets' pockets form {len(solids)} piece(s), "
        "not one each — some are merging into each other, which a blind "
        "design is supposed to rule out"
    )

    # Each pocket is the same axis as its own stub and a smaller radius, so
    # it is a subset of it by construction, and the stub is itself one of
    # the envelope's own pieces — this should never fire. Kept as a
    # defensive check on that construction rather than trusted outright, the
    # same reason `single_solid` above is measured rather than assumed.
    envelope = _envelope(w)
    leak = pockets - envelope
    leak_v = 0.0 if leak is None else leak.volume
    assert leak_v < TOL, (
        f"the pockets poke {leak_v:.3f} mm3 outside the hull — a pocket is "
        "wider than its own stub, which should not be possible from the spec"
    )

    consistency = abs((envelope.volume - pockets.volume) - part.volume)
    assert consistency < 1.0, (
        f"envelope minus pockets is {envelope.volume - pockets.volume:.1f} "
        f"mm3, but the built part measures {part.volume:.1f} mm3 — "
        "something else touched the geometry after the boolean"
    )

    for s in w.sockets:
        od_got, id_got = mouth(part, s, w)
        od_want, id_want = w.od_stub(s.od), w.id_hole(s.od)
        assert abs(od_got - od_want) < TOL and abs(id_got - id_want) < TOL, (
            f"the {s.od:g} mm socket at {s.angle:g} deg measures "
            f"{od_got:.2f}/{id_got:.2f} mm OD/ID, wanted {od_want:.2f}/{id_want:.2f}"
        )
        wall_got = (od_got - id_got) / 2
        assert abs(wall_got - w.wall) < TOL, (
            f"the {s.od:g} mm socket's wall measures {wall_got:.2f} mm, "
            f"wanted {w.wall:.2f}"
        )

        # The floor's own depth, not trusted from SOCKET_DEPTH: this
        # workspace's first real bug was assuming a cavity was as deep as
        # the extrusion that produced it, and shelling laid a wall's worth
        # of material under the step instead. Measured on the pocket built
        # fresh from the spec, the same defensive habit as the checks above.
        axis = direction(s.angle, w.plan_rotation)
        pocket = _bore(w.id_hole(s.od) / 2, w, s.angle)
        near, far = _axial_extent(pocket, axis)
        assert abs(far - w.reach) < TOL, (
            f"the {s.od:g} mm socket's pocket reaches to {far:.2f} mm, not "
            f"{w.reach:.2f} — its mouth is not where the tube's own mouth is"
        )
        depth = far - near
        assert abs(depth - SOCKET_DEPTH) < TOL, (
            f"the {s.od:g} mm socket's pocket is {depth:.2f} mm deep, wanted "
            f"{SOCKET_DEPTH:.2f}"
        )


if __name__ == "__main__":
    w = Wing()
    w.validate()
    print(f"min_reach = {w.min_reach:.2f} mm (where mouths pull free of each other)")
    print(f"reach     = {w.reach:.2f} mm (pivot to mouth)")
    for s in w.sockets:
        print(
            f"  {s.od:5.1f} mm pipe at {s.angle:5.1f} deg  ->  "
            f"OD {w.od_stub(s.od):.2f}  ID {w.id_hole(s.od):.2f}"
        )
