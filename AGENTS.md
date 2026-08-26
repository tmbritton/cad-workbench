# AGENTS.md

A build123d workspace for functional 3D-printed parts. Models are Python; the
geometry is checked by assertions and exported to STEP and STL for slicing.

## Layout

```
projects/<name>/     one folder per part or family of parts
  README.md          measurements first, then decisions, then print settings
  *.py               models
cadkit/              shared helpers — selectors, checks, printer, materials
tools/               build driver, viewer, renderer, scaffolder
tests/               builds every model and runs its own checks
inputs/              third-party geometry models build from; gitignored in full
exports/             generated; gitignored in full
```

`inputs/` holds geometry this repo did not make — another generator's output, a
downloaded mesh, a scan. It is gitignored because it is not ours to carry and
because binary blobs in history are permanent. A model that reads from it says
so in its project README and raises `FileNotFoundError` naming the path when it
is absent; the suite turns that into a skip rather than a failure, so a
checkout without the geometry is quiet rather than permanently red.

## Commands

| Command | What it does |
|---|---|
| `mise build` | build every project |
| `mise build <project>` | build one project into `exports/<project>/` |
| `mise build <project> <model>` | build one model |
| `mise test` | build everything and run every `check()`, plus mesh validation |
| `mise test <project> [model]` | the same, scoped to one project |
| `mise check [project] [model]` | the design-for-FDM rules: will it actually print |
| `mise slice [project] [model]` | real print time and filament weight, from the slicer |
| `mise inspect <project> [model]` | faces, edges, plate contact, drift from a target mesh |
| `mise card [project]` | regenerate the as-built block in each project README |
| `mise dev <project> [model]` | live viewer at localhost:32323, rebuilds on save |
| `mise render <project> [model]` | PNG views of the exported STLs, no GPU needed |
| `mise new <project> [model]` | scaffold a project folder |
| `mise format` | ruff format and lint |

`-n` / `--dry-run` on `build` checks without writing. Flags after the names on
`mise test` pass through to pytest (`mise test dehydrator-riser -x`).

Running a model file directly (`python projects/x/thing.py`) does the same
thing for one model — it goes through the same code path, so the two cannot
drift.

**Projects do not block each other.** `mise build` attempts every model even
after one fails and still exports the ones that worked; `mise build <project>`
and `mise test <project>` ignore everything outside that project entirely. A
half-finished model in one project is never a reason to be stuck in another.

## The model contract

A model is any `.py` in a project folder, not starting with `_`, that defines
`build()`. Files starting with `_`, and files with no `build()`, are helpers:
importable by their siblings, never exported.

```python
MATERIAL = ASA  # optional — enables the mass column
DEFAULT = True  # optional — `mise dev <project>` shows this one
ALLOW = {}  # optional — printability rules this part overrules, with reasons
SUPPORT = True  # optional — this part needs support; `mise slice` costs it in
BRIM = 5.0  # optional — brim width in mm, likewise


def build() -> Part: ...  # required, no arguments
def check(part) -> None: ...  # optional, assertions


if __name__ == "__main__":
    from cadkit import cli

    raise SystemExit(cli(build, check))
```

Project folders go on `sys.path`, so a model imports its siblings by bare name
(`import collar`). That means **model filenames must be valid Python module
names** — underscores, not hyphens. The folder may be kebab-case.

`build()` may take keyword arguments with defaults; the driver calls it with
none. That is how variants work.

`DEFAULT` affects only `mise dev` with no model named. Without it the viewer
shows the first model alphabetically, which is right for a project with one
part and wrong for a family — reaching for `mise dev ball-bearing` and getting
the plainest of its seven bearings is a papercut every time. One model per
project may claim it; two is an error naming both.

## How to work here

**Write self-checking models.** Every model should assert what it must be true
for: solid count, the dimensions that actually mate, bed fit. `check()` runs
*before* anything is written, so a failure leaves the previous export in place
rather than replacing it with wrong geometry — a stale STL announces itself
when the print does not match, a fresh wrong one does not. Assert the
dimensions that mate, not the ones that merely restate the code, and put the
numbers in the message.

`cadkit` has the reusable ones: `single_solid`, `fits_bed`, `cavity_ceiling`,
`watertight`. Add to it only when a second project needs the same thing.

**Run `mise check` before you print.** Those assertions say the model is what
it claims to be; `mise check` asks the other question, which is whether it can
come off the plate. Eight rules in `cadkit/dfm.py`, measured on the tessellated
part rather than on the source: surface reaching too far from anything holding
it up, walls under two beads, slopes past 45 degrees over open air, a rounded
bottom edge where a chamfer belongs, faces narrower than one extrusion, slender
upright pins, sharp corners on a large footprint in a material that lifts, and
a centre of mass too near the edge of the base. `mise build --check` runs the
same set; `mise dev` runs the ones that need no ray casting on every save.

Every rule has legitimate exceptions, so a model overrules one **with a
reason**:

```python
ALLOW = {"overhang": "the seat ring, printed on support; ring test, 13 Aug 2026"}
```

An empty reason is an error, and so is a rule name that does not exist — a typo
there would otherwise silence nothing at all, quietly. The reason is not
ceremony: it is the only record of whether the exception was reasoned or merely
convenient, which is the same argument this file makes for commenting the *why*
of a dimension. Allowed findings still print, dimmed, so they stay readable.

`mise test` fails only on what the rules call fatal — a surface starting in
mid-air, a wall thinner than the nozzle can lay down. Warnings are judgement
calls and belong in `mise check`, where a person reads them.

**Cost the print before you start it.** `mise slice` hands the STL to the
installed OrcaSlicer or Bambu Studio, headless, with this printer's own vendor
profiles, and reports the minutes and grams it comes back with. The mass in the
build report is `density x solid volume` and assumes the part is solid through:
the collar is 173 g by that arithmetic and 153 g through a slicer. `--3mf`
writes the settings into `exports/<project>/<model>.3mf`, so the slicer opens
on a plate already set up.

`SUPPORT` and `BRIM` belong in the model, not on the command line. They are
things a test print taught you about the part, they change the cost more than
anything else in the report, and next year the only place anyone will look for
them is the file. Say in the project README *why*; the model carries the fact.

Slicer settings are otherwise left alone on purpose. It is tempting to have
`mise slice` raise the wall count to this workspace's structural minimum or
swap the infill pattern, but those are decisions about the part rather than
consequences of a finding, and a report that quietly re-tunes what it is
measuring is not measuring anything. The one exception is a brim, which
`cadkit.slicing.tuned` adds when the warp or stability rule fires — those are
the two failures a brim answers.

**A number nobody can account for belongs in `measurements.toml`.** Most
dimensions belong in the model, next to the comment saying why — the script is
the explanation, and splitting a number from its reason across two files makes
both worse. The exception is a number whose *provenance* is the interesting
part: a value reasoned rather than measured, one off a scan, one waiting on a
test print. Those go in a `measurements.toml` beside the models, where `how`
is required and `provisional = true` means `mise check` keeps mentioning it
until somebody settles it. `projects/ball-bearing` has the three that
REFERENCE.md admits were reasoned from line width and never printed.

**Measure, do not assume.** The bug that cost the most on this workspace's
first part was assuming a cavity was as deep as the extrusion that produced it.
Shelling laid a wall's worth of material under the step and it was 1.8 mm
shallower. Query the geometry for the number and assert it.

**Comment the *why*, in millimetres.** The existing models are the house style:
group constants into **measured**, **decided** and **derived**, and say what a
derived one is derived from. `STEP_Z = SOCKET_D + WALL` needs its paragraph, or
someone simplifies it back into a bug.

**Select by meaning, not index.** Name an edge via the face that bounds it
(`face.outer_wire().edges()`), and re-query after every operation — chamfers
and fillets rebuild the topology, so a face held from before the operation
refers to geometry that no longer exists. An index-based selector still builds;
it just chamfers the wrong edge.

`mise inspect <project> <model>` is how you find out what is there to name: it
lists the flat faces by height, which is what `horizontal_face_at` and
`cavity_ceiling` are indexed on, and the largest faces by area, which is
usually what somebody meant by "the top". `mise render --section y` cuts the
part open when the feature is inside.

**Chamfer with `polish`, not with `chamfer`.** `chamfer(part.edges(), 1.0)`
raises as soon as one edge in the set has no room, and does not say which.
`cadkit.polish.polish` bisects the batch instead and returns the largest set
that lands, naming the rest through its `report=` list — and refuses an edge
whose chamfer would leave a face thinner than a bead even where the kernel
agreed. Helices and edges shorter than the chamfer are dropped before the
kernel is asked anything, which is the difference between eight seconds and
ninety on a threaded part.

**Variants are models, not flags.** A test print is a separate file that
imports every dimension from the parent model and only removes material — never
retyped numbers, never a CLI flag that writes a differently-named STL. The
file is the name. See `ring.py` and `coupon.py`.

**Gate expensive prints.** Before committing hours and a few hundred grams:
a small local coupon, then a full-footprint version with the tall parts
truncated, then the real part. Each gate must prove something the previous one
could not — if the answer is "nothing", skip it. Scaling in the slicer is not a
substitute: scaling Z scales the mating features too.

## Working with the user

They measure with calipers and supply dimensions, sketches, photos and a
description; the agent writes the build123d; they learn by adjusting the
script. So the script is the explanation — readability is a feature, not
polish.

What to ask for, by question type:

- **Dimensions** → calipers. Never read a dimension off a photo.
- **Topology, orientation, which-way-round** → a photo.
- **Anything that mates** → a hand cross-section sketch with dimensions. Both
  of the first part's longest-lived bugs were cross-section questions.
- **Function** → one sentence on what the part must *do*. "It sits on the male
  end of another tray" resolved more than any dimension did.

Prefer one or two questions in plain prose, with the reasoning stated up front,
over grids of multiple-choice options.

## The printer

Bambu Lab H2S: 340 × 320 × 340 mm build volume, single nozzle (0.4 mm),
enclosed with an actively heated chamber up to 65 °C, 350 °C hotend, 120 °C
bed. These live in `cadkit/printer.py`; `fits_bed()` asserts against them.

Filament is a per-project choice, not a workspace constant — anything the
printer supports is available. Each project's README names its own material and
print settings, and marks which of them were *validated* on a test print rather
than assumed.

Two consequences of the hardware that recur: the heated chamber rules out
low-Tg support material (PLA softens in the feed path), and the single nozzle
makes every filament change a full purge.

Generic design-for-FDM numbers and sources are in `REFERENCE.md`.
