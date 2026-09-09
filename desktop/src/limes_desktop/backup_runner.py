# desktop/src/limes_desktop/backup_runner.py | v0.1.0 | FR-DC-060..062: worker-command backup runner
"""Backup orchestration for the desktop client (Task 11).

No backup logic lives here: the single implementation is the worker command
`docker compose exec worker limes backup` (FR-DC-060). This runner only
checks prerequisites, streams the process output line-wise, parses the dump
filename from that output, and verifies API recovery after exit 0 (FR-DC-062).
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QProcess, Signal

from limes_desktop.config import ConnectionProfile

# FR-DC-060: exact command, verbatim. The worker is the single implementation.
_COMMAND = ["docker", "compose", "exec", "worker", "limes", "backup"]

_DUMP_RE = re.compile(r"\S*limes-\d+T\d+\.dump")


class BackupRunner(QObject):
    """Runs the worker backup command and verifies recovery afterwards."""

    output_line = Signal(str)
    finished = Signal(int, object)  # exit_code, health_ok (bool | None)

    def __init__(
        self,
        client_factory: Callable[[], object],
        process_factory: Callable[[], QProcess] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._client_factory = client_factory
        self._process_factory: Callable[[], QProcess] = (
            process_factory if process_factory is not None else self._default_process
        )
        self.health_ok: bool | None = None
        self.dump_path: str | None = None
        self._running = False

    @staticmethod
    def _default_process() -> QProcess:
        proc = QProcess()
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        return proc

    def prerequisites(self, profile: ConnectionProfile) -> list[str]:
        """Human-readable reasons backup cannot run; empty list = OK (FR-DC-063)."""
        reasons: list[str] = []
        if shutil.which("docker") is None:
            reasons.append("docker CLI not found in PATH")
        root = profile.compose_root
        if root is None:
            reasons.append("no compose root configured for this profile (backup disabled)")
        elif not Path(root).is_dir():
            reasons.append(f"compose root is not a directory: {root}")
        return reasons

    def run(self, profile: ConnectionProfile) -> None:
        if self._running:
            return
        proc = self._process_factory()
        self.health_ok = None
        self.dump_path = None
        self._running = True
        proc.setWorkingDirectory(profile.compose_root or "")
        proc.readyReadStandardOutput.connect(self._make_reader(proc))
        proc.finished.connect(self._make_finisher(proc))
        proc.start(_COMMAND[0], _COMMAND[1:])

    def _make_reader(self, proc: QProcess) -> Callable[[], None]:
        def read() -> None:
            data = bytes(proc.readAll().data()).decode(errors="replace")
            for line in data.splitlines():
                if line:
                    match = _DUMP_RE.search(line)
                    if match:
                        self.dump_path = match.group(0)
                    self.output_line.emit(line)

        return read

    def _make_finisher(self, proc: QProcess) -> Callable[[int], None]:
        def finish(code: int) -> None:
            self._running = False
            if code == 0:
                # FR-DC-062: verify recovery via API health; a failure to reach
                # the API maps to health_ok=False (no retry — §4).
                try:
                    self._client_factory().health()  # type: ignore[attr-defined]
                    self.health_ok = True
                except Exception:
                    self.health_ok = False
            else:
                self.health_ok = None
            self.finished.emit(code, self.health_ok)

        return finish
