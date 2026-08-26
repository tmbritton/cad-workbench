"""Whether a part will print, as opposed to whether it is well-formed.

`cadkit.checks` answers questions about the model: is it one solid, does it fit
the plate, did the tessellation survive. Every one of those can pass on a part
that is physically unprintable — a 0.3 mm wall is a perfectly valid solid, and
a shelf hanging in mid-air exports without a murmur.

These rules answer the other question. They are deliberately advisory: nearly
every one of them has a legitimate exception, and a check that cannot be
overruled with a reason is a check that gets ignored wholesale. A model says so
in its own file:

    ALLOW = {"overhang": "the seat ring, printed on support; ring test, 13 Aug 2026"}

The reason is not decoration. It is the only thing that tells the next person
whether the exception was reasoned or merely convenient, which is the same
argument the project READMEs make for recording *why* a dimension is what it
is. An empty reason is an error.

Most rules read the mesh rather than the B-rep, because "does this overhang
need support" is answered by the triangle normals the slicer reads. The two
that are genuinely about the model — a face narrower than one extrusion, a pin
too slender to print — read the B-rep, where the question has an exact answer.

Thresholds come from `cadkit.printer` and the design-for-FDM table in
REFERENCE.md. Where a rule needed a number neither of those had, it is named
and defended in `Limits` below rather than buried in the rule.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from functools import cached_property

from cadkit import printer
from cadkit.select import shape

# Rule names, in report order. Also the set an ALLOW key is checked against: a
# typo there would otherwise silence nothing at all, quietly.
RULES = (
    "unsupported",
    "thin_wall",
    "overhang",
    "bed_overhang",
    "thin_face",
    "thin_pin",
    "warp_risk",
    "stability",
)


@dataclass(frozen=True)
class Finding:
    """One thing wrong with a part, and where to look for it."""

    rule: str
    severity: str  # "fail", "warn", or "allowed"
    message: str
    value: float | None = None
    where: tuple[float, float, float] | None = None
    reason: str | None = None  # why it was allowed, when it was

    def line(self) -> str:
        at = ""
        if self.where is not None:
            x, y, z = self.where
            at = f"  [at {x:.0f}, {y:.0f}, {z:.0f}]"
        because = f"  (allowed: {self.reason})" if self.reason else ""
        return f"{self.rule}: {self.message}{at}{because}"


@dataclass(frozen=True)
class Limits:
    """Every threshold the rules use, in one place so they can be argued with.

    The ones without a printer.py or REFERENCE.md source:

    flat_deg      how far off horizontal a face may be and still count as a
                  roof rather than a slope. Only `overhang` reads it, to leave
                  flat roofs to `unsupported`, which measures the thing that
                  actually decides them.
    severe_deg    where an overhang stops being a warning. Support material is
                  effectively unavailable on this machine (heated chamber, one
                  nozzle), so a 45-degree overhang is a smell and a
                  70-degree one is a plan to print air.
    bridge_mm     reach, in millimetres from the nearest thing holding it up,
                  that prints flat without thinking about it. The dehydrator
                  collar's ledge is 12.5 mm and came off the plate clean, so
                  the number is above that; well-cooled PLA goes further.
    unsupported_mm reach past which no amount of cooling helps and the answer
                  is to turn the part over or change the model.
    sliver_mm2    area under which a narrow face is ignored. Threads and
                  imported meshes carry thousands of near-degenerate faces;
                  what this rule is for is the long thin strip a chamfer leaves
                  when it very nearly did not fit, and that has area.
    corner_deg    turn, accumulated within corner_window_mm of a footprint
                  vertex, that makes it a corner rather than a curve. An 8 mm
                  fillet turns 90 degrees over 12.5 mm of arc and stays under.
    footprint_mm2 flat footprint area, at warp = 1.0, above which a sharp
                  corner is worth mentioning. Scaled by the material's warp
                  ranking, so ASA is held to roughly this and PLA to ten times
                  it. The dehydrator collar is 634 cm2 of ASA and fifteen times
                  over the line, and stays quiet because its corners already
                  turn only ten degrees within the window — which is the rule
                  working, not the rule missing it.
    seed          fixes the surface sampling. Not a threshold — a promise that
                  the same part gives the same answer twice.
    thin_fraction share of the sampled surface that has to sit on thin material
                  before the rule says anything. A wall is a surface, and every
                  genuinely thin wall tried here scored between 8 and 99 per
                  cent. What lives below three per cent is surface detail whose
                  cross-section legitimately tapers — the crest of an ISO
                  thread is the case that set this number, and a thread is not
                  a thin wall.
    leverage      centre-of-mass height divided by its clearance from the edge
                  of the footprint. A tall thing on a narrow base is fine until
                  something nudges it; this is where "fine" stops.
    """

    # The half-degree is not slack in the rule, it is slack in the arithmetic:
    # a nominal 45-degree chamfer tessellates to 45.0000-something, and
    # REFERENCE.md recommends exactly that chamfer. Without it, the one feature
    # the reference tells you to add is the one the checker complains about.
    overhang_deg: float = printer.MAX_OVERHANG_DEG + 0.5
    severe_deg: float = 70.0
    flat_deg: float = 2.0
    min_wall: float = printer.MIN_WALL
    sound_wall: float = printer.SOUND_WALL
    bridge_mm: float = 15.0
    unsupported_mm: float = 40.0
    patch_mm2: float = 2.0  # unsupported patches smaller than this are not worth saying
    face_width: float = printer.LINE_W
    sliver_mm2: float = 1.0  # below this a narrow face is kernel dust, not a feature
    pin_dia: float = 5.0
    corner_deg: float = 60.0
    corner_window_mm: float = 4.0
    footprint_mm2: float = 4000.0
    leverage: float = 20.0
    layer_h: float = printer.LAYER_H
    thin_fraction: float = 0.03
    # Sampling is random, and an unseeded random check is one you cannot act
    # on: run it twice and the wall is 1.18 mm, then 1.33, and neither number
    # is wrong. Fixed here so a finding is reproducible, `mise card` produces
    # no diff unless the geometry moved, and "did my change help" has an
    # answer. Change it to see how much of a finding is the sample and how
    # much is the part.
    seed: int = 20260813  # share of sampled surface before thin_wall speaks
    samples: int = 2000
    patches: int = 2  # findings emitted per rule, worst first


class Scene:
    """A built part, its mesh, and the handful of arrays every rule wants.

    Tessellating and slicing up normals costs more than any single rule does,
    so it happens once here and the rules read it. Nothing is computed until
    something asks for it — `mise build` runs the cheap rules only.
    """

    def __init__(self, part, material=None, limits: Limits | None = None):
        self.part = shape(part)
        self.material = material
        self.limits = limits or Limits()

    @cached_property
    def mesh(self):
        from cadkit.mesh import from_part

        return from_part(self.part)

    @cached_property
    def z_min(self) -> float:
        return float(self.mesh.vertices[:, 2].min())

    @cached_property
    def normals(self):
        return self.mesh.face_normals

    @cached_property
    def areas(self):
        return self.mesh.area_faces

    @cached_property
    def angle(self):
        """Overhang angle per triangle: 0 for a wall, 90 for a flat roof."""
        import numpy as np

        return np.degrees(np.arcsin(np.clip(-self.normals[:, 2], 0.0, 1.0)))

    @cached_property
    def tri_z(self):
        """(lowest, highest) z of each triangle."""
        z = self.mesh.vertices[self.mesh.faces][:, :, 2]
        return z.min(axis=1), z.max(axis=1)

    @cached_property
    def on_bed(self):
        """Triangles that are the footprint: flat, facing down, at the plate.

        Excluded from every overhang rule. The bottom of a part is a 90-degree
        overhang by the arithmetic and the easiest thing in the world to print.
        """
        import numpy as np

        _, high = self.tri_z
        flat_down = self.normals[:, 2] < -np.cos(np.radians(self.limits.flat_deg))
        return flat_down & (high <= self.z_min + 1e-6)

    @cached_property
    def airborne(self):
        """Down-facing triangles with open air beneath them."""
        return _airborne(self)

    @cached_property
    def footprint(self):
        """Convex hull of the footprint in XY, counter-clockwise, or None."""
        import numpy as np
        from scipy.spatial import ConvexHull

        pts = self.mesh.vertices[self.mesh.faces[self.on_bed]].reshape(-1, 3)[:, :2]
        if len(pts) < 3:
            return None
        try:
            hull = ConvexHull(pts)
        except Exception:  # coincident or collinear contact points
            return None
        return np.asarray(pts[hull.vertices], dtype=float)


# ---------------------------------------------------------------------------
# Rules. Each takes a Scene and returns findings, worst first.
# ---------------------------------------------------------------------------


def _patch_report(scene, mask, rule, severity, describe):
    """Turn a triangle mask into at most `patches` findings, largest first."""
    from cadkit.mesh import regions

    out = []
    for patch in regions(scene.mesh, mask)[: scene.limits.patches]:
        area = float(scene.areas[patch].sum())
        if area < scene.limits.patch_mm2:
            continue
        centre = scene.mesh.triangles_center[patch]
        weight = scene.areas[patch]
        where = tuple(float(v) for v in (centre * weight[:, None]).sum(0) / weight.sum())
        message, value = describe(scene, patch, area)
        out.append(Finding(rule, severity, message, value, where))
    return out


def _airborne(scene):
    """Down-facing triangles with nothing directly beneath them.

    The gate every overhang rule sits behind. A sloped or flat down-face that
    has solid material a layer below it is just the side of something standing
    on something else, and there is nothing to say about it.
    """
    import numpy as np

    lim = scene.limits
    low, _ = scene.tri_z
    candidates = (scene.angle > lim.overhang_deg) & ~scene.on_bed
    candidates &= low > scene.z_min + lim.layer_h
    if not candidates.any():
        return np.zeros(len(scene.mesh.faces), dtype=bool)

    idx = np.flatnonzero(candidates)
    origins = scene.mesh.triangles_center[idx] - [0.0, 0.0, 1e-3]
    down = np.tile([0.0, 0.0, -1.0], (len(idx), 1))
    airborne = np.zeros(len(scene.mesh.faces), dtype=bool)
    airborne[idx[~scene.mesh.ray.intersects_any(origins, down)]] = True
    return airborne


def unsupported(scene) -> list[Finding]:
    """Surface with air beneath it, judged by how far it has to reach.

    Bridges print — a hole ceiling is unsupported too, and it comes out fine,
    because the plastic is anchored to a wall at both ends and only has to
    cross. What decides the outcome is the distance from the nearest thing
    holding it up, and that one number covers both failures: a 12 mm ledge is
    nothing, a 40 mm span comes out furred, and an arm sticking out of a post
    with nothing under it at all is a bird's nest.

    Support material is close to unavailable on this machine — one nozzle, and
    a heated chamber that softens the low-Tg filaments usually used for it — so
    the answer to a bad one is to change the model or turn the part over.
    """
    from cadkit.mesh import reach, regions

    lim = scene.limits
    airborne = scene.airborne
    if not airborne.any():
        return []

    out = []
    for patch in regions(scene.mesh, airborne)[: lim.patches * 4]:
        area = float(scene.areas[patch].sum())
        if area < lim.patch_mm2:
            continue
        distance, held = reach(scene.mesh, patch)
        if distance <= lim.bridge_mm:
            continue

        low, _ = scene.tri_z
        height = float(low[patch].min() - scene.z_min)
        centre = scene.mesh.triangles_center[patch].mean(axis=0)
        where = tuple(float(v) for v in centre)

        if held <= 0.0:
            out.append(
                Finding(
                    "unsupported",
                    "fail",
                    f"{area:.0f} mm2 of surface starts {height:.1f} mm above the "
                    f"plate with nothing beneath it and nothing holding its edges",
                    float("inf"),
                    where,
                )
            )
        elif distance > lim.unsupported_mm:
            out.append(
                Finding(
                    "unsupported",
                    "fail",
                    f"{area:.0f} mm2 reaching {distance:.0f} mm from anything that "
                    f"holds it up ({held:.0%} of its outline is on a wall); nothing "
                    f"bridges that far",
                    distance,
                    where,
                )
            )
        else:
            out.append(
                Finding(
                    "unsupported",
                    "warn",
                    f"{distance:.0f} mm unsupported reach across {area:.0f} mm2 "
                    f"({held:.0%} of its outline is on a wall); bridges go about "
                    f"{lim.bridge_mm:.0f} mm before they sag",
                    distance,
                    where,
                )
            )

    order = {"fail": 0, "warn": 1}
    out.sort(key=lambda f: (order[f.severity], -(f.value or 0)))
    return out[: lim.patches]


def overhang(scene) -> list[Finding]:
    """A slope over air steep enough to droop, however short the reach.

    `unsupported` asks how far the plastic has to travel; this asks how much of
    each new layer hangs past the one below it. They catch different things: a
    two-millimetre lip at 80 degrees reaches nowhere and still comes out as a
    row of dropped beads, and a gentle 30-degree cone reaching across a hundred
    millimetres is fine the whole way.
    """
    lim = scene.limits
    steep = scene.airborne & (scene.angle < 90.0 - lim.flat_deg)
    if not steep.any():
        return []

    def describe(scene, patch, area):
        worst = float(scene.angle[patch].max())
        return (
            f"{area:.0f} mm2 overhanging up to {worst:.0f} degrees from vertical "
            f"over open air (the support-free limit is "
            f"{printer.MAX_OVERHANG_DEG:.0f})",
            worst,
        )

    severe = steep & (scene.angle > lim.severe_deg)
    return _patch_report(scene, severe, "overhang", "warn", describe) or _patch_report(
        scene, steep, "overhang", "warn", describe
    )


def thin_wall(scene) -> list[Finding]:
    """Material thinner than the printer can lay down as a wall.

    Measured by casting a ray inward from a sampled point and keeping only the
    hits that land on a surface roughly facing back — a wall has two sides that
    are close to antiparallel. Without that filter every convex corner reads as
    a thin wall, because the ray leaves immediately, and the rule drowns in
    false positives on any chamfered part.

    Each body is measured against itself. A print-in-place assembly has bodies
    a fraction of a millimetre apart on purpose, and a ray that crossed the gap
    would report the clearance as a wall.
    """
    import numpy as np
    import trimesh

    lim = scene.limits
    mesh = scene.mesh
    bodies = mesh.split(only_watertight=False) or [mesh]
    total = sum(len(b.faces) for b in bodies)

    thickness: list = []
    points: list = []
    for body in bodies:
        budget = max(200, int(lim.samples * len(body.faces) / total))
        # Seeded per body, so adding a body does not reshuffle the others.
        pts, fidx = trimesh.sample.sample_surface(
            body, budget, seed=lim.seed + len(body.faces)
        )
        n = body.face_normals[fidx]
        loc, ray, tri = body.ray.intersects_location(
            pts - n * 1e-4, -n, multiple_hits=False
        )
        if len(ray) == 0:
            continue
        d = np.linalg.norm(loc - pts[ray], axis=1)
        facing = (n[ray] * body.face_normals[tri]).sum(1)
        keep = facing < -0.5  # within 60 degrees of antiparallel
        thickness.append(d[keep])
        points.append(pts[ray][keep])

    if not thickness:
        return []
    thickness = np.concatenate(thickness)
    points = np.concatenate(points)
    if len(thickness) == 0:
        return []

    for floor, severity, what in (
        (lim.min_wall, "fail", "cannot be printed at all"),
        (lim.sound_wall, "warn", "is a single pair of beads and will flex"),
    ):
        under = thickness < floor
        # One stray sample is a tessellation artefact or the very tip of a
        # cone, not a verdict on the part. A real thin wall is a surface, and a
        # surface catches a share of an area-weighted sample.
        if under.mean() < lim.thin_fraction:
            continue
        # The median of the samples that are actually under the floor, not a
        # fixed percentile of everything: quoting the 2nd percentile next to
        # "1% of the surface" gives two numbers that contradict each other.
        typical = float(np.median(thickness[under]))
        worst = int(np.argmin(thickness))
        return [
            Finding(
                "thin_wall",
                severity,
                f"{under.mean():.0%} of the sampled surface sits on material under "
                f"{floor:.2f} mm, which {what} "
                f"(those run about {typical:.2f} mm, thinnest {thickness[worst]:.2f})",
                typical,
                tuple(float(v) for v in points[worst]),
            )
        ]
    return []


def bed_overhang(scene) -> list[Finding]:
    """A rounded bottom edge, where a chamfered one belongs.

    REFERENCE.md makes the case: a fillet at the plate leaves a horizontal
    tangent at z=0, which is a severe overhang in exactly the place adhesion
    matters most, and the first layer is the one that has nothing to stick to
    but glass. A chamfer at the same edge is 45 degrees all the way down.
    """
    lim = scene.limits
    low, _ = scene.tri_z
    first = low < scene.z_min + 2 * lim.layer_h
    tangent = (scene.angle > lim.severe_deg) & ~scene.on_bed & first
    if not tangent.any():
        return []

    def describe(scene, patch, area):
        worst = float(scene.angle[patch].max())
        return (
            f"the bottom edge leaves the plate at {worst:.0f} degrees from vertical "
            f"over {area:.0f} mm2 — a chamfer there prints, a fillet does not",
            worst,
        )

    return _patch_report(scene, tangent, "bed_overhang", "warn", describe)


def thin_face(scene) -> list[Finding]:
    """A face narrower than a single extrusion.

    Width as 2 x area / perimeter, which is the width of the strip a face would
    be if it were one — the right question for the long slivers a chamfer
    leaves when it very nearly runs out of room. The slicer either drops these
    or prints them as a lone wandering bead, and neither is what was drawn.
    """
    lim = scene.limits
    slivers = []
    for face in scene.part.faces():
        try:
            perimeter = face.outer_wire().length
        except Exception:
            continue
        # Below this a face is kernel dust — a seam, a degenerate patch at a
        # pole — not a feature anyone drew. A sliver worth reporting is a long
        # thin strip, so it is narrow *and* has area: the near-zero-width faces
        # a thread or an imported mesh is full of are neither drawn nor a
        # problem, and reporting three thousand of them buries the one chamfer
        # that really did run out of room.
        if perimeter <= 0 or face.area < lim.sliver_mm2:
            continue
        width = 2 * face.area / perimeter
        if width < lim.face_width:
            slivers.append((width, face))
    if not slivers:
        return []

    # A part rebuilt from an imported mesh is thousands of triangles, and a
    # good share of any triangulation is narrow. Counting them is arithmetic,
    # not a finding, and it would bury the one real sliver on a modelled part.
    faces = len(scene.part.faces())
    if faces and len(slivers) > 0.25 * faces:
        return [
            Finding(
                "thin_face",
                "warn",
                f"{len(slivers)} of {faces} faces are narrower than one "
                f"{lim.face_width:.2f} mm extrusion — this part is a triangulated "
                f"mesh, so the rule has nothing to say about it",
                None,
            )
        ]

    slivers.sort(key=lambda w: w[0])
    width, face = slivers[0]
    centre = face.center()
    return [
        Finding(
            "thin_face",
            "warn",
            f"{len(slivers)} face(s) narrower than one {lim.face_width:.2f} mm "
            f"extrusion; the narrowest is {width:.3f} mm wide",
            width,
            (centre.X, centre.Y, centre.Z),
        )
    ]


def thin_pin(scene) -> list[Finding]:
    """An upright post too slender to survive being printed, or being used.

    A vertical pin is a stack of tiny layers with almost no bonded area between
    them, so it snaps at a layer line under a load the same plastic would shrug
    off lying down. Thicken it, lie it down, or use a metal one.
    """
    from build123d import GeomType

    lim = scene.limits
    found = []
    for face in scene.part.faces().filter_by(GeomType.CYLINDER):
        # A trimmed or seam face can have neither a radius nor an axis to give.
        if face.radius is None or face.axis_of_rotation is None:
            continue
        radius = float(face.radius)
        if radius * 2 >= lim.pin_dia:
            continue
        axis = face.axis_of_rotation
        if abs(axis.direction.Z) < 0.9:  # not upright; a different problem
            continue

        # Convex means material inside the cylinder — a pin. Concave is a hole,
        # which has its own rules and none of them are this one.
        centre = face.center()
        offset = centre - axis.position
        radial = offset - axis.direction * offset.dot(axis.direction)
        if radial.length < 1e-9 or face.normal_at(centre).dot(radial.normalized()) < 0:
            continue

        box = face.bounding_box()
        height = box.size.Z
        if height <= 2 * radius * 2:
            continue
        found.append((radius, height, centre))

    if not found:
        return []
    radius, height, centre = min(found, key=lambda f: f[0])
    return [
        Finding(
            "thin_pin",
            "warn",
            f"upright pin {radius * 2:.1f} mm across and {height:.1f} mm tall "
            f"({len(found)} like it); it will break at a layer line",
            radius * 2,
            (centre.X, centre.Y, centre.Z),
        )
    ]


def _hull_corners(hull, window: float):
    """Turn accumulated within `window` of each footprint vertex, in degrees.

    A tessellated arc is a run of shallow turns and a real corner is one sharp
    one, so measuring the turn between the chords reaching a fixed distance
    either side tells them apart. A vertex-by-vertex angle cannot: on a circle
    approximated by a hundred segments, every vertex looks nearly straight.
    """
    import numpy as np

    n = len(hull)
    if n < 3:
        return np.zeros(0), np.zeros((0, 2))

    step = np.linalg.norm(np.roll(hull, -1, axis=0) - hull, axis=1)
    if step.sum() < 4 * window:  # too small for the window to mean anything
        return np.zeros(0), np.zeros((0, 2))

    def walk(i, direction):
        travelled = 0.0
        j = i
        for _ in range(n):
            k = (j - 1) % n if direction < 0 else j
            travelled += step[k]
            j = (j + direction) % n
            if travelled >= window:
                break
        return j

    turns = np.zeros(n)
    for i in range(n):
        back = hull[i] - hull[walk(i, -1)]
        fwd = hull[walk(i, +1)] - hull[i]
        nb, nf = np.linalg.norm(back), np.linalg.norm(fwd)
        if nb < 1e-9 or nf < 1e-9:
            continue
        cos = float(np.clip(np.dot(back / nb, fwd / nf), -1.0, 1.0))
        turns[i] = np.degrees(np.arccos(cos))
    return turns, hull


def warp_risk(scene) -> list[Finding]:
    """A sharp corner on a large flat footprint, in a material that lifts.

    Shrinkage pulls a cooling first layer toward its own centre, and a corner
    is where that pull has the least plastic to fight. Rounding it spreads the
    same force along an arc. The area threshold scales with the material,
    because the same footprint that is a certainty in ASA is a non-event in PLA.
    """
    import numpy as np
    from scipy.spatial import ConvexHull

    hull = scene.footprint
    if hull is None:
        return []

    lim = scene.limits
    warp = scene.material.warp if scene.material is not None else 0.5
    if warp <= 0.01:
        return []
    area = float(ConvexHull(hull).volume)  # 2D hull "volume" is its area
    if area * warp < lim.footprint_mm2:
        return []

    turns, pts = _hull_corners(hull, lim.corner_window_mm)
    if len(turns) == 0 or turns.max() < lim.corner_deg:
        return []

    worst = int(np.argmax(turns))
    material = scene.material.name if scene.material is not None else "this material"
    return [
        Finding(
            "warp_risk",
            "warn",
            f"{area / 100:.0f} cm2 flat footprint in {material} with a "
            f"{turns[worst]:.0f}-degree corner; round it to about "
            f"{2 * lim.corner_window_mm:.0f} mm so the first layer has nowhere to peel "
            f"from",
            float(turns[worst]),
            (float(pts[worst][0]), float(pts[worst][1]), scene.z_min),
        )
    ]


def stability(scene) -> list[Finding]:
    """A part whose centre of mass sits near, or past, the edge of its base.

    Two different failures, one measurement. Past the edge and it falls over on
    the plate before it is finished; near the edge and it prints, then topples
    the first time it is used for whatever it was made for.
    """
    import numpy as np
    from build123d import CenterOf

    hull = scene.footprint
    if hull is None or len(hull) < 3:
        return []

    com = scene.part.center(CenterOf.MASS)
    p = np.array([com.X, com.Y])
    edges = np.roll(hull, -1, axis=0) - hull

    # Signed area of each triangle (hull edge, com). A counter-clockwise hull
    # has them all positive when the point is inside.
    cross = edges[:, 0] * (p[1] - hull[:, 1]) - edges[:, 1] * (p[0] - hull[:, 0])
    inside = bool((cross >= 0).all())

    t = np.clip(((p - hull) * edges).sum(1) / (edges**2).sum(1), 0.0, 1.0)
    clearance = float(np.linalg.norm(hull + t[:, None] * edges - p, axis=1).min())
    height = float(com.Z - scene.z_min)

    if not inside:
        return [
            Finding(
                "stability",
                "fail",
                f"the centre of mass is {clearance:.0f} mm outside the footprint; "
                f"the part tips over on the plate",
                clearance,
                (float(p[0]), float(p[1]), float(com.Z)),
            )
        ]

    if clearance < 1e-6:
        return []
    leverage = height / clearance
    if leverage < scene.limits.leverage:
        return []
    return [
        Finding(
            "stability",
            "warn",
            f"centre of mass {height:.0f} mm up with only {clearance:.1f} mm of "
            f"footprint outside it (leverage {leverage:.0f}:1)",
            leverage,
            (float(p[0]), float(p[1]), float(com.Z)),
        )
    ]


_IMPLEMENTATIONS = {
    "unsupported": unsupported,
    "thin_wall": thin_wall,
    "overhang": overhang,
    "bed_overhang": bed_overhang,
    "thin_face": thin_face,
    "thin_pin": thin_pin,
    "warp_risk": warp_risk,
    "stability": stability,
}

# The rules that need no ray casting and no sampling. `mise build` runs these,
# so the report gains something without the rebuild loop gaining a second; the
# rest wait for `mise check`, which is the command you run when you are about
# to spend an evening and 200 grams on the result.
CHEAP = ("bed_overhang", "thin_face", "thin_pin", "warp_risk", "stability")


@dataclass(frozen=True)
class Report:
    findings: list[Finding] = field(default_factory=list)

    @property
    def failures(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "fail"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "warn"]

    @property
    def allowed(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "allowed"]

    def __bool__(self) -> bool:
        return bool(self.failures or self.warnings)


def validate_allow(allow) -> dict[str, str]:
    """A model's ALLOW dict, or a message saying what is wrong with it."""
    allow = allow or {}
    if not isinstance(allow, dict):
        raise TypeError("ALLOW must be a dict of rule name -> reason")
    unknown = sorted(set(allow) - set(RULES))
    if unknown:
        raise ValueError(
            f"ALLOW names no such rule: {', '.join(unknown)} — "
            f"known rules are {', '.join(RULES)}"
        )
    blank = sorted(k for k, v in allow.items() if not str(v).strip())
    if blank:
        raise ValueError(
            f"ALLOW needs a reason, not just a rule name: {', '.join(blank)} — "
            "the reason is the only record of whether the exception was thought about"
        )
    return {k: str(v).strip() for k, v in allow.items()}


def inspect_part(
    part,
    material=None,
    allow=None,
    limits: Limits | None = None,
    rules=RULES,
) -> Report:
    """Run the rules over a built part.

    A rule that raises is reported as a finding rather than propagating. These
    are advisory, and a part that defeats one rule's geometry assumptions
    should still get the other eight.
    """
    allow = validate_allow(allow)
    scene = Scene(part, material=material, limits=limits)

    findings: list[Finding] = []
    for name in RULES:
        if name not in rules:
            continue
        try:
            produced = _IMPLEMENTATIONS[name](scene)
        except Exception as exc:  # noqa: BLE001 - advisory, never fatal
            findings.append(
                Finding(name, "warn", f"rule could not run: {type(exc).__name__}: {exc}")
            )
            continue
        for finding in produced:
            if name in allow:
                finding = replace(finding, severity="allowed", reason=allow[name])
            findings.append(finding)

    order = {"fail": 0, "warn": 1, "allowed": 2}
    findings.sort(key=lambda f: (order[f.severity], RULES.index(f.rule)))
    return Report(findings)
