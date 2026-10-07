# desktop/src/limes_desktop/views/ops/ledger.py | v0.1.0 | FR-DC-051: cost ledger
"""Read-only cost entries, period spend, and per-model/per-run groupings."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from limes_desktop.api.errors import ApiError, ApiUnreachable
from limes_desktop.api.models import CostLedger

_COLUMNS = ["ledger id", "period", "run", "purpose", "model", "cost EUR", "created"]

_NO_RUN = "(no run)"  # grouping key for entries without a run_id


class LedgerView(QWidget):
    """Read-only ledger entries + per-model/per-run spend + running total."""

    def __init__(
        self,
        client_factory: Callable[[], Any],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._client_factory = client_factory
        self._ledger: CostLedger | None = None

        self.entries_table = QTableWidget(0, len(_COLUMNS), self)
        self.entries_table.setHorizontalHeaderLabels(_COLUMNS)
        self.entries_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.entries_table.verticalHeader().setVisible(False)

        self.total_label = QLabel("total: —", self)
        self.period_label = QLabel("period: —", self)
        self.error_pane = QLabel("", self)
        self.error_pane.setWordWrap(True)
        self.error_pane.setStyleSheet("color: #c62828;")
        self.error_pane.setVisible(False)

        layout = QVBoxLayout(self)
        layout.addWidget(self.error_pane)
        layout.addWidget(self.entries_table)
        layout.addWidget(self.total_label)
        layout.addWidget(self.period_label)

    # -- seams for tests ------------------------------------------------------

    def error_text(self) -> str:
        return self.error_pane.text()

    def running_total(self) -> float:
        """Sum of entry costs, computed client-side (FR-DC-051)."""
        if self._ledger is None:
            return 0.0
        return sum(e.cost_eur for e in self._ledger.entries)

    def spend_by_model(self) -> dict[str, float]:
        if self._ledger is None:
            return {}
        totals: dict[str, float] = {}
        for e in self._ledger.entries:
            totals[e.model_id] = totals.get(e.model_id, 0.0) + e.cost_eur
        return totals

    def spend_by_run(self) -> dict[str, float]:
        if self._ledger is None:
            return {}
        totals: dict[str, float] = {}
        for e in self._ledger.entries:
            key = e.run_id if e.run_id else _NO_RUN
            totals[key] = totals.get(key, 0.0) + e.cost_eur
        return totals

    # -- behavior ---------------------------------------------------------------

    def refresh_ledger(self) -> None:
        """One ledger fetch; safe to call directly from tests."""
        try:
            ledger = self._client_factory().cost_ledger()
        except (ApiError, ApiUnreachable) as exc:
            self._show_error(getattr(exc, "detail", str(exc)))
            return
        self._show_error(None)
        self.set_ledger(ledger)

    def set_ledger(self, ledger: CostLedger) -> None:
        self._ledger = ledger
        self.entries_table.setRowCount(len(ledger.entries))
        for row, entry in enumerate(ledger.entries):
            cells = [
                entry.ledger_id,
                entry.period,
                entry.run_id or _NO_RUN,
                entry.purpose,
                entry.model_id,
                f"{entry.cost_eur:.2f}",
                entry.created_at,
            ]
            for col, text in enumerate(cells):
                self.entries_table.setItem(row, col, QTableWidgetItem(text))
        self.total_label.setText(f"total: {self.running_total():.2f} EUR")
        self.period_label.setText(f"period: {ledger.period}; spend: {ledger.spend_eur:.2f} EUR")

    def _show_error(self, detail: str | None) -> None:
        if detail is None:
            self.error_pane.setVisible(False)
            self.error_pane.setText("")
        else:
            self.error_pane.setText(detail)
            self.error_pane.setVisible(True)

    def showEvent(self, event: Any) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        self.refresh_ledger()
