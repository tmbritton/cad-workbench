"""Assertions a model can make about itself.

A model that builds is not a model that is correct. Every one of these exists
because the corresponding failure produces geometry that exports without
complaint and is only discovered on the plate, hours later.

Use them from a model's `check()`:

    def check(part):
        single_solid(part)
        fits_bed(part)
"""

from __future__ import annotations

from pathlib import Path

from cadkit import printer
from cadkit.select import shape


def single_solid(obj) -> None:
    """The part must be one connected lump.

    The classic failure is a shell or a boolean that leaves two pieces touching
    at nothing — an open collar whose lip never actually joins its wall. Both
    halves are valid solids, the STL exports cleanly, and the slicer prints two
    unconnected rings.
    """
    solids = shape(obj).solids()
    if len(solids) != 1:
        vols = ", ".join(f"{s.volume / 1000:.1f} cm3" for s in solids)
        raise AssertionError(
            f"expected one connected solid, got {len(solids)} ({vols}) — "
            "some feature is not joined to the rest of the part"
        )


def fits_bed(obj, margin: float = 0.0) -> None:
    """The part must fit the build volume in the orientation it is modelled in.

    `margin` shrinks the envelope, for a brim or for keeping clear of the
    gantry at the edges of the plate.
    """
    ok, message = bed_fit(shape(obj), margin)
    if not ok:
        raise AssertionError(message)


def bed_fit(obj, margin: float = 0.0) -> tuple[bool, str]:
    """`fits_bed` without raising — returns (ok, explanation).

    The build driver calls this on every model and warns rather than failing,
    because a part deliberately modelled oversized for later splitting is a
    legitimate thing to have in the tree.
    """
    size = shape(obj).bounding_box().size
    limits = (
        printer.BUILD_X - 2 * margin,
        printer.BUILD_Y - 2 * margin,
        printer.BUILD_Z - margin,
    )
    got = (size.X, size.Y, size.Z)
    over = [
        f"{axis} {g:.1f} > {lim:.1f}"
        for axis, g, lim in zip("XYZ", got, limits, strict=True)
        if g > lim
    ]
    if not over:
        return True, ""

    hint = ""
    if size.X <= limits[1] and size.Y <= limits[0] and size.Z <= limits[2]:
        hint = " — rotating 90 degrees about Z would fit"
    return False, (
        f"exceeds the {printer.NAME} build volume "
        f"({printer.BUILD_X:.0f} x {printer.BUILD_Y:.0f} x {printer.BUILD_Z:.0f}): "
        f"{', '.join(over)}{hint}"
    )


def watertight(
    stl_path: str | Path,
    volume_mm3: float | None = None,
    tol: float = 0.005,
    bodies: int = 1,
) -> None:
    """The exported mesh must be printable, not merely well-formed.

    Checks the STL rather than the B-rep, because the tessellation is what the
    slicer actually sees. A mesh can be non-manifold, have inverted normals, or
    have split into several bodies during triangulation while the solid it came
    from was fine.

    Passing `volume_mm3` (the solid's own volume) also catches the subtler
    case: a mesh that is watertight and manifold but encloses a different
    amount of space than the model does, which means the tessellation dropped
    or duplicated a face.

    `bodies` is how many separate lumps the mesh should contain. One is the
    right default for a part, but a print-in-place assembly is several on
    purpose — a bearing prints as two races and a ring of rolling elements that
    never touch. Pass the solid's own count and the check becomes what it was
    always trying to be: the tessellation neither split a body nor welded two
    together. `single_solid` is still where a part says it must be one lump.
    """
    import trimesh  # imported lazily; only needed when this check is used

    mesh = trimesh.load_mesh(str(stl_path))

    # OCCT closes a surface of revolution at its poles with two zero-area
    # triangles — every sphere, cone or dome has them. They enclose nothing and
    # cannot seal a hole, but they read as unpaired edges, so without this a
    # ball bearing looks like a mesh full of holes and a real defect would be
    # lost in the noise. Dropped here rather than tolerated below, so
    # everything after this line is still judged strictly.
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()

    problems = []
    if not mesh.is_watertight:
        problems.append("not watertight (has holes or unpaired edges)")
    if not mesh.is_winding_consistent:
        problems.append("inconsistent winding (some normals are inverted)")
    if mesh.body_count != bodies:
        problems.append(f"{mesh.body_count} disconnected bodies, expected {bodies}")

    if volume_mm3 is not None and mesh.is_watertight:
        drift = abs(mesh.volume - volume_mm3) / volume_mm3
        if drift > tol:
            problems.append(
                f"mesh volume {mesh.volume / 1000:.1f} cm3 differs from the solid's "
                f"{volume_mm3 / 1000:.1f} cm3 by {drift:.1%} (tolerance {tol:.1%})"
            )

    if problems:
        raise AssertionError(f"{Path(stl_path).name}: " + "; ".join(problems))
