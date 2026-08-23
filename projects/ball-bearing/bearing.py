"""Parametric print-in-place bearing — 6000, dumbbell elements.

A translation of an OpenSCAD/BOSL2 generator into build123d, with the bugs
taken out. The shape is the same one the original was reaching for: two races
split out of the radial gap, a ring of rolling elements captured between them,
and everything printed in one go with a clearance gap instead of an assembly
step.

Proportions, all derived from the trade size and nothing else:

    wall   = (od - bore) / 6      the radial gap divided three ways —
                                  inner race, rolling element, outer race
    mid_r  = (bore + od) / 4      the pitch circle, halfway across
    element_d = 2 * wall * f      f = 1.0 ball, 0.95 roller, 0.75 dumbbell

`roller.py` and `flanged.py` are the same generator at other settings.

    mise build ball-bearing

## What was wrong with the original

Roughly in order of how much each one costs:

1.  **`id`, `od`, `width`, `flange`, `fd`, `fw` were each both a parameter and
    a local.** OpenSCAD resolves every reference in a scope to the *last*
    assignment of that name, so `info = is_undef(trade_size) ? [id, od, ...]`
    read the `id = info[0]` written below it — a recursive declaration. The
    custom-size path could not produce a part at all. Nothing here shadows: a
    trade size resolves to a `Size`, and overrides are separate arguments that
    refuse to be given alongside one.

2.  **The ball skirt was cut once, not once per ball.** The support ring under
    the balls has a single notch where it needs `count` of them — there is no
    `for` around that cut. It stays a continuous ring, welded to every ball
    (it is deliberately grown 0.12 mm into them), and the bearing comes off the
    plate as one solid lump that cannot turn.

3.  **`clearance` was a radial widening, not a gap.** `ball_shape()` grew the
    roller and dumbbell profiles in X and left Y alone, so every face that is
    not square to the radius got less than the number asked for. The 45 degree
    flanks that do the axial retention on both shapes — the roller's shoulders,
    both walls of the dumbbell's groove — come out at `clearance * cos 45`:
    0.106 mm of a requested 0.15, measured. That is the wrong side of what a
    0.4 mm nozzle will bridge, and the dumbbell was the default. Here the
    pocket is the element's own profile put through a 2D `offset()`, which
    moves every face by the same amount because it cannot do anything else.

4.  **Elements were counted along the arc, not the chord.** `floor(PI * mid_d *
    (1 - spacing) / ball_d)` measures centre-to-centre the long way round the
    pitch circle; the straight line between two elements is shorter. Wherever
    the arc count lands just above an integer the elements overlap — 26 of the
    255 trade size and element combinations do, at `spacing = 0`, which is the
    setting documented as "touching". The worst is a 635's balls, by 1.6%.

5.  **A missing trade size indexed the table with an empty list.** `search()`
    answers "not found" with `[]`, and `data[[]]` is not an error message.
    `_sizes.lookup()` raises one.

6.  **`chamfer` was unbounded.** No standard size trips it — the thinnest race
    in the table is 1.06 mm and the narrowest bearing 3.97 mm wide, both of
    which swallow the 0.6 default — but nothing stopped the custom path asking
    for a chamfer bigger than the race it cuts. Clamped here to what the
    section can give up.

"""

from __future__ import annotations

import math
from dataclasses import dataclass

import _sizes
from build123d import (
    Axis,
    Box,
    Circle,
    Cylinder,
    Kind,
    Part,
    Plane,
    Polygon,
    Pos,
    Rot,
    Sphere,
    mirror,
    offset,
    revolve,
)

from cadkit import fits_bed
from cadkit.materials import PETG
from cadkit.printer import MIN_WALL, NOZZLE_D

MATERIAL = PETG

# ---- decided ---------------------------------------------------------------
# Element diameter as a fraction of the raceway gap (2 * wall). A ball fills it
# exactly; a roller is pulled in slightly so its retaining shoulder has
# somewhere to go; a dumbbell is smaller again because its races are thickened
# to carry the rib that holds it in.
ELEMENT_FRACTION = {"ball": 1.0, "roller": 0.95, "dumbbell": 0.75}

# Dumbbell races grow inwards by a quarter wall each, which is where the
# retaining rib comes from.
DUMBBELL_RACE = 1.25

# How far the sacrificial skirt is grown into the underside of a ball. A ball
# has nothing under it to print onto, so the skirt is fused rather than left
# with a gap — it is snapped off, not slid off. One extrusion's worth: enough
# to bond, little enough to break by hand.
SKIRT_BITE = 0.12

# Rolling elements are placed by the chord between their centres, not by arc
# length, so `spacing` means what it says: the gap between two elements as a
# fraction of their diameter, 0 being touching.
DEFAULT_SPACING = 0.05

# Gap between an element and its raceway, on every face. 0.15 is two thirds of
# a 0.4 mm nozzle's line width — below about 0.1 the two weld on the first
# print, above about 0.25 the bearing rattles.
DEFAULT_CLEARANCE = 0.15

DEFAULT_CHAMFER = 0.6

# The smallest gap worth asking a 0.4 mm nozzle for. Below this the two faces
# are nearer to each other than the machine's own positioning error, and
# whether the bearing turns is decided by the print rather than by the model.
# A decision rather than a law, and the conservative end of it — lower it if a
# test print says the machine can hold a finer gap open.
MIN_CLEARANCE = 0.10

# Tolerance for measuring the built part back. Loose next to OCCT's own
# precision, tight next to anything a 0.4 mm nozzle can express.
TOL = 1e-3


@dataclass(frozen=True)
class Bearing:
    """Every dimension of one bearing, measured or derived, in one place.

    `build()` draws from this and `check()` measures back against it, so there
    is no second copy of the arithmetic to drift.
    """

    # ---- as ordered --------------------------------------------------------
    bore: float
    od: float
    width: float
    element: str = "dumbbell"
    flange: bool = False
    flange_d: float = 0.0
    flange_w: float = 0.0
    spacing: float = DEFAULT_SPACING
    clearance: float = DEFAULT_CLEARANCE
    chamfer: float = DEFAULT_CHAMFER
    name: str = "custom"

    @classmethod
    def of(cls, trade_size: str | None = None, **overrides) -> Bearing:
        """A bearing by trade size, or by explicit dimensions.

        The trade size supplies bore / od / width / flange and nothing else;
        element type, clearance and the rest stay as given. Passing both is an
        error rather than a silent precedence rule — that ambiguity is what the
        original's shadowed parameters turned into a recursive declaration.
        """
        if trade_size is None:
            return cls(**overrides)

        clash = {"bore", "od", "width", "flange", "flange_d", "flange_w"} & set(overrides)
        if clash:
            raise ValueError(
                f"{trade_size} already fixes {', '.join(sorted(clash))}; "
                "pass a trade size or explicit dimensions, not both"
            )
        size = _sizes.lookup(trade_size)
        return cls(
            bore=size.bore,
            od=size.od,
            width=size.width,
            flange=size.flange,
            flange_d=size.flange_d,
            flange_w=size.flange_w,
            name=size.name,
            **overrides,
        )

    # ---- derived -----------------------------------------------------------
    @property
    def wall(self) -> float:
        """One third of the radial gap: inner race, element, outer race."""
        return (self.od - self.bore) / 6

    @property
    def mid_r(self) -> float:
        """Pitch radius — the circle the element centres run on."""
        return (self.bore + self.od) / 4

    @property
    def race_t(self) -> float:
        """Radial thickness of each race before the groove is cut."""
        return self.wall * (DUMBBELL_RACE if self.element == "dumbbell" else 1.0)

    @property
    def element_d(self) -> float:
        return 2 * self.wall * ELEMENT_FRACTION[self.element]

    @property
    def count(self) -> int:
        """How many elements fit round the pitch circle.

        By the chord between adjacent centres, `2 * mid_r * sin(pi / n)`, not
        by arc length. The arc is always longer, so counting with it packs the
        elements closer than asked and, at `spacing = 0`, into each other.
        """
        pitch = self.element_d * (1 + self.spacing)
        return math.floor(math.pi / math.asin(min(1.0, pitch / (2 * self.mid_r))))

    @property
    def edge_chamfer(self) -> float:
        """`chamfer`, clamped to what the sections it cuts can actually give up.

        A chamfer bigger than the race is thick removes the race; one bigger
        than half the width removes the part. BOSL2 threw on the first and the
        original never bounded it, which is why a 0.6 default and an R2 could
        not be asked for together.
        """
        cap = 0.4 * min(self.race_t, self.width / 2)
        if self.flange:
            cap = min(cap, 0.4 * min((self.flange_d - self.od) / 2, self.flange_w))
        return min(self.chamfer, cap)

    @property
    def race_min(self) -> float:
        """Thinnest section of either race: what is left under the raceway.

        Both races come out the same here — the pocket is cut from the middle
        of the gap and reaches `element_d / 2 + clearance` each way — so one
        number covers them. This is the section that fails in service, and on
        the small trade sizes it is the reason a bearing cannot be printed at
        all: there is only so much material in `(od - bore) / 2` to divide
        three ways.
        """
        return 1.5 * self.wall - self.element_d / 2 - self.clearance

    @property
    def face_lip(self) -> float:
        """Race material above and below the raceway, at the bearing's faces.

        What holds a ball in axially. Rollers and dumbbells run out to the
        faces on purpose and are retained by a shoulder or a rib instead, so
        this only means anything for balls.
        """
        return self.width / 2 - (self.element_d / 2 + self.clearance)

    @property
    def skirt_h(self) -> float:
        """Plate to the underside of a ball, plus the bite that fuses them."""
        return (self.width - self.element_d) / 2 + SKIRT_BITE

    def validate(self) -> None:
        """Everything that has to hold before any geometry is drawn.

        Not a `check()` — these are preconditions on the numbers, and a
        violated one produces geometry that is nonsense rather than merely
        wrong, so it is worth refusing before OCCT is asked to do the boolean.
        """
        if self.element not in ELEMENT_FRACTION:
            raise ValueError(
                f"unknown element {self.element!r}; "
                f"one of {', '.join(sorted(ELEMENT_FRACTION))}"
            )
        if not 0 <= self.spacing <= 0.5:
            raise ValueError(f"spacing {self.spacing} is outside 0 to 0.5")
        if self.clearance < MIN_CLEARANCE:
            raise ValueError(
                f"clearance {self.clearance} is under {MIN_CLEARANCE} mm, which "
                f"a {NOZZLE_D} mm nozzle cannot be relied on to leave open — the "
                "element and its raceway will weld somewhere round the circle"
            )
        if self.clearance >= self.wall / 2:
            raise ValueError(
                f"clearance {self.clearance} is more than half a race wall "
                f"({self.wall / 2:.2f} mm); the raceway would cut clean through"
            )
        if self.flange and not (
            self.flange_d > self.od and 0 < self.flange_w < self.width
        ):
            raise ValueError(
                f"flange {self.flange_d} x {self.flange_w} does not sit on a "
                f"{self.od} x {self.width} bearing"
            )
        # The two that rule out whole trade sizes, and the reason this is a
        # `validate()` and not just a `check()`: they are arithmetic, they are
        # what someone gets wrong by asking for a small bearing, and finding
        # out from a boolean ten seconds later is a worse answer than finding
        # out from the numbers now.
        if self.race_min < MIN_WALL:
            hint = (
                ""
                if self.element == "dumbbell"
                else " — try element='dumbbell', whose races are the thickened ones"
            )
            raise ValueError(
                f"{self.name} in {self.element}s leaves {self.race_min:.2f} mm "
                f"of race under the raceway, under the {MIN_WALL:.2f} mm "
                f"two-perimeter floor. {self.od - self.bore:.2f} mm of radial gap "
                f"does not divide three ways at {self.clearance} mm clearance"
                f"{hint}"
            )
        if self.element == "ball" and self.face_lip < MIN_WALL:
            raise ValueError(
                f"{self.name}'s raceway would leave {self.face_lip:.2f} mm of "
                f"race at each face, under the {MIN_WALL:.2f} mm floor — nothing "
                f"holds the balls in. {self.width:.2f} mm is too narrow for a "
                f"{self.element_d:.2f} mm ball; try element='dumbbell' or 'roller', "
                "which are retained by a rib rather than by the groove's shoulders"
            )
        if self.count < 3:
            raise ValueError(
                f"only {self.count} elements fit at spacing {self.spacing}; "
                "three is the fewest that can hold the races concentric"
            )
        # One inequality, three reasons: a ball wider than the bearing sticks
        # out of both faces, a roller's two end chamfers meet and swallow its
        # body, and a dumbbell's waist runs off the end of its own rim.
        if self.element_d >= self.width:
            raise ValueError(
                f"a {self.element_d:.2f} mm {self.element} does not fit in a "
                f"{self.width:.2f} mm wide bearing — the radial gap is too big "
                "for the width, which is not a bearing this generator can draw"
            )


# ---- profiles --------------------------------------------------------------
# Everything below is drawn in the half-plane as (radius, height) and revolved
# about Z. Sketch X is radius, sketch Y is the bearing axis, and `Plane.XZ *`
# stands the drawing up before `revolve` spins it.


def _revolved(points) -> Part:
    """Spin a (radius, height) polygon about the bearing axis."""
    return revolve(Plane.XZ * Polygon(*points, align=None), Axis.Z)


def _element_half(b: Bearing) -> list[tuple[float, float]]:
    """The rolling element's own profile, axis to rim, bottom to top.

    Returned as the right half so the same points serve twice: revolved on
    their own they are the element, mirrored and moved out to `mid_r` they are
    the pocket it turns in.
    """
    r = b.element_d / 2
    half_w = b.width / 2

    if b.element == "roller":
        # A cylinder with both ends chamfered back to a narrower stub. The
        # chamfer is the shoulder the raceway grips; the stub carries on to the
        # bearing's faces so the race never has to bridge over the roller.
        cut = b.element_d / 4  # 45 degrees, so the stub is `cut` long too
        stub = r - cut
        body = half_w - cut
        return [
            (0, -half_w),
            (stub, -half_w),
            (stub, -body),
            (r, -body + cut),
            (r, body - cut),
            (stub, body),
            (stub, half_w),
            (0, half_w),
        ]

    if b.element == "dumbbell":
        # Full width, with a V cut round its waist. The race fills that V with
        # a matching rib, which is what stops the dumbbell walking out
        # sideways. Both flanks are at 45 degrees so neither the groove's roof
        # nor the rib's underside needs support.
        depth = b.element_d / 4
        mouth = 5 * b.element_d / 12  # half-height where the V meets the rim
        floor = b.element_d / 6  # half-height at the bottom of the V
        return [
            (0, -half_w),
            (r, -half_w),
            (r, -mouth),
            (r - depth, -floor),
            (r - depth, floor),
            (r, mouth),
            (r, half_w),
            (0, half_w),
        ]

    raise AssertionError(f"{b.element} has no swept profile")  # balls are spheres


def _pocket(b: Bearing) -> Part:
    """The volume taken out of both races so an element can turn in them.

    The element's own profile grown by `clearance` — through `offset()`, which
    moves every face by the same amount and so cannot repeat the original's
    mistake of growing the profile in one direction and short-changing every
    face that is not square to it.
    """
    if b.element == "ball":
        grown = Circle(b.element_d / 2 + b.clearance)
    else:
        half = Polygon(*_element_half(b), align=None)
        whole = half + mirror(half, about=Plane.YZ)
        grown = offset(whole, b.clearance, kind=Kind.INTERSECTION)

    return revolve(Plane.XZ * Pos(b.mid_r, 0) * grown, Axis.Z)


def _inner_race(b: Bearing) -> Part:
    """Bore to raceway, chamfered where it meets the bore at both faces."""
    r0, r1 = b.bore / 2, b.bore / 2 + b.race_t
    z, c = b.width / 2, b.edge_chamfer
    return _revolved(
        [(r0 + c, -z), (r1, -z), (r1, z), (r0 + c, z), (r0, z - c), (r0, -z + c)]
    )


def _outer_race(b: Bearing) -> Part:
    """Raceway to rim, with the flange drawn as part of the same profile.

    One L-shaped section rather than a ring stacked on a tube: a union of two
    solids meeting on a shared face is a boolean waiting to go wrong, and this
    way the flange cannot come out as its own body.
    """
    r0, r1 = b.od / 2 - b.race_t, b.od / 2
    z, c = b.width / 2, b.edge_chamfer

    if not b.flange:
        return _revolved(
            [(r0, -z), (r1 - c, -z), (r1, -z + c), (r1, z - c), (r1 - c, z), (r0, z)]
        )

    # Flanged: the bottom chamfer moves out to the flange's rim, because the
    # rim is now the edge that is exposed. The original suppressed the
    # chamfer there and left the flange sharp.
    fr = b.flange_d / 2
    return _revolved(
        [
            (r0, -z),
            (fr - c, -z),
            (fr, -z + c),
            (fr, -z + b.flange_w),
            (r1, -z + b.flange_w),
            (r1, z - c),
            (r1 - c, z),
            (r0, z),
        ]
    )


def _elements(b: Bearing) -> list[Part]:
    """One rolling element per station round the pitch circle."""
    one = Sphere(b.element_d / 2) if b.element == "ball" else _revolved(_element_half(b))
    one = Pos(b.mid_r, 0, 0) * one
    return [Rot(0, 0, i * 360 / b.count) * one for i in range(b.count)]


def _skirts(b: Bearing) -> list[Part]:
    """Breakaway supports under the balls. Balls only — nothing else needs them.

    A sphere has a single point touching the plate and 90 degrees of overhang
    above it, so each ball gets a stub of ring from the plate up into its
    underside. The ring is notched between every pair of balls — `count`
    notches, which is the one the original left as a single cut — so what comes
    off the plate is one skirt per ball, each snapped off by hand, rather than
    a continuous ring gluing the whole bearing together.
    """
    if b.element != "ball":
        return []

    ring = _revolved(
        [
            (b.mid_r - b.wall / 4, -b.width / 2),
            (b.mid_r + b.wall / 4, -b.width / 2),
            (b.mid_r + b.wall / 4, -b.width / 2 + b.skirt_h),
            (b.mid_r - b.wall / 4, -b.width / 2 + b.skirt_h),
        ]
    )

    # Wider than the ring is thick, so a notch severs it rather than grooving
    # it, and taller for the same reason at the top.
    notch = Box(b.wall, b.element_d / 2, b.skirt_h + 0.02)
    for i in range(b.count):
        angle = (i + 0.5) * 360 / b.count
        ring -= Rot(0, 0, angle) * Pos(b.mid_r, 0, -b.width / 2 + b.skirt_h / 2) * notch
    return [ring]


def solid(b: Bearing) -> Part:
    """The whole bearing: two races, `count` elements, skirts if it needs them."""
    b.validate()
    part = _inner_race(b) + _outer_race(b) - _pocket(b)
    for piece in _elements(b) + _skirts(b):
        part += piece
    return part


# ---- the model -------------------------------------------------------------
SPEC = Bearing.of("6000", element="dumbbell")


def build() -> Part:
    return solid(SPEC)


def check(part) -> None:
    check_bearing(part, SPEC)


def check_bearing(part, b: Bearing) -> None:
    """Measure the built bearing against the numbers it was drawn from.

    The assertions worth having are the ones about the gaps, because a bearing
    whose raceway is 0.15 mm wrong is a bearing-shaped lump and looks identical
    in a preview.
    """
    fits_bed(part)

    # Two races and `count` elements, each element carrying its own skirt where
    # there is one. Anything touching its neighbour fuses into it, so this
    # count is what a print-in-place part is really claiming: the original's
    # single skirt notch shows up here as one lump instead of thirteen.
    solids = part.solids()
    want = 2 + b.count
    assert len(solids) == want, (
        f"expected {want} free bodies (2 races + {b.count} {b.element}s), got "
        f"{len(solids)} — parts that should be separate are touching, or the "
        "raceway has cut a race in two"
    )

    inner, outer, elements = _bodies(part, b)

    # Envelope. The flange, when there is one, is the widest thing on the part.
    size = part.bounding_box().size
    across = b.flange_d if b.flange else b.od
    assert abs(size.X - across) < TOL and abs(size.Y - across) < TOL, (
        f"measures {size.X:.3f} x {size.Y:.3f} mm across, wanted {across:.3f}"
    )
    assert abs(size.Z - b.width) < TOL, (
        f"stands {size.Z:.3f} mm tall, wanted {b.width:.3f} — an element or a "
        "skirt is proud of the bearing's faces"
    )

    # The two gaps that decide whether it turns, as the shortest distance in
    # three dimensions between an element and each race — deliberately not a
    # radial measurement, because the original's roller and dumbbell measured
    # correct radially and came out at 0.106 mm across the 45 degree flanks
    # that actually hold them in.
    for what, race in (("inner", inner), ("outer", outer)):
        gap = elements[0].distance_to(race)
        assert abs(gap - b.clearance) < TOL, (
            f"{gap:.3f} mm between a {b.element} and the {what} race, wanted "
            f"{b.clearance:.3f} — "
            + ("they will fuse on the plate" if gap < b.clearance else "it will rattle")
        )

    # Two perimeters of material have to survive under each raceway, all the
    # way round and all the way along. `validate()` has already done this
    # arithmetic; this is the built solid agreeing with it.
    sleeve_h = b.width - 2 * b.edge_chamfer
    for what, race, r0, r1 in (
        ("inner", inner, b.bore / 2, b.bore / 2 + MIN_WALL),
        ("outer", outer, b.od / 2 - MIN_WALL, b.od / 2),
    ):
        eaten = _sleeve_eaten(race, r0, r1, sleeve_h)
        assert eaten < TOL, (
            f"the raceway takes {eaten:.3f} mm3 out of the {MIN_WALL:.2f} mm "
            f"sleeve under the {what} race, which should be untouched — the "
            f"race is {b.race_min:.2f} mm at its thinnest"
        )

    # Rotational symmetry: every element the same as every other. Catches a
    # placement that has walked one into a race and had material trimmed off it
    # by the boolean — which leaves the body count right and the bearing wrong.
    volumes = [s.volume for s in elements]
    assert max(volumes) - min(volumes) < 1e-6 * max(volumes), (
        f"the {b.count} {b.element}s differ in volume "
        f"({min(volumes):.4f} to {max(volumes):.4f} mm3)"
    )


def _bodies(part, b: Bearing):
    """The part's solids, told apart by where they sit rather than by index.

    A race is a body of revolution, so it is the one centred on the bearing
    axis; which race it is follows from whether it lies inside or outside the
    pitch circle. Everything else is a rolling element.
    """
    inner = outer = None
    elements = []
    for s in part.solids():
        box = s.bounding_box()
        if math.hypot(box.center().X, box.center().Y) > TOL:
            elements.append(s)
        elif box.max.X < b.mid_r:
            inner = s
        else:
            outer = s

    assert inner is not None and outer is not None and elements, (
        "could not find an inner race, an outer race and some elements — the "
        "part is not the shape this check was written for"
    )
    return inner, outer, elements


def _sleeve_eaten(race, r0: float, r1: float, height: float) -> float:
    """How much of a sleeve of material the raceway has cut into, mm3.

    Asks the question directly — does a wall this thick survive everywhere? —
    rather than measuring a thickness at one chosen height and trusting that
    height to be the worst. It is not: the obvious place to slice is the pitch
    plane, and on a dumbbell that is exactly where the retaining rib sits, so
    it reads the *thickest* section of the race. Slicing there passed an R2
    whose rim section was 0.64 mm against a 0.84 mm floor.

    `height` is trimmed by the end chamfers, which take some of this sleeve on
    purpose and are not the raceway's doing.
    """
    sleeve = Cylinder(r1, height) - Cylinder(r0, height)
    return (sleeve - race).volume


if __name__ == "__main__":
    from cadkit import cli

    raise SystemExit(cli(build, check))
