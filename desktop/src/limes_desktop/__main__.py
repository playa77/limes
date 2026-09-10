# desktop/src/limes_desktop/__main__.py | v0.1.0 | entry point: version flag, guard, MainWindow
from __future__ import annotations

import sys

VERSION = "0.1.0"


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--version" in args:
        print(f"limes-desktop {VERSION}")
        raise SystemExit(0)

    from PySide6.QtWidgets import QApplication

    from limes_desktop.app import GUARD_NAME, already_running

    app = QApplication.instance() or QApplication(args)

    if already_running(GUARD_NAME):
        # another instance owns the guard; just exit quietly (NFR-DC-070)
        raise SystemExit(0)

    from PySide6.QtNetwork import QLocalServer

    server = QLocalServer()
    QLocalServer.removeServer(GUARD_NAME)  # clean up stale socket from a crash
    if not server.listen(GUARD_NAME):
        raise SystemExit(0)

    from limes_desktop.api.client import ApiClient
    from limes_desktop.config import ConnectionProfile, ProfileStore
    from limes_desktop.state import SessionState
    from limes_desktop.views.main_window import MainWindow

    store = ProfileStore()
    active = store.active()

    state = SessionState()

    # client_factory must rebind to the current profile's base_url (FR-DC-002):
    # connection_changed first rebinds the client, then MainWindow's handler
    # (connected later, so it runs second) probes the new endpoint.
    base_holder: list[str] = [
        active.base_url if active is not None else "http://127.0.0.1:8000"
    ]
    client_holder: list[ApiClient | None] = [None]

    def _rebind_client(profile: object) -> None:
        base_holder[0] = (
            profile.base_url
            if isinstance(profile, ConnectionProfile)
            else "http://127.0.0.1:8000"
        )
        old = client_holder[0]
        if old is not None:
            old.close()
        client_holder[0] = None

    state.connection_changed.connect(_rebind_client)
    if active is not None:
        state.set_connection(active)

    def client_factory() -> ApiClient:
        if client_holder[0] is None:
            client_holder[0] = ApiClient(base_holder[0])
        client = client_holder[0]
        assert client is not None  # set above when the holder was empty
        return client

    win = MainWindow(state, store, client_factory)
    win.show()
    raise SystemExit(int(app.exec()))


if __name__ == "__main__":
    main()
