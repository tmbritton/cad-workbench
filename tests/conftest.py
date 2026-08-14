"""Scoping the suite to one project.

Every model in the workspace is a separate test, which is the right default —
a change to `cadkit` should be checked against every part in the tree. But it
is the wrong thing to be blocked by: an unfinished model in one project should
not stand between you and testing the project you are actually working on.

`--project` and `--model` deselect rather than skip, so a scoped run reports
only what it actually checked.
"""

from __future__ import annotations


def pytest_addoption(parser) -> None:
    parser.addoption(
        "--project",
        action="append",
        default=[],
        metavar="NAME",
        help="only test this project; repeatable",
    )
    parser.addoption(
        "--model",
        action="append",
        default=[],
        metavar="NAME",
        help="only test this model; repeatable",
    )


def pytest_collection_modifyitems(config, items) -> None:
    projects = set(config.getoption("--project"))
    models = set(config.getoption("--model"))
    if not (projects or models):
        return

    selected, deselected = [], []
    for item in items:
        callspec = getattr(item, "callspec", None)
        if callspec is None:
            # Unparametrised guards — the ones that check discovery itself
            # still found something. Cheap, and relevant to any scoped run.
            selected.append(item)
            continue

        params = callspec.params
        wrong_project = projects and params.get("project_name") not in projects
        wrong_model = models and params.get("model_name") not in models
        (deselected if wrong_project or wrong_model else selected).append(item)

    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = selected
