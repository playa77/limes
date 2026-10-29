# desktop/tests/unit/test_main_window_viz.py | v0.1.0 | MainWindow registers viz views (Task 9)
from __future__ import annotations

from typing import Any

from limes_desktop.config import ProfileStore
from limes_desktop.state import SessionState
from limes_desktop.views.main_window import MainWindow
from test_main_window_support import FakeClient


def test_viz_views_registered_in_stack(qtbot: Any) -> None:
    state = SessionState()
    win = MainWindow(state, ProfileStore(), FakeClient)  # type: ignore[arg-type]
    qtbot.addWidget(win)

    # viz views must exist and sit in the stack, but must not instantiate
    # QWebEngineView at construction time (NFR-DC-071: lazy)
    assert win.stack.widget(5) is win.network_view
    assert win.stack.widget(6) is win.map_view
    assert win.stack.widget(7) is win.timeline_view


def test_viz_construction_does_not_load_webengine(qtbot: Any, record_property: Any) -> None:
    # NFR-DC-071: importing the app shell (which only lazily imports the viz
    # modules inside __init__) must not pull in QtWebEngine
    import os
    import subprocess
    import sys

    desktop_src = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "src")
    )
    import json

    code = """
import json, sys, time
start = time.monotonic()
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import QThreadPool
from limes_desktop.state import SessionState
from limes_desktop.views.main_window import MainWindow
from test_main_window_support import FakeClient
app = QApplication([])
win = MainWindow(SessionState(), None, FakeClient)
win.show()
win.search_bar.line_edit.setFocus()
QTest.keyClicks(win.search_bar.line_edit, 'ready')
assert win.search_bar.line_edit.text() == 'ready'
assert 'PySide6.QtWebEngineWidgets' not in sys.modules
assert 'PySide6.QtWebEngineCore' not in sys.modules
print(json.dumps({'startup_to_search_seconds': time.monotonic() - start,
                  'platform': 'offscreen', 'webengine_loaded': False}))
QThreadPool.globalInstance().waitForDone()
win.close()
"""
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=60,
        env={**os.environ, "PYTHONPATH": desktop_src + os.pathsep + os.path.dirname(__file__)},
    )
    assert result.returncode == 0, result.stderr
    observation = json.loads(result.stdout.strip().splitlines()[-1])
    record_property("offscreen_cold_start_seconds", observation["startup_to_search_seconds"])
    assert observation["webengine_loaded"] is False
