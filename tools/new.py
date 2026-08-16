#!/usr/bin/env python
"""Scaffold a new project folder.

    mise new spool-holder             # projects/spool-holder/spool_holder.py
    mise new spool-holder bracket     # projects/spool-holder/bracket.py

Writes a model already wired to the contract — `build()`, `check()`, and the
`__main__` stub — plus a README with the measurement tables empty and waiting.
Filling those in first is the point: a dimension that only exists inside the
Python is a dimension nobody can check against the real object.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date

from cadkit.export import GREEN, GREY, OFF, PROJECTS, RED, ROOT

MODEL_TEMPLATE = '''\
"""{title}.

All dimensions from README.md in this folder.

Describe the part in a sentence: what it mates with, which way up it prints,
and what would make it wrong.
"""

from build123d import BuildPart, BuildSketch, Rectangle, extrude

from cadkit import fits_bed, single_solid
from cadkit.materials import ASA

MATERIAL = ASA

# ---- measured -------------------------------------------------------------
# Dimensions taken off the real object with calipers. Never off a photo.

# ---- decided --------------------------------------------------------------
# Choices, each with the reason it was chosen.
WALL = 1.8

# ---- derived --------------------------------------------------------------
# Anything computed from the above. Say what it is derived from, and why.


def build() -> BuildPart:
    """The part."""
    with BuildPart() as part:
        with BuildSketch():
            Rectangle(40, 20)
        extrude(amount=WALL)

    return part


def check(part) -> None:
    """What must be true, or this should not reach the plate.

    Assert the dimensions that mate, not the ones that are merely convenient —
    a check that restates the code catches nothing.
    """
    single_solid(part)
    fits_bed(part)


if __name__ == "__main__":
    from cadkit import cli

    raise SystemExit(cli(build, check))
'''

README_TEMPLATE = """\
# {title}

Started {today}. One sentence on what this part is for and what it has to fit.

## Measured

Taken off the real object with calipers.

| Dimension | Value | Notes |
|---|---|---|
| | | |

## Decided

Choices, each with its reason.

| Dimension | Value | Why |
|---|---|---|
| Wall | 1.8 mm | |

## Derived

Computed from the above. Anything here that a model hard-codes instead is a bug
waiting to happen.

| Dimension | Value | From |
|---|---|---|
| | | |

## Models

| File | What it is |
|---|---|
| `{module}.py` | |

## Print settings

Filament, orientation, supports, brim — and which of these were *validated* on a
test print rather than assumed.

## Open questions

-
"""


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")


def module_name(text: str) -> str:
    name = re.sub(r"[^a-z0-9_]+", "_", text.strip().lower()).strip("_")
    if not name or name[0].isdigit():
        raise SystemExit(f"{name!r} is not a usable Python module name")
    return name


def title(text: str) -> str:
    return text.replace("-", " ").replace("_", " ").capitalize()


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join(__doc__.splitlines()[2:]),
    )
    ap.add_argument("project", help="project folder name, e.g. spool-holder")
    ap.add_argument(
        "model",
        nargs="?",
        help="first model's name; defaults to the project name",
    )
    args = ap.parse_args()

    project_name = slug(args.project)
    if not project_name:
        print(
            f"{RED}{args.project!r} leaves nothing to name a folder{OFF}", file=sys.stderr
        )
        return 1

    # The folder can be kebab-case; the model cannot. Project folders go on
    # sys.path and models import each other by bare name, so a hyphen in a
    # module name makes it unimportable.
    model = module_name(args.model or project_name)

    project = PROJECTS / project_name
    if project.exists():
        print(f"{RED}projects/{project_name}/ already exists{OFF}", file=sys.stderr)
        return 1

    project.mkdir(parents=True)
    written = []

    model_path = project / f"{model}.py"
    model_path.write_text(MODEL_TEMPLATE.format(title=title(model)))
    written.append(model_path)

    readme = project / "README.md"
    readme.write_text(
        README_TEMPLATE.format(
            title=title(project_name), today=date.today().isoformat(), module=model
        )
    )
    written.append(readme)

    for path in written:
        print(f"{GREEN}new{OFF}  {path.relative_to(ROOT)}")
    print(f"{GREY}     mise build {project_name}{OFF}")
    print(f"{GREY}     mise dev {project_name}{OFF}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
