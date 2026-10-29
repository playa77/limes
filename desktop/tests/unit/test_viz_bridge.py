# desktop/tests/unit/test_viz_bridge.py | v0.1.0 | VizBridge contract + selection (FR-DC-040..043)
from __future__ import annotations

import json
from typing import Any

from limes_desktop.api.models import EdgeRef, EntityRef, GraphResult
from limes_desktop.state import QueryOutcomeBundle, SessionState
from limes_desktop.views.viz.bridge import VizBridge, map_payload


def _bundle(nodes: list[EntityRef], edges: list[EdgeRef]) -> QueryOutcomeBundle:
    return QueryOutcomeBundle(
        result=GraphResult(nodes=nodes, edges=edges, counts={"rows": len(nodes)}),
        coverage=None,
        source="cypher",
        cypher="MATCH (n) RETURN n",
    )


def _node(eid: str, type_: str, **props: Any) -> EntityRef:
    return EntityRef(entity_id=eid, type=type_, label=eid.upper(), properties=dict(props))


def test_push_result_serializes_exact_contract() -> None:
    bridge = VizBridge()
    bundle = _bundle(
        [_node("e-1", "Organization"), _node("e-2", "Place", latitude=52.5, longitude=13.4)],
        [EdgeRef(relation="located_in", subject_id="e-1", object_id="e-2", confidence=0.9)],
    )
    payload = json.loads(bridge.push_result(bundle))
    assert set(payload.keys()) == {"nodes", "edges", "coverage"}
    assert payload["nodes"][0]["id"] == "e-1"
    assert payload["nodes"][0]["type"] == "Organization"
    assert payload["nodes"][1]["geometry"] is None  # geometry is map-payload-only
    # the map payload (FR-DC-041) carries point geometry in Leaflet order
    assert json.loads(map_payload(bundle))["nodes"][0]["geometry"] == [52.5, 13.4]
    assert payload["edges"][0]["relation"] == "located_in"
    assert payload["edges"][0]["source"] == "e-1"
    assert payload["edges"][0]["target"] == "e-2"
    assert payload["coverage"] is None


def test_on_node_clicked_emits_selection_changed() -> None:
    bridge = VizBridge()
    seen: list[str] = []
    bridge.selection_changed.connect(seen.append)
    bridge.on_node_clicked("e-1")
    assert seen == ["e-1"]
    bridge.on_node_clicked("")  # empty click clears the selection
    assert seen == ["e-1", ""]


def test_expand_requested_emits_selected_node_id() -> None:
    bridge = VizBridge()
    seen: list[str] = []
    bridge.expand_requested.connect(seen.append)
    bridge.on_node_clicked("e-7")
    bridge.on_expand_clicked()
    assert seen == ["e-7"]


def test_on_temporal_range_emits_temporal_filter() -> None:
    state = SessionState()
    bridge = VizBridge()
    bridge.set_state(state)
    seen: list[Any] = []
    state.temporal_filter_changed.connect(seen.append)
    bridge.on_temporal_range("2020-01-01", "2024-01-01")
    assert len(seen) == 1
    assert seen[0].validity_from == "2020-01-01"
    assert seen[0].validity_to == "2024-01-01"


def test_bridge_module_is_headless_safe() -> None:
    # NFR-DC-071: importing the bridge module must not pull in QWebEngine.
    # Run in a subprocess so earlier test-module imports can't pollute sys.modules.
    import os
    import subprocess
    import sys

    desktop_src = os.path.join(os.path.dirname(__file__), "..", "..", "src")
    code = (
        "import sys; import limes_desktop.views.viz.bridge as m; "
        "assert 'PySide6.QtWebEngineWidgets' not in sys.modules; "
        "assert not hasattr(m, 'QWebEngineView'); print('ok')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=60,
        env={**os.environ, "PYTHONPATH": os.path.abspath(desktop_src)},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("ok")


def test_belief_vs_validity_split_in_push_result() -> None:
    bridge = VizBridge()
    bundle = _bundle(
        [_node("e-1", "Organization")],
        [
            EdgeRef(
                relation="located_in",
                subject_id="e-1",
                object_id="e-1",
                valid_from="2020-01-01T00:00:00+00:00",
                recorded_at="2021-06-01T00:00:00+00:00",
            )
        ],
    )
    payload = json.loads(bridge.push_result(bundle))
    edge = payload["edges"][0]
    assert edge["valid_from"] == "2020-01-01T00:00:00+00:00"
    assert edge["belief_recorded_at"] == "2021-06-01T00:00:00+00:00"
