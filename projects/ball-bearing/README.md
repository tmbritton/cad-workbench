# ball-bearing

A parametric print-in-place bearing: two races, a ring of rolling elements
captured between them, printed in one piece with a clearance gap where an
assembly step would otherwise go. 85 standard trade sizes, or any bore / OD /
width you give it.

Translated from an OpenSCAD/BOSL2 generator, which is why the geometry is the
shape it is and why [the bugs](#what-was-wrong-with-the-original) below get
their own section. `_bearing.py` carries the same list in its header.

## Changing one

**Everything you would want to change is in [`parameters.py`](parameters.py).**
One file, one spec per part, with the shared numbers at the top so a single
edit reaches all six:

```python
CLEARANCE = 0.15  # gap on every face of every rolling element
BORE_FIT = 0.0  # opens the bore when a shaft comes out tight

LAZY_SUSAN = Bearing(
    bore=52,
    od=72,
    width=8,
    element="dumbbell",
    count=12,
    plate=Plate(diameter=100, thickness=4, holes=6, hole_d=4.5),
    **_COMMON,
)
```

The model files are the contract and nothing else — a docstring saying what the
part is for, and four lines of `build()` and `check()`. The geometry is in
`_bearing.py` and has nothing in it worth tuning.

Change a line and save. With the viewer running it redraws immediately:

```
mise dev ball-bearing lazy_susan   # localhost:32323, rebuilds on every save
```

A setting that cannot be built is refused from the numbers alone, before any
geometry, so a wrong one costs a second rather than a print.

## Every setting

### The envelope

| | |
|---|---|
| `bore` | the hole down the middle |
| `od` | outside diameter |
| `width` | how thick, along the axis |

Or `Bearing.of("6205")` to take all three from a trade size. Passing both is an
error rather than a precedence rule.

**The radial gap is what you are really dividing.** `(od - bore) / 2` has to
hold an inner race, a rolling element and an outer race, so it — not the
outside diameter — decides how big the elements come out. A 72 mm bearing over
a 20 mm bore leaves 26 mm of gap and asks for 17 mm rolling elements, which is
a bearing for a crane. `lazy_susan.py` is a 52 mm bore, and gets 5 mm ones.

The plate is the widest part, not the bearing, so a turntable that has to be
100 mm across the top is a bearing rather smaller than that — 72 mm here,
which leaves a 14 mm ring of plate for the bolt holes.

### The proportions

Leave any of these `None` and it comes out as a third of the radial gap, which
is roughly what a trade bearing looks like. Set it and it is what you said.
This is the part the original generator could not express at all: it hard-coded
`(od - bore) / 6` and every other dimension followed from it.

| | |
|---|---|
| `race_t` | radial thickness of each race. Thicker races mean smaller elements, and room for a bigger boss |
| `element_d` | rolling element diameter. Has to be big enough to reach into both races — see `groove_depth` below |
| `count` | how many. Cheap way to cut build time on a large bearing: a 100 mm ring fits 43 dumbbells and 12 hold a table top perfectly well |

### Print fit

| | |
|---|---|
| `clearance` | gap on **every** face of every element, 0.15 mm. The number to change first if it comes out fused or rattly |
| `spacing` | gap between neighbouring elements, as a fraction of one |
| `chamfer` | break on the bore and rim edges. Clamped to what the section can give up |
| `bore_fit` | opens the bore without moving any of the proportions — for when a 10 mm hole prints at 9.8 and the shaft will not go in |
| `od_fit` | takes the outside in, likewise, for a press fit into a housing |

### The lazy-susan top — `plate=Plate(...)`

A disc on the **outer** race. The same feature as an F-series bearing's flange,
at whatever diameter you want: 1.5 mm proud of the OD makes a locating lip,
100 mm on a 72 mm bearing makes a turntable top.

| | |
|---|---|
| `diameter` | outside of the plate. Must clear `od` |
| `thickness` | drawn *within* the bearing width, not added to it |
| `holes`, `hole_d` | bolt circle, to screw a table top down. 4.5 mm clears an M4 |
| `hole_pcd` | bolt circle diameter; `None` puts it in the middle of the annulus |

It is drawn as part of the outer race's own section, so it cannot come off the
printer as a loose collar, and it sits on the build-plate face, so it needs no
support at any diameter.

### The threaded flange — `boss=Boss(...)`

A tube on the **inner** race. Prints as a vertical tube rising from the far
face; turn the finished part over in use and it hangs below the inner ring,
which is what "a flange that extends down from the inner ring" means once it
has been through a printer.

| | |
|---|---|
| `length` | how far it stands off the bearing |
| `thread` | an ISO 261 designation — `"M12"` for the coarse pitch, `"M12x1.5"` for a fine one. `None` for a plain spigot |
| `external` | `True` cuts the thread on the outside, making a stud that screws into something. `False` taps the bore, so a bolt screws up into it |
| `od`, `bore` | for a plain boss. A thread fixes whichever one it is cut on, and setting both is an error |

Threads come from `bd_warehouse`, drawn to the ISO 68-1 profile — 60 degree
flanks, crest truncated at H/8, root at H/4. `_threads.py` holds the ISO 261
pitch tables and refuses anything that is not a real thread: `M12x1.3` is not
an M12, and `M6x0.75` is a real thread that a 0.4 mm nozzle cannot form, so
both are turned away by name.

**The boss has to fit inside the inner race**, and that is tighter than it
looks. A roller and a dumbbell are drawn to the full width, so their raceway is
cut right out to both end faces and the inner race is *narrower there* than at
the pitch plane. A boss sized to the mid-width thickness overhangs the rolling
elements' end faces, and a fuse does not care that the overlap is a sliver — it
welds the boss to every element and the bearing comes out as one lump. So a
tapped M12 needs a 40 mm bearing, not a 30 mm one, and asking for it on the
30 mm gets you the 0.60 mm of wall it would have had, by name.

### What is not settable, and why

`mid_r`, the pitch circle, is always midway across the gap: the races grow
inwards from the bore and the OD, so the middle of what is left is the middle.
`groove_depth`, how far the raceway cuts into each race, follows from
`race_t`, `element_d` and `clearance` — it is checked rather than set, because
it is the one relationship the locked proportions used to guarantee for free.
Under one bead of it and the elements sit in a slot wider than they are, with
no axial capture, and the bearing is a rattle.

## The seven models

| Model | Bearing | Elements | What it is for |
|---|---|---|---|
| **`turntable_post.py`** | 6 x 44 x 10 | dumbbell | **everything at once** — 100 mm top plate *and* an M12 stud |
| `bearing.py` | 6000 | dumbbell | the plain one to print — no overhang anywhere, no supports |
| `roller.py` | 6000 | roller | line contact instead of point — more load, less spin |
| `flanged.py` | F6000ZZ | ball | flange path and breakaway skirts |
| `lazy_susan.py` | 52 x 72 x 8 | dumbbell | the turntable: 100 mm top plate, 6 bolt holes |
| `threaded_boss.py` | 8 x 40 x 10 | dumbbell | 18 mm boss, tapped M12 |
| `threaded_stud.py` | 6 x 28 x 8 | dumbbell | 14 mm boss, M10 on the outside |

**To see the whole assembly**, preview `turntable_post` — it is the only model
with both features on it. The rest show one thing each.

```
mise dev   ball-bearing turntable_post   # live viewer at localhost:32323
mise build ball-bearing                  # all seven
mise test  ball-bearing                  # build, check, and validate the meshes
```

`mise dev ball-bearing` with no model name shows `turntable_post`, because that
model sets `DEFAULT = True`. Name any of the others to see them instead.

`lazy_susan.py` cannot also carry a stud: its inner race is 57 mm across and
ISO 261 stops at M64, so no thread would reach. That is why the combined part
is a smaller bearing with fatter races.

`parameters.py` holds every setting. `_bearing.py` is the generator, `_sizes.py`
the trade table and `_threads.py` the ISO 261 pitches. All four are helpers —
none defines `build()`, so none is ever exported. `parameters.py` has no leading
underscore on purpose: it is the file you are meant to open, and the suite lists
it as a skip rather than hiding it.

To see what the trade sizes will build, without building anything:

```
python projects/ball-bearing/_bearing.py            # every size, and what it builds
python projects/ball-bearing/_bearing.py R12 ball   # why that one is refused
```

### A bearing you mean to keep

A new bearing is a new file, because the file is the name — `mise build` writes
`<model>.stl`, and an STL called `bearing.stl` that was built with different
settings last Tuesday is how you print the wrong part. Copy any of the six and
change the `SPEC`; the file is a dozen lines, and the settings are most of them.

## What the defaults work out to

Nothing here is measured off a real bearing. Left alone, the proportions come
out as thirds of the radial gap, which is roughly what a trade bearing looks
like:

| | |
|---|---|
| `wall` | `(od - bore) / 6` — the gap divided three ways, inner race / element / outer race |
| `mid_r` | `(bore + od) / 4` — the pitch circle, halfway across. Not settable |
| `race_t` | `wall`, or `1.25 × wall` for a dumbbell |
| `element_d` | `2 × wall × f`, `f` = 1.0 ball, 0.95 roller, 0.75 dumbbell |
| `count` | as many as fit on the pitch circle by **chord**, at `spacing` × `element_d` between them |

For a 6000 (10 × 26 × 8) that is a 2.67 mm wall, a 9 mm pitch radius, and 13
dumbbells of 4.0 mm. Any of `race_t`, `element_d` and `count` can be given
instead — see [Every setting](#every-setting).

The dumbbell's races are thickened by a quarter wall each, inwards, and that
extra material is where the retaining rib comes from — the rib fills a 45
degree V round the dumbbell's waist and is what stops it walking out sideways.
Both flanks are at 45 degrees, so neither the groove's roof nor the rib's
underside needs support. That is the reason `bearing.py` is the dumbbell and
not the ball.

The inch series in `_sizes.py` uses the **open** widths. Most R sizes are also
sold shielded or sealed in a wider shell — an R8 is 1/4" open and 5/16" shielded
— so a printed "R8" is a drop-in for the open one only.

## What was wrong with the original

Six, roughly in order of how much each one costs.

1. **`id`, `od`, `width`, `flange`, `fd`, `fw` were each both a parameter and a
   local.** OpenSCAD resolves every reference in a scope to the *last*
   assignment of that name, so `info = is_undef(trade_size) ? [id, od, ...]`
   read the `id = info[0]` written below it. A recursive declaration: the
   custom-size path could not produce a part at all, and the flange asserts
   above it were checking values that did not exist yet.

2. **The ball skirt was cut once, not once per ball.** The support ring under
   the balls has a single notch where it needs `count` of them — there is no
   `for` around that cut. It stays a continuous ring, welded to every ball (it
   is deliberately grown 0.12 mm into them), so the bearing comes off the plate
   as one lump. This is the one that looks perfect in a preview.

3. **`clearance` was a radial widening, not a gap.** `ball_shape()` grew the
   roller and dumbbell profiles in X and left Y alone, so every face that is
   not square to the radius got less than the number asked for. The 45 degree
   flanks that do the axial retention on both shapes — the roller's shoulders,
   both walls of the dumbbell's groove — come out at `clearance × cos 45`:
   **0.106 mm of a requested 0.15**, measured on a 6000 either way. Not zero,
   so it is not an outright weld, but it is the wrong side of what a 0.4 mm
   nozzle bridges, and the dumbbell was the default element.

4. **Elements were counted along the arc, not the chord.** `floor(PI * mid_d *
   (1 - spacing) / ball_d)` measures centre-to-centre the long way round the
   pitch circle; the straight line between two elements is shorter. Wherever
   the arc count lands just above an integer they overlap — **26 of the 255
   size and element combinations do** at `spacing = 0`, the setting documented
   as "touching". Worst is a 635's balls, by 1.6% of a ball.

5. **A missing trade size indexed the table with an empty list.** `search()`
   answers "not found" with `[]`, and `data[[]]` is not an error message.

6. **`chamfer` was unbounded.** No standard size trips it — the thinnest race
   in the table is 1.06 mm and the narrowest bearing 3.97 mm wide, and both
   swallow the 0.6 mm default — but nothing stopped the custom path asking for
   a chamfer bigger than the race it cuts, and BOSL2 throws rather than clamps.

Two more that are the generator's design rather than defects, noted because
they look like faults from the outside. The part is *supposed* to come off the
plate as many bodies — that is what print-in-place means, and `check()` counts
them rather than demanding one. And the roller's full-width stub does nick
about 0.1 mm off the inner race's outer face, because the stub diameter is
fixed at half the roller's and leaves no room for the clearance to sit in;
harmless, and `check()` measures what is left rather than trusting it.

## What the models check

`check()` runs before anything is written, so a failure leaves the previous
export in place. Each model measures the solid it just built:

- **Body count** is `2 + count`. Anything touching its neighbour fuses into
  it, so this is what a print-in-place part is really claiming — bug 2 above
  shows up here as one lump instead of thirteen, without anyone having to
  think about which face.
- **The two raceway gaps**, as the shortest distance in three dimensions
  between an element and each race. Both must be `clearance` exactly, not
  merely non-zero: bug 3 measures correct radially and comes out 30% short
  across the flanks that do the work, which only a 3D distance sees.
- **A two-perimeter sleeve of material under each raceway**, tested by
  subtracting the race from it and asking whether anything is left. The first
  version of this measured a thickness at the pitch plane instead, which is
  wrong on a dumbbell — the pitch plane is where the retaining rib sits, so it
  read the *thickest* section and passed an R2 whose rim section was 0.64 mm.
- **Rotational symmetry** — every element the same volume, which catches a
  placement that walked one into a race and had material trimmed off it.
- **The thread is the thread it is named after** — measured over one whole
  pitch, so the helix passes through every angle and the extreme radius is
  certainly in the band. An M12 that comes out 11.9 is not an M12, and the
  bolt bought for it is the way you would otherwise find out.
- **Every bolt hole open all the way through.** A hole the plate profile
  swallowed leaves a plate that looks right from every angle.
- Overall envelope, and for `flanged.py` and `lazy_susan.py` that the plate
  came out as part of the outer race rather than a loose disc, and that every
  skirt reaches the plate.

`_sizes.py` validates the whole trade table at import: no duplicates, bore
inside OD, and every flange clearing the OD it sits on.

### Where it refuses

`validate()` runs on the numbers before any geometry is drawn, so an
unbuildable combination fails in milliseconds with a message naming what to
change, rather than after ten seconds of booleans:

    >>> Bearing.of("R12", element="ball").validate()
    ValueError: R12's raceway would leave 0.11 mm of race at each face, under
    the 0.84 mm floor — nothing holds the balls in. 7.94 mm is too narrow for
    a 7.41 mm ball; try element='dumbbell' or 'roller', which are retained by
    a rib rather than by the groove's shoulders

Two rules rule out whole trade sizes, and both come from `cadkit.printer`'s
two-perimeter floor rather than from anything invented here:

- **Race under the raceway** — `1.5 × wall − element_d/2 − clearance`, the same
  for both races because the pocket is cut from the middle of the gap. Rejects
  27 of the 255 combinations: the small sizes (R2–R4, 605, 6800–6803,
  F686ZZ–F689ZZ) have only so much material in `(od − bore) / 2` to divide
  three ways.
- **Race at the faces**, balls only — `width/2 − element_d/2 − clearance`, the
  material that stops a ball pushing out sideways. Rejects 16, almost all of
  the inch series plus 635 and 16004/16005: those are wide across the gap and
  narrow along the axis, so a ball fills the width and leaves a knife edge.
  Rollers and dumbbells run out to the faces on purpose and are held by a
  shoulder or a rib, so the rule does not apply to them.

Setting the proportions by hand adds one more, and it is the relationship the
locked thirds used to guarantee for free:

- **`groove_depth`**, how far the raceway cuts into each race, must be at least
  one 0.42 mm bead. Under that the elements sit in a slot wider than they are,
  with no axial capture at all, and the bearing is a rattle rather than a
  bearing. This is what catches `element_d` set too small for the `race_t` it
  is paired with.

Plus the ordinary ones: clearance under 0.10 mm (below what a 0.4 mm nozzle
can be relied on to leave open) or over half a race wall, fewer than three
elements or more than fit, an element wider than the bearing, a plate that does
not clear the OD it sits on or whose bolt holes run out of metal, a boss wider
than the inner race is at the face it stands on or too thin-walled *at the
thread root* — which on an M12 is 10.11 mm, not 12, so measuring at the crest
overstates the wall by nearly half — a thread with under three turns on it, and
any designation ISO 261 does not list.

Together that is **40 of 255 refused, 215 built and checked**. The dumbbell
survives every trade size except the four smallest, which is the other reason
`bearing.py` is the one with `element="dumbbell"`.

## Printing

PETG, 0.4 mm nozzle, 0.2 mm layers. Not validated on a print yet — the numbers
below are the starting point, not a result.

| | |
|---|---|
| material | PETG — tough, indifferent to a warm chamber, and it does not fuse across a small gap as readily as PLA does |
| layer height | 0.2 mm. The clearance is axial as well as radial, so the gap above and below each element is one layer thick — a taller layer eats it |
| walls | 2 minimum. The thinnest race section on a 6000 dumbbell is 2.85 mm, which is six perimeters wide, so the races are solid either way; what matters is that nothing forces an extra bead into the raceway |
| thin-wall / gap fill | **off**. The 0.15 mm gap is a third of a 0.42 mm extrusion, so it is a void the slicer leaves rather than a feature it prints. Any setting that decides to fill it welds the bearing shut |
| supports | none, on any of the three models. `flanged.py` prints its own, as the skirts |
| seam | random or scarf — a seam lined up down a raceway is a ridge to roll over |

Then: on `flanged.py`, snap the skirts off before turning it. On all three,
expect the first turn to need a firm twist, and give it a few dozen turns to
bed in.

The clearance is the number to change if it comes out wrong, and it is one
argument: `Bearing.of("6000", element="dumbbell", clearance=0.2)`. Fused
solid means it wants more; rattly means less.
