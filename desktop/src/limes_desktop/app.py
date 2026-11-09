# desktop/src/limes_desktop/app.py | v1.1.0 | single-instance guard (NFR-DC-070)
"""Process-level single-instance guard for the desktop launcher.

The retired Qt stack guarded itself with a QLocalServer name; the FastAPI
launcher replacements is a plain advisory file lock. An advisory `flock` is
chosen because it is released by the operating system when the owning process
dies — a crashed launcher never leaves the stale-socket residue the old
`QLocalServer.removeServer` cleanup had to erase. The launcher replacement is
a plain advisory file lock, not a new server.

The lock lives under `$XDG_RUNTIME_DIR` (falling back to the system temporary
directory), separate from the profile store, and is namespaced by UID so two
users on one host do not claim each other's guard.
"""

from __future__ import annotations

import fcntl
import os
import tempfile

GUARD_NAME = "limes-desktop"

# Module-level handle registry: the descriptor must stay open for the process
# lifetime, otherwise the lock is released early.
_holds: dict[str, int] = {}


def guard_path(name: str = GUARD_NAME) -> str:
    runtime = os.environ.get("XDG_RUNTIME_DIR", "") or tempfile.gettempdir()
    return os.path.join(runtime, f"{name}-{os.getuid()}.lock")


def guard_instance(name: str = GUARD_NAME) -> bool:
    """Try to become the single running launcher instance.

    Returns True (and holds the guard until process exit) for the first
    caller whose process keeps the lock; False when another instance already
    owns it. No log output and no stale-file cleanup dances: a dead owner
    releases the lock automatically.
    """

    path = guard_path(name)
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return False
    try:
        os.write(fd, str(os.getpid()).encode())
    except OSError:
        # The lock still holds; the pid note is best-effort diagnostics.
        pass
    _holds[name] = fd
    return True
