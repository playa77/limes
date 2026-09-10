# desktop/src/limes_desktop/views/ops/ingest.py | v0.1.0 | FR-DC-050: ingest status
"""Ingest status view (FR-DC-050): a read-only table of `IngestRun` rows with
a 10 s auto-refresh QTimer that runs ONLY while the view is visible —
`showEvent` starts it, `hideEvent` stops it. Connection failures degrade to
an inline error pane (AC-DC-6, no exception escape) and pause the timer.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from limes_desktop.api.errors import ApiError, ApiUnreachable
from limes_desktop.api.models import IngestRun

REFRESH_INTERVAL_MS = 10_000

_COLUMNS = [
    "source",
    "mode",
    "run id",
    "started",
    "finished",
    "records",
    "nodes created",
    "nodes matched",
    "assertions written",
    "skipped",
    "rejected",
    "gated out",
    "errors",
    "cost EUR",
]

COLUMN_ERRORS = _COLUMNS.index("errors")


class IngestView(QWidget):
    """Read-only ingest run table; auto-refreshes every 10 s while visible."""

    def __init__(
        self,
        client_factory: Callable[[], Any],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._client_factory = client_factory
        self._ticks = 0

        self.table = QTableWidget(0, len(_COLUMNS), self)
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)

        self.error_pane = QLabel("", self)
        self.error_pane.setWordWrap(True)
        self.error_pane.setStyleSheet("color: #c62828;")
        self.error_pane.setVisible(False)

        layout = QVBoxLayout(self)
        layout.addWidget(self.error_pane)
        layout.addWidget(self.table)
        self._footer = QHBoxLayout()
        layout.addLayout(self._footer)

        self._timer = self._make_timer()
        self._timer.timeout.connect(self.refresh_runs)

    def _make_timer(self) -> Any:
        from PySide6.QtCore import QTimer

        timer = QTimer(self)
        timer.setInterval(REFRESH_INTERVAL_MS)
        return timer

    # -- seams for tests ------------------------------------------------------

    def error_text(self) -> str:
        return self.error_pane.text()

    # -- behavior ---------------------------------------------------------------

    def refresh_runs(self) -> None:
        """One ingest-status fetch; safe to call directly from tests."""
        self._ticks += 1
        try:
            runs = self._client_factory().ingest_status()
        except (ApiError, ApiUnreachable) as exc:
            self._show_error(getattr(exc, "detail", str(exc)))
            self._timer.stop()  # pause auto-refresh while unreachable
            return
        self._show_error(None)
        self.set_runs(runs)
        if not self._timer.isActive():
            self._timer.start()

    def set_runs(self, runs: list[IngestRun]) -> None:
        self.table.setRowCount(len(runs))
        for row, run in enumerate(runs):
            cells = [
                run.source_id,
                run.mode,
                run.run_id,
                run.started_at,
                run.finished_at or "",
                str(run.records_fetched),
                str(run.nodes_created),
                str(run.nodes_matched),
                str(run.assertions_written),
                str(run.assertions_skipped),
                str(run.assertions_rejected),
                str(run.documents_gated_out),
                str(run.errors),
                f"{run.cost_eur:.2f}",
            ]
            for col, text in enumerate(cells):
                self.table.setItem(row, col, QTableWidgetItem(text))

    def _show_error(self, detail: str | None) -> None:
        if detail is None:
            self.error_pane.setVisible(False)
            self.error_pane.setText("")
        else:
            self.error_pane.setText(detail)
            self.error_pane.setVisible(True)

    # -- visibility-gated auto-refresh (FR-DC-050) -----------------------------

    def showEvent(self, event: Any) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        # refresh_runs() starts the timer on success and leaves it stopped
        # when unreachable (FR-DC-050: no ticking while degraded)
        self.refresh_runs()

    def hideEvent(self, event: Any) -> None:  # noqa: N802 (Qt naming)
        super().hideEvent(event)
        self._timer.stop()
