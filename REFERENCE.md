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
  what `mise watch` displays; `tools/watch.py` is a file-watching wrapper.
  Two gotchas worth remembering: importing `yacv_server` **starts a server as a
  side effect**, so use the module-level `show`/`clear` rather than
  constructing a `YACV()`; and its graceful-shutdown timers apply at exit, not
  during the run.
- [watchfiles](https://github.com/samuelcolvin/watchfiles) — the filesystem
  watching behind the rebuild loop.
- [trimesh](https://trimesh.org/) — mesh-level validation of exported STLs
  (watertight, manifold, winding, body count). Used by `cadkit.checks`.

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
  what the two-gate strategy does anyway.
- **Printer-specific dimensional accuracy uncalibrated.** Every tolerance above
  is a generic starting point until measured against a printed part.
- **Measurement technique.** Getting reliable dimensions off an existing object
  — datum choice, where to take a radius — is its own skill and has no source
  here yet.
