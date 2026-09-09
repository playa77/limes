# desktop/src/limes_desktop/views/query_history.py | v0.1.0 | FR-DC-033: saved queries panel
"""Saved queries panel: save the current query text under a name, list saved
queries, delete. Save captures surface ("nlq" | "cypher") plus the query
text; delete calls `ApiClient.delete_saved_query`.
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
from limes_desktop.state import SessionState

SavedRow = tuple[str, str, str]  # (saved_query_id, question, cypher)


class SavedQueriesPanel(QWidget):
    """Save/delete saved queries (FR-DC-033)."""

    def __init__(
        self,
        state: SessionState,
        client_factory: Callable[[], Any],
        query_text: Callable[[], str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._client_factory = client_factory
        self._query_text = query_text
        self._rows: list[SavedRow] = []

        self.name_edit = QLineEdit(self)
        self.name_edit.setPlaceholderText("saved query name…")
        self.save_button = QPushButton("Save", self)
        self.list_widget = QListWidget(self)
        self.delete_button = QPushButton("Delete", self)
        self.error_pane = QLabel("", self)
        self.error_pane.setWordWrap(True)
        self.error_pane.setStyleSheet("color: #c62828;")
        self.error_pane.setVisible(False)

        name_row = QHBoxLayout()
        name_row.addWidget(self.name_edit)
        name_row.addWidget(self.save_button)

        layout = QVBoxLayout(self)
        layout.addLayout(name_row)
        layout.addWidget(self.list_widget)
        layout.addWidget(self.delete_button)
        layout.addWidget(self.error_pane)

        self.save_button.clicked.connect(self._save)
        self.delete_button.clicked.connect(self._delete)

    # -- seams for tests ------------------------------------------------------

    def set_queries(self, rows: list[SavedRow]) -> None:
        self._rows = list(rows)
        self.list_widget.clear()
        for _qid, question, cypher in self._rows:
            self.list_widget.addItem(QListWidgetItem(f"{question} — {cypher}"))

    def error_text(self) -> str:
        return self.error_pane.text()

    # -- behavior ---------------------------------------------------------------

    def _save(self) -> None:
        name = self.name_edit.text().strip()
        text = self._query_text().strip()
        if not name or not text:
            return
        try:
            self._client_factory().save_query(name, text, {"result_count": 0, "pinned": False})
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

    def _show_error(self, detail: str | None) -> None:
        if detail is None:
            self.error_pane.setVisible(False)
            self.error_pane.setText("")
        else:
            self.error_pane.setText(detail)
            self.error_pane.setVisible(True)
