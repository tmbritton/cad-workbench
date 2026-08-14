# Mechanical CAD for 3D Printing — Resources

Curated sources for FreeCAD 1.1 and design-for-FDM. Knowledge in lessons is drawn
from here, not from the agent's memory.

## Knowledge

### build123d (primary sources) — current toolchain

- [build123d documentation](https://build123d.readthedocs.io/)
  The primary source. Use for: the API, builder vs algebra mode, and the
  selector system for picking faces and edges.
- [build123d — Tips, Best Practices and FAQ](https://build123d.readthedocs.io/en/latest/tips.html)
  Use for: the idioms that stop models becoming brittle. Read early.
- [build123d — External Tools and Libraries](https://build123d.readthedocs.io/en/latest/external.html)
  Viewers, editor integrations, and interop. Use for: seeing geometry without a
  full CAD GUI.
- [build123d on GitHub](https://github.com/gumyr/build123d)
  Issues are a genuine reference when the docs are thin.
- [CadQuery](https://github.com/CadQuery/cadquery)
  The sibling project — same OCCT kernel, fluent API. Still actively maintained;
  its examples often translate with light editing.

### Tooling

- [yacv — Yet Another CAD Viewer](https://github.com/Yeicor/yacv) — by Yeicor, MIT.
  Browser-based viewer for build123d/CadQuery geometry, no editor extension
  required. Serves a WebGL frontend on `localhost:32323` and pushes updates over
  websocket. This is what `mise run watch` displays; `tools/watch.py` is only a
  file-watching wrapper around it.
  Use for: seeing geometry while modelling. Two gotchas worth remembering —
  importing `yacv_server` **starts a server as a side effect**, so use the
  module-level `show`/`clear` aliases rather than constructing your own `YACV()`;
  and its graceful-shutdown timers apply at exit, not during the run.
- [watchfiles](https://github.com/samuelcolvin/watchfiles)
  Filesystem watching behind the rebuild loop. Use for: any "re-run on save" tool.

### FreeCAD (superseded as the modelling tool)

Kept for reference and as an STL/STEP viewer. See [[0002-pivot-to-build123d]].


- [FreeCAD Wiki — Sketcher Tutorial](https://wiki.freecad.org/Sketcher_Tutorial/en)
  The official walkthrough of sketching and constraining. Use for: what each
  constraint does, and what "fully constrained" means.
- [FreeCAD Wiki — PartDesign Workbench](https://wiki.freecad.org/PartDesign_Workbench)
  Reference for the Body/sketch/feature model that all mechanical modeling in
  FreeCAD sits on. Use for: what a feature is, additive vs subtractive, feature order.
- [FreeCAD Wiki — Interface Customization](https://wiki.freecad.org/Interface_Customization/en)
  Use for: toolbar/shortcut setup once the default layout starts costing time.
- [FreeCAD — Features overview](https://www.freecad.org/features.php?lang=en)
  Official description of what each workbench is for. Use for: deciding which
  workbench a task belongs in, rather than forcing a tool that half-fits.

### Design for FDM printing

- [Protolabs Network — How to design parts for FDM 3D printing](https://www.hubs.com/knowledge-base/how-design-parts-fdm-3d-printing/)
  The core design-for-FDM reference. Use for: overhang limits, wall thickness,
  orientation, warping.
- [Protolabs Network — Key design considerations for 3D printing](https://www.hubs.com/knowledge-base/key-design-considerations-3d-printing/)
  Process-agnostic overview. Use for: sanity-checking a design before slicing.
- [Protolabs Network — Designing snap-fit joints](https://www.hubs.com/knowledge-base/how-design-snap-fit-joints-3d-printing/)
  Use for: clips, catches, and any part that has to grip another without fasteners.
- [Protolabs Network — Enclosure design guide](https://www.hubs.com/knowledge-base/enclosure-design-3d-printing-step-step-guide/)
  Use for: boxes, lids, bosses, and screw-hole placement.
- [Protolabs Network — DFM tips for thin walls](https://www.hubs.com/knowledge-base/dfm-tips-for-3d-printed-parts-with-thin-walls/)
  Use for: when a wall is thin enough to need ribs instead.

Numbers worth remembering from the above (to be promoted to a reference sheet
once confirmed against the actual printer):
- Minimum printable wall ≈ 0.8 mm; 2 mm for anything structural.
- Overhangs beyond 45° from vertical need support.
- ~0.5 mm clearance around internal components; ±0.25 mm on clearance holes.
- Keep 1.5–2× wall thickness between holes, and between a hole and an edge.
- Fillet corners — reduces stress concentration and prints better.

### Material and thermal behaviour

- [Wevolver — ASA glass transition temperature](https://www.wevolver.com/article/asa-glass-transition-temperature)
  Use for: confirming ASA's thermal headroom (Tg ≈ 105 °C) and annealing guidance.
- [Eolas Prints — How to print ASA](https://eolasprints.com/en-us/blogs/3d-printing-guides/how-to-print-with-asa-filament)
  Use for: enclosure, bed temp, and warp mitigation when the tray is printed.
- [3D Solved — Filament glass transition temperatures](https://3dsolved.com/3d-filament-glass-transition-temperatures/)
  Comparison table across materials. Use for: checking a material against an
  operating temperature.
- [Sovol — Filament drying temperature guide](https://sovol.eu/blogs/new/commonfilamentdryingtemperatures-guide-for-3d-printing)
  Use for: the drying temperature the part must survive, per filament type.

Established for this project:
- ASA Tg ≈ 105 °C. Drying runs 40–80 °C. **Thermal margin is comfortable** — the
  holder can dry any filament, including nylon at 80 °C.
- ASA prints at 240–260 °C, bed 90–110 °C, enclosure strongly preferred.
- ASA's dominant failure mode here is **warping on a large flat footprint**, not
  heat softening. That pushes the design toward fillets, a non-solid tray, and
  avoiding wide unbroken flat spans.

## Wisdom (Communities)

- [FreeCAD Official Forum](https://forum.freecad.org/)
  Where FreeCAD's own developers answer. High signal, tolerant of beginners who
  post a screenshot and the actual file. Use for: "why did my model break when I
  edited that sketch", workbench choice, anything version-specific.
- r/FreeCAD — beginner-friendly, fast turnaround on interface confusion.
- r/functionalprint — critique of parts that have to *work*, not look good.
  Use for: judging whether a design will survive its actual job.

_(Reddit links omitted as bare names — the search tool is blocked from reddit.com,
so these are unverified pointers rather than confirmed-good communities.)_

No community preference stated yet by the user.

## Gaps

Things the mission needs but that aren't yet covered by a trusted source:

- **Wiki content unverified.** wiki.freecad.org sits behind Anubis anti-bot,
  so the agent could not read these pages directly — only confirm they resolve.
  Their accuracy for 1.1 specifically has not been checked. They open fine in a
  browser.
- **No vetted video course.** Searches surface Udemy/Amazon products for
  "FreeCAD 1.1 2026" that are commercial and unreviewed. Not listed until one
  is actually assessed.
- **Printer-specific data missing.** Nozzle diameter and measured dimensional
  accuracy are unknown. Every tolerance number above is a generic starting point
  until calibrated against the real machine.
- **No hard ASA shrinkage figure.** Sources describe it only qualitatively
  ("lower than ABS"). A specific percentage was not found, and that number is
  precisely what the tray's stacking fit depends on. Best resolved empirically
  with a printed test coupon rather than by further searching.
- **Dehydrator geometry unknown.** The stacking interface is the highest-risk
  dimension in the project and has not been measured or sourced yet.
- **No measurement-technique source.** Getting real-world dimensions off an
  existing object (calipers, datum choice) is a distinct skill and needs its own
  reference.
