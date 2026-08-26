"""Turning a solid into the triangles a slicer will actually see.

The B-rep is what a model is written against; the mesh is what gets printed.
Most of the questions in `cadkit.dfm` are questions about the mesh, because
"will this overhang need support" is answered by the same triangle normals the
slicer reads, not by the analytic surface they were sampled from.

Everything here funnels through `_clean`, so the one OCCT quirk that would
otherwise poison every mesh-level judgement is dealt with in a single place.
"""

from __future__ import annotations

from pathlib import Path

# Matches `export_stl`'s default, so the mesh a check reasons about is the mesh
# the exported file contains. Diverging here would mean passing a check on a
# tessellation nobody ever slices.
TOLERANCE = 1e-3
ANGULAR_TOLERANCE = 0.1


def _clean(mesh):
    """Drop OCCT's pole triangles and weld the result.

    OCCT closes a surface of revolution at its poles with two zero-area
    triangles — every sphere, cone or dome has them. They enclose nothing and
    cannot seal a hole, but they read as unpaired edges, so without this a ball
    bearing looks like a mesh full of holes and a real defect is lost in the
    noise. Dropped rather than tolerated, so every judgement made afterwards is
    still made strictly.
    """
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()
    return mesh


def from_stl(path: str | Path):
    """Load an exported STL as a cleaned trimesh."""
    import trimesh  # imported lazily; build123d alone does not need it

    return _clean(trimesh.load_mesh(str(path)))


def from_part(part, tolerance: float = TOLERANCE):
    """Tessellate a solid to a cleaned trimesh, without writing a file.

    `mise check` runs on parts that were never exported — a model being
    iterated on, or one whose `check()` is expected to fail — so the mesh has
    to be reachable from the solid in memory rather than from `exports/`.
    """
    import numpy as np
    import trimesh

    from cadkit.select import shape

    vertices, faces = shape(part).tessellate(tolerance, ANGULAR_TOLERANCE)
    return _clean(
        trimesh.Trimesh(
            vertices=np.array([(v.X, v.Y, v.Z) for v in vertices], dtype=float),
            faces=np.array(faces, dtype=np.int64),
            process=False,
        )
    )


def regions(mesh, mask):
    """Group the triangles selected by `mask` into connected patches.

    A rule that reports "1400 mm2 of overhang" says nothing actionable; one
    that reports "the largest unsupported patch is 62 mm across, at z=14" says
    where to look. Connectivity is taken from shared edges, so two roofs at the
    same height stay two roofs.

    Yields boolean masks, largest patch first.
    """
    import numpy as np
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    chosen = np.flatnonzero(mask)
    if chosen.size == 0:
        return []

    # face_adjacency lists pairs of triangles sharing an edge. Keeping only the
    # pairs where both sides are selected is what stops a patch leaking across
    # the unselected geometry between two separate patches.
    index = np.full(len(mesh.faces), -1, dtype=np.int64)
    index[chosen] = np.arange(chosen.size)
    pairs = mesh.face_adjacency
    both = index[pairs[:, 0]] >= 0
    both &= index[pairs[:, 1]] >= 0
    edges = index[pairs[both]]

    graph = coo_matrix(
        (np.ones(len(edges)), (edges[:, 0], edges[:, 1])),
        shape=(chosen.size, chosen.size),
    )
    count, labels = connected_components(graph, directed=False)

    out = []
    for label in range(count):
        patch = np.zeros(len(mesh.faces), dtype=bool)
        patch[chosen[labels == label]] = True
        out.append(patch)
    out.sort(key=lambda p: -mesh.area_faces[p].sum())
    return out


def boundary(mesh, mask):
    """The edges of a patch that no second patch triangle shares.

    Where the patch stops being the patch — the rim of a hole ceiling, the free
    end of a cantilever. Both of the questions worth asking about an
    unsupported region are asked of this outline rather than of its interior.
    """
    import numpy as np

    edges = np.sort(mesh.faces[mask][:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2), axis=1)
    unique, counts = np.unique(edges, axis=0, return_counts=True)
    return unique[counts == 1]


def held_rim(mesh, mask):
    """The boundary edges of a patch where a wall carries on down.

    The dihedral tells them apart. Where a down-facing roof meets the bore wall
    that holds it up, the solid turns through more than a straight angle — a
    concave edge. Where the underside of an arm sticking out of a post runs out
    of arm, it meets the end face at a convex one, and there is nothing on the
    far side of it. An arch over a through-hole has no edge at all: the surface
    keeps tilting until it is a wall, and a smooth rim is held for the same
    reason a concave one is.

    Purely local, and it needs no ray casting. Probing outward and downward
    instead — the obvious approach — gets the arch wrong, which is the shape
    this repo's imported PVC fitting is mostly made of.

    Returns (held edges as vertex-index pairs, held share of the rim by length).
    """
    import numpy as np

    pairs = mesh.face_adjacency
    if len(pairs) == 0:
        return np.zeros((0, 2), dtype=np.int64), 0.0

    inside = mask[pairs]
    rim = inside[:, 0] ^ inside[:, 1]  # exactly one side of the edge is ours
    if not rim.any():
        return np.zeros((0, 2), dtype=np.int64), 0.0

    edges = mesh.face_adjacency_edges[rim]
    convex = mesh.face_adjacency_convex[rim]
    length = np.linalg.norm(
        mesh.vertices[edges[:, 0]] - mesh.vertices[edges[:, 1]], axis=1
    )
    total = length.sum()
    share = float(length[~convex].sum() / total) if total > 0 else 0.0
    return edges[~convex], share


def reach(mesh, mask, step: float = 0.5):
    """How far the plastic has to travel from the nearest thing holding it up.

    The one number that decides whether an unsupported patch is a bridge or a
    bird's nest, and it is the same number for both: a hole ceiling held all
    round reads as its own diameter, an arm sticking fifty millimetres out of a
    post reads as a hundred, and the difference between them needs no second
    rule.

    Measured as the greatest distance from anywhere on the patch to the nearest
    held rim, doubled — because a patch held on two sides is crossed from both
    of them at once. A patch with nothing holding it anywhere is unbounded.

    Returns (reach in mm, held share of the rim by length).
    """
    import numpy as np
    from scipy.spatial import cKDTree

    edges, share = held_rim(mesh, mask)
    if len(edges) == 0:
        return float("inf"), 0.0

    # Walk the held edges at `step` so a long straight edge is as well
    # represented as a tessellated curve.
    a, b = mesh.vertices[edges[:, 0], :2], mesh.vertices[edges[:, 1], :2]
    length = np.linalg.norm(b - a, axis=1)
    counts = np.maximum(1, np.ceil(length / step).astype(int))
    points = np.concatenate(
        [
            a[i] + np.linspace(0, 1, counts[i], endpoint=False)[:, None] * (b[i] - a[i])
            for i in range(len(edges))
        ]
    )

    # Centroids and vertices both: on a coarsely tessellated roof the centroid
    # grid alone misses the middle of the span by a fifth.
    inside = np.vstack(
        [
            mesh.triangles_center[mask][:, :2],
            mesh.vertices[mesh.faces[mask]].reshape(-1, 3)[:, :2],
        ]
    )
    return float(cKDTree(points).query(inside)[0].max() * 2), share
