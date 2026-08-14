"""Build every model in the workspace and hold it to its own assertions.

This is not a unit-test suite — there is nothing here that a model does not
already claim about itself. What it adds is *breadth*: a change to `cadkit`, to
a shared dimension, or to build123d itself gets checked against every part in
the tree rather than the one that happened to be open.

Each model is a separate test so a failure names the part.
"""

from __future__ import annotations

import pytest

from cadkit.checks import watertight
from cadkit.discover import is_model, load, model_files, project_path, projects
from cadkit.export import build_model, material_of

CASES = [
    (project.name, path.stem) for project in projects() for path in model_files(project)
]


@pytest.mark.parametrize(
    ("project_name", "model_name"),
    CASES,
    ids=[f"{p}/{m}" for p, m in CASES],
)
def test_model(project_name: str, model_name: str) -> None:
    project = next(p for p in projects() if p.name == project_name)

    with project_path(project):
        module = load(model_name)
        if not is_model(module):
            pytest.skip(f"{model_name}.py is a helper, not a model")

        result = build_model(
            project=project_name,
            name=model_name,
            build_fn=module.build,
            check_fn=getattr(module, "check", None),
            material=material_of(module),
        )

    # The mesh, not the solid. A valid B-rep can still tessellate into
    # something the slicer chokes on, and the STL is what actually gets sliced.
    watertight(result.stl, volume_mm3=result.volume)


def test_workspace_has_projects() -> None:
    """Guards the discovery logic itself.

    Every test above is generated from `projects()`, so if discovery silently
    returned nothing the suite would pass with zero cases.
    """
    assert projects(), "no project folders found under projects/"
