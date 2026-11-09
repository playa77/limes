# desktop/src/limes_desktop/__main__.py | v1.1.0 | entry point: version, guard, loopback serve
"""CLI entry point for the LIMES web desktop launcher.

`limes-desktop` binds the loopback interface only (127.0.0.1). The
single-instance guard (NFR-DC-070) is an advisory lock taken before the
bind: a second invocation exits quietly when another launcher already
holds the guard — including a second launch with a different port
override, so "one desktop session" is a process-level rule, not a
per-port accident.

Credentials: `LIMES_OPERATOR_TOKEN` / `LIMES_API_TOKEN` from the
environment, or an interactive getpass prompt when stdin is a TTY and no
environment credential exists. Everything stays in process memory for one
session — the profile store and every response stay token-free.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from typing import TYPE_CHECKING

from limes_desktop.app import guard_instance

if TYPE_CHECKING:
    from collections.abc import Sequence


def _port() -> int:
    raw = os.environ.get("LIMES_DESKTOP_PORT", "").strip()
    if not raw:
        from limes_desktop.webapp import DEFAULT_PORT

        return DEFAULT_PORT
    try:
        port = int(raw)
    except ValueError as exc:
        raise SystemExit(f"LIMES_DESKTOP_PORT is not an integer: {raw!r}") from exc
    if not (1025 <= port <= 65535):
        raise SystemExit(f"LIMES_DESKTOP_PORT out of range 1025..65535: {port}")
    return port


def _credential() -> tuple[str, str] | None:
    """Session credential from the environment or an interactive prompt.

    Returns (token, kind). No file is read, nothing is echoed, and the
    profile store never receives it.
    """

    operator = os.environ.get("LIMES_OPERATOR_TOKEN", "").strip()
    if operator:
        return operator, "operator"
    api = os.environ.get("LIMES_API_TOKEN", "").strip()
    if api:
        return api, "api"
    if sys.stdin.isatty():
        token = getpass.getpass("LIMES API token (session only): ").strip()
        if token:
            return token, "api"
    return None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="limes-desktop",
        description="Serve the LIMES web desktop on loopback (static SPA + /api bearer proxy)",
    )
    parser.add_argument(
        "--version", action="store_true", help="print the desktop version and exit"
    )
    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    if args.version:
        from limes_desktop.webapp import VERSION

        print(f"limes-desktop {VERSION}")
        return 0

    if not guard_instance():
        # Another launcher owns the guard; exit quietly (NFR-DC-070).
        return 0

    port = _port()

    import uvicorn

    from limes_desktop.webapp import create_launcher_app, resolve_dist_dir

    try:
        dist = resolve_dist_dir()
    except RuntimeError as exc:
        print(f"limes-desktop: {exc}", file=sys.stderr)
        return 2

    app = create_launcher_app(dist_dir=dist, env_credential=_credential())
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
