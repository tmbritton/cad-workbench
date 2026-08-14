"""The machine these parts are printed on.

One place for the numbers that constrain every project, so a model can assert
against them instead of the constraint being discovered in the slicer.
"""

from __future__ import annotations

NAME = "Bambu Lab H2S"

# Build volume, mm. Nothing larger than this can be printed in one piece.
BUILD_X = 340.0
BUILD_Y = 320.0
BUILD_Z = 340.0

# Single nozzle: every filament change is a full purge, so multi-material on
# this machine costs time and waste rather than being free.
NOZZLES = 1
NOZZLE_D = 0.4

# Enclosed, with an actively heated chamber. This is why a filament choice is
# not purely about the part: the chamber temperature also has to be survivable
# by whatever is sitting in the feed path.
CHAMBER_MAX_C = 65.0
HOTEND_MAX_C = 350.0
BED_MAX_C = 120.0

# Extrusion width follows the nozzle, so wall thickness wants to be a multiple
# of it. Below two perimeters a wall is a single bead and behaves like one.
LINE_W = 0.42
MIN_WALL = 2 * LINE_W  # 0.84 — printable
SOUND_WALL = 4 * LINE_W  # 1.68 — the floor for anything structural

# Overhang steeper than this off vertical needs support.
MAX_OVERHANG_DEG = 45.0
