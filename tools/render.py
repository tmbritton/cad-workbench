#!/usr/bin/env python
"""Render an STL to PNG, without a GPU.

Offscreen GL is unavailable inside the Flatpak sandboxes on this machine, so
this does its own orthographic z-buffer rasterisation with numpy and writes the
image with Pillow. Flat shading, one key light plus fill, backface culling.

    mise run render                 # all views
    uv run python tools/render.py --view iso --out /tmp/x.png
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]

# azimuth, elevation in degrees
VIEWS = {
    "iso": (42.0, 26.0),
    "front": (0.0, 0.0),
    "side": (90.0, 0.0),
    "top": (0.0, 89.9),
    "under": (32.0, -34.0),
    # The coupon's corner sits at +X/+Y. The camera looks along +Y in the
    # rotated frame, so its world azimuth is -90 - az; -135 puts it on the
    # corner's outside rather than staring into the concave face.
    "corner": (225.0, 22.0),
    "corner-under": (215.0, -26.0),
}

BG = np.array([246, 247, 244], dtype=float)
FACE = np.array([170, 178, 172], dtype=float)
KEY = np.array([0.35, -0.55, 0.75])
FILL = np.array([-0.6, 0.3, 0.35])


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


def render(tris: np.ndarray, size: tuple[int, int], view: str) -> Image.Image:
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
    key = np.clip(ncam @ (KEY / np.linalg.norm(KEY)), 0, 1)
    fill = np.clip(ncam @ (FILL / np.linalg.norm(FILL)), 0, 1)
    shade = 0.20 + 0.68 * key + 0.22 * fill

    colour = np.clip(FACE[None, :] * shade[:, None], 0, 255)

    frame = np.tile(BG, (h, w, 1))
    zbuf = np.full((h, w), np.inf)

    order = np.argsort(-depth.mean(axis=1))
    for i in order:
        if not facing[i]:
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stl", default=str(ROOT / "model" / "collar.stl"))
    ap.add_argument("--view", default="all", choices=["all", *VIEWS])
    ap.add_argument("--out", default=None)
    ap.add_argument("--size", default="900x700")
    args = ap.parse_args()

    w, h = (int(v) for v in args.size.lower().split("x"))
    tris = load_stl(Path(args.stl))
    print(f"{len(tris):,} triangles")

    views = list(VIEWS) if args.view == "all" else [args.view]
    outdir = ROOT / "model" / "renders"
    outdir.mkdir(exist_ok=True)

    for v in views:
        img = render(tris, (w, h), v)
        dest = Path(args.out) if args.out else outdir / f"collar-{v}.png"
        img.save(dest)
        print(f"  {v:<6} -> {dest}")


if __name__ == "__main__":
    main()
