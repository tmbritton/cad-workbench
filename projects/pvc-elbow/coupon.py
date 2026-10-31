"""One full-depth elbow socket for a cheap pipe fit test.

This is the actual elbow with the other leg and most of the gusset trimmed
away. It retains the same 16.4 mm bore, 30 mm blind pocket, top screw opening,
horizontal print orientation and flattened underside as the full elbow. The
earlier trial coupon with this bore fitted the 14.6 mm pipe in ASA; the parent
now uses that successful bore too.

    mise build pvc-elbow coupon
"""

from __future__ import annotations

import math

import elbow
from build123d import Align, Box, Part, Pos

from cadkit import fits_bed, single_solid

MATERIAL = elbow.MATERIAL
SUPPORT = elbow.SUPPORT
ALLOW = {
    "unsupported": (
        "the horizontal test socket needs slicer supports removable through "
        "its mouth, exactly as on the parent elbow; not yet verified by a print"
    )
}


def build() -> Part:
    """Trim the elbow to one complete socket without changing its fit."""
    start = elbow.SOCKET_ROOT - elbow.WALL
    half_width = elbow.OUTER_R + 1
    window = Pos(start, -half_width, -1) * Box(
        elbow.REACH - start + 1,
        2 * half_width,
        elbow.TOP_Z + 2,
        align=(Align.MIN, Align.MIN, Align.MIN),
    )
    return elbow.build() & window


def check(part: Part) -> None:
    single_solid(part)
    fits_bed(part)
    mouth = [
        face
        for face in part.faces()
        if abs(face.center().X - elbow.REACH) < 1e-3 and len(face.wires()) == 2
    ]
    assert len(mouth) == 1, "fit coupon must retain the full socket mouth"
    inner = min(mouth[0].wires(), key=lambda wire: wire.length)
    bore_d = inner.length / math.pi
    assert abs(bore_d - elbow.SOCKET_D) < 1e-2, (
        f"fit coupon socket ID {bore_d:.2f} mm, wanted {elbow.SOCKET_D:.2f} mm"
    )
    floor = [
        face
        for face in part.faces()
        if abs(face.center().X - elbow.SOCKET_ROOT) < 1e-3
        and abs(face.area - math.pi * elbow.SOCKET_R**2) < 1e-2
    ]
    assert len(floor) == 1, "fit coupon must retain the blind pocket floor"
    depth = mouth[0].center().X - floor[0].center().X
    assert abs(depth - elbow.SOCKET_DEPTH) < 1e-3, (
        f"fit coupon insertion is {depth:.2f} mm, wanted {elbow.SOCKET_DEPTH:.2f} mm"
    )
    assert not part.is_inside(
        (elbow.REACH - elbow.SCREW_FROM_MOUTH, 0, elbow.TOP_Z - elbow.WALL / 2)
    ), "fit coupon must retain the screw opening into the socket"


if __name__ == "__main__":
    from cadkit import cli

    raise SystemExit(cli(build, check))
