# ball-bearing

A parametric print-in-place bearing: two races, a ring of rolling elements
captured between them, printed in one piece with a clearance gap where an
assembly step would otherwise go. 85 standard trade sizes, or any bore / OD /
width you give it.

Translated from an OpenSCAD/BOSL2 generator, which is why the geometry is the
shape it is and why [the bugs](#what-was-wrong-with-the-original) below get
their own section. `bearing.py` carries the same list in its header.

## The three models

| Model | Size | Elements | Why it exists |
|---|---|---|---|
| `bearing.py` | 6000 | dumbbell | the one to print — no overhang anywhere, no supports to break off |
| `roller.py` | 6000 | roller | line contact instead of point — more load, less spin. Also support-free |
| `flanged.py` | F6000ZZ | ball | flange path and breakaway skirts, both of which nothing else covers |

```
mise build ball-bearing            # all three
mise test ball-bearing             # build, check, and validate the meshes
```

`_sizes.py` is the trade table. It is a helper, not a model — no `build()`, and
the leading underscore keeps it out of the export sweep.

## Dimensions

Nothing here is measured off a real bearing. Everything is derived from the
trade size, which is the whole point of a generator:

| | |
|---|---|
| `wall` | `(od - bore) / 6` — the radial gap divided three ways, inner race / element / outer race |
| `mid_r` | `(bore + od) / 4` — the pitch circle, halfway across the gap |
| `element_d` | `2 * wall * f`, `f` = 1.0 ball, 0.95 roller, 0.75 dumbbell |
| `count` | as many as fit on the pitch circle by **chord**, at `spacing` × `element_d` between them |
| `clearance` | 0.15 mm, on every face of every element |

For a 6000 (10 × 26 × 8) that is a 2.67 mm wall, a 9 mm pitch radius, and 13
dumbbells of 4.0 mm.

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
- Overall envelope, and for `flanged.py` that the flange came out as part of
  the outer race and that every skirt reaches the plate.

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

Plus the ordinary ones: clearance under 0.10 mm (below what a 0.4 mm nozzle
can be relied on to leave open) or over half a race wall, fewer than three
elements, an element wider than the bearing, a flange that does not clear the
OD it sits on.

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
