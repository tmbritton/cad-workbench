# cad-workbench

A [build123d](https://build123d.readthedocs.io/) workspace for functional
3D-printed parts. Models are Python, geometry is checked by assertions, and
exports go to STEP and STL for slicing.

```
mise run setup                  # install dependencies
mise build                      # build every project into exports/
mise build dehydrator-riser     # build one
mise dev dehydrator-riser       # live viewer at localhost:32323
mise check                      # will it print? overhangs, walls, warp, tipping
mise check ball-bearing flanged # ...or just one model
mise slice dehydrator-riser     # what it costs: real minutes and grams
mise slice dehydrator-riser --3mf  # ...and a 3MF the slicer opens ready to go
mise inspect ball-bearing flanged  # what it is made of: faces, edges, drift
mise render dehydrator-riser --section y  # PNGs, cut open
mise card                       # regenerate the as-built block in each README
mise test                       # build everything and run every check
mise test dehydrator-riser      # ...or just one project
mise new spool-holder           # scaffold a new project
```

## Projects

| Project | What it is |
|---|---|
| [`dehydrator-riser`](projects/dehydrator-riser/) | a collar that raises a food dehydrator's lid clear of a filament spool, turning it into an overnight dryer. Printed and in use. |
| [`ball-bearing`](projects/ball-bearing/) | a parametric print-in-place bearing generator — any size, 85 standard trade sizes, three rolling-element shapes, an optional turntable top plate and an optional ISO-threaded boss. Races and elements print in one piece. Translated from an OpenSCAD generator, with its bugs listed and fixed. Not yet printed. |
| [`pvc-6-way-converter`](projects/pvc-6-way-converter/) | a six-way PVC node, five sockets of one pipe size and one of the next. Not designed here: it repairs an external generator's output, which capped the large arm. Not yet printed. |

Each project folder holds its own README with the measurements the models are
built from, and the print settings that were validated on a test print.

## How it fits together

A model is any `.py` in a project folder that defines `build()`. It may also
define `check(part)`, which runs before anything is written — so a failed
assertion leaves the previous export alone rather than replacing it with
geometry that is wrong in a way nobody noticed.

`cadkit/` holds the shared pieces: selectors that name geometry by what it is
rather than by list position, checks (`single_solid`, `fits_bed`,
`watertight`), the printer's envelope, and filament densities.

Those checks say a model is *well-formed*. Whether it will come off the plate
is a different question, and `mise check` asks it: `cadkit/dfm.py` measures the
built part against eight design-for-FDM rules — surfaces reaching too far from
anything holding them up, walls under two beads, slopes past 45 degrees over
open air, a rounded bottom edge where a chamfer belongs, faces narrower than
one extrusion, slender upright pins, sharp corners on a large footprint in a
material that lifts, and a centre of mass too near the edge of the base.

Nothing there is absolute — every one of those has a legitimate exception, so a
model declares its own and says why:

```python
ALLOW = {"overhang": "the seat ring, printed on support; ring test, 13 Aug 2026"}
```

Allowed findings still show up in `mise check`, dimmed, with their reason
attached. They are the part of a design somebody decided about, which makes
them the part most worth being able to read a year later.

`mise slice` asks the third question — what the print costs. The mass in the
build report is density times solid volume, an upper bound that assumes the
part is solid through; the collar is 173 g by that arithmetic and 153 g through
a slicer at stock settings. `cadkit/slicing.py` drives the installed
OrcaSlicer or Bambu Studio headlessly with this printer's own vendor profiles
and reads the time and weight back out of the G-code. `--3mf` writes
`exports/<project>/<model>.3mf` with those settings embedded, so the slicer
opens on a plate that needs no setting up.

A part that has to be printed with support, or with a brim, says so next to its
material, because that is a fact about the part and it was learned on a print:

```python
SUPPORT = True  # the seat ring hangs over its own cavity; validated 13 Aug 2026
BRIM = 5.0  # 90 mm tall on 17.5 cm2 of bed contact
```

`mise inspect` answers the question a selector needs answered — what faces and
edges are actually there, what touches the plate, and, for a part rebuilt from
somebody else's mesh, how far it has drifted from it in both directions.
`mise render --section y` cuts a part open so a cavity or a print-in-place gap
can be seen, with the exposed interior shaded warmer than the outside.

`mise card` regenerates a marked block at the end of each project README with
the facts only building can produce — size, bodies, mass, what the printability
rules said, which measurements are still provisional. It carries no timestamp,
so running it twice leaves no diff, which makes it safe to run on reflex.

Two more things worth knowing about. `cadkit.polish` chamfers every edge that
will take one and names the ones that will not, instead of the kernel refusing
the whole batch and saying nothing about which edge was at fault. And a
`measurements.toml` beside the models holds any dimension whose provenance is
the interesting part — `how` it was arrived at is required, and one marked
`provisional = true` keeps showing up in `mise check` until a print settles it.

Conventions, and the reasoning behind them, are in [AGENTS.md](AGENTS.md).
Sources and design-for-FDM numbers are in [REFERENCE.md](REFERENCE.md).
