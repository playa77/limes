# desktop/tests/unit/test_cli.py | v1.1.0 | entry-point behaviors: version, port, dist
"""CLI behaviors of `limes_desktop.__main__.main`: --version prints and exits
0 without importing uvicorn; the port override is validated with a clear
message; a missing web bundle names the exact build command (exit code 2).
The serve path itself is exercised by docker-free desktop run directions,
not in CI (`uvicorn.run` would block the test process)."""

from __future__ import annotations

from pathlib import Path

import pytest
from limes_desktop.__main__ import _port, main


def test_version_prints_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    from limes_desktop.webapp import VERSION

    assert main(["--version"]) == 0
    assert capsys.readouterr().out == f"limes-desktop {VERSION}\n"


def test_port_override_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LIMES_DESKTOP_PORT", raising=False)
    default = _port()
    assert 1025 <= default <= 65535

    monkeypatch.setenv("LIMES_DESKTOP_PORT", "8999")
    assert _port() == 8999

    monkeypatch.setenv("LIMES_DESKTOP_PORT", "not-a-port")
    with pytest.raises(SystemExit, match="not an integer"):
        _port()

    monkeypatch.setenv("LIMES_DESKTOP_PORT", "80")
    with pytest.raises(SystemExit, match="out of range"):
        _port()


def test_missing_bundle_names_the_build_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("LIMES_DESKTOP_PORT", raising=False)
    monkeypatch.setenv("LIMES_DESKTOP_DIST", str(tmp_path / "nonexistent-dist"))
    # Never bind the real guard: process-level interaction stays out of CI.
    monkeypatch.setattr("limes_desktop.app.guard_instance", lambda *a, **k: True)

    code = main([])
    assert code == 2
    message = capsys.readouterr().err
    assert "pnpm build" in message
    assert "nonexistent-dist" in message
