#!/usr/bin/env python
"""Live-reloading viewer for one model.

Watches a project folder and rebuilds on every save, pushing new geometry to a
browser viewer at http://localhost:32323. Edit in Neovim, `:w`, watch the part
change.

    mise dev dehydrator-riser          # the project's default model
    mise dev dehydrator-riser coupon   # a named one

The task is `dev` rather than `watch` because mise has a built-in `watch` that
would shadow it. The file keeps the name that says what it does.

Models stay free of viewer imports — a model is a pure function from constants
to geometry, and this script is the only thing that knows a viewer exists. That
keeps `mise build` headless and the models testable.
"""

from __future__ import annotations

import argparse
import os
import socket
import traceback
from pathlib import Path

from cadkit.checks import bed_fit
from cadkit.discover import find_project, is_model, load, model_files, project_path
from cadkit.export import GREEN, GREY, OFF, RED, ROOT, YELLOW
from cadkit.select import shape

# yacv waits this long at *shutdown* for a browser to connect before giving up.
# The default is 12s of hanging on Ctrl-C; we want to exit promptly. Set here
# rather than in main() because it must land before `import yacv_server`.
os.environ.setdefault("YACV_GRACEFUL_SECS_CONNECT", "0.5")
os.environ.setdefault("YACV_GRACEFUL_SECS_WORK", "0.5")

HOST = os.getenv("YACV_HOST", "localhost")
PORT = int(os.getenv("YACV_PORT", "32323"))


def preflight() -> None:
    """Fail loudly if the port is taken.

    This must run *before* importing yacv_server, because that import starts an
    HTTP server as a side effect — on a background thread, where a bind failure
    would otherwise leave a watcher that looks healthy and serves nothing.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        # Match http.server, which sets allow_reuse_address. Without this the
        # check is stricter than the real bind and false-positives on a
        # TIME_WAIT socket left by the previous run.
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((HOST, PORT))
        except OSError:
            print(f"{RED}port {PORT} is already in use{OFF}")
            print(f"{GREY}another watcher is probably still running:{OFF}")
            print(f"  ss -ltnp | grep {PORT}")
            print(f"{GREY}or use a different port:{OFF}")
            print("  YACV_PORT=32324 mise dev <project>")
            raise SystemExit(1) from None


def describe(part) -> str:
    """The facts worth checking on every rebuild."""
    size = part.bounding_box().size
    solids = len(part.solids())
    warn = "" if solids == 1 else f"  {RED}<- expected 1{OFF}"
    return (
        f"{solids} solid  "
        f"{size.X:.1f} x {size.Y:.1f} x {size.Z:.1f} mm  "
        f"{part.volume / 1000:,.1f} cm3{warn}"
    )


def default_model(project: Path) -> str:
    """The model to show when the user names only a project.

    A model claims it by setting `DEFAULT = True`. Worth doing wherever the
    part someone actually wants to look at is not the one that happens to sort
    first: ball-bearing's assembled turntable is `turntable_post.py`, six files
    below `bearing.py`, and reaching for `mise dev ball-bearing` and getting a
    plain 26 mm ring is a papercut every time you come back to the project.

    Without the marker it is the first model alphabetically, which is the right
    answer for a project with one.
    """
    claimed, fallback = [], None
    with project_path(project):
        for path in model_files(project):
            try:
                module = load(path.stem)
            except Exception:
                # A model that will not import is the build driver's problem to
                # report, not this function's; it just cannot be the default.
                continue
            if not is_model(module):
                continue
            if getattr(module, "DEFAULT", False):
                claimed.append(path.stem)
            if fallback is None:
                fallback = path.stem

    if len(claimed) > 1:
        raise SystemExit(
            f"{project.name}: {' and '.join(claimed)} both set DEFAULT = True; "
            "one model may claim it, or none"
        )
    if claimed:
        return claimed[0]
    if fallback is None:
        raise SystemExit(f"{project.name} contains no model that defines build()")
    return fallback


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join(__doc__.splitlines()[2:]),
    )
    ap.add_argument("project", help="project folder name")
    ap.add_argument("model", nargs="?", help="model name; default is the project's first")
    args = ap.parse_args()

    project = find_project(args.project)
    name = (args.model or default_model(project)).removesuffix(".py")
    if not (project / f"{name}.py").is_file():
        raise SystemExit(f"no such model: {project.name}/{name}.py")

    preflight()

    # Imported only after preflight — see the note there.
    from watchfiles import watch
    from yacv_server import clear, show

    def rebuild() -> None:
        # Re-imported from scratch rather than reloaded: a model's siblings are
        # ordinary modules too, and reloading only the one that changed would
        # leave stale constants behind when a shared dimension moves.
        try:
            with project_path(project):
                module = load(name)
                if not is_model(module):
                    print(f"{RED}{name}.py defines no build(){OFF}")
                    return
                part = shape(module.build())
                check = getattr(module, "check", None)
                if check is not None:
                    check(part)
        except AssertionError as exc:
            print(f"{RED}check failed{OFF} {exc}")
            print(f"{GREY}viewer still showing the last good version{OFF}")
            return
        except Exception:
            print(f"{RED}build failed{OFF}")
            traceback.print_exc()
            print(f"{GREY}viewer still showing the last good version{OFF}")
            return

        clear()
        show(part.wrapped, names=[name])
        print(f"{GREEN}ok{OFF}  {describe(part)}")
        ok, message = bed_fit(part)
        if not ok:
            print(f"{YELLOW}warn{OFF} {message}")

    print(f"{GREY}watching{OFF} {project.relative_to(ROOT)}/  {GREY}showing{OFF} {name}")
    rebuild()
    print(f"{GREY}viewer  {OFF} http://{HOST}:{PORT}")
    print(f"{GREY}stop    {OFF} Ctrl-C\n")

    try:
        for changes in watch(project, watch_filter=lambda _c, p: p.endswith(".py")):
            names = sorted({Path(p).name for _, p in changes})
            print(f"{GREY}changed{OFF} {', '.join(names)}")
            rebuild()
    except KeyboardInterrupt:
        print(f"\n{GREY}stopping{OFF}")


if __name__ == "__main__":
    main()
