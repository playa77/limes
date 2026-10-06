# desktop/tests/unit/test_viz_page.py | v0.1.0 | lazy rendering and native shutdown guards
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from limes_desktop.api.models import GraphResult
from limes_desktop.config import ProfileStore
from limes_desktop.state import QueryOutcomeBundle, SessionState
from limes_desktop.views.main_window import MainWindow
from test_main_window_support import FakeClient


def test_result_does_not_initialize_hidden_viz_views(qtbot: Any) -> None:
    state = SessionState()
    win = MainWindow(state, ProfileStore(), FakeClient)  # type: ignore[arg-type]
    qtbot.addWidget(win)
    state.publish(QueryOutcomeBundle(result=GraphResult(), coverage=None, source="cypher"))

    for view in (win.network_view, win.map_view, win.timeline_view):
        assert view._view is None
        assert view._page is None
        assert view._pending_payload is not None


def test_visible_page_flushes_latest_payload_and_shuts_down(tmp_path: Path) -> None:
    # A subprocess checks the native teardown exit status, which a normal
    # assertion in the parent pytest process cannot detect.
    (tmp_path / "test.html").write_text(
        "<html><script>window.pushResult = value => window.payload = value;</script></html>"
    )
    code = '''
import sys
from pathlib import Path
import shiboken6
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from limes_desktop.state import SessionState
from limes_desktop.views.viz import page as module

app = QApplication([])
module.WEB_DIR = Path(sys.argv[1])
view = module.VizPage('test.html', SessionState())
view.push_payload('{"value": 1}')
view.push_payload('{"value": 2}')
assert view._view is None and view._page is None
view.show()
page = view._page
assert page is not None
profile = page.profile()
assert profile.isOffTheRecord()
assert profile.parent() is page

def loaded(ok):
    if not ok:
        app.exit(2)
        return
    page.runJavaScript('JSON.stringify(window.payload)',
        lambda value: app.exit(0 if value == '{"value":2}' else 3))

page.loadFinished.connect(loaded)
QTimer.singleShot(10000, lambda: app.exit(4))
assert app.exec() == 0
order = []
page.destroyed.connect(lambda: order.append('page'))
profile.destroyed.connect(lambda: order.append('profile'))
shiboken6.delete(view)
assert order == ['page', 'profile'], order
print('rendered and destroyed')
'''
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)],
        capture_output=True, text=True, timeout=30,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "XDG_CACHE_HOME": str(tmp_path)},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "rendered and destroyed" in result.stdout
    assert "WebEnginePage still not deleted" not in result.stderr
