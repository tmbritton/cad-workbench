"""The three-line `__main__` every model ends with.

    if __name__ == "__main__":
        from cadkit import cli
        cli(build, check)

Running a model directly is for iterating; `mise build <project>` is for
producing files you will slice. Both go through `build_model`, so they write
identical geometry to identical paths.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cadkit.export import (
    GREEN,
    GREY,
    OFF,
    RED,
    ROOT,
    YELLOW,
    build_model,
    material_of,
)


def cli(build_fn, check_fn=None, argv: list[str] | None = None) -> int:
    """Build the calling module and report.

    Project and model name come from the file's own location, so a model never
    has to repeat where it lives — moving the file moves its exports with it.
    """
    main = sys.modules["__main__"]
    path = Path(getattr(main, "__file__", "") or "").resolve()
    if not path.name:
        raise RuntimeError("cli() must be called from a script, not an interactive shell")

    ap = argparse.ArgumentParser(description=(main.__doc__ or "").strip().splitlines()[0])
    ap.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="build and check, but write nothing",
    )
    args = ap.parse_args(argv)

    try:
        result = build_model(
            project=path.parent.name,
            name=path.stem,
            build_fn=build_fn,
            check_fn=check_fn,
            material=material_of(main),
            write=not args.dry_run,
        )
    except AssertionError as exc:
        print(f"{RED}FAIL{OFF} {path.stem}: {exc}", file=sys.stderr)
        return 1

    print(f"{GREEN}ok{OFF}   {result.line()}")
    for warning in result.warnings:
        print(f"{YELLOW}warn{OFF} {warning}")
    if not args.dry_run:
        rel = result.stl.parent.relative_to(ROOT)
        print(f"{GREY}     -> {rel}/{result.name}.{{stl,step}}{OFF}")
    return 0
