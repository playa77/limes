# desktop/src/limes_desktop/app.py | v0.1.0 | App bootstrap: single-instance guard (NFR-DC-070)
from __future__ import annotations

GUARD_NAME = "limes-desktop"


def already_running(name: str = GUARD_NAME) -> bool:
    """True if another limes-desktop instance owns the QLocalServer name."""
    from PySide6.QtNetwork import QLocalSocket

    probe = QLocalSocket()
    probe.connectToServer(name)
    running = probe.waitForConnected(100)
    probe.disconnectFromServer()
    return running
