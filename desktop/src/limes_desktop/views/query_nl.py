# desktop/src/limes_desktop/views/query_nl.py | v0.1.0 | FR-DC-030: NLQ + editable Cypher
"""NLQ view: question input, generated-Cypher editor, Run button.

FR-DC-030's always-editable rule: the generated Cypher lands in a plain
`QPlainTextEdit` (never read-only), and Run re-executes the *edited* text via
`query_cypher`. Write-clause rejections surface `ApiError.detail` verbatim
in the error pane. Results render through `SessionState.publish`, so the
shared `CoveragePanel` empty state applies (never a bare "no results").
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from limes_desktop.api.errors import ApiError, ApiUnreachable
from limes_desktop.api.models import GraphResult, NlqOutcome
from limes_desktop.state import QueryOutcomeBundle, SessionState


class NlqView(QWidget):
    """Ask a natural-language question, inspect and edit the Cypher it produced."""

    def __init__(
        self,
        state: SessionState,
        client_factory: Callable[[], Any],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._client_factory = client_factory
        self._nlq_outcome = None

        self.question_edit = QLineEdit(self)
        self.question_edit.setPlaceholderText("Question (DE/EN)…")
        self.submit_button = QPushButton("Ask", self)
        self.cypher_edit = QPlainTextEdit(self)
        self.cypher_edit.setPlaceholderText("generated Cypher (editable)")
        self.run_button = QPushButton("Run", self)
        self.metadata_label = QLabel("", self)
        self.metadata_label.setWordWrap(True)
        self.error_pane = QLabel("", self)
        self.error_pane.setWordWrap(True)
        self.error_pane.setStyleSheet("color: #c62828;")
        self.error_pane.setVisible(False)

        layout = QVBoxLayout(self)
        layout.addWidget(self.question_edit)
        layout.addWidget(self.submit_button)
        layout.addWidget(QLabel("Cypher (editable):", self))
        layout.addWidget(self.cypher_edit)
        layout.addWidget(self.run_button)
        layout.addWidget(self.metadata_label)
        layout.addWidget(self.error_pane)
        layout.addStretch(1)

        self.submit_button.clicked.connect(self._submit)
        self.run_button.clicked.connect(self._run_cypher)

    # -- seams for tests ------------------------------------------------------

    def metadata_text(self) -> str:
        return self.metadata_label.text()

    def error_text(self) -> str:
        return self.error_pane.text()

    # -- behavior ---------------------------------------------------------------

    def _submit(self) -> None:
        question = self.question_edit.text().strip()
        if not question:
            return
        try:
            outcome = self._client_factory().query_nl(question)
        except (ApiError, ApiUnreachable) as exc:
            self._show_error(getattr(exc, "detail", str(exc)))
            return
        self._show_error(None)
        self._nlq_outcome = outcome
        self.cypher_edit.setPlainText(outcome.cypher)
        notes = "; ".join(outcome.notes) if outcome.notes else ""
        self.metadata_label.setText(f"{question}{(' — ' + notes) if notes else ''}")
        self._state.publish(
            QueryOutcomeBundle(
                result=outcome.results if outcome.results is not None else _empty_result(),
                coverage=None,
                source="nlq",
                cypher=outcome.cypher,
                nlq=NlqOutcome(
                    question=question,
                    cypher=outcome.cypher,
                    results=outcome.results,
                    notes=outcome.notes,
                ),
            )
        )

    def _run_cypher(self) -> None:
        cypher = self.cypher_edit.toPlainText().strip()
        if not cypher:
            return
        try:
            outcome = self._client_factory().query_cypher(cypher)
        except (ApiError, ApiUnreachable) as exc:
            self._show_error(getattr(exc, "detail", str(exc)))
            return
        self._show_error(None)
        # re-running edited cypher counts as an nlq-run in the console history
        self._state.publish(
            QueryOutcomeBundle(
                result=outcome.results,
                coverage=outcome.coverage,
                source="nlq-run",
                cypher=outcome.cypher,
                nlq=self._nlq_outcome,
            )
        )

    def _show_error(self, detail: str | None) -> None:
        if detail is None:
            self.error_pane.setVisible(False)
            self.error_pane.setText("")
        else:
            # verbatim per FR-DC-032 — no rephrasing, no prefix
            self.error_pane.setText(detail)
            self.error_pane.setVisible(True)


def _empty_result() -> GraphResult:
    return GraphResult()
