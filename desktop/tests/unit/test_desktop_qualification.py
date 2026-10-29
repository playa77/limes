"""DC-14 regressions: admissible chains, real web bridge, network and UI recovery."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from limes_desktop.api.errors import ApiUnreachable
from limes_desktop.api.models import EdgeRef, EntityRef, GraphResult
from limes_desktop.config import ProfileStore
from limes_desktop.state import QueryOutcomeBundle, SessionState, TemporalFilter
from limes_desktop.views.main_window import MainWindow
from limes_desktop.views.query_builder import BuilderView
from limes_desktop.views.viz.bridge import map_payload, temporal_bundle
from test_main_window_support import FakeClient


def test_builder_self_both_and_entire_suffix_refill(qtbot: Any) -> None:
    view = BuilderView(SessionState(), FakeClient)
    qtbot.addWidget(view)
    view.set_schema(
        {
            "entity_types": [{"name": name} for name in ("A", "B", "C", "D")],
            "relation_types": [
                {"name": "both", "domain": ["A", "C"], "range": ["A", "B"]},
                {"name": "next", "domain": ["B"], "range": ["D"]},
            ],
        }
    )
    first = view.hop_rows[0]
    first.direction_combo.setCurrentIndex(first.direction_combo.findData("in"))
    assert first.direction_combo.currentData() == "in"  # never reset to outgoing
    first.target_combo.setCurrentText("C")
    view.add_hop()
    view.add_hop()
    # A change invalidates choices all the way down, not just the immediate row.
    view.start_type_combo.setCurrentText("D")
    assert view.hop_rows[0].relation_combo.count() == 1
    spec = view._spec()
    assert spec is not None
    assert spec["hops"][0] == {"relation": "next", "direction": "in", "target_type": "B"}
    current = spec["start_type"]
    for hop in spec["hops"]:
        assert hop["direction"] in view._directions_for(current, hop["relation"])
        current = hop["target_type"]


def test_temporal_intervals_belief_offsets_and_unknown_geometry(qtbot: Any) -> None:
    from limes_desktop.views.viz.map import MapView
    from limes_desktop.views.viz.network import NetworkView
    from limes_desktop.views.viz.timeline import TimelineView

    state = SessionState()
    views = [NetworkView(state), MapView(state), TimelineView(state)]
    for view in views:
        qtbot.addWidget(view)
        state.result_arrived.connect(view.on_result_arrived)
    nodes = [
        EntityRef(key, "test", key, props)
        for key, props in (
            ("a", {"latitude": 52.5, "longitude": 13.4}),
            ("b", {"latitude": float("nan"), "longitude": 0}),
            ("c", {"latitude": "invalid", "longitude": 190}),
        )
    ]
    bundle = QueryOutcomeBundle(
        GraphResult(
            nodes=nodes,
            edges=[
                EdgeRef(
                    "overlap",
                    "a",
                    "b",
                    valid_from="2019-01-01",
                    valid_to="2022-01-01",
                    recorded_at="2021-01-01T01:00:00+01:00",
                ),
                EdgeRef("future", "a", "b", recorded_at="2023-01-01"),
                EdgeRef("retracted", "a", "b", recorded_at="2018-01-01", retracted_at="2020-01-01"),
                EdgeRef("unknown", "a", "b"),
            ],
        ),
        None,
        "test",
    )
    state.publish(bundle)
    state.set_selection("a")
    state.set_temporal_filter(TemporalFilter("2021-01-01", "2021-01-01", "2021-01-01T00:00:00Z"))
    filtered = temporal_bundle(bundle, state.temporal_filter)
    assert [e.relation for e in filtered.result.edges] == ["overlap", "unknown"]
    payloads = [json.loads(view._pending_payload) for view in views]
    assert [e["relation"] for e in payloads[0]["edges"]] == ["overlap", "unknown"]
    assert all(payload["selected_id"] == "a" for payload in payloads)
    assert payloads[1]["missing_geometry"] == 2
    assert json.loads(map_payload(bundle))["nodes"][0]["geometry"] == [52.5, 13.4]
    assert payloads[2]["validity"][0]["t"] == "2019-01-01"
    assert len(bundle.result.edges) == 4  # filtering never mutates evidence/history


def test_startup_remains_interactive_and_probe_recovers(qtbot: Any, tmp_path: Path) -> None:
    gate = threading.Event()

    class SlowClient(FakeClient):
        def health(self):
            gate.wait(3)
            return super().health()

    client = SlowClient()
    start = time.monotonic()
    win = MainWindow(SessionState(), ProfileStore(tmp_path), lambda: client)
    qtbot.addWidget(win)
    win.show()
    win.search_bar.line_edit.setText("interactive before health")
    assert time.monotonic() - start < 3
    qtbot.waitUntil(lambda: bool(win.banner._tasks))
    assert win.search_bar.line_edit.isEnabled()
    gate.set()
    qtbot.waitUntil(lambda: win.banner.status_text() == "ok")
    client.fail = True
    win.banner.refresh_async()
    qtbot.waitUntil(lambda: win.banner.status_text() == "degraded")
    assert win.banner._timer.isActive()
    client.fail = False
    win.banner.refresh_async()
    qtbot.waitUntil(lambda: win.banner.status_text() == "ok")
    assert all(view._view is None for view in (win.network_view, win.map_view, win.timeline_view))


def test_profile_probe_cannot_replace_current_connection(qtbot: Any, tmp_path: Path) -> None:
    gate = threading.Event()

    class OldClient(FakeClient):
        def health(self):
            gate.wait(3)
            raise ApiUnreachable("old profile")

    old, current = OldClient(), FakeClient()
    holder = [old]
    win = MainWindow(SessionState(), ProfileStore(tmp_path), lambda: holder[0])
    qtbot.addWidget(win)
    qtbot.waitUntil(lambda: bool(win.banner._tasks))
    holder[0] = current
    win._state.set_connection(None)
    qtbot.waitUntil(lambda: win.banner.status_text() == "ok")
    gate.set()
    qtbot.waitUntil(lambda: not win.banner._tasks)
    assert win.banner.status_text() == "ok"


def test_network_policy_denies_external_and_outside_local_assets(tmp_path: Path) -> None:
    from limes_desktop.views.viz.network_policy import LocalResourcesOnly
    from PySide6.QtCore import QUrl

    asset = tmp_path / "assets"
    asset.mkdir()
    (asset / "local.js").write_text("// local")
    guard = LocalResourcesOnly(asset)
    assert guard.allows(QUrl.fromLocalFile(str(asset / "local.js")))
    assert guard.allows(QUrl("qrc:///qtwebchannel/qwebchannel.js"))
    for url in (
        "https://tile.openstreetmap.org/1/1/1.png",
        "http://127.0.0.1:8000/health",
        "file:///etc/passwd",
        "wss://outside.test",
        "data:text/html,test",
    ):

        class Request:
            blocked = False

            def requestUrl(self, selected=url):
                return QUrl(selected)

            def block(self, value):
                self.blocked = value

        request = Request()
        guard.interceptRequest(request)
        assert request.blocked, url  # deliberate forbidden URL must fail closed
    assert len(guard.blocked_urls) == 5


def test_actual_web_pages_selection_render_and_forbidden_request(tmp_path: Path) -> None:
    code = r"""
import json
import shiboken6
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication
from limes_desktop.api.models import EntityRef, EdgeRef, GraphResult
from limes_desktop.state import SessionState, QueryOutcomeBundle
from limes_desktop.views.viz.map import MapView
from limes_desktop.views.viz.network import NetworkView
from limes_desktop.views.viz.timeline import TimelineView

app = QApplication([])
def wait(predicate):
    loop = QEventLoop()
    timer = QTimer()
    timer.timeout.connect(lambda: loop.quit() if predicate() else None)
    timer.start(20)
    QTimer.singleShot(15000, loop.quit)
    loop.exec()
    timer.stop()
    assert predicate(), 'timed out'
def js(page, expression):
    results = []
    page.runJavaScript(expression, results.append)
    wait(lambda: bool(results))
    return results[0]
state = SessionState()
bundle = QueryOutcomeBundle(GraphResult(nodes=[
    EntityRef('a', 'test', '<b>literal</b>', {'latitude': 52.5, 'longitude': 13.4}),
    EntityRef('b', 'test', 'B', {'latitude': 51.0, 'longitude': 12.0}),
], edges=[EdgeRef('test', 'a', 'b', valid_from='2020-01-01',
                 recorded_at='2021-01-01')]), None, 'test')
for kind in (NetworkView, MapView, TimelineView):
    view = kind(state)
    view.resize(800, 600)
    view.on_result_arrived(bundle)
    view.show()
    wait(lambda: view._loaded)
    page = view._page
    wait(lambda: js(page, "typeof bridge !== 'undefined' && bridge !== null") == True)
    assert js(page, "typeof bridge.on_node_clicked") == 'function'
    if kind is MapView:
        assert js(page, 'markerLayer.getLayers().length') == 2
        point = js(page, 'JSON.stringify(markerLayer.getLayers()[0].getLatLng())')
        assert json.loads(point) == {'lat':52.5,'lng':13.4}
        js(page, "markerLayer.getLayers()[0].fire('click'); true")
    elif kind is NetworkView:
        assert js(page, 'cy.nodes().length') == 2
        js(page, "cy.getElementById('a').emit('tap'); true")
    else:
        wait(lambda: js(page, "!!document.getElementById('tl').data") == True)
        assert js(page, "document.getElementById('tl').data[1].name") == 'belief time (recorded_at)'
        js(page, "document.getElementById('tl').emit('plotly_click', "
                 "{points:[{customdata:'a'}]}); true")
    wait(lambda: state.selection == 'a')
    state.set_selection(None)
    from PySide6.QtWebEngineCore import QWebEngineSettings
    page.settings().setAttribute(
        QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
    # Deliberate forbidden resource: the real interceptor must observe and reject it.
    js(page, "var denied = new Image(); denied.src='https://forbidden.invalid/dc14.png';")
    wait(lambda: any('forbidden.invalid' in url for url in view._network_guard.blocked_urls))
    shiboken6.delete(view)
print('real web render, Qt slots and blocked requests passed')
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "XDG_CACHE_HOME": str(tmp_path)},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "blocked requests passed" in result.stdout
