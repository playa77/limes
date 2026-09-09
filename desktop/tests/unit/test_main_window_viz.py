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


def test_viz_construction_does_not_load_webengine(qtbot: Any) -> None:
    # NFR-DC-071: importing the app shell (which only lazily imports the viz
    # modules inside __init__) must not pull in QtWebEngine
    import os
    import subprocess
    import sys

    desktop_src = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "src")
    )
    code = (
        "import sys; import limes_desktop.views.main_window; "
        "assert 'PySide6.QtWebEngineWidgets' not in sys.modules"
        " or sys.exit('eager webengine import'); print('ok')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=60,
        env={**os.environ, "PYTHONPATH": desktop_src},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("ok")
