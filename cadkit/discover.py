"""Finding projects and importing the models inside them.

Project folders go on `sys.path` rather than being packages, so a model can
import its siblings by bare name (`import collar`) and still be runnable as a
plain script. The cost is that module names are only unique within a project,
which `project_path` is careful to contain.
"""

from __future__ import annotations

import importlib
import sys
from contextlib import contextmanager, suppress
from pathlib import Path

from cadkit.export import PROJECTS


def projects() -> list[Path]:
    """Every project folder, alphabetically."""
    if not PROJECTS.is_dir():
        return []
    return sorted(
        p for p in PROJECTS.iterdir() if p.is_dir() and not p.name.startswith(".")
    )


def find_project(name: str) -> Path:
    """Resolve a project name, with the available ones in the error."""
    for project in projects():
        if project.name == name:
            return project
    available = ", ".join(p.name for p in projects()) or "none"
    raise SystemExit(f"no such project: {name}\navailable: {available}")


def model_files(project: Path) -> list[Path]:
    """Candidate model files, alphabetically.

    Whether a file is really a model is only decided after import, by whether it
    defines `build()`. Leading-underscore files are helpers and are never even
    considered.
    """
    return sorted(p for p in project.glob("*.py") if not p.name.startswith("_"))


@contextmanager
def project_path(project: Path):
    """Put a project folder on sys.path, and take its modules back off after.

    The purge is the point. Without it, two projects that each contain a
    `plate.py` would share whichever was imported first — no error, no warning,
    and the wrong geometry exported under the right filename.
    """
    project = project.resolve()
    before = set(sys.modules)
    sys.path.insert(0, str(project))
    try:
        yield project
    finally:
        with suppress(ValueError):
            sys.path.remove(str(project))
        for name in list(sys.modules.keys() - before):
            origin = getattr(sys.modules.get(name), "__file__", None)
            if origin and Path(origin).resolve().is_relative_to(project):
                del sys.modules[name]


def load(name: str):
    """Import a model module. Only valid inside `project_path`."""
    return importlib.import_module(name)


def is_model(module) -> bool:
    return callable(getattr(module, "build", None))
