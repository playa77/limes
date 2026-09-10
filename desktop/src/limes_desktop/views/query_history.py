# desktop/src/limes_desktop/views/query_history.py | v0.1.1 | FR-DC-033: saved queries panel
"""Saved queries panel: save the current query under a name, list saved
queries, delete. Save captures the surface dimension ("nlq" | "cypher") and
the query text separately, plus the last published outcome's result count;
delete calls `ApiClient.delete_saved_query`. The list refreshes from
GET /saved-queries when the panel becomes visible or via the Refresh button.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from limes_desktop.api.errors import ApiError, ApiUnreachable
from limes_desktop.api.models import GraphResult
from limes_desktop.state import QueryOutcomeBundle, SessionState

SavedRow = tuple[str, str, str]  # (saved_query_id, question, cypher)


class SavedQueriesPanel(QWidget):
    """Save/delete/list saved queries (FR-DC-033)."""

    def __init__(
        self,
        state: SessionState,
        client_factory: Callable[[], Any],
        current_query: Callable[[], tuple[str, str]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._client_factory = client_factory
        self._current_query = current_query  # -> (surface, query text)
        self._rows: list[SavedRow] = []
        self._result_count = 0

        self.name_edit = QLineEdit(self)
        self.name_edit.setPlaceholderText("saved query name…")
        self.save_button = QPushButton("Save", self)
        self.refresh_button = QPushButton("Refresh", self)
        self.list_widget = QListWidget(self)
        self.delete_button = QPushButton("Delete", self)
        self.error_pane = QLabel("", self)
        self.error_pane.setWordWrap(True)
        self.error_pane.setStyleSheet("color: #c62828;")
        self.error_pane.setVisible(False)

        name_row = QHBoxLayout()
        name_row.addWidget(self.name_edit)
        name_row.addWidget(self.save_button)
        name_row.addWidget(self.refresh_button)

        layout = QVBoxLayout(self)
        layout.addLayout(name_row)
        layout.addWidget(self.list_widget)
        layout.addWidget(self.delete_button)
        layout.addWidget(self.error_pane)

        self.save_button.clicked.connect(self._save)
        self.refresh_button.clicked.connect(self.refresh_queries)
        self.delete_button.clicked.connect(self._delete)

        # result_count of a save derives from the last published outcome
        state.result_arrived.connect(self._on_result)

    # -- seams for tests ------------------------------------------------------

    def set_queries(self, rows: list[SavedRow]) -> None:
        self._rows = list(rows)
        self.list_widget.clear()
        for _qid, question, cypher in self._rows:
            self.list_widget.addItem(QListWidgetItem(f"{question} — {cypher}"))

    def error_text(self) -> str:
        return self.error_pane.text()

    # -- behavior ---------------------------------------------------------------

    def refresh_queries(self) -> None:
        """Fetch the saved-query list from the API (explicit or on show)."""
        try:
            saved = self._client_factory().saved_queries()
        except (ApiError, ApiUnreachable) as exc:
            self._show_error(getattr(exc, "detail", str(exc)))
            return
        self._show_error(None)
        self.set_queries([(q.saved_query_id, q.question, q.cypher) for q in saved])

    def _on_result(self, bundle: QueryOutcomeBundle) -> None:
        result = bundle.result
        if isinstance(result, GraphResult):
            self._result_count = len(result.nodes)

    def _save(self) -> None:
        name = self.name_edit.text().strip()
        surface, text = self._current_query()
        text = text.strip()
        if not name or not text:
            return
        try:
            self._client_factory().save_query(
                name, surface, {"cypher": text, "result_count": self._result_count}
            )
        except (ApiError, ApiUnreachable) as exc:
            self._show_error(getattr(exc, "detail", str(exc)))
            return
        self._show_error(None)
        self.name_edit.clear()

    def _delete(self) -> None:
        row = self.list_widget.currentRow()
        if not (0 <= row < len(self._rows)):
            return
        saved_query_id = self._rows[row][0]
        try:
            self._client_factory().delete_saved_query(saved_query_id)
        except (ApiError, ApiUnreachable) as exc:
            self._show_error(getattr(exc, "detail", str(exc)))
            return
        self._show_error(None)
        del self._rows[row]
        self.list_widget.takeItem(row)

    def showEvent(self, event: Any) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        self.refresh_queries()

    def _show_error(self, detail: str | None) -> None:
        if detail is None:
            self.error_pane.setVisible(False)
            self.error_pane.setText("")
        else:
            self.error_pane.setText(detail)
            self.error_pane.setVisible(True)
