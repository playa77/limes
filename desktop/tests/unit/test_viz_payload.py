# desktop/tests/unit/test_viz_payload.py | v0.1.0 | map/timeline payload shaping (FR-DC-041/042)
from __future__ import annotations

import json
from typing import Any

from limes_desktop.api.models import EdgeRef, EntityRef, GraphResult
from limes_desktop.state import QueryOutcomeBundle
from limes_desktop.views.viz.bridge import map_payload, timeline_payload


def _bundle(nodes: list[EntityRef], edges: list[EdgeRef]) -> QueryOutcomeBundle:
    return QueryOutcomeBundle(
        result=GraphResult(nodes=nodes, edges=edges, counts={"rows": len(nodes)}),
        coverage=None,
        source="cypher",
    )


def _node(eid: str, type_: str, **props: Any) -> EntityRef:
    return EntityRef(entity_id=eid, type=type_, label=eid.upper(), properties=dict(props))


def test_map_payload_excludes_null_geometry() -> None:
    bundle = _bundle(
        [
            _node("e-1", "Organization"),
            _node("e-2", "Location", latitude=52.5, longitude=13.4),
            _node("e-3", "Location", latitude=None, longitude=None),
        ],
        [],
    )
    payload = json.loads(map_payload(bundle))
    assert [n["id"] for n in payload["nodes"]] == ["e-2"]
    assert payload["nodes"][0]["geometry"] == [13.4, 52.5]  # Leaflet [lon, lat] order


def test_map_payload_marks_edges_of_selected_entity() -> None:
    bundle = _bundle(
        [
            _node("e-1", "Organization", latitude=51.0, longitude=12.0),
            _node("e-2", "Location", latitude=52.5, longitude=13.4),
        ],
        [EdgeRef(relation="located_in", subject_id="e-1", object_id="e-2")],
    )
    payload = json.loads(map_payload(bundle, selected_id="e-1"))
    assert payload["lines"][0]["points"] == [[12.0, 51.0], [13.4, 52.5]]
    assert payload["lines"][0]["selected"] is True


def test_timeline_payload_splits_validity_vs_belief() -> None:
    bundle = _bundle(
        [_node("e-1", "Organization")],
        [
            EdgeRef(
                relation="located_in",
                subject_id="e-1",
                object_id="e-1",
                valid_from="2020-01-01T00:00:00+00:00",
                recorded_at="2021-06-01T00:00:00+00:00",
            ),
            EdgeRef(relation="known_for", subject_id="e-1", object_id="e-1"),
        ],
    )
    payload = json.loads(timeline_payload(bundle))
    assert len(payload["validity"]) == 1
    assert payload["validity"][0]["t"] == "2020-01-01T00:00:00+00:00"
    assert payload["validity"][0]["kind"] == "validity"
    assert len(payload["belief"]) == 1
    assert payload["belief"][0]["t"] == "2021-06-01T00:00:00+00:00"
    assert payload["belief"][0]["kind"] == "belief"
    # an edge with neither timestamp appears in neither series
    assert all(e["relation"] != "known_for" for e in payload["validity"] + payload["belief"])


def test_timeline_payload_honors_temporal_filter() -> None:
    bundle = _bundle(
        [],
        [
            EdgeRef(
                relation="located_in",
                subject_id="a",
                object_id="b",
                valid_from="2019-01-01T00:00:00+00:00",
                recorded_at="2019-01-02T00:00:00+00:00",
            ),
            EdgeRef(
                relation="known_for",
                subject_id="a",
                object_id="b",
                valid_from="2023-01-01T00:00:00+00:00",
                recorded_at="2023-01-02T00:00:00+00:00",
            ),
        ],
    )
    payload = json.loads(timeline_payload(bundle, validity_from="2022-01-01"))
    assert [e["relation"] for e in payload["validity"]] == ["known_for"]
    assert [e["relation"] for e in payload["belief"]] == ["known_for"]
