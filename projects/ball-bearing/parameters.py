"""Every number you would want to change, for every part in this project.

One file. If you are adjusting a bearing, a turntable or a threaded boss, this
is the only place you need to open — the geometry that reads these lives in
`_bearing.py` and has nothing in it worth tuning.

Not a model: no `build()`, so `mise build` skips it and nothing is exported
from it. The six models each import their own spec from here and do nothing
else.

    mise dev   ball-bearing lazy_susan     # edit below, save, watch it redraw
    mise build ball-bearing                # all six

Anything unbuildable is refused from the numbers alone, before geometry, with a
message naming what to change. To see what the trade sizes will take:

    python projects/ball-bearing/_bearing.py            # every size
    python projects/ball-bearing/_bearing.py R12 ball   # why that one is refused

Each spec is a `Bearing`. The three envelope dimensions are required; leave
`race_t`, `element_d` and `count` out and they come out as thirds of the radial
gap, which is roughly what a trade bearing looks like. Full reference for every
field is in README.md, under "Every setting".
"""

from __future__ import annotations

from _bearing import Bearing, Boss, Plate

from cadkit.materials import PETG

# ============================================================================
# Shared — these apply to every part below
# ============================================================================

# PETG: tough, indifferent to a warm chamber, and it does not fuse across a
# small gap as readily as PLA. Every model reports its mass with this.
MATERIAL = PETG

# The gap on every face of every rolling element. The number to change first if
# a printed bearing comes out fused solid (raise it) or rattly (lower it).
# Under 0.10 is refused: a 0.4 mm nozzle cannot be relied on to leave it open.
CLEARANCE = 0.15

# Gap between neighbouring elements, as a fraction of one element. 0 is
# touching. Some slack keeps them from binding as the races flex.
SPACING = 0.05

# Break on the bore and rim edges. Clamped down automatically when a section is
# too thin to give this much up, so it is safe to leave alone.
CHAMFER = 0.6

# Printer fit. Holes come out undersize and outsides oversize by roughly a
# nozzle's worth; measure a printed bearing and put the error here. These move
# the drawn surfaces only — every proportion stays where the design put it.
BORE_FIT = 0.0  # added to the bore, so a shaft that was tight goes in
OD_FIT = 0.0  # taken off the outside, for a press fit into a housing

# Applied to every spec below, so one edit reaches all six parts.
_COMMON = dict(
    clearance=CLEARANCE,
    spacing=SPACING,
    chamfer=CHAMFER,
    bore_fit=BORE_FIT,
    od_fit=OD_FIT,
)


# ============================================================================
# bearing.py — the plain one, a 6000 in dumbbells
# ============================================================================
# The default part. A dumbbell is a cylinder with a 45 degree V round its
# waist, and the race fills that V with a matching rib: nothing on the part
# overhangs past 45 degrees, so it prints with no support and no skirts to
# break off. 13 elements at these proportions.

BEARING = Bearing.of(
    "6000",  # 10 x 26 x 8. Any of the 85 trade sizes, or spell it out
    element="dumbbell",  # "dumbbell", "roller" or "ball"
    **_COMMON,
)


# ============================================================================
# roller.py — the same 6000 in cylindrical rollers
# ============================================================================
# Line contact where a dumbbell is closer to point contact: carries more and
# spins less freely. Also support-free.

ROLLER = Bearing.of(
    "6000",
    element="roller",
    **_COMMON,
)


# ============================================================================
# flanged.py — F6000ZZ in balls, the awkward case
# ============================================================================
# Balls need breakaway skirts, because a sphere touches the plate at a point
# and overhangs 90 degrees above it. Snap them off before turning it. Prefer
# the dumbbell unless something actually wants point contact.
#
# F6000ZZ is the 6000 with a flange on it, so all three of the small models are
# the same bearing. Its trade size brings its own 28.5 x 1.5 plate.

FLANGED = Bearing.of(
    "F6000ZZ",
    element="ball",
    **_COMMON,
)


# ============================================================================
# lazy_susan.py — turntable, 100 mm across the top
# ============================================================================
# 100 mm is the whole thing: the top plate is the widest part, so it is the
# plate that is 100 and the bearing under it has to be smaller. 72 mm leaves a
# 14 mm ring of plate outside the bearing, which is enough for six M4 holes
# without crowding either edge.
#
# The bore then follows from the outside, because the radial gap
# `(od - bore)/2` is what gets divided three ways — inner race, element, outer
# race. A 72 mm outside over a 52 mm bore leaves 10 mm of gap, which comes out
# as 4.2 mm races and 5 mm dumbbells. Shrink the bore instead and the elements
# grow to match: a 72 over a 20 would ask for 17 mm ones.
#
# The plate is drawn as part of the outer race and sits on the build plate, so
# it needs no support at any diameter. Turn the finished part over and it is
# the top: plate and outer race turn together on the inner race, which is what
# you screw down.

LAZY_SUSAN = Bearing(
    bore=52,  # the hole down the middle
    od=72,  # the bearing, sized so the plate has a ring to sit on
    width=8,
    element="dumbbell",
    count=12,  # leave it out and 37 fit — and take far longer to build
    plate=Plate(
        diameter=100,  # the whole thing, across the top
        thickness=4,  # drawn within the bearing width, not added to it
        holes=6,  # to screw a table top down
        hole_d=4.5,  # clearance for an M4
        hole_pcd=None,  # None puts the bolt circle mid-ring, at 86 mm
    ),
    **_COMMON,
)


# ============================================================================
# threaded_boss.py — bearing on a tapped M12 socket
# ============================================================================
# The inner race carries a tube with an ISO M12 coarse thread cut in its bore,
# so a standard M12 bolt screws into it. In use the part is the other way up
# from how it prints, and the boss hangs below the inner ring.
#
# 40 mm outside rather than anything smaller because the thread has to fit
# *inside* the inner race, and the raceway cuts that race back at the very face
# the boss stands on. Ask for this on a 30 mm outside and it is refused, with
# the 0.60 mm of wall it would have had.

THREADED_BOSS = Bearing(
    bore=8,
    od=40,
    width=10,
    element="dumbbell",
    boss=Boss(
        length=18,  # how far it stands off the bearing
        thread="M12",  # ISO 261 coarse, 1.75 pitch. "M12x1.5" for fine
        external=False,  # tapped: a bolt screws up into it
    ),
    **_COMMON,
)


# ============================================================================
# threaded_stud.py — bearing on an M10 stud
# ============================================================================
# The same feature the other way round: the thread is cut on the outside,
# making a stud that screws into a tapped hole.
#
# A printed thread is not a machined one. It will take a nut; treat its load
# rating as unknown until you have pulled one apart.

THREADED_STUD = Bearing(
    bore=6,
    od=28,
    width=8,
    element="dumbbell",
    race_t=5,  # wider than the default 3.67, so the race can carry an M10
    boss=Boss(
        length=14,
        thread="M10",  # ISO 261 coarse, 1.5 pitch
        external=True,  # a stud: it screws into something
    ),
    **_COMMON,
)


# ============================================================================
# turntable_post.py — everything at once: a 90 mm top on an M12 stud
# ============================================================================
# The whole assembly in one part, and the one to preview if you want to see how
# the pieces sit together. A disc on the outer race, a threaded stud on the
# inner race, and the bearing between them — printed as one piece, in one go.
#
# In use it is upside down from how it prints: the stud screws into a base and
# stays put, and the 90 mm top turns on it.
#
# The proportions are set rather than left to the generator, and they are what
# makes both features fit at once. The bearing has to be big enough across for
# a 90 mm plate to have something to hold on to, and its inner race has to be
# fat enough to carry an M12 — but the elements still have to fit in a 10 mm
# width. 6 mm races with 8 mm dumbbells is what threads that needle; the
# generator's own thirds would give 6.3 mm races and 9.5 mm elements, and the
# raceway would leave too little of the inner race to put a stud on.

TURNTABLE_POST = Bearing(
    bore=6,  # a through hole down the middle of the stud
    od=44,  # the bearing
    width=10,
    element="dumbbell",
    race_t=6,  # fat races: the inner one has to carry the M12
    element_d=8,  # what is left of the 19 mm gap once the races have theirs
    plate=Plate(
        diameter=90,  # the top
        thickness=4,
        holes=6,
        hole_d=4.5,
    ),
    boss=Boss(
        length=18,
        thread="M12",  # ISO 261 coarse
        external=True,  # a stud: it screws into a base
    ),
    **_COMMON,
)
