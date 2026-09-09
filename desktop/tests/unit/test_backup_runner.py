# desktop/tests/unit/test_backup_runner.py | v0.1.0 | FR-DC-060..063: backup runner + dialog
"""BackupRunner and BackupDialog (Task 11), headless.

The real QProcess is never started in tests: BackupRunner accepts a
process factory seam, and the fake process below is a plain QObject with
the same signals QProcess exposes (readyReadStandardOutput, finished).
No real docker, no real HTTP (health is a stub client).
"""

from __future__ import annotations

from typing import Any

import pytest
from PySide6.QtCore import QObject, Signal

from limes_desktop.backup_runner import BackupRunner
from limes_desktop.config import ConnectionProfile
from limes_desktop.views.backup import BackupDialog

_COMMAND = ["docker", "compose", "exec", "worker", "limes", "backup"]


class FakeProcess(QObject):
    """Duck-typed QProcess: same signals, records start() arguments."""

    readyReadStandardOutput = Signal()
    finished = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.started_program: str | None = None
        self.started_args: list[str] | None = None
        self.working_dir: str | None = None
        self.pending_lines: list[str] = []
        self.exit_code: int | None = None

    def setWorkingDirectory(self, path: str) -> None:
        self.working_dir = path

    def start(self, program: str, args: list[str]) -> None:
        self.started_program = program
        self.started_args = args

    def readAll(self) -> Any:
        if not self.pending_lines:
            data = b""
        else:
            data = ("\n".join(self.pending_lines) + "\n").encode()
            self.pending_lines = []
        # mimic QByteArray: expose .data()
        return type("FakeByteArray", (), {"data": staticmethod(lambda: data)})()

    def emit_lines(self, lines: list[str]) -> None:
        self.pending_lines = lines
        self.readyReadStandardOutput.emit()

    def emit_finished(self, code: int) -> None:
        self.exit_code = code
        self.finished.emit(code)


class FakeClient:
    def __init__(self, healthy: bool = True) -> None:
        self.healthy = healthy
        self.health_calls = 0

    def health(self) -> Any:
        self.health_calls += 1
        if self.healthy:
            return object()
        raise RuntimeError("api down")


class Recorder:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.finished: list[tuple[int, Any]] = []

    def on_line(self, line: str) -> None:
        self.lines.append(line)

    def on_finished(self, code: int, health_ok: Any) -> None:
        self.finished.append((code, health_ok))


def make_runner(monkeypatch: pytest.MonkeyPatch, client: FakeClient) -> tuple[BackupRunner, FakeProcess]:
    proc = FakeProcess()

    def factory() -> FakeProcess:
        return proc

    runner = BackupRunner(client_factory=lambda: client, process_factory=factory)
    return runner, proc


def profile(compose_root: str | None = "/tmp") -> ConnectionProfile:
    # "/tmp" exists, so only the targeted prerequisite fires in each test
    return ConnectionProfile(name="p", compose_root=compose_root)


def test_run_builds_exact_command_with_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    monkeypatch.setattr("limes_desktop.backup_runner.shutil.which", lambda name: "/usr/bin/docker")
    client = FakeClient()
    rec = Recorder()
    runner, proc = make_runner(monkeypatch, client)
    runner.output_line.connect(rec.on_line)
    runner.finished.connect(rec.on_finished)
    root = tmp_path / "compose"
    root.mkdir()
    monkeypatch.setattr("limes_desktop.backup_runner.shutil.which", lambda name: "/usr/bin/docker")  # noqa: F841
    runner, proc = make_runner(monkeypatch, client)
    rec = Recorder()
    runner.output_line.connect(rec.on_line)
    runner.finished.connect(rec.on_finished)
    runner.run(profile(str(root)))
    assert proc.started_program == "docker"
    assert proc.started_args == _COMMAND[1:]
    assert proc.working_dir == str(root)


def test_prerequisites_missing_docker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("limes_desktop.backup_runner.shutil.which", lambda name: None)
    runner = BackupRunner(client_factory=lambda: FakeClient())
    reasons = runner.prerequisites(profile())
    assert len(reasons) == 1
    assert "docker" in reasons[0]


def test_prerequisites_compose_root_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("limes_desktop.backup_runner.shutil.which", lambda name: "/usr/bin/docker")
    runner = BackupRunner(client_factory=lambda: FakeClient())
    reasons = runner.prerequisites(profile(None))
    assert len(reasons) == 1
    assert "compose" in reasons[0].lower()


def test_prerequisites_compose_root_not_a_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("limes_desktop.backup_runner.shutil.which", lambda name: "/usr/bin/docker")
    runner = BackupRunner(client_factory=lambda: FakeClient())
    reasons = runner.prerequisites(profile("/nonexistent/nope"))
    assert len(reasons) == 1


def test_output_lines_flow_to_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("limes_desktop.backup_runner.shutil.which", lambda name: "/usr/bin/docker")
    client = FakeClient()
    runner, proc = make_runner(monkeypatch, client)
    rec = Recorder()
    runner.output_line.connect(rec.on_line)
    runner.run(profile())
    proc.emit_lines(["starting backup", "dump written"])
    assert rec.lines == ["starting backup", "dump written"]


def test_dump_filename_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("limes_desktop.backup_runner.shutil.which", lambda name: "/usr/bin/docker")
    client = FakeClient()
    runner, proc = make_runner(monkeypatch, client)
    rec = Recorder()
    runner.finished.connect(rec.on_finished)
    runner.run(profile())
    proc.emit_lines(["backup complete: dumps/limes-20260909T120000.dump"])
    proc.emit_finished(0)
    assert runner.dump_path == "dumps/limes-20260909T120000.dump"
    assert runner.health_ok is True


def test_exit_zero_calls_health(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("limes_desktop.backup_runner.shutil.which", lambda name: "/usr/bin/docker")
    client = FakeClient()
    runner, proc = make_runner(monkeypatch, client)
    rec = Recorder()
    runner.finished.connect(rec.on_finished)
    runner.run(profile())
    proc.emit_finished(0)
    assert client.health_calls == 1
    assert rec.finished == [(0, True)]


def test_exit_nonzero_no_health_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("limes_desktop.backup_runner.shutil.which", lambda name: "/usr/bin/docker")
    client = FakeClient()
    runner, proc = make_runner(monkeypatch, client)
    rec = Recorder()
    runner.finished.connect(rec.on_finished)
    runner.run(profile())
    proc.emit_finished(1)
    assert client.health_calls == 0
    assert rec.finished == [(1, None)]
    assert runner.health_ok is None


def test_unhealthy_api_after_exit_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("limes_desktop.backup_runner.shutil.which", lambda name: "/usr/bin/docker")
    client = FakeClient(healthy=False)
    runner, proc = make_runner(monkeypatch, client)
    rec = Recorder()
    runner.finished.connect(rec.on_finished)
    runner.run(profile())
    proc.emit_finished(0)
    assert client.health_calls == 1
    assert rec.finished == [(0, False)]


def test_dialog_run_disabled_without_prerequisites_check(
    monkeypatch: pytest.MonkeyPatch, qtbot: Any
) -> None:
    monkeypatch.setattr("limes_desktop.backup_runner.shutil.which", lambda name: None)
    runner = BackupRunner(client_factory=lambda: FakeClient())
    dlg = BackupDialog(runner)
    qtbot.addWidget(dlg)
    dlg.set_profile(profile(None))
    assert not dlg.run_button.isEnabled()
    reasons_text = dlg.reason_label.text()
    assert reasons_text.strip() != ""


def test_dialog_consequence_text_verbatim(
    monkeypatch: pytest.MonkeyPatch, qtbot: Any
) -> None:
    monkeypatch.setattr("limes_desktop.backup_runner.shutil.which", lambda name: "/usr/bin/docker")
    runner = BackupRunner(client_factory=lambda: FakeClient())
    dlg = BackupDialog(runner)
    qtbot.addWidget(dlg)
    dlg.set_profile(profile())
    assert dlg.run_button.isEnabled()
    full = dlg.consequence_label.text() + dlg.reason_label.text()
    assert "Neo4j unavailable for the duration; graceful stop up to ~120 s" in full
