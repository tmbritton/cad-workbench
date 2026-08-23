# cad-workbench

A [build123d](https://build123d.readthedocs.io/) workspace for functional
3D-printed parts. Models are Python, geometry is checked by assertions, and
exports go to STEP and STL for slicing.

```
mise run setup                  # install dependencies
mise build                      # build every project into exports/
mise build dehydrator-riser     # build one
mise dev dehydrator-riser       # live viewer at localhost:32323
mise test                       # build everything and run every check
mise test dehydrator-riser      # ...or just one project
mise new spool-holder           # scaffold a new project
```

## Projects

| Project | What it is |
|---|---|
| [`dehydrator-riser`](projects/dehydrator-riser/) | a collar that raises a food dehydrator's lid clear of a filament spool, turning it into an overnight dryer. Printed and in use. |
| [`ball-bearing`](projects/ball-bearing/) | a parametric print-in-place bearing — 85 standard trade sizes, three rolling-element shapes, races and elements printed in one piece. Translated from an OpenSCAD generator, with its bugs listed and fixed. Not yet printed. |
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

Conventions, and the reasoning behind them, are in [AGENTS.md](AGENTS.md).
Sources and design-for-FDM numbers are in [REFERENCE.md](REFERENCE.md).
