# desktop/src/limes_desktop/views/backup.py | v0.1.0 | FR-DC-061/063: backup confirmation dialog
"""BackupDialog (Task 11): consequence confirmation before running a backup.

The consequence text names the effects verbatim (FR-DC-061); Run stays
disabled with the prerequisite reasons shown inline until they clear
(FR-DC-063).
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QWidget

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

    def set_profile(self, profile: ConnectionProfile) -> None:
        self._profile = profile
        reasons = self._runner.prerequisites(profile)
        self.reason_label.setText("\n".join(reasons))
        self.run_button.setEnabled(not reasons)

    def _on_run(self) -> None:
        if self._profile is not None:
            self._runner.run(self._profile)
        self.accept()
