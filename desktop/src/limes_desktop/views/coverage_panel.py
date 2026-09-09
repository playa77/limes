# desktop/src/limes_desktop/views/coverage_panel.py | v0.1.0 | FR-DC-034: diagnosis empty state
"""Shared coverage panel.

When a query returns an empty result the panel IS the empty state: one row
per hop from the coverage Diagnosis (which hop emptied the set plus the
graph-wide relation counts), never a bare "no results" (FR-DC-034,
AC-DC-3). Non-empty results show the collapsible coverage summary.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from limes_desktop.api.models import CoverageReport, Diagnosis
from limes_desktop.state import QueryOutcomeBundle, SessionState

_EMPTY_STATE_TEXT = "query emptied the result set — see hop diagnosis below"


class CoveragePanel(QWidget):
    """Coverage summary + hop-level diagnosis empty state (FR-DC-034)."""

    def __init__(self, state: SessionState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state

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

        state.result_arrived.connect(self._on_result)

    # -- inputs ---------------------------------------------------------------

    def set_diagnosis(self, diagnosis: Diagnosis | None) -> None:
        """Inject the query's Diagnosis (empty results carry one)."""
        self._diagnosis = diagnosis

    def render(self, coverage: CoverageReport | None) -> None:  # type: ignore[override]  # shadows QWidget.render(QPainter) deliberately: this widget is data-driven, never painted
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
            "<br>".join(f"<b>{name}</b>: {value}" for name, value in self._summary_rows)
        )

    # -- seams ----------------------------------------------------------------

    def summary_text(self) -> str:
        return "\n".join(f"{name}: {value}" for name, value in self._summary_rows)

    # -- signal wiring ----------------------------------------------------------

    def _on_result(self, bundle: QueryOutcomeBundle) -> None:
        result = bundle.result
        if isinstance(result, list):
            return  # search hits are not this panel's concern
        empty = not getattr(result, "nodes", None) and not getattr(result, "entity", None)
        if empty and self._diagnosis is not None:
            self._show_diagnosis(self._diagnosis)
            self.summary_widget.setVisible(False)
        else:
            self.render(bundle.coverage)

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
