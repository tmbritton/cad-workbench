#!/usr/bin/env python
"""Build models and run their checks, optionally scoped to one project.

    mise test                          # every project
    mise test dehydrator-riser         # one project
    mise test dehydrator-riser collar  # one model
    mise test dehydrator-riser -x      # flags pass through to pytest

Same shape as `mise build`, deliberately: leading bare words name a project and
its models, and everything from the first `-` onward belongs to pytest.
"""

from __future__ import annotations

import sys

import pytest

from cadkit.discover import model_files, projects
from cadkit.export import GREY, OFF, RED


def split(argv: list[str]) -> tuple[list[str], list[str]]:
    """Bare words first, then everything from the first flag onward.

    A plain positional/optional split would swallow the argument of a pytest
    flag — `-k foo` would file `foo` as a model name. This rule needs no
    knowledge of pytest's options to get that right.
    """
    for i, arg in enumerate(argv):
        if arg.startswith("-"):
            return argv[:i], argv[i:]
    return argv, []


def main() -> int:
    if "-h" in sys.argv[1:] or "--help" in sys.argv[1:]:
        print(__doc__.strip())
        print("\npytest's own options follow the project and model names.")
        return 0

    names, passthrough = split(sys.argv[1:])
    project_name, model_names = (names[0], names[1:]) if names else (None, [])

    available = {p.name: p for p in projects()}
    if project_name and project_name not in available:
        print(f"{RED}no such project: {project_name}{OFF}", file=sys.stderr)
        print(f"{GREY}available: {', '.join(available) or 'none'}{OFF}", file=sys.stderr)
        return 1

    if model_names:
        known = {p.stem for p in model_files(available[project_name])}
        missing = sorted(set(model_names) - known)
        if missing:
            print(
                f"{RED}no such model in {project_name}: {', '.join(missing)}{OFF}",
                file=sys.stderr,
            )
            return 1

    argv = ["-q", *passthrough]
    if project_name:
        argv += ["--project", project_name]
    for model in model_names:
        argv += ["--model", model]

    return int(pytest.main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
