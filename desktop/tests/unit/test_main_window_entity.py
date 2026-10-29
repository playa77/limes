# desktop/tests/unit/test_main_window_entity.py | v0.1.0 | MainWindow registers EntityView (Task 6)
from __future__ import annotations

from typing import Any

from limes_desktop.config import ProfileStore
from limes_desktop.state import SessionState
from limes_desktop.views.entity import EntityView
from limes_desktop.views.main_window import MainWindow
from test_main_window_support import FakeClient


def test_entity_view_registered_in_stack(qtbot: Any) -> None:
    state = SessionState()
    win = MainWindow(state, ProfileStore(), FakeClient)  # type: ignore[arg-type]
    qtbot.addWidget(win)

    assert isinstance(win.entity_view, EntityView)
    assert win.entity_view in [win.stack.widget(i) for i in range(win.stack.count())]
    # Task-5 seams intact: startup probe ran, banner present
    qtbot.waitUntil(lambda: win.banner.status_text() == "ok")
    assert win.banner.version_label_text() == "ontology 1.0.0"
