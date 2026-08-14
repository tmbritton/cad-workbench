"""Selectors that name geometry by what it is, not by where it landed in a list.

Indices into `part.faces()` are stable only until the next operation. A chamfer
rebuilds the topology and renumbers everything, so a model written against
`faces()[3]` breaks silently — it still builds, it just chamfers the wrong edge.
Everything here answers a question about the geometry instead.
"""

from __future__ import annotations

from build123d import Axis, Plane


def shape(obj):
    """Accept a builder or a shape and return the shape.

    Builder mode hands back a `BuildPart` whose geometry lives on `.part`;
    algebra mode hands back the `Part` directly. Callers should not have to
    care which style a model was written in.
    """
    return getattr(obj, "part", obj)


def faces_by_z(obj):
    """Every face parallel to XY, lowest first."""
    return shape(obj).faces().filter_by(Plane.XY).sort_by(Axis.Z)


def horizontal_face_at(obj, z: float, tol: float = 1e-6):
    """The single face parallel to XY whose centre sits at height `z`.

    Re-query this after every operation rather than holding onto the result:
    each chamfer or fillet replaces the faces it touches with new ones, and a
    face object from before the operation refers to geometry that no longer
    exists.
    """
    for face in faces_by_z(obj):
        if abs(face.center().Z - z) < tol:
            return face
    heights = ", ".join(f"{f.center().Z:.2f}" for f in faces_by_z(obj))
    raise ValueError(f"no horizontal face at z={z:.3f}; found faces at {heights}")


def cavity_ceiling(obj, tol: float = 1e-6) -> float:
    """Height of the lowest horizontal face above z=0.

    For an open collar or any shelled part sitting on the plate, this is the
    underside of the first web — the surface whatever goes inside seats
    against. Worth measuring rather than assuming: shelling lays a wall's worth
    of material under a step, so the cavity is one wall shallower than the step
    height that produced it.
    """
    for face in faces_by_z(obj):
        if face.center().Z > tol:
            return face.center().Z
    raise ValueError("no horizontal face above z=0; part has no cavity ceiling")
