# Dehydrator riser collar

A spacer that drops into a stackable food-dehydrator tray stack and raises the
lid clear of a filament spool lying flat in a tray. The dehydrator becomes an
overnight filament dryer without modifying anything.

An open collar — no floor, no spool arm. A spool lies flat in an existing tray;
all that was missing was height.

**Printed and in use.** Both test gates passed first time; the full collar
followed.

## Measured

Off the trays with calipers, except the corner radii, which came from a printed
radius gauge.

| Dimension | Value | Notes |
|---|---|---|
| Wall thickness | 1.8 mm | the existing tray wall |
| Female socket | 295 × 211 mm | internal; receives the male rim of the tray below |
| Socket depth | 18 mm | `SOCKET_D` — how far the rim below goes in |
| Female corner | R26 | internal radius of the socket |
| Male section | 285 × 204 mm | external; plugs into the socket above |
| Male corner | R19 | external radius — **sharper than the socket it enters** |
| Lid | same as the female portion | so the lid seats on this collar exactly as on a tray |
| Central hole | ⌀48 mm | in the tray floor; not modelled here — see open questions |

The male and female labels were swapped once, early on, when the numbers came
out with the male larger than the female. The values above are post-swap.

## Decided

| Dimension | Value | Why |
|---|---|---|
| `MALE_H` | 70 mm | exposed male wall; the height that clears the spool. Started at 65 and was retuned during testing — it affects nothing that mates. |
| `LIP_CHAMFER` | 1.5 mm | breaks the two sharp outer edges of the protruding lip. A chamfer, not a fillet: a fillet on the bottom edge leaves a horizontal tangent at z=0, a severe overhang on the first layers. 1.5 rather than 1.8 because the bottom face is only one wall wide and a full-wall chamfer would leave a knife edge. |

## Derived

| Dimension | Value | From |
|---|---|---|
| `FEM_OUTER_X/Y` | 298.6 × 214.6 | `FEM + 2 × WALL` — the socket walls wrap the 295 × 211 opening |
| `STEP_Z` | 19.8 mm | `SOCKET_D + WALL` — **not** `SOCKET_D` |
| `TOTAL_H` | 89.8 mm | `STEP_Z + MALE_H` |
| `STACK_GAIN` | 71.8 mm | `MALE_H + WALL` — what the stack actually gains per collar |

### Why `STEP_Z` is not `SOCKET_D`

Shelling lays a wall's worth of material *under* the step, and that web's
underside is the ceiling the rim below seats against. Extruding only `SOCKET_D`
put the cavity ceiling at 16.20 mm instead of 18.00 — the collar would have
perched 1.8 mm proud of the shoulder instead of seating flush like a tray.

This is measured on every build (`cavity_ceiling(part)` in `check()`), not
assumed. It is also why `STACK_GAIN` is `MALE_H + WALL` and not `MALE_H`.

## Clearance

The male section is *sharper* than the socket it enters (R19 into R26), so the
straight-run clearance and the corner clearance are not the same number. Found
by sampling the signed distance between the two rounded-rectangle profiles:

| Where | Clearance per side |
|---|---|
| Straight run, X | 5.00 mm |
| Straight run, Y | 3.50 mm |
| **Corners** | **2.97 mm** ← the tightest point anywhere on the profile |

Positive everywhere, so it drops in — but the corners are where it would bind
first if anything shifted.

## Models

| File | What it is | Mass |
|---|---|---|
| `collar.py` | the real part | 173 g |
| `ring.py` | full perimeter, male truncated to its engaged length | 78 g |
| `coupon.py` | one corner, male truncated | 8 g |

`ring` and `coupon` import every dimension from `collar` and only remove
material, so a test print cannot drift from the part it tests. Both are
`collar.build(male_h=SOCKET_D)` — above the engaged length the male is plain
wall and tests nothing.

## Print settings

**Validated on the ring test, 13 Aug 2026.** Filament: ASA, on the Bambu H2S
with the chamber heated. The 298.6 × 214.6 footprint fits the bed in one piece.

- **Supports: required, and "everywhere" rather than build-plate-only.** The
  seat ring at `z = SOCKET_D` is a horizontal cantilever (5.0 mm in X, 3.5 mm
  in Y, 2.97 mm at the corners) hanging inward over the socket cavity, and it
  does not bridge unsupported. An earlier prediction that it would was wrong.
  Removal is easy — the collar is open at both ends, so the column pushes
  straight out — and it does not mark the seat: the ring test fitted perfectly.
- **Support material: ASA, the same as the part.** Not PLA. The chamber runs
  near 65 °C, above PLA's Tg of ~60 °C, so PLA softens in the feed path and
  heat-creeps; the H2S is single-nozzle, so every swap is a full purge; and the
  two cooling profiles conflict (ASA wants no early fan, PLA wants full). The
  PLA-interface trick is for dual-nozzle machines with cool chambers. If
  supports are hard to remove, raise the support top Z-gap rather than changing
  material.
  In the slicer, with one filament loaded the support-filament dropdown is
  inert and reads `Default` — that already means ASA. Nothing to change.
- **Brim: 5 mm, inner and outer.** 89.8 mm tall on only 17.5 cm² of bed contact
  (2.7% of its footprint envelope); a 5 mm outer brim is about 3.8× that.
- **Orientation as modelled**, bottom face on the plate. No rotation.

## Test-print gates

| Gate | Mass | What only it could prove |
|---|---|---|
| Corner coupon | 8 g | corner clearance, seat depth, socket fit |
| Full ring | 78 g | four corners at once, no rocking, warping over the real footprint, first-layer adhesion at scale |
| Real part | 173 g | — |

86 g and under two hours spent before committing to the real print. Both gates
passed first time; the ring test is also what surfaced the support requirement.

## Open questions

- Is the ⌀48 central hole in the tray floor flat, or a raised chimney the spool
  bore sits over? Only matters if it is tall enough to intrude into the spool's
  space — it does not affect the collar.
