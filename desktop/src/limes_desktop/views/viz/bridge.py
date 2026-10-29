# desktop/src/limes_desktop/views/viz/bridge.py | v0.1.0 | Qt-JS bridge + payload builders
"""Serialization contract shared by the three viz pages and their tests.

This module must stay importable without QtWebEngine: the QWebEngineView
subclass lives in `page.py` and is imported only when a viz view is actually
instantiated (NFR-DC-071 — the unit suite stays headless-safe).
"""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import QObject, Signal

from limes_desktop.api.models import EntityRef, GraphResult
from limes_desktop.state import QueryOutcomeBundle, SessionState, TemporalFilter

__all__ = ["VizBridge", "bundle_graph", "map_payload", "timeline_payload", "viz_page"]


def bundle_graph(bundle: QueryOutcomeBundle) -> GraphResult:
    """The GraphResult of a bundle, tolerating non-graph outcomes."""
    result = bundle.result
    return result if isinstance(result, GraphResult) else GraphResult()


def _entity_payload(node: EntityRef, geometry: list[float] | None) -> dict[str, Any]:
    return {
        "id": node.entity_id,
        "type": node.type,
        "label": node.label,
        "geometry": geometry,
        "claim": {
            key: node.properties.get(key)
            for key in (
                "modality",
                "attribution",
                "assessment",
                "event_status",
                "time_precision",
                "event_candidate",
                "evidence_document_id",
                "source_trust",
                "confidence",
            )
        }
        if node.properties.get("claim_id")
        else None,
    }


def _geometry_of(node: EntityRef) -> list[float] | None:
    lat = node.properties.get("latitude")
    lon = node.properties.get("longitude")
    if lat is None or lon is None:
        return None
    # Leaflet order: [longitude, latitude]
    return [float(lon), float(lat)]


def map_payload(bundle: QueryOutcomeBundle, selected_id: str | None = None) -> str:
    """FR-DC-041: point-geometry markers + the selected entity's geo polylines."""
    graph = bundle_graph(bundle)
    by_id = {n.entity_id: n for n in graph.nodes}
    nodes = [
        _entity_payload(n, _geometry_of(n)) for n in graph.nodes if _geometry_of(n) is not None
    ]

    lines: list[dict[str, Any]] = []
    for edge in graph.edges:
        if selected_id is None or selected_id not in (edge.subject_id, edge.object_id):
            continue
        a = _geometry_of(by_id[edge.subject_id]) if edge.subject_id in by_id else None
        b = _geometry_of(by_id[edge.object_id]) if edge.object_id in by_id else None
        if a is None or b is None:
            continue
        lines.append({"points": [a, b], "relation": edge.relation, "selected": True})

    return json.dumps({"nodes": nodes, "lines": lines, "coverage": None})


def timeline_payload(
    bundle: QueryOutcomeBundle,
    validity_from: str | None = None,
    validity_to: str | None = None,
) -> str:
    """FR-DC-042: one point per assertion instant, split validity vs belief."""
    graph = bundle_graph(bundle)
    validity: list[dict[str, Any]] = []
    belief: list[dict[str, Any]] = []
    for edge in graph.edges:
        base = {
            "relation": edge.relation,
            "source": edge.subject_id,
            "target": edge.object_id,
            "assertion_id": edge.assertion_id,
        }
        if (
            edge.valid_from
            and (validity_from is None or edge.valid_from >= validity_from)
            and (validity_to is None or edge.valid_from <= validity_to)
        ):
            validity.append({**base, "t": edge.valid_from, "kind": "validity"})
        if (
            edge.recorded_at
            and (validity_from is None or edge.recorded_at >= validity_from)
            and (validity_to is None or edge.recorded_at <= validity_to)
        ):
            belief.append({**base, "t": edge.recorded_at, "kind": "belief"})
    # Qualified artifacts stay separate from factual edges. Unknown event time
    # contributes only belief time; proposals/denials are explicitly labeled.
    for node in graph.nodes:
        props = node.properties
        if not props.get("claim_id"):
            continue
        base = {
            "relation": f"{props.get('modality', 'unknown')}: {props.get('relation', '')}",
            "source": props.get("subject_id"),
            "target": props.get("object_id"),
            "assertion_id": props["claim_id"],
            "event_status": props.get("event_status"),
            "time_precision": props.get("time_precision", "unknown"),
        }
        for name, series in (("valid_from", validity), ("recorded_at", belief)):
            instant = props.get(name)
            if name == "valid_from" and props.get("time_precision", "unknown") == "unknown":
                continue
            if (
                instant
                and (validity_from is None or instant >= validity_from)
                and (validity_to is None or instant <= validity_to)
            ):
                series.append(
                    {**base, "t": instant, "kind": "validity" if name == "valid_from" else "belief"}
                )
    return json.dumps({"validity": validity, "belief": belief, "coverage": None})


def network_payload(bundle: QueryOutcomeBundle) -> str:
    """FR-DC-040: the full nodes/edges/coverage JSON the network page renders."""
    graph = bundle_graph(bundle)
    nodes = [_entity_payload(n, None) for n in graph.nodes]
    edges = [
        {
            "source": e.subject_id,
            "target": e.object_id,
            "relation": e.relation,
            "confidence": e.confidence,
            "assertion_id": e.assertion_id,
            "valid_from": e.valid_from,
            "valid_to": e.valid_to,
            "belief_recorded_at": e.recorded_at,
        }
        for e in graph.edges
    ]
    coverage = bundle.coverage
    coverage_json: Any = (
        {
            "relation_counts": dict(coverage.relation_counts),
            "contributing_sources": list(coverage.contributing_sources),
        }
        if coverage is not None
        else None
    )
    return json.dumps({"nodes": nodes, "edges": edges, "coverage": coverage_json})


class VizBridge(QObject):
    """Slots the HTML pages call over QWebChannel + signals back into Qt."""

    selection_changed = Signal(str)
    expand_requested = Signal(str)
    temporal_filter_changed = Signal(str, str)  # validity_from, validity_to

    def __init__(self) -> None:
        super().__init__()
        self._state: SessionState | None = None
        self._selected_id: str | None = None

    def set_state(self, state: SessionState) -> None:
        self._state = state

    # -- slots called from JS (QWebChannel) ---------------------------------

    def push_result(self, bundle: QueryOutcomeBundle) -> str:
        """Default serialization for the network page (nodes/edges/coverage)."""
        return network_payload(bundle)

    def on_node_clicked(self, entity_id: str) -> None:
        self._selected_id = entity_id or None
        self.selection_changed.emit(entity_id)
        if self._state is not None and entity_id:
            self._state.set_selection(entity_id)

    def on_expand_clicked(self) -> None:
        """MainWindow wires `expand_requested` to ApiClient.entity_neighbors."""
        if self._selected_id is not None:
            self.expand_requested.emit(self._selected_id)

    def on_temporal_range(self, validity_from: str, validity_to: str) -> None:
        self.temporal_filter_changed.emit(validity_from, validity_to)
        if self._state is not None:
            self._state.set_temporal_filter(
                TemporalFilter(validity_from=validity_from, validity_to=validity_to)
            )

    def selected_id(self) -> str | None:
        return self._selected_id


def viz_page(*args: Any, **kwargs: Any) -> Any:
    """Import-lazy VizPage factory (NFR-DC-071)."""
    from limes_desktop.views.viz.page import VizPage

    return VizPage(*args, **kwargs)
