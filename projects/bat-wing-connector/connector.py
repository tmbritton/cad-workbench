"""Bat-wing PVC finger connector.

Part of a bat puppet's wing: the "arm" (1/2" PVC) and four "fingers"
(1/4" PVC) emerge as short collars from a broad circular palm. The fingers
fan around one side of the palm (`Wing.wrist_angle`,
`Wing.finger_angle_step`), matching the connector's top-view sketch.

Every socket is a blind pocket, not a through-bore. Sockets used to share
one open, connected interior on purpose — so something could be threaded
from the trunk into any finger — but at this wide a fan that means support
material generated deep inside a sealed cavity with no way back out to clear
it. Blind pockets in a solid circular palm (`Wing.joint_r`/`joint_h`) traded
that option away for a part that can actually be cleaned up after printing.

Prints with the circular palm flat on the bed. The five radial collars are
horizontal and need support beneath their outer walls and inside their blind
pockets; every support remains reachable directly from a socket mouth.

    mise dev   bat-wing-connector
    mise build bat-wing-connector
"""

from __future__ import annotations

from _wing import Wing, check_wing, solid
from build123d import Part

from cadkit.materials import PETG

# Indoor puppet part, no UV or heat case that would want ASA's extra warp
# resistance over PETG's easier print.
MATERIAL = PETG

SPEC = Wing()

# Laying the broad palm flat gives the part a stable full-face footprint, but
# leaves every radial collar horizontal. Slicer supports beneath and inside
# them are reachable from their open mouths because the pockets are blind and
# separate, not one sealed shared interior. Not yet validated on a print;
# `mise slice` costs the support material in once it is.
SUPPORT = True
ALLOW = {
    "unsupported": (
        "the five horizontal socket collars are printed on slicer-generated "
        "supports, removable through each open mouth because every pocket is "
        "blind and separate; not yet validated on a print"
    )
}


def build() -> Part:
    return solid(SPEC)


def check(part) -> None:
    check_wing(part, SPEC)


if __name__ == "__main__":
    from cadkit import cli

    raise SystemExit(cli(build, check))
