# Reference

Sources and numbers this workspace is built on. Design decisions should be
traceable to something here or to a measurement, not to an agent's recollection.

## build123d

- [build123d documentation](https://build123d.readthedocs.io/) — the API,
  builder vs algebra mode, and the selector system for picking faces and edges.
- [Tips, Best Practices and FAQ](https://build123d.readthedocs.io/en/latest/tips.html)
  — the idioms that stop models becoming brittle. Worth rereading periodically.
- [External Tools and Libraries](https://build123d.readthedocs.io/en/latest/external.html)
  — viewers, editor integrations, interop.
- [build123d on GitHub](https://github.com/gumyr/build123d) — the issue tracker
  is a genuine reference where the docs are thin.
- [CadQuery](https://github.com/CadQuery/cadquery) — the sibling project, same
  OCCT kernel, fluent API rather than builders. Separately maintained, not a
  predecessor; its examples usually translate with light editing.
- [bd_warehouse](https://bd-warehouse.readthedocs.io/) — parametric threads,
  fasteners, bearings, gears, pipes, o-rings, retaining rings, sprockets,
  flanges. Not a dependency yet. Add it the first time a project needs a real
  thread or a fastener with a matching clearance hole, rather than modelling
  one by hand.

## Tooling

- [yacv — Yet Another CAD Viewer](https://github.com/Yeicor/yacv) (MIT, by
  Yeicor) — browser viewer for build123d geometry, no editor extension needed.
  Serves WebGL on `localhost:32323` and pushes updates over websocket. This is
  what `mise dev` displays; `tools/watch.py` is a file-watching wrapper.
  Two gotchas worth remembering: importing `yacv_server` **starts a server as a
  side effect**, so use the module-level `show`/`clear` rather than
  constructing a `YACV()`; and its graceful-shutdown timers apply at exit, not
  during the run.
- [watchfiles](https://github.com/samuelcolvin/watchfiles) — the filesystem
  watching behind the rebuild loop.
- [trimesh](https://trimesh.org/) — mesh-level validation of exported STLs
  (watertight, manifold, winding, body count), and the ray casting and surface
  sampling the design-for-FDM rules are built on. Used by `cadkit.checks`,
  `cadkit.mesh` and `cadkit.dfm`. Its ray engine needs `rtree` present to build
  a spatial index; without it every ray query raises rather than falling back,
  which is why `rtree` is a declared dependency and not an optional extra.
- **OrcaSlicer / Bambu Studio, headless.** `cadkit/slicing.py` shells out to
  whichever is installed and reads time and weight back from the G-code header.
  Four things about that interface each cost an hour to find out and are worth
  writing down: the vendor profiles are a tree of `inherits` and have to be
  flattened before `--load-settings` will take them; flattening must **keep**
  `from`, `instantiation` and `setting_id`, or the slicer decides the process
  is incompatible with the printer and says so in a message about 3MFs;
  `curr_bed_type` has to name a plate the filament allows, which a profile
  encodes by giving the plates it forbids a bed temperature of zero; and
  `--export-3mf` takes a bare filename, because the slicer joins it onto
  `--outputdir` and an absolute path there becomes nonsense. Both slicers are
  installed here as Flatpaks holding `filesystems=home` and nothing else, which
  is why the scratch directory is under `exports/` and not under `/tmp` — from
  inside the sandbox a path in `/tmp` is simply not there, and the error says
  the file is missing rather than that it is forbidden.
- [nurb](https://github.com/Shpigford/nurb) (FSL-1.1-MIT, by Josh Shpigford) —
  "agentic CAD for 3D printing": the same bet as this workspace, build123d and
  OCCT underneath, packaged as a product. Not a dependency. It is here because
  `cadkit/dfm.py` is a reimplementation of the idea behind its `checks.py` — a
  part should be measured against the printer before it is sliced — and because
  its design doctrine is a readable survey of FDM rules of thumb, if an
  unsourced one. The rules here were rederived and recalibrated against the
  parts in this tree; several of nurb's are absent, and the two that judge
  unsupported geometry are merged into one, because what decides the outcome is
  the reach from the nearest support rather than the shape of the gap.
  `cadkit/polish.py` takes its bisecting chamfer from nurb's `polish.py`, which
  is the best small idea in that codebase: when the kernel refuses a batch of
  edges without saying which one is at fault, split the batch. What is added
  here is the two filters in front of it — an edge shorter than the chamfer, or
  one that is neither straight nor a circular arc, cannot take a chamfer at any
  size, and skipping the kernel call for those turns a ninety-second pass on a
  threaded boss into an eight-second one that also finds a better answer.
  `cadkit/slicing.py` follows the same idea as its `slicing.py` — the one
  program guaranteed to know this version's settings schema is the slicer, so
  let it write its own 3MF — and none of its code.

## Design for FDM

- [Protolabs Network — How to design parts for FDM 3D printing](https://www.hubs.com/knowledge-base/how-design-parts-fdm-3d-printing/)
  — the core reference: overhang limits, wall thickness, orientation, warping.
- [Key design considerations for 3D printing](https://www.hubs.com/knowledge-base/key-design-considerations-3d-printing/)
  — process-agnostic overview, good for sanity-checking before slicing.
- [Designing snap-fit joints](https://www.hubs.com/knowledge-base/how-design-snap-fit-joints-3d-printing/)
  — clips, catches, anything that grips without fasteners.
- [Enclosure design guide](https://www.hubs.com/knowledge-base/enclosure-design-3d-printing-step-step-guide/)
  — boxes, lids, bosses, screw-hole placement.
- [DFM tips for thin walls](https://www.hubs.com/knowledge-base/dfm-tips-for-3d-printed-parts-with-thin-walls/)
  — when a wall is thin enough to need ribs instead.

Starting numbers from the above. These are generic until calibrated against the
actual machine, so treat a first print as the calibration:

| Rule of thumb | Value |
|---|---|
| Minimum printable wall | ~0.8 mm (two 0.4 mm beads) |
| Wall for anything structural | 2 mm |
| Overhang needing support | beyond 45° from vertical |
| Clearance around internal components | ~0.5 mm |
| Clearance holes | ±0.25 mm |
| Spacing between holes, or hole to edge | 1.5–2× wall thickness |

The numbers `cadkit/dfm.py` adds to that table, none of which has a source
better than practice, all of them named and argued in its `Limits` docstring:
a 15 mm unsupported reach before a bridge is worth mentioning and 40 mm before
nothing helps; 70 degrees as where an overhang stops being a warning; a
60-degree turn within 4 mm of a footprint vertex as what makes it a corner
rather than a curve; 20:1 centre-of-mass leverage as where a narrow base stops
being fine. Each was set by running the rule over the parts in this tree and
seeing where it started saying things that were not true.

Fillet or chamfer corners: it reduces stress concentration and prints better.
On a first layer prefer a chamfer — a fillet leaves a horizontal tangent at
z=0, which is a severe overhang exactly where adhesion matters most.

## Materials

- [Wevolver — ASA glass transition temperature](https://www.wevolver.com/article/asa-glass-transition-temperature)
  — ASA's thermal headroom (Tg ≈ 105 °C) and annealing guidance.
- [Eolas Prints — How to print ASA](https://eolasprints.com/en-us/blogs/3d-printing-guides/how-to-print-with-asa-filament)
  — enclosure, bed temp, warp mitigation.
- [3D Solved — Filament glass transition temperatures](https://3dsolved.com/3d-filament-glass-transition-temperatures/)
  — comparison table; use to check a material against an operating temperature.
- [Sovol — Filament drying temperature guide](https://sovol.eu/blogs/new/commonfilamentdryingtemperatures-guide-for-3d-printing)
  — drying temperatures, which is what a dryer part must survive.

Densities and Tg values used for mass estimates live in `cadkit/materials.py`.
They are nominal: density varies a few percent between brands, Tg more than
that between formulations.

## Communities

For questions that need practitioner judgement rather than a document:

- [FreeCAD Official Forum](https://forum.freecad.org/) — broad CAD and
  design-for-manufacture questions, tolerant of beginners who post the file.
- r/functionalprint — critique of parts that have to *work*. Good for judging
  whether a design will survive its actual job.
- r/cad_programming, and the build123d GitHub Discussions, for code-CAD
  specifics.

## Gaps

Things worth a source that does not yet have one:

- **No hard ASA shrinkage figure.** Sources describe it only qualitatively
  ("lower than ABS"). Best resolved empirically with a test coupon, which is
  what the two-gate strategy does anyway. `Material.warp` in
  `cadkit/materials.py` is therefore a *ranking* between filaments and not a
  percentage: it scales one threshold in the warp rule, so its ordering has to
  be right and its absolute value does not. Replacing it with a measured
  shrinkage would be a real improvement and needs a source this file lacks.
- **Nothing here has been printed *and weighed*.** The masses in the project
  READMEs are `density x solid volume` — the same figure `mise build` prints,
  not a scale reading — so they cannot confirm the slicer's number and the
  slicer's number cannot confirm them. One finished print on a kitchen scale
  settles both at once, and it is the cheapest open item on this list.
- **Bridging distance unmeasured on this machine.** The 15 mm the rules warn
  past is generic FDM practice. The dehydrator collar's 12.5 mm ledge came off
  the plate clean in ASA, which is the only local evidence there is; a
  staircase coupon of widening spans would settle it in one print.
- **Printer-specific dimensional accuracy uncalibrated.** Every tolerance above
  is a generic starting point until measured against a printed part.
- **No print-in-place clearance figure.** The table above gives ~0.5 mm for
  clearance around internal components, which is an assembly figure — parts
  that go together after printing. A gap that is *printed* as a gap is a
  different question, and `projects/ball-bearing` currently answers it with
  0.15 mm and a 0.10 mm floor, both reasoned from line width rather than
  sourced. A test print of the bearing would settle it.
- **Measurement technique.** Getting reliable dimensions off an existing object
  — datum choice, where to take a radius — is its own skill and has no source
  here yet.
