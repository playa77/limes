# desktop/src/limes_desktop/views/query_cypher.py | v0.1.0 | FR-DC-032: console + history.json
"""Cypher console: free-form Cypher editor, history combo, verbatim errors.

History is populated from `SessionState.history()` entries whose source is
`cypher` or `nlq-run` (most recent last). Cross-session persistence is
opt-in via the toolbar checkbox: when enabled, executed queries are written
to `history.json` next to `profiles.json` in the config dir (off by default).
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from limes_desktop.api.errors import ApiError, ApiUnreachable
from limes_desktop.state import QueryOutcomeBundle, SessionState

HISTORY_SOURCES = frozenset({"cypher", "nlq-run"})
_HISTORY_MAX = 100


class HistoryStore:
    """Optional cross-session query history persisted to history.json."""

    def __init__(self, config_dir: Path | None = None) -> None:
        self._dir = (
            config_dir
            if config_dir is not None
            else Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
            / "limes-desktop"
        )
        self.enabled = False

    @property
    def _file(self) -> Path:
        return self._dir / "history.json"

    def load(self) -> list[str]:
        try:
            raw = json.loads(self._file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(raw, list):
            return []
        entries = [str(item) for item in raw if isinstance(item, str)]
        return entries[-_HISTORY_MAX:]

    def append(self, query: str) -> None:
        entries = self.load()
        entries.append(query)
        entries = entries[-_HISTORY_MAX:]
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file.write_text(json.dumps(entries, indent=2), encoding="utf-8")


class CypherConsole(QWidget):
    """Free-form Cypher surface (FR-DC-032) with history and saved-query input."""

    def __init__(
        self,
        state: SessionState,
        client_factory: Callable[[], Any],
        history_store: HistoryStore | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._client_factory = client_factory
        self._history_store = history_store

        self.editor = QPlainTextEdit(self)
        self.editor.setPlaceholderText("MATCH (n) RETURN n …")
        self.run_button = QPushButton("Run", self)
        self.history = QComboBox(self)
        self.history.setEnabled(False)
        self.error_pane = QLabel("", self)
        self.error_pane.setWordWrap(True)
        self.error_pane.setStyleSheet("color: #c62828;")
        self.error_pane.setVisible(False)
        self.persist_checkbox = QCheckBox("persist history across sessions", self)

        toolbar_row = QVBoxLayout()
        toolbar_row.addWidget(self.persist_checkbox)
        toolbar_row.addWidget(self.history)

        layout = QVBoxLayout(self)
        layout.addLayout(toolbar_row)
        layout.addWidget(self.editor)
        layout.addWidget(self.run_button)
        layout.addWidget(self.error_pane)
        layout.addStretch(1)

        self.run_button.clicked.connect(self._run)
        self.history.activated.connect(self._on_history_pick)
        self.persist_checkbox.toggled.connect(self._on_persist_toggled)

    # -- seams for tests ------------------------------------------------------

    def error_text(self) -> str:
        return self.error_pane.text()

    def refresh_history(self) -> None:
        entries = [
            b.cypher for b in self._state.history() if b.source in HISTORY_SOURCES and b.cypher
        ]
        if self._history_store is not None and self._history_store.enabled:
            entries = self._history_store.load() + entries
        entries = entries[-_HISTORY_MAX:]
        self.history.blockSignals(True)
        self.history.clear()
        for entry in entries:
            self.history.addItem(entry)
        self.history.setEnabled(bool(entries))
        self.history.blockSignals(False)

    # -- behavior ---------------------------------------------------------------

    def _run(self) -> None:
        cypher = self.editor.toPlainText().strip()
        if not cypher:
            return
        try:
            outcome = self._client_factory().query_cypher(cypher)
        except (ApiError, ApiUnreachable) as exc:
            # verbatim detail (§4 / FR-DC-032)
            self._show_error(getattr(exc, "detail", str(exc)))
            return
        self._show_error(None)
        if self._history_store is not None and self._history_store.enabled:
            self._history_store.append(cypher)
        self._state.publish(
            QueryOutcomeBundle(
                result=outcome.results,
                coverage=outcome.coverage,
                source="cypher",
                cypher=cypher,
            )
        )
        self.refresh_history()

    def _on_history_pick(self, index: int) -> None:
        text = self.history.itemText(index)
        self.editor.setPlainText(text)

    def _on_persist_toggled(self, checked: bool) -> None:
        if self._history_store is not None:
            self._history_store.enabled = checked
            if checked:
                self.refresh_history()

    def _show_error(self, detail: str | None) -> None:
        if detail is None:
            self.error_pane.setVisible(False)
            self.error_pane.setText("")
        else:
            self.error_pane.setText(detail)
            self.error_pane.setVisible(True)
