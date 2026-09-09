# desktop/tests/unit/test_search_debounce.py | v0.1.0 | FR-DC-010/011 search bar
from __future__ import annotations

from typing import Any

import pytest
from limes_desktop.state import SessionState
from limes_desktop.views.main_window import MainWindow
from limes_desktop.views.search import SearchBar
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from test_main_window_support import FakeClient


@pytest.fixture()
def state() -> SessionState:
    return SessionState()


def test_typing_fires_exactly_one_search_submitted_after_debounce(
    qtbot: Any, state: SessionState
) -> None:
    bar = SearchBar(state)
    qtbot.addWidget(bar)
    fired: list[str] = []
    bar.search_submitted.connect(fired.append)

    QTest.keyClicks(bar.line_edit, "acme")

    # during the 300 ms window nothing fires yet
    assert fired == []
    qtbot.waitUntil(lambda: fired != [], timeout=1000)
    assert fired == ["acme"]


def test_enter_on_highlighted_hit_sets_selection(qtbot: Any, state: SessionState) -> None:
    bar = SearchBar(state)
    qtbot.addWidget(bar)
    client = FakeClient()
    win = MainWindow(state, None, lambda: client)  # type: ignore[arg-type]
    qtbot.addWidget(win)

    bar.line_edit.setText("acme")
    win._run_search("acme")
    assert len(bar._hits) == 2

    selections: list[str | None] = []
    state.selection_changed.connect(selections.append)

    bar.line_edit.setFocus()
    QTest.keyClick(bar.line_edit, Qt.Key.Key_Down)
    QTest.keyClick(bar.line_edit, Qt.Key.Key_Return)

    assert selections == ["e1"]


def test_arrow_keys_move_list_selection(qtbot: Any, state: SessionState) -> None:
    bar = SearchBar(state)
    qtbot.addWidget(bar)
    client = FakeClient()
    win = MainWindow(state, None, lambda: client)  # type: ignore[arg-type]
    qtbot.addWidget(win)
    bar.line_edit.setText("acme")
    win._run_search("acme")

    assert bar.list_view.currentIndex().row() == -1
    QTest.keyClick(bar.line_edit, Qt.Key.Key_Down)
    assert bar.list_view.currentIndex().row() == 0
    QTest.keyClick(bar.line_edit, Qt.Key.Key_Down)
    assert bar.list_view.currentIndex().row() == 1
