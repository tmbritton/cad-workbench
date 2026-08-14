#!/usr/bin/env python
"""Live-reloading viewer for the collar model.

Watches model/ and rebuilds on every save, pushing new geometry to a browser
viewer at http://localhost:32323. Edit in Neovim, `:w`, watch the part change.

The model stays free of viewer imports — collar.py is a pure function from
constants to geometry, and this script is the only thing that knows a viewer
exists. That keeps `mise run build` headless and the model testable.

    mise run watch
"""

from __future__ import annotations

import os
import socket
import sys
import traceback
from pathlib import Path

# yacv waits this long at *shutdown* for a browser to connect before giving up.
# The default is 12s of hanging on Ctrl-C; we want to exit promptly.
os.environ.setdefault("YACV_GRACEFUL_SECS_CONNECT", "0.5")
os.environ.setdefault("YACV_GRACEFUL_SECS_WORK", "0.5")

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "model"
HOST = os.getenv("YACV_HOST", "localhost")
PORT = int(os.getenv("YACV_PORT", "32323"))

GREY, GREEN, RED, OFF = "\033[90m", "\033[32m", "\033[31m", "\033[0m"


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
            print(f"  YACV_PORT=32324 mise run watch")
            raise SystemExit(1)


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


def main() -> None:
    preflight()

    # Imported only after preflight — see the note there.
    import importlib

    from watchfiles import watch
    from yacv_server import clear, show

    sys.path.insert(0, str(MODEL_DIR))
    import collar

    def rebuild() -> None:
        try:
            importlib.reload(collar)
            part = collar.build().part
        except Exception:
            print(f"{RED}build failed{OFF}")
            traceback.print_exc()
            print(f"{GREY}viewer still showing the last good version{OFF}")
            return
        clear()
        show(part.wrapped, names=["collar"])
        print(f"{GREEN}ok{OFF}  {describe(part)}")

    print(f"{GREY}watching{OFF} {MODEL_DIR.relative_to(ROOT)}/")
    rebuild()
    print(f"{GREY}viewer  {OFF} http://{HOST}:{PORT}")
    print(f"{GREY}stop    {OFF} Ctrl-C\n")

    try:
        for changes in watch(MODEL_DIR, watch_filter=lambda _c, p: p.endswith(".py")):
            names = sorted({Path(p).name for _, p in changes})
            print(f"{GREY}changed{OFF} {', '.join(names)}")
            rebuild()
    except KeyboardInterrupt:
        print(f"\n{GREY}stopping{OFF}")


if __name__ == "__main__":
    main()
