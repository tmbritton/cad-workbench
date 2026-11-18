# Corrected reference: boat trim holder

## Dominant silhouette and topology

An open-bottom arch with short level shoulders and downturned ends. The user's
correction and instruction to proceed establish this topology:

```text
Z-axis view (width goes into the page)

                      crown
                 ____/     \____
           _____/               \_____
          /                            \
          |                            |
          |                            |
          ends terminate here: no inward feet

outer end → rounded corner → drilled shoulder → arch
                                             → mirrored shoulder/corner/end
```

One continuous plastic strip, extruded across 37 mm; two holes pierce the
4.5 mm shoulder/arch strip, centred across that width. The 3.2 mm downturned
ends are not drilled. There is no second return at their bottoms.

## Reference review

Primary reference: `inputs/boat-trim-piece/1000002442.jpg`, rotated 90 degrees
counterclockwise for comparison to the model's +Z view. Both end corners and
the central arch were cropped and enlarged independently. Each end terminates
in a straight cut; the corner is at its upper end. The shoulders flatten before
the central arch, rather than forming bumps above an angular inner contour.
The rough patch under the arch is damage/residue, not a modeled boss.

The photo looks approximately along the section extrusion axis, with an
estimated 5–15 degree obliquity (roughly 0 degree azimuth / 80 degree elevation
in the model frame). It is not calibrated or orthographic. Far-side depth and
exact hole axes cannot be established from this view. The other two photos
establish the two holes and constant-width strip; the user confirms their
placement in the 4.5 mm plastic. No millimetre dimensions are read from pixels.

## Dimension sources

| Feature | Value | Source/status |
|---|---:|---|
| Overall length / width / height | 102 / 37 / 42 mm | user-confirmed |
| Original crown radius | 46 mm | user subsequently questioned this measurement and relaxed the radius constraint |
| Shoulder and arch thickness | 4.5 mm | user-confirmed; use a normal offset |
| End thickness | 3.2 mm | user-confirmed |
| End-region height | 20 mm | sketch/user; interpreted as underside-of-shoulder height |
| Holes | 2 × 4.5 mm | user-confirmed |
| End to nearest hole edge | 12.4 mm | user-confirmed, projected end-to-end direction |
| End blends and arch transition positions | see measurements.toml | design estimates, not photo measurements |

The earlier answer of 20 mm to a question about an inward lip followed an
incorrect topology proposed by the agent. It does not justify retaining a
bottom flange after the user's explicit correction. Only the independently
confirmed 20 mm end-region height is used here.

## Modeling decisions

- Bézier-defined profile: cubic end corners and two mirrored quintic
  half-arches. The half-arches start with zero slope and curvature at the
  shoulders, and meet with matching slope and curvature at the crown.
- The first correction's circular crown still produced a visible bump at its
  transitions. The user requested a smoother curve and said the radius might
  have been measured incorrectly. The circular constraint is now removed;
  the original 46 mm value is reference-only.
- The upper strip's inner contour is a 4.5 mm normal offset, not an unrelated
  curve or a vertical translation; end blends transition to 3.2 mm walls.
- Mirror the two ends, and use straight hole axes along Y; those are inferred
  from the sketch and the top/bottom photos, not calibrated from the side view.
- No countersinks, damage, extra bosses or clearance allowances are inferred.

## Failure criteria for the Z-axis render

1. Any inward-projecting bottom foot or shelf: fail.
2. Mounting holes in the thin end walls instead of the upper strip: fail.
3. Kinks, bulging shoulders or independently drawn inner curves that pinch the
   4.5 mm strip: fail.
4. A filled underside, additional body, or changed 102 × 42 section envelope:
   fail.

These capture the previous model's actual mistakes; successful CAD/mesh checks
alone did not establish that it matched the reference.
