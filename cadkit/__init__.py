"""Shared helpers for every project in this workbench.

Small on purpose. Anything here is something more than one project needs, or a
check that has already caught a real mistake — geometry that is specific to one
part belongs in that part's file, where it can be read next to the dimension it
came from.
"""

from cadkit.checks import bed_fit, fits_bed, single_solid, watertight
from cadkit.cli import cli
from cadkit.select import cavity_ceiling, faces_by_z, horizontal_face_at, shape

__all__ = [
    "bed_fit",
    "cavity_ceiling",
    "cli",
    "faces_by_z",
    "fits_bed",
    "horizontal_face_at",
    "shape",
    "single_solid",
    "watertight",
]
