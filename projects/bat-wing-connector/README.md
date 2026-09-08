# Bat-wing connector

Started 2026-08-29. Part of a bat puppet's wing: one 1/2" PVC "arm" meets
four 1/4" PVC "fingers" that fan out to support the wing membrane. All five
pipes enter short collars around a broad circular palm. The fingers occupy
one side of it at roughly 40° intervals, from the lower-left collar through
the right-hand collar in the top-view sketch.

Every socket is a blind pocket, not a through-bore. An earlier version had
all five sockets open into one shared, connected interior on purpose, so
something could be threaded from the trunk into any finger — abandoned once
the fan widened enough that it meant slicer support material generated deep
inside a sealed cavity, with no way back out to clear it after printing.

## Measured

Not taken off a physical part for this project — cited from
`projects/pvc-6-way-converter/converter.py`, which caliper-measured the same
PVC stock (checked against the actual pipe, not a Schedule 40 nominal chart).

| Dimension | Value | Notes |
|---|---|---|
| 1/2" PVC OD / ID | 19.8 / 15.8 mm | caliper, `pvc-6-way-converter` |
| 1/4" PVC OD / ID | 13.7 / 9.7 mm | caliper, `pvc-6-way-converter` |

## Decided

| Dimension | Value | Why |
|---|---|---|
| Wall | 2.0 mm | starting point, per REFERENCE.md's structural floor |
| Finger angle step | 40° | between adjacent fingers; read from the topology in the top-view sketch |
| Wrist angle | 50° | trunk to the nearest finger in the top-view sketch; the previous symmetric 120° default wrapped the sockets around 240° and put fingers on the wrong side of the palm |
| Finger count | 4 | as sketched, matching a bat's four non-thumb fingers |
| Clearance | 0.25 mm (provisional) | REFERENCE.md's generic clearance-hole figure; see `measurements.toml` |
| Socket depth | 22 mm (provisional) | how deep a socket's blind pocket reaches in from the mouth — see `measurements.toml` |
| Material | PETG | indoor puppet part, no UV/heat case for ASA's extra warp resistance |

Sockets are blind, and the circular palm at the pivot is solid — there is no
shared interior cavity anywhere in the part. The hull is a plain union of six
cylinders: the broad palm (axis across the fan) plus five short collars that
start one wall inside its perimeter. The collars do not run through the
centre as spokes. An earlier version made the palm only large enough to join
those spokes; that produced a small axle-like pivot with long exposed tubes,
not the dominant round body in the top-view sketch.

## Derived

Computed in `_wing.py`'s `Wing` dataclass — nothing here is hardcoded twice.

| Dimension | Value (at the defaults above) | From |
|---|---|---|
| `id_hole` | 20.3 mm (trunk), 14.2 mm (finger) | pipe OD + 2×clearance |
| `od_stub` | 24.3 mm (trunk), 18.2 mm (finger) | id_hole + 2×wall |
| `min_reach` | 25.0 mm | where two neighbouring tube mouths pull apart — `Wing.min_reach` |
| `reach` | 49.0 mm | min_reach + wall + socket_depth |
| `joint_r` / `joint_h` | 37.2 / 28.3 mm | broad palm radius and thickness — `min_reach` plus one trunk-collar radius; thickness clears the largest collar |
| `collar_root` | 35.2 mm | each collar starts one wall inside the palm perimeter |
| Exposed collar length | 13.8 mm | mouth reach minus `collar_root`; the rest of each 22 mm blind socket sits inside the palm |
| Socket angles | 0°, 50°, 90°, 130°, 170° | trunk, then wrist_angle + i×finger_angle_step |

## Models

| File | What it is |
|---|---|
| `connector.py` | the connector: `Wing()` at the defaults above |

`_wing.py` is the generator — a `Wing` spec, `solid()` to draw it, and
`check_wing()` to measure one back. Run it directly to print the resolved
numbers for any spec without building geometry:

    python projects/bat-wing-connector/_wing.py

## Print settings

PETG, with the circular palm lying flat on the bed for a broad, stable
footprint. All five radial collars are horizontal, so `SUPPORT = True` asks
the slicer to support their outside walls and blind-pocket ceilings. Those
supports remain reachable from each open mouth; there is no sealed shared
interior to trap them. Nothing here has been validated on an actual print
yet.

## Printability

The palm's full circular face provides the bed contact. `mise check` still
reports the expected overhangs beneath the five horizontal collars; the fatal
`unsupported` findings are allowed because `SUPPORT = True` is deliberate and
each blind pocket can be cleaned through its own mouth. The generated block
below records the measured findings.

A render may show a dark crease where a collar exits the palm. It is a union
seam, not a gap: each collar begins one full wall inside the palm perimeter.
A small fillet could round that transition after the basic proportions are
validated, at the cost of the model no longer being a plain union of
cylinders.

## Open questions

- **Supports in the horizontal collars are unvalidated.** The first print
  should confirm they come out through each mouth and leave usable socket
  surfaces. If not, the fallback is a split-print design rather than changing
  the top-view layout.
- **`clearance` and `socket_depth` are both reasoned, not dry-fitted.** A test
  print with real 1/2" and 1/4" PVC settles both; `mise check` will keep
  naming them until then.
- **Gate the print**: per AGENTS.md, a `coupon.py` next — trunk plus one
  finger only, full diameters, the joint included — proves the socket fit
  and the palm-to-collar joint before spending filament on the full
  5-socket part.

## As built

<!-- AUTO: regenerated by `mise card`. Do not hand-edit. -->

| Model | Size (mm) | Volume (cm3) | Bodies | Est. mass |
|---|---|---|---|---|
| `connector` | 99.5 x 86.8 x 28.3 | 120.0 | 1 | 152 g PETG |

Estimated mass is `density x solid volume` and assumes the part is solid through. `mise slice` gives the real figure.

**Printability** (`mise check`)

- `connector` warns: 43 mm2 overhanging up to 87 degrees from vertical over open air (the support-free limit is 45)
- `connector` warns: 42 mm2 overhanging up to 87 degrees from vertical over open air (the support-free limit is 45)
- `connector` allowed: 25 mm unsupported reach across 228 mm2 (30% of its outline is on a wall); bridges go about 15 mm before they sag
  - allowed because: the five horizontal socket collars are printed on slicer-generated supports, removable through each open mouth because every pocket is blind and separate; not yet validated on a print
- `connector` allowed: 25 mm unsupported reach across 168 mm2 (26% of its outline is on a wall); bridges go about 15 mm before they sag
  - allowed because: the five horizontal socket collars are printed on slicer-generated supports, removable through each open mouth because every pocket is blind and separate; not yet validated on a print

**Still provisional** (`measurements.toml`)

- `clearance` = 0.25 mm — REFERENCE.md's clearance-hole table (+/-0.25mm); untested for a printed socket against real PVC at this OD
- `socket_depth` = 22 mm — typical PVC slip-fit socket depth is roughly 1x the pipe OD; this is engagement length added on top of Wing.min_reach, the separate point where a mouth pulls clear of its neighbour (varies with wrist_angle/finger_angle_step). Also now a blind pocket depth, not a through-bore. Not dry-fitted.

<!-- /AUTO -->
