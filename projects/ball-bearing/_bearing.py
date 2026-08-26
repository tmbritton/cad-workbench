"""The bearing generator. A helper, not a model — the models are the thin files.

`bearing.py`, `roller.py` and `flanged.py` are each a dozen lines: a `Bearing`
saying which bearing to draw, and the model contract. Everything that draws one
is here, so a model file holds nothing but the settings you would want to
change, and changing one does not mean scrolling past six hundred lines of
geometry to find it.

    from _bearing import Bearing, check_bearing, solid

    SPEC = Bearing.of("6205", element="roller", clearance=0.2)

To see what you can ask for, run this file. It prints every trade size with the
element shapes that size will actually build, and with two arguments it says
why one is refused:

    python projects/ball-bearing/_bearing.py
    python projects/ball-bearing/_bearing.py R12 ball

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

import _pipe
import _sizes
import _threads
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
    Vertex,
    mirror,
    offset,
    revolve,
)

from cadkit import fits_bed
from cadkit.measure import measured
from cadkit.printer import LINE_W, MIN_WALL, NOZZLE_D

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
# test print says the machine can hold a finer gap open. Which is why it lives
# in measurements.toml marked provisional, with the two gaps it governs.
MIN_CLEARANCE = measured("clearance_floor")

# Tolerance for measuring the built part back. Loose next to OCCT's own
# precision, tight next to anything a 0.4 mm nozzle can express.
TOL = 1e-3


@dataclass(frozen=True)
class Plate:
    """A disc on the outer race — a bearing flange, or a lazy-susan top.

    The same feature at two scales. An F-series bearing's flange is a locating
    lip a millimetre or two proud of the OD; a turntable top is the same annulus
    at 100 mm with bolt holes in it. One shape, so there is one thing to get
    right rather than two.

    It is drawn as part of the outer race's own section, not stacked on it, so
    it cannot come off the printer as a loose collar. It sits at the end of the
    bearing that faces the build plate — which is what makes it printable at
    any diameter, with no overhang to support. Turn the finished part over and
    that face is the top.
    """

    diameter: float
    thickness: float = 3.0
    holes: int = 0
    hole_d: float = 4.5  # clearance for an M4
    hole_pcd: float | None = None  # None: midway between the OD and the rim

    def pcd(self, od: float) -> float:
        """Bolt circle diameter, defaulted to the middle of the annulus."""
        return self.hole_pcd if self.hole_pcd is not None else (od + self.diameter) / 2


@dataclass(frozen=True)
class Boss:
    """A tube on the inner race — a spigot, a threaded stud, or a tapped socket.

    Rises from the end of the bearing away from the build plate, so it prints
    as a vertical tube with nothing overhanging. Turn the part over in use and
    it is a flange hanging down from the inner ring, which is what it is for:
    the outer race and its plate turn, this stays put.

    `thread` is an ISO 261 designation — "M12", or "M12x1.5" for a fine pitch —
    or an NPT pipe size — "1 NPT" or "3/4 NPT" — for a stud that threads into a
    piece of threaded PVC; see `_pipe.py` for what that stands in for and why.
    `external` puts the thread on the outside, making a stud that screws into
    something; otherwise the bore is tapped and a bolt screws up into it. The
    form comes from `bd_warehouse`, drawn to ISO 68-1 (NPT threads too — cut
    straight, not to the true 1:16 taper; `_pipe.py` explains why).
    """

    length: float
    thread: str | None = None
    external: bool = False
    od: float | None = None  # None: flush with the inner race
    bore: float | None = None  # None: the bearing's own bore, carried through


@dataclass(frozen=True)
class Bearing:
    """Every dimension of one bearing, given or derived, in one place.

    `build()` draws from this and `check()` measures back against it, so there
    is no second copy of the arithmetic to drift.

    The three sizes are the envelope. `race_t`, `element_d` and `count` are the
    proportions inside it: leave them None and they come out as thirds of the
    radial gap, which is what a trade bearing looks like; set them and they are
    what you said. That split is the whole point of the class — a 100 mm
    turntable and a 6000 have the same envelope arithmetic and completely
    different proportions, and the original generator could only express one.
    """

    # ---- the envelope ------------------------------------------------------
    bore: float
    od: float
    width: float

    # ---- what runs between the races ---------------------------------------
    element: str = "dumbbell"

    # ---- proportions. None means "a third of the gap", the trade look -------
    race_t: float | None = None  # radial thickness of each race
    element_d: float | None = None  # rolling element diameter
    count: int | None = None  # how many of them

    # ---- print fit ---------------------------------------------------------
    spacing: float = DEFAULT_SPACING  # gap between elements, as a fraction of one
    clearance: float = DEFAULT_CLEARANCE  # gap on every face of every element
    chamfer: float = DEFAULT_CHAMFER  # break on the bore and rim edges
    bore_fit: float = 0.0  # opens the bore without moving the proportions
    od_fit: float = 0.0  # takes the OD in, likewise

    # ---- what hangs off it -------------------------------------------------
    plate: Plate | None = None  # on the outer race
    boss: Boss | None = None  # on the inner race

    name: str = "custom"

    def __post_init__(self) -> None:
        """Fill in whichever proportions were left to the generator.

        Resolved once, here, rather than on every access: downstream code and
        `check()` both want a number, and neither should have to know or care
        which of them was asked for and which was worked out.
        """
        if self.element not in ELEMENT_FRACTION:
            raise ValueError(
                f"unknown element {self.element!r}; "
                f"one of {', '.join(sorted(ELEMENT_FRACTION))}"
            )
        set_ = object.__setattr__  # frozen, and this is the one place it moves
        if self.race_t is None:
            thicken = DUMBBELL_RACE if self.element == "dumbbell" else 1.0
            set_(self, "race_t", self.wall * thicken)
        if self.element_d is None:
            set_(self, "element_d", 2 * self.wall * ELEMENT_FRACTION[self.element])
        if self.count is None:
            set_(self, "count", self.fits_round)

    @classmethod
    def of(cls, trade_size: str | None = None, **overrides) -> Bearing:
        """A bearing by trade size, or by explicit dimensions.

        The trade size supplies bore / od / width and, on an F-series, its
        flange; everything else stays as given. Passing both is an error rather
        than a silent precedence rule — that ambiguity is what the original's
        shadowed parameters turned into a recursive declaration.
        """
        if trade_size is None:
            return cls(**overrides)

        clash = {"bore", "od", "width"} & set(overrides)
        if clash:
            raise ValueError(
                f"{trade_size} already fixes {', '.join(sorted(clash))}; "
                "pass a trade size or explicit dimensions, not both"
            )
        size = _sizes.lookup(trade_size)
        if size.flange and "plate" not in overrides:
            overrides["plate"] = Plate(size.flange_d, size.flange_w)
        return cls(
            bore=size.bore,
            od=size.od,
            width=size.width,
            name=size.name,
            **overrides,
        )

    # ---- derived -----------------------------------------------------------
    @property
    def gap(self) -> float:
        """Radial space between the bore and the OD, for everything to fit in."""
        return (self.od - self.bore) / 2

    @property
    def wall(self) -> float:
        """A third of the gap — the proportion a trade bearing comes out at."""
        return self.gap / 3

    @property
    def mid_r(self) -> float:
        """Pitch radius: the circle the element centres run on, midway across.

        Independent of `race_t` — the races grow inwards from the bore and the
        OD, so the middle of what is left stays in the middle.
        """
        return (self.bore + self.od) / 4

    @property
    def bore_drawn(self) -> float:
        """The hole actually cut, once `bore_fit` has opened it up."""
        return self.bore + self.bore_fit

    @property
    def od_drawn(self) -> float:
        """The outside actually cut, once `od_fit` has taken it in."""
        return self.od - self.od_fit

    @property
    def fits_round(self) -> int:
        """How many elements fit on the pitch circle at this spacing.

        By the chord between adjacent centres, `2 * mid_r * sin(pi / n)`, not
        by arc length. The arc is always longer, so counting with it packs the
        elements closer than asked and, at `spacing = 0`, into each other.
        """
        pitch = self.element_d * (1 + self.spacing)
        return math.floor(math.pi / math.asin(min(1.0, pitch / (2 * self.mid_r))))

    @property
    def groove_depth(self) -> float:
        """How far the raceway cuts into each race.

        Zero or less means the elements are not gripped at all: they sit in a
        slot wider than they are and the bearing is a rattle. This is the
        number that decoupling `race_t` from `element_d` puts in the user's
        hands, so it is the number that has to be checked.
        """
        return (self.bore / 2 + self.race_t) - (
            self.mid_r - self.element_d / 2 - self.clearance
        )

    @property
    def edge_chamfer(self) -> float:
        """`chamfer`, clamped to what the sections it cuts can actually give up.

        A chamfer bigger than the race is thick removes the race; one bigger
        than half the width removes the part. BOSL2 threw on the first and the
        original never bounded it, which is why a 0.6 default and an R2 could
        not be asked for together.
        """
        cap = 0.4 * min(self.race_t, self.width / 2)
        if self.plate is not None:
            cap = min(
                cap, 0.4 * min((self.plate.diameter - self.od) / 2, self.plate.thickness)
            )
        return min(self.chamfer, cap)

    @property
    def race_min(self) -> float:
        """Thinnest section of either race: what is left under the raceway.

        Each race runs from the surface the world sees to wherever the raceway
        stops it, so the fits count against it: opening the bore takes the
        material out of the inner race, not out of the gap. Whichever race is
        thinner is the one that fails, so this reports that one.
        """
        floor = self.mid_r - self.element_d / 2 - self.clearance
        crest = self.mid_r + self.element_d / 2 + self.clearance
        inner = min(self.bore / 2 + self.race_t, floor) - self.bore_drawn / 2
        outer = self.od_drawn / 2 - max(self.od / 2 - self.race_t, crest)
        return min(inner, outer)

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

    @property
    def inner_race_od(self) -> float:
        """Outside of the inner race *at its end face* — the widest a boss may be.

        Not `bore + 2 * race_t`. A roller and a dumbbell are drawn to the full
        width, so their raceway is cut right out to both faces and the inner
        race is narrower there than it is at the pitch plane. A boss sized to
        the mid-width thickness overhangs the rolling elements' end faces, and
        a fuse does not care that the overlap is a sliver: it welds the boss to
        every element and the whole bearing comes out as one lump.

        A ball's raceway closes before it reaches the faces — that is the
        face-lip rule — so there the full thickness is available.
        """
        at_face = self.bore / 2 + self.race_t
        if self.element != "ball":
            at_face = min(at_face, self.mid_r - self.element_d / 2 - self.clearance)
        return 2 * at_face

    @property
    def boss_thread(self) -> _threads.Thread | _pipe.Pipe | None:
        """The boss's thread, or None for a plain one.

        Two families, told apart by shape: `"1 NPT"` goes to `_pipe.py`
        (checked first, since an NPT-shaped designation for an unlisted size
        should fail with *that* module's message, not `_threads.py`'s
        "not a metric thread" one), everything else to `_threads.py` against
        ISO 261. Both return an object with the same four attributes
        (`name`, `pitch`, `major_d`, `minor_d`) — nothing below this property
        cares which module built it.
        """
        if self.boss is None or self.boss.thread is None:
            return None
        if _pipe.is_pipe(self.boss.thread):
            return _pipe.parse(self.boss.thread)
        return _threads.parse(self.boss.thread)

    @property
    def boss_od(self) -> float:
        """Outside of the boss.

        An external thread fixes it: a stud's outside diameter *is* the
        thread's major diameter, which is the whole meaning of the
        designation. Otherwise it defaults flush with the inner race.
        """
        if self.boss.od is not None:
            return self.boss.od
        thread = self.boss_thread
        if thread is not None and self.boss.external:
            return thread.major_d
        return self.inner_race_od

    @property
    def boss_bore(self) -> float:
        """Bore of the boss.

        An internal thread fixes it the same way: the hole a thread is cut in
        is at its major diameter. Otherwise the bearing's bore carries through.
        """
        if self.boss.bore is not None:
            return self.boss.bore
        thread = self.boss_thread
        if thread is not None and not self.boss.external:
            return thread.major_d
        return self.bore_drawn

    def validate(self) -> None:
        """Everything that has to hold before any geometry is drawn.

        Not a `check()` — these are preconditions on the numbers, and a
        violated one produces geometry that is nonsense rather than merely
        wrong, so it is worth refusing before OCCT is asked to do the boolean.
        """
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
        if not 0 < self.bore_drawn < self.od_drawn:
            raise ValueError(
                f"a {self.bore_drawn:.2f} mm bore and a {self.od_drawn:.2f} mm "
                "outside do not describe a ring"
            )

        # Decoupling `race_t` and `element_d` hands over the one relationship
        # the locked proportions used to guarantee: that the raceway actually
        # cuts into both races. Without it the elements sit in a slot wider
        # than they are and the bearing is a rattle with no axial capture.
        if self.groove_depth < LINE_W:
            raise ValueError(
                f"the raceway cuts only {self.groove_depth:.2f} mm into each "
                f"race, under one {LINE_W:.2f} mm bead — a {self.element_d:.2f} mm "
                f"{self.element} does not fill the {self.gap - 2 * self.race_t:.2f} mm "
                "between races. Make the element bigger or the races thicker"
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
        if self.count > self.fits_round:
            raise ValueError(
                f"{self.count} {self.element}s will not go round a "
                f"{2 * self.mid_r:.2f} mm pitch circle at {self.element_d:.2f} mm "
                f"each; {self.fits_round} fit at spacing {self.spacing}"
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
        if self.plate is not None:
            self._validate_plate()
        if self.boss is not None:
            self._validate_boss()

    def _validate_plate(self) -> None:
        """The disc on the outer race, and the bolt holes through it."""
        plate = self.plate
        if plate.diameter <= self.od:
            raise ValueError(
                f"a {plate.diameter:.1f} mm plate does not clear a "
                f"{self.od:.1f} mm outside — it has nowhere to be"
            )
        if not 0 < plate.thickness < self.width:
            raise ValueError(
                f"a {plate.thickness:.1f} mm plate does not fit inside a "
                f"{self.width:.1f} mm bearing; it is drawn within the width, "
                "not added to it"
            )
        if plate.thickness < MIN_WALL:
            raise ValueError(
                f"a {plate.thickness:.2f} mm plate is under the "
                f"{MIN_WALL:.2f} mm two-perimeter floor"
            )
        if plate.holes:
            if plate.holes < 2:
                raise ValueError(f"{plate.holes} bolt hole is not a bolt circle")
            pcd = plate.pcd(self.od)
            inner = (pcd - plate.hole_d) / 2 - self.od / 2
            outer = plate.diameter / 2 - (pcd + plate.hole_d) / 2
            if min(inner, outer) < MIN_WALL:
                raise ValueError(
                    f"{plate.holes} x {plate.hole_d:.1f} mm holes on a "
                    f"{pcd:.1f} mm circle leave {min(inner, outer):.2f} mm of "
                    f"plate at the tightest edge, under the {MIN_WALL:.2f} mm "
                    f"floor — the annulus runs {self.od / 2:.1f} to "
                    f"{plate.diameter / 2:.1f} mm"
                )
            # Two holes are as close to each other as they are to an edge.
            step = math.pi * pcd / plate.holes - plate.hole_d
            if step < MIN_WALL:
                raise ValueError(
                    f"{plate.holes} holes on a {pcd:.1f} mm circle leave "
                    f"{step:.2f} mm between them, under the {MIN_WALL:.2f} mm floor"
                )

    def _validate_boss(self) -> None:
        """The tube on the inner race, and whatever thread is cut on it."""
        boss = self.boss
        if boss.length <= 0:
            raise ValueError(f"a {boss.length} mm boss is not a boss")
        od, bore = self.boss_od, self.boss_bore
        if od > self.inner_race_od + TOL:
            raise ValueError(
                f"a {od:.2f} mm boss overhangs the inner race, which is only "
                f"{self.inner_race_od:.2f} mm across at the face the boss "
                f"stands on — it would sit on the {self.element}s' end faces "
                "and fuse to every one of them. Thin the boss, or widen the "
                "race with race_t"
            )
        # Where the metal is thinnest, which is not where the boss is widest.
        # An external thread's root is a whole thread depth inside its major
        # diameter — on an M12 that is 10.11, not 12 — so measuring at the
        # crest overstates the wall by nearly half.
        thread = self.boss_thread
        root = thread.minor_d if (thread is not None and boss.external) else od
        wall = (root - bore) / 2
        if wall < MIN_WALL:
            where = "at the thread root" if root != od else ""
            raise ValueError(
                f"a {od:.2f} mm boss over a {bore:.2f} mm bore is {wall:.2f} mm "
                f"of wall{where}, under the {MIN_WALL:.2f} mm floor"
            )
        if boss.bore is not None and self.boss_thread is not None and not boss.external:
            raise ValueError(
                f"{boss.thread} tapped in the boss fixes its bore at "
                f"{self.boss_thread.major_d:g} mm; do not also set boss bore"
            )
        if boss.od is not None and self.boss_thread is not None and boss.external:
            raise ValueError(
                f"{boss.thread} cut on the boss fixes its outside at "
                f"{self.boss_thread.major_d:g} mm; do not also set boss od"
            )
        if bore >= self.inner_race_od or od <= self.bore_drawn:
            raise ValueError(
                f"a boss of {bore:.2f} to {od:.2f} mm does not overlap the "
                f"inner race, which runs {self.bore_drawn:.2f} to "
                f"{self.inner_race_od:.2f} mm — it would print in mid-air"
            )
        if boss.thread is not None and boss.length < 3 * self.boss_thread.pitch:
            raise ValueError(
                f"a {boss.length:.1f} mm boss holds under three turns of "
                f"{self.boss_thread.name} ({self.boss_thread.pitch:g} mm pitch); "
                "a thread shorter than that strips rather than holds"
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
    r0, r1 = b.bore_drawn / 2, b.bore / 2 + b.race_t
    z, c = b.width / 2, b.edge_chamfer
    return _revolved(
        [(r0 + c, -z), (r1, -z), (r1, z), (r0 + c, z), (r0, z - c), (r0, -z + c)]
    )


def _outer_race(b: Bearing) -> Part:
    """Raceway to rim, with the plate drawn as part of the same profile.

    One L-shaped section rather than a disc stacked on a tube: a union of two
    solids meeting on a shared face is a boolean waiting to go wrong, and this
    way the plate cannot come off the printer as a loose collar.

    The plate sits at the end facing the build plate, so it needs no support
    at any diameter — which is what lets the same feature be a 1.5 mm bearing
    flange and a 100 mm turntable top.
    """
    r0, r1 = b.od / 2 - b.race_t, b.od_drawn / 2
    z, c = b.width / 2, b.edge_chamfer

    if b.plate is None:
        return _revolved(
            [(r0, -z), (r1 - c, -z), (r1, -z + c), (r1, z - c), (r1 - c, z), (r0, z)]
        )

    # The bottom chamfer moves out to the plate's rim, because the rim is now
    # the edge that is exposed. The original suppressed the chamfer there and
    # left the flange sharp.
    plate = b.plate
    pr = plate.diameter / 2
    race = _revolved(
        [
            (r0, -z),
            (pr - c, -z),
            (pr, -z + c),
            (pr, -z + plate.thickness),
            (r1, -z + plate.thickness),
            (r1, z - c),
            (r1 - c, z),
            (r0, z),
        ]
    )

    if plate.holes:
        pcd = plate.pcd(b.od)
        hole = Cylinder(plate.hole_d / 2, plate.thickness + 1)
        for i in range(plate.holes):
            at = Rot(0, 0, i * 360 / plate.holes) * Pos(
                pcd / 2, 0, -z + plate.thickness / 2
            )
            race -= at * hole
    return race


def _boss(b: Bearing) -> Part:
    """The tube on the inner race, threaded or plain.

    Drawn rising from the face away from the build plate, so it is a vertical
    tube and prints with nothing overhanging — thread included, since a helix
    on a vertical cylinder never exceeds its own lead angle. In use the part is
    the other way up and this hangs below the inner ring.

    The thread form comes from `bd_warehouse`, to ISO 68-1. It is inset by a
    pitch at each end: partly because a real thread runs out before a shoulder,
    and partly because a thread whose end face is coincident with the tube's is
    a union OCCT sometimes returns as nothing at all.
    """
    from bd_warehouse.thread import IsoThread  # only when a boss asks for one

    boss = b.boss
    thread = b.boss_thread
    z0 = b.width / 2
    core_r, hole_r = b.boss_od / 2, b.boss_bore / 2

    form = None
    if thread is not None:
        run = boss.length - 2 * thread.pitch
        form = IsoThread(
            major_diameter=thread.major_d,
            pitch=thread.pitch,
            length=run,
            external=boss.external,
            end_finishes=("fade", "fade"),
        )
        # An external thread stands proud of its core, an internal one is cut
        # into the bore: either way the plain tube stops at the minor diameter
        # and the form supplies the rest.
        if boss.external:
            core_r = form.min_radius
        else:
            hole_r = thread.major_d / 2
        form = Pos(0, 0, z0 + thread.pitch) * form

    tube = Pos(0, 0, z0 + boss.length / 2) * (
        Cylinder(core_r, boss.length) - Cylinder(hole_r, boss.length)
    )
    return tube if form is None else tube + form


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
    if b.boss is not None:
        part += _boss(b)  # fuses into the inner race, which it stands on
    for piece in _elements(b) + _skirts(b):
        part += piece
    return part


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

    # Envelope. The plate, when there is one, is the widest thing on the part,
    # and the boss the tallest.
    size = part.bounding_box().size
    across = b.plate.diameter if b.plate is not None else b.od_drawn
    tall = b.width + (b.boss.length if b.boss is not None else 0.0)
    assert abs(size.X - across) < TOL and abs(size.Y - across) < TOL, (
        f"measures {size.X:.3f} x {size.Y:.3f} mm across, wanted {across:.3f}"
    )
    assert abs(size.Z - tall) < TOL, (
        f"stands {size.Z:.3f} mm tall, wanted {tall:.3f} — an element or a "
        "skirt is proud of the bearing's faces, or the boss is the wrong length"
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
        ("inner", inner, b.bore_drawn / 2, b.bore_drawn / 2 + MIN_WALL),
        ("outer", outer, b.od_drawn / 2 - MIN_WALL, b.od_drawn / 2),
    ):
        eaten = _sleeve_eaten(race, r0, r1, sleeve_h)
        assert eaten < TOL, (
            f"the raceway takes {eaten:.3f} mm3 out of the {MIN_WALL:.2f} mm "
            f"sleeve under the {what} race, which should be untouched — the "
            f"race is {b.race_min:.2f} mm at its thinnest"
        )

    # A thread has to be the thread it is named after, or the designation on
    # the model is a lie and the bolt that was bought for it does not fit.
    # Measured over one whole pitch, so the helix passes through every angle
    # and the extreme radius is certainly somewhere in the band.
    if b.boss is not None and b.boss_thread is not None:
        thread = b.boss_thread
        z = b.width / 2 + b.boss.length / 2
        band = part & Pos(0, 0, z) * Box(4 * b.od, 4 * b.od, thread.pitch)
        if b.boss.external:
            got, want, what = band.bounding_box().size.X, thread.major_d, "major"
        else:
            got, want, what = (
                2 * Vertex(0, 0, z).distance_to(band),
                thread.minor_d,
                "minor",
            )
        assert abs(got - want) < 0.05, (
            f"the boss measures {got:.3f} mm on its {what} diameter, but "
            f"{thread.name} is {want:.3f} — that is not a {thread.name}"
        )

    # Every bolt hole open all the way through. A hole that the plate profile
    # swallowed still leaves a plate that looks right from every angle.
    if b.plate is not None and b.plate.holes:
        pcd = b.plate.pcd(b.od)
        probe = Cylinder(b.plate.hole_d / 2 - TOL, 4 * b.plate.thickness)
        for i in range(b.plate.holes):
            at = Rot(0, 0, i * 360 / b.plate.holes) * Pos(
                pcd / 2, 0, -b.width / 2 + b.plate.thickness / 2
            )
            # An intersection that finds nothing comes back as None rather
            # than an empty solid, and nothing is exactly what an open hole
            # should contain.
            obstruction = outer & (at * probe)
            blocked = 0.0 if obstruction is None else obstruction.volume
            assert blocked < TOL, (
                f"bolt hole {i + 1} of {b.plate.holes} is obstructed by "
                f"{blocked:.2f} mm3 of plate"
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


def catalogue() -> str:
    """Every trade size against every element shape, and what each will build.

    The question you have before writing a model file, answered without
    building anything: `validate()` is arithmetic, so the whole table comes
    back instantly.
    """
    lines = []
    for size in _sizes.TABLE:
        cells, counts = [], []
        for kind in ELEMENT_FRACTION:
            b = Bearing.of(size.name, element=kind)
            try:
                b.validate()
            except ValueError:
                cells.append(f"{kind[:4]} --")
            else:
                cells.append(f"{kind[:4]} ok")
                counts.append(f"{b.count} {kind}s")
        flange = f"  flange {size.flange_d:g} x {size.flange_w:g}" if size.flange else ""
        lines.append(
            f"{size.name:9} {size.bore:5.1f} {size.od:5.1f} {size.width:4.1f}   "
            + "  ".join(cells)
            + f"   {', '.join(counts) or 'nothing this generator will print'}"
            + flange
        )
    return "\n".join(lines)


def why(trade_size: str, element: str) -> str:
    """Why one combination is refused, in the words `validate()` would use."""
    try:
        Bearing.of(trade_size, element=element).validate()
    except ValueError as refused:
        return str(refused)
    return f"{trade_size} in {element}s builds"


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 3:
        print(why(sys.argv[1], sys.argv[2]))
    else:
        print(f"{'size':9} {'bore':>5} {'od':>5} {'w':>4}")
        print(catalogue())
