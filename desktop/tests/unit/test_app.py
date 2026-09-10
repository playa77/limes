# desktop/tests/unit/test_app.py | v0.1.0 | entry point: version flag + guard (NFR-DC-070)
from __future__ import annotations

from typing import Any

import pytest
from limes_desktop.app import GUARD_NAME, already_running


def test_version_flag_exits_zero_without_gui(capsys: Any) -> None:
    from limes_desktop.__main__ import main

    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "limes-desktop" in out


def test_already_running_false_on_fresh_name() -> None:
    # no existing server with this name in this test process
    assert already_running(GUARD_NAME + "-test-fresh") is False


def test_already_running_true_when_server_exists() -> None:
    from PySide6.QtNetwork import QLocalServer

    name = GUARD_NAME + "-test-existing"
    server = QLocalServer()
    assert QLocalServer.removeServer(name) or True
    assert server.listen(name)
    try:
        assert already_running(name) is True
    finally:
        server.close()
