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
exports/             generated; gitignored in full
```

## Commands

| Command | What it does |
|---|---|
| `mise build` | build every project |
| `mise build <project>` | build one project into `exports/<project>/` |
| `mise build <project> <model>` | build one model |
| `mise test` | build everything and run every `check()`, plus mesh validation |
| `mise watch <project> [model]` | live viewer at localhost:32323, rebuilds on save |
| `mise render <project> [model]` | PNG views of the exported STLs, no GPU needed |
| `mise new <project> [model]` | scaffold a project folder |
| `mise fmt` | ruff format and lint |

`-n` / `--dry-run` on `build` checks without writing.

Running a model file directly (`python projects/x/thing.py`) does the same
thing for one model — it goes through the same code path, so the two cannot
drift.

## The model contract

A model is any `.py` in a project folder, not starting with `_`, that defines
`build()`. Files starting with `_`, and files with no `build()`, are helpers:
importable by their siblings, never exported.

```python
MATERIAL = ASA  # optional — enables the mass column


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
