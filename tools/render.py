#!/usr/bin/env python
"""Render a project's exported STLs to PNG, without a GPU.

Offscreen GL is unavailable inside the Flatpak sandboxes on this machine, so
this does its own orthographic z-buffer rasterisation with numpy and writes the
image with Pillow. Flat shading, one key light plus fill, backface culling.

    mise render dehydrator-riser                  # every model, every view
    mise render dehydrator-riser collar           # one model
    mise render dehydrator-riser collar -v iso    # one view
    mise render dehydrator-riser collar --section y     # cut through the middle
    mise render dehydrator-riser collar --section z=20  # cut at a height

`--section` cuts the part on a plane and keeps the near half, so a cavity, a
counterbore or the gap in a print-in-place assembly can be seen. With no value
it cuts through the middle of the part on that axis. The exposed interior is
shaded warmer than the outside, because otherwise a cut part and a hollow one
look the same.

Reads from exports/<project>/ and writes to exports/<project>/renders/, so it
runs after `mise build`, not instead of it.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from cadkit.export import EXPORTS, GREY, OFF, RED, ROOT

# azimuth, elevation in degrees
VIEWS = {
    "iso": (42.0, 26.0),
    "front": (0.0, 0.0),
    "side": (90.0, 0.0),
    "top": (0.0, 89.9),
    "under": (32.0, -34.0),
    # For a part cut down to one corner at +X/+Y: puts the camera on the
    # corner's outside rather than staring into the concave face.
    "corner": (225.0, 22.0),
    "corner-under": (215.0, -26.0),
}

BG = np.array([246, 247, 244], dtype=float)
FACE = np.array([170, 178, 172], dtype=float)
# What a section cut reveals: the inside of the far wall, which is a surface
# facing away from the camera and would otherwise be culled. Warmer and darker
# than the outside, so a cut-open render reads as cut open at a glance rather
# than as a part that has gone strangely concave.
CUT = np.array([196, 150, 120], dtype=float)
KEY = np.array([0.35, -0.55, 0.75])
FILL = np.array([-0.6, 0.3, 0.35])

AXIS = {"x": 0, "y": 1, "z": 2}


def clip(tris: np.ndarray, axis: int, at: float, above: bool) -> np.ndarray:
    """Keep one half of the geometry, cutting the triangles that straddle.

    A triangle across the plane becomes one or two new ones, so the cut edge is
    exact rather than ragged at triangle boundaries. Nothing caps the opening:
    the renderer stops culling back faces instead, which shows the inside of
    the far wall and is both cheaper and more honest — a cap would draw a
    surface the part does not have.

    Which half survives is the caller's business and it is not a preference.
    The half to keep is the one *away* from the camera, or the cut opens
    backwards and the render is indistinguishable from the uncut part.
    """
    keep = tris[:, :, axis] >= at if above else tris[:, :, axis] <= at
    count = keep.sum(axis=1)

    out = [tris[count == 3]]
    for tri, mask, n in zip(
        tris[(count == 1) | (count == 2)],
        keep[(count == 1) | (count == 2)],
        count[(count == 1) | (count == 2)],
        strict=True,
    ):
        inside = [tri[i] for i in range(3) if mask[i]]
        outside = [tri[i] for i in range(3) if not mask[i]]

        def cross(a, b):
            t = (at - a[axis]) / (b[axis] - a[axis])
            return a + t * (b - a)

        if n == 1:
            a = inside[0]  # one corner survives: one new triangle
            out.append(np.array([[a, cross(a, outside[0]), cross(a, outside[1])]]))
        else:
            a, b = inside
            pa, pb = cross(a, outside[0]), cross(b, outside[0])
            out.append(np.array([[a, b, pb], [a, pb, pa]]))

    stacked = [o for o in out if len(o)]
    return np.concatenate(stacked) if stacked else np.zeros((0, 3, 3))


def load_stl(path: Path) -> np.ndarray:
    """Return an (n, 3, 3) array of triangle vertices from a binary STL."""
    data = path.read_bytes()
    if data[:5] == b"solid" and b"facet" in data[:512]:
        raise ValueError("ASCII STL not supported; export binary")
    (count,) = struct.unpack("<I", data[80:84])
    rec = np.frombuffer(data, dtype=np.uint8, count=count * 50, offset=84)
    rec = rec.reshape(count, 50)
    verts = rec[:, 12:48].copy().view("<f4").reshape(count, 3, 3)
    return verts.astype(float)


def rotation(azimuth: float, elevation: float) -> np.ndarray:
    a, e = np.radians(azimuth), np.radians(elevation)
    rz = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
    rx = np.array([[1, 0, 0], [0, np.cos(e), -np.sin(e)], [0, np.sin(e), np.cos(e)]])
    # world -> camera: spin about Z, then tip about X
    return rx @ rz


def render(
    tris: np.ndarray, size: tuple[int, int], view: str, two_sided: bool = False
) -> Image.Image:
    w, h = size
    rot = rotation(*VIEWS[view])

    centre = (tris.reshape(-1, 3).min(0) + tris.reshape(-1, 3).max(0)) / 2
    cam = (tris - centre) @ rot.T

    # Orthographic fit with a margin.
    lo, hi = cam.reshape(-1, 3).min(0), cam.reshape(-1, 3).max(0)
    span = max(hi[0] - lo[0], hi[2] - lo[2]) * 1.12
    scale = min(w, h) / span

    # Screen space: x right, z up (y is depth, into the screen).
    sx = cam[:, :, 0] * scale + w / 2
    sy = h / 2 - cam[:, :, 2] * scale
    depth = cam[:, :, 1]

    e1 = tris[:, 1] - tris[:, 0]
    e2 = tris[:, 2] - tris[:, 0]
    normals = np.cross(e1, e2)
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = np.divide(normals, lengths, out=np.zeros_like(normals), where=lengths > 0)
    ncam = normals @ rot.T

    facing = ncam[:, 1] < 0  # normal pointing toward the camera

    # After a cut, the surfaces worth seeing are the ones facing away: the
    # inside of the far wall. Light them by their flipped normal, or they come
    # out uniformly black and the interior reads as a hole.
    lit = np.where(facing[:, None], ncam, -ncam)
    key = np.clip(lit @ (KEY / np.linalg.norm(KEY)), 0, 1)
    fill = np.clip(lit @ (FILL / np.linalg.norm(FILL)), 0, 1)
    shade = 0.20 + 0.68 * key + 0.22 * fill

    base = np.where(facing[:, None], FACE[None, :], CUT[None, :])
    colour = np.clip(base * shade[:, None], 0, 255)

    frame = np.tile(BG, (h, w, 1))
    zbuf = np.full((h, w), np.inf)

    order = np.argsort(-depth.mean(axis=1))
    for i in order:
        if not (facing[i] or two_sided):
            continue
        x0, x1 = sx[i], sy[i]
        xmin = max(int(np.floor(x0.min())), 0)
        xmax = min(int(np.ceil(x0.max())) + 1, w)
        ymin = max(int(np.floor(x1.min())), 0)
        ymax = min(int(np.ceil(x1.max())) + 1, h)
        if xmin >= xmax or ymin >= ymax:
            continue

        px, py = np.meshgrid(
            np.arange(xmin, xmax) + 0.5, np.arange(ymin, ymax) + 0.5, indexing="xy"
        )
        ax, ay = x0[0], x1[0]
        bx, by = x0[1], x1[1]
        cx, cy = x0[2], x1[2]
        det = (by - ay) * (cx - ax) - (bx - ax) * (cy - ay)
        if abs(det) < 1e-12:
            continue
        l0 = ((by - ay) * (px - ax) - (bx - ax) * (py - ay)) / det
        l1 = ((ay - cy) * (px - ax) - (ax - cx) * (py - ay)) / det
        l2 = 1.0 - l0 - l1
        inside = (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
        if not inside.any():
            continue

        zt = depth[i]
        z = l2 * zt[0] + l1 * zt[1] + l0 * zt[2]
        sub = zbuf[ymin:ymax, xmin:xmax]
        hit = inside & (z < sub)
        if not hit.any():
            continue
        sub[hit] = z[hit]
        frame[ymin:ymax, xmin:xmax][hit] = colour[i]

    return Image.fromarray(frame.astype(np.uint8), "RGB")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join(__doc__.splitlines()[2:]),
    )
    ap.add_argument("project", help="project folder name")
    ap.add_argument("models", nargs="*", help="model names; omit to render all")
    ap.add_argument("-v", "--view", default="all", choices=["all", *VIEWS])
    ap.add_argument("--size", default="900x700", help="pixels, WxH (default 900x700)")
    ap.add_argument(
        "--section",
        metavar="AXIS[=MM]",
        help="cut on x, y or z and keep the near half; omit =MM to cut at the middle",
    )
    args = ap.parse_args()

    cut = None
    if args.section:
        name, _, where = args.section.lower().partition("=")
        if name not in AXIS:
            print(f"{RED}--section takes x, y or z, not {name!r}{OFF}", file=sys.stderr)
            return 1
        cut = (AXIS[name], float(where) if where else None)

    exported = EXPORTS / args.project
    if not exported.is_dir():
        print(
            f"{RED}nothing exported for {args.project}{OFF}\n"
            f"{GREY}run: mise build {args.project}{OFF}",
            file=sys.stderr,
        )
        return 1

    stls = sorted(exported.glob("*.stl"))
    if args.models:
        wanted = {m.removesuffix(".stl") for m in args.models}
        stls = [p for p in stls if p.stem in wanted]
        missing = wanted - {p.stem for p in stls}
        if missing:
            print(
                f"{RED}not exported: {', '.join(sorted(missing))}{OFF}\n"
                f"{GREY}run: mise build {args.project}{OFF}",
                file=sys.stderr,
            )
            return 1
    if not stls:
        print(f"{RED}no STLs in {exported.relative_to(ROOT)}{OFF}", file=sys.stderr)
        return 1

    w, h = (int(v) for v in args.size.lower().split("x"))
    views = list(VIEWS) if args.view == "all" else [args.view]
    outdir = exported / "renders"
    outdir.mkdir(parents=True, exist_ok=True)

    for stl in stls:
        tris = load_stl(stl)
        print(f"{stl.stem}  {GREY}{len(tris):,} triangles{OFF}")

        at = None
        if cut is not None:
            axis, at = cut
            if at is None:
                flat = tris.reshape(-1, 3)[:, axis]
                at = float((flat.min() + flat.max()) / 2)
            print(f"  {GREY}cut at {'xyz'[axis]}={at:g}{OFF}")

        for view in views:
            shown, suffix = tris, ""
            if cut is not None:
                # The camera sits at -Y in camera space and looks toward +Y, so
                # the world direction it looks along is the second row of the
                # rotation. Keep whichever half is behind the cut *from here*,
                # and the same command gives a useful picture from every angle.
                looking = rotation(*VIEWS[view]).T @ np.array([0.0, 1.0, 0.0])
                shown = clip(tris, axis, at, above=looking[axis] > 0)
                suffix = f"-cut-{'xyz'[axis]}{at:g}"
                if not len(shown):
                    print(f"  {view:<12} {RED}the cut removes the whole part{OFF}")
                    continue

            dest = outdir / f"{stl.stem}{suffix}-{view}.png"
            render(shown, (w, h), view, two_sided=cut is not None).save(dest)
            print(f"  {view:<12} -> {dest.relative_to(ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
