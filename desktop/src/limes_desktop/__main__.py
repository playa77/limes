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
    from limes_desktop.config import ProfileStore
    from limes_desktop.state import SessionState
    from limes_desktop.views.main_window import MainWindow

    store = ProfileStore()
    active = store.active()
    client: ApiClient | None = None

    def client_factory() -> ApiClient:
        nonlocal client
        if client is None:
            base = active.base_url if active is not None else "http://127.0.0.1:8000"
            client = ApiClient(base)
        return client

    state = SessionState()
    if active is not None:
        state.set_connection(active)

    win = MainWindow(state, store, client_factory)
    win.show()
    raise SystemExit(int(app.exec()))


if __name__ == "__main__":
    main()
