# desktop/src/limes_desktop/views/backup.py | v0.1.0 | FR-DC-061/063: backup confirmation dialog
"""BackupDialog (Task 11): consequence confirmation before running a backup.

The consequence text names the effects verbatim (FR-DC-061); Run stays
disabled with the prerequisite reasons shown inline until they clear
(FR-DC-063).
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from limes_desktop.backup_runner import BackupRunner
from limes_desktop.config import ConnectionProfile

_CONSEQUENCES = "Neo4j unavailable during backup; clean shutdown can take up to 180 seconds"


class BackupDialog(QDialog):
    """Confirmation dialog for the worker backup command."""

    def __init__(self, runner: BackupRunner, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Run backup")
        self._runner = runner
        self._profile: ConnectionProfile | None = None

        self.consequence_label = QLabel(_CONSEQUENCES, self)
        self.reason_label = QLabel("", self)
        self.run_button = QPushButton("Run backup", self)
        self.cancel_button = QPushButton("Cancel", self)
        self.run_button.setEnabled(False)
        self.reason_label.setText("Checking API and operator backup capability…")
        self.output = QTextEdit(self)
        self.output.setReadOnly(True)
        runner.output_line.connect(self.output.append)
        runner.finished.connect(self._finished)
        self.cancel_button.clicked.connect(self.reject)
        self.run_button.clicked.connect(self._on_run)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel("This requests a server backup using your operator credential.", self)
        )
        layout.addWidget(self.consequence_label)
        layout.addWidget(self.reason_label)
        layout.addWidget(self.run_button)
        layout.addWidget(self.cancel_button)
        layout.addWidget(self.output)

    def set_profile(self, profile: ConnectionProfile) -> None:
        self._profile = profile
        reasons = self._runner.prerequisites(profile)
        self.reason_label.setText("\n".join(reasons))
        self.run_button.setEnabled(not reasons)

    def set_available(self, profile: ConnectionProfile, available: bool) -> None:
        self._profile = profile
        self.run_button.setEnabled(available and self._runner._task is None)
        self.reason_label.setText(
            "" if available else "Backup requires a reachable API and an operator credential."
        )

    def _on_run(self) -> None:
        if self._profile is not None and self.run_button.isEnabled():
            self.run_button.setEnabled(False)
            self.reason_label.setText(
                "Backup in progress. Leaving this view does not cancel the server job."
            )
            self._runner.run(self._profile)

    def _finished(self, code: int, healthy: object) -> None:
        if code == 0 and healthy is True:
            message = (
                f"Backup complete; API healthy. Dump: {self._runner.dump_path or 'not reported'}"
            )
        elif code == 0:
            message = (
                "Backup completed; API health is not confirmed. Check connection before continuing."
            )
        else:
            message = "Backup failed or observation disconnected. No automatic retry."
        self.reason_label.setText(message)
        # Capability refresh re-enables deliberate submission, never automatic replay.
