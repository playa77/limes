# desktop/src/limes_desktop/views/coverage_panel.py | v0.1.0 | FR-DC-034: diagnosis empty state
"""Shared coverage panel.

When a query returns an empty result the panel IS the empty state: one row
per hop from the coverage Diagnosis (which hop emptied the set plus the
graph-wide relation counts), never a bare "no results" (FR-DC-034,
AC-DC-3). Non-empty results show the collapsible coverage summary.
"""

from __future__ import annotations

from collections.abc import Callable
from html import escape
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from limes_desktop.api.models import CoverageReport, Diagnosis, OfficesResponse
from limes_desktop.state import QueryOutcomeBundle, SessionState

_EMPTY_STATE_TEXT = "query emptied the result set — see hop diagnosis below"


class _CoverageSignals(QObject):
    completed = Signal(int, object)


class _CoverageRead(QRunnable):
    def __init__(self, client: Any, generation: int) -> None:
        super().__init__()
        self.client = client
        self.generation = generation
        self.signals = _CoverageSignals()

    def run(self) -> None:
        try:
            result = self.client.public_offices(limit=1, include_members=False)
        except Exception as exc:
            result = exc
        self.signals.completed.emit(self.generation, result)


class CoveragePanel(QWidget):
    """Coverage summary + hop-level diagnosis empty state (FR-DC-034)."""

    def __init__(
        self,
        state: SessionState,
        parent: QWidget | None = None,
        client_factory: Callable[[], Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._diagnosis: Diagnosis | None = None
        self._client_factory = client_factory
        self._offices: OfficesResponse | None = None
        self._offices_task: _CoverageRead | None = None
        self._offices_generation = 0
        state.connection_changed.connect(self._offices_connection_changed)

        self.diagnosis_table = QTableWidget(0, 3, self)
        self.diagnosis_table.setHorizontalHeaderLabels(["hop", "relation", "graph-wide count"])
        self.diagnosis_table.horizontalHeader().setStretchLastSection(True)
        self.diagnosis_table.setVisible(False)

        self._empty_label = QLabel(_EMPTY_STATE_TEXT, self)
        self._empty_label.setWordWrap(True)
        self._empty_label.setVisible(False)

        self.summary_widget = QWidget(self)
        self._summary_rows: list[tuple[str, str]] = []
        summary_layout = QVBoxLayout(self.summary_widget)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        self._summary_label = QLabel("", self.summary_widget)
        self._summary_label.setWordWrap(True)
        self._summary_label.setTextFormat(Qt.TextFormat.RichText)
        self._toggle = QCheckBox("coverage summary", self.summary_widget)
        self._toggle.setChecked(True)
        self._toggle.toggled.connect(self._summary_label.setVisible)
        summary_layout.addWidget(self._toggle)
        summary_layout.addWidget(self._summary_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._empty_label)
        layout.addWidget(self.diagnosis_table)
        layout.addWidget(self.summary_widget)
        self.offices_button = QPushButton("Public office coverage", self)
        self.offices_button.setVisible(client_factory is not None)
        self.offices_button.clicked.connect(self._load_offices)
        self.offices_table = QTableWidget(0, 5, self)
        self.offices_table.setHorizontalHeaderLabels(
            ["Institution", "Status", "Loaded / acquired", "Observed", "Diagnosis"]
        )
        self.offices_table.setVisible(False)
        self.offices_table.cellDoubleClicked.connect(self._select_office_snapshot)
        self.offices_note = QLabel("", self)
        self.offices_note.setWordWrap(True)
        self.offices_note.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.offices_button)
        layout.addWidget(self.offices_table)
        layout.addWidget(self.offices_note)

        state.result_arrived.connect(self._on_result)

    # -- inputs ---------------------------------------------------------------

    def set_diagnosis(self, diagnosis: Diagnosis | None) -> None:
        """Inject the query's Diagnosis (empty results carry one)."""
        self._diagnosis = diagnosis

    def show_coverage(self, coverage: CoverageReport | None) -> None:
        """Render a coverage report; `None` clears the panel."""
        self._summary_rows = []
        self._summary_label.setText("")
        self._empty_label.setVisible(False)
        self.diagnosis_table.setRowCount(0)
        self.diagnosis_table.setVisible(False)
        self.is_showing_empty_state = False
        if coverage is None:
            self.summary_widget.setVisible(False)
            return
        self.summary_widget.setVisible(True)
        for relation, count in sorted(coverage.relation_counts.items()):
            self._summary_rows.append((relation, str(count)))
        for source in coverage.contributing_sources:
            refreshed = coverage.source_refresh.get(source)
            when = refreshed if refreshed else "never"
            self._summary_rows.append((source, when))
        self._summary_label.setText(
            "<br>".join(
                f"<b>{escape(name)}</b>: {escape(value)}" for name, value in self._summary_rows
            )
        )

    def _load_offices(self) -> None:
        if self._client_factory is None or self._offices_task is not None:
            return
        self.offices_table.setRowCount(0)
        self._offices = None
        try:
            client = self._client_factory()
        except Exception as exc:
            self.offices_note.setText(f"Public office coverage unavailable: {exc}")
            return
        self.offices_button.setEnabled(False)
        self.offices_note.setText("Reading acquired public office coverage…")
        self._offices_generation += 1
        self._offices_task = _CoverageRead(client, self._offices_generation)
        self._offices_task.signals.completed.connect(self._offices_finished)
        QThreadPool.globalInstance().start(self._offices_task)

    def _offices_connection_changed(self, profile: object) -> None:
        del profile
        self._offices_generation += 1
        self._offices = None
        self.offices_table.setRowCount(0)
        self.offices_note.setText("Connection changed; refresh acquired coverage.")

    @Slot(int, object)
    def _offices_finished(self, generation: int, result: object) -> None:
        self._offices_task = None
        self.offices_button.setEnabled(True)
        if generation != self._offices_generation:
            return
        if isinstance(result, OfficesResponse):
            self.show_offices(result)
        else:
            self.offices_note.setText(f"Public office coverage unavailable: {result}")

    def show_offices(self, result: OfficesResponse) -> None:
        self._offices = result
        self.offices_table.setVisible(True)
        self.offices_table.setRowCount(len(result.scopes))
        for index, scope in enumerate(result.scopes):
            values = [
                scope.institution,
                scope.status,
                f"{scope.loaded} / {scope.acquired}",
                scope.observed_at or "unknown",
                "; ".join(scope.diagnosis),
            ]
            for column, value in enumerate(values):
                self.offices_table.setItem(index, column, QTableWidgetItem(value))
        self.offices_note.setText(
            f"Selection coverage: {result.coverage_status}. "
            "Double-click an acquired scope to inspect its snapshot and evidence. "
            + " ".join(result.diagnosis)
        )

    def _select_office_snapshot(self, row: int, column: int) -> None:
        del column
        if self._offices is not None and 0 <= row < len(self._offices.scopes):
            snapshot = self._offices.scopes[row].snapshot_id
            if snapshot:
                self._state.set_selection(snapshot)

    # -- seams ----------------------------------------------------------------

    def summary_text(self) -> str:
        return "\n".join(f"{name}: {value}" for name, value in self._summary_rows)

    # -- signal wiring ----------------------------------------------------------

    def _on_result(self, bundle: QueryOutcomeBundle) -> None:
        result = bundle.result
        if isinstance(result, list):
            return  # search hits are not this panel's concern
        empty = not getattr(result, "nodes", None) and not getattr(result, "entity", None)
        # diagnosis preference: what the bundle carried (real /query/* payloads
        # attach diagnosis on empty results) over any externally injected one
        diagnosis = bundle.diagnosis if bundle.diagnosis is not None else self._diagnosis
        if empty and diagnosis is not None:
            self._show_diagnosis(diagnosis)
            self.summary_widget.setVisible(False)
        else:
            self.show_coverage(bundle.coverage)

    # -- diagnosis empty state (FR-DC-034 / AC-DC-3) -----------------------------

    def _show_diagnosis(self, diagnosis: Diagnosis) -> None:
        self.is_showing_empty_state = True
        self.summary_widget.setVisible(False)
        counts = diagnosis.relation_counts
        self.diagnosis_table.setVisible(True)
        self.diagnosis_table.setRowCount(max(len(counts), 1))
        note = diagnosis.note or f"hop {diagnosis.clause_index} ({diagnosis.failing_clause})"
        self._empty_label.setVisible(True)
        self._empty_label.setText(f"{_EMPTY_STATE_TEXT}\n{note}")
        for row, (relation, count) in enumerate(sorted(counts.items())):
            emptied = relation == diagnosis.failing_clause
            hop_label = f"hop {diagnosis.clause_index}{' (emptied)' if emptied else ''}"
            self.diagnosis_table.setItem(row, 0, QTableWidgetItem(hop_label))
            self.diagnosis_table.setItem(row, 1, QTableWidgetItem(relation))
            self.diagnosis_table.setItem(row, 2, QTableWidgetItem(str(count)))
