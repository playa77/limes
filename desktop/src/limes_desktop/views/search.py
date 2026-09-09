# desktop/src/limes_desktop/views/search.py | v0.1.0 | Debounced search bar (FR-DC-010/011)
from __future__ import annotations

from PySide6.QtCore import (
    QAbstractListModel,
    QEvent,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QLineEdit, QListView, QVBoxLayout, QWidget

from limes_desktop.api.models import SearchHit
from limes_desktop.state import QueryOutcomeBundle, SessionState

DEBOUNCE_MS = 300


class _SearchListModel(QAbstractListModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._hits: list[SearchHit] = []

    def set_hits(self, hits: list[SearchHit]) -> None:
        self.beginResetModel()
        self._hits = list(hits)
        self.endResetModel()

    def rowCount(
        self,
        parent: QModelIndex | QPersistentModelIndex | None = None,
    ) -> int:  # noqa: N802
        if parent is not None and isinstance(parent, QModelIndex) and parent.isValid():
            return 0
        return len(self._hits)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if role == Qt.ItemDataRole.DisplayRole and 0 <= index.row() < len(self._hits):
            return self._hits[index.row()].label
        return None

    def hit_at(self, row: int) -> SearchHit | None:
        if 0 <= row < len(self._hits):
            return self._hits[row]
        return None


class SearchBar(QWidget):
    """Search input + hit list; 300 ms debounce, arrow/Enter keyboard flow."""

    search_submitted = Signal(str)

    def __init__(self, state: SessionState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state

        self.line_edit = QLineEdit(self)
        self.line_edit.setPlaceholderText("Search entities and documents…")
        self.list_view = QListView(self)
        self._model = _SearchListModel(self)
        self.list_view.setModel(self._model)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.line_edit)
        layout.addWidget(self.list_view)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(DEBOUNCE_MS)
        self._debounce.timeout.connect(self._fire_search)

        self.line_edit.textEdited.connect(self._debounce.start)
        self.line_edit.returnPressed.connect(self._fire_search)
        # arrow keys navigate the list while focus stays in the line edit
        self.line_edit.installEventFilter(self)

        state.result_arrived.connect(self._on_result)

    # -- seams for tests -----------------------------------------------------

    def _fire_search(self) -> None:
        text = self.line_edit.text().strip()
        if text:
            self.search_submitted.emit(text)

    @property
    def _hits(self) -> list[SearchHit]:
        return self._model._hits

    # -- behavior ------------------------------------------------------------

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self.line_edit and event.type() == QEvent.Type.KeyPress:
            assert isinstance(event, QKeyEvent)
            key = event.key()
            if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                row = self.list_view.currentIndex().row()
                if key == Qt.Key.Key_Down:
                    row = min(row + 1, self._model.rowCount() - 1)
                else:
                    row = max(row - 1, 0)
                if self._model.rowCount() > 0:
                    self.list_view.setCurrentIndex(
                        self._model.index(row, 0)
                    )
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._accept_current()
                return True
        return super().eventFilter(watched, event)

    def _accept_current(self) -> None:
        hit = self._model.hit_at(self.list_view.currentIndex().row())
        if hit is not None:
            self._state.set_selection(hit.id)

    def _on_result(self, bundle: QueryOutcomeBundle) -> None:
        if bundle.source != "search":
            return
        if isinstance(bundle.result, list):
            self._model.set_hits(bundle.result)
