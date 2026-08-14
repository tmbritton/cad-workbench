#!/usr/bin/env python
"""Build every model in a project and export STEP and STL.

    mise build                        # every project
    mise build dehydrator-riser       # one project
    mise build dehydrator-riser ring  # one model

A model is any .py in a project folder, not starting with `_`, that defines
`build()`. Anything else is a helper: it can be imported by models in the same
folder, but is never exported.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from cadkit.discover import is_model, load, model_files, project_path, projects
from cadkit.export import (
    EXPORTS,
    GREEN,
    GREY,
    OFF,
    PROJECTS,
    RED,
    ROOT,
    YELLOW,
    build_model,
    material_of,
)


def build_project(project: Path, only: list[str], write: bool) -> tuple[int, int]:
    """Build the requested models in one project. Returns (built, failed)."""
    candidates = model_files(project)
    if only:
        wanted = {name.removesuffix(".py") for name in only}
        missing = wanted - {p.stem for p in candidates}
        if missing:
            names = ", ".join(sorted(missing))
            print(
                f"{RED}no such model in {project.name}: {names}{OFF}",
                file=sys.stderr,
            )
            return 0, len(missing)
        candidates = [p for p in candidates if p.stem in wanted]

    # Flushed, because failures below go to stderr as they happen while the
    # results table is printed at the end. Without this the header lands after
    # its own errors whenever stdout is piped.
    print(f"{GREY}{project.name}{OFF}", flush=True)

    results: list = []
    failed = 0
    skipped: list[str] = []

    with project_path(project):
        for path in candidates:
            try:
                module = load(path.stem)
            except Exception:
                print(f"{RED}FAIL{OFF} {path.stem}: import failed", file=sys.stderr)
                traceback.print_exc()
                failed += 1
                continue

            if not is_model(module):
                skipped.append(path.stem)
                continue

            try:
                results.append(
                    build_model(
                        project=project.name,
                        name=path.stem,
                        build_fn=module.build,
                        check_fn=getattr(module, "check", None),
                        material=material_of(module),
                        write=write,
                    )
                )
            except AssertionError as exc:
                print(f"{RED}FAIL{OFF} {path.stem}: {exc}", file=sys.stderr)
                failed += 1
            except Exception:
                print(f"{RED}FAIL{OFF} {path.stem}: build raised", file=sys.stderr)
                traceback.print_exc()
                failed += 1

    width = max((len(r.name) for r in results), default=0)
    for result in results:
        print(f"  {GREEN}ok{OFF}   {result.line(width)}")
        for warning in result.warnings:
            print(f"  {YELLOW}warn{OFF} {result.name}: {warning}")

    if skipped:
        print(f"  {GREY}helpers, not exported: {', '.join(skipped)}{OFF}")
    if results and write:
        print(f"  {GREY}-> {(EXPORTS / project.name).relative_to(ROOT)}/{OFF}")

    return len(results), failed


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join(__doc__.splitlines()[2:]),
    )
    ap.add_argument("project", nargs="?", help="project folder name; omit to build all")
    ap.add_argument(
        "models", nargs="*", help="model names; omit to build all in the project"
    )
    ap.add_argument(
        "-n", "--dry-run", action="store_true", help="build and check, but write nothing"
    )
    args = ap.parse_args()

    available = projects()
    if not available:
        print(f"{RED}no projects found in {PROJECTS}{OFF}", file=sys.stderr)
        return 1

    if args.project:
        chosen = [p for p in available if p.name == args.project]
        if not chosen:
            names = ", ".join(p.name for p in available)
            print(f"{RED}no such project: {args.project}{OFF}", file=sys.stderr)
            print(f"{GREY}available: {names}{OFF}", file=sys.stderr)
            return 1
    else:
        chosen = available

    built = failed = 0
    for project in chosen:
        b, f = build_project(project, args.models, write=not args.dry_run)
        built += b
        failed += f

    if failed:
        print(f"\n{RED}{failed} failed{OFF}, {built} built", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
