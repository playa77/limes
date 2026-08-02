# src/limes/ui/callbacks/selection.py | v1.0.0 | introduced by WP-36
"""Shared selection state (Doc 1 §6.5, AC-29): the callbacks that turn a
tap in any pane into a `selection` store update, and the single
`render_panes` callback that re-renders all three panes from
(`current-result`, `selection`) — one interaction cycle, three panes.

The panes' render functions are pure and take the selection explicitly, so
the AC-29 property is testable by calling `render_panes` directly. The
dash callback-context reads live behind the `triggered_*` helpers, which
tests replace with fixed values.
"""

from __future__ import annotations

import json
from typing import Any

from dash import ALL, Input, Output, State, ctx, no_update
from dash.exceptions import PreventUpdate

from limes.ui import api_client as api
from limes.ui.components import map as map_component
from limes.ui.components import network as network_component
from limes.ui.components import provenance as provenance_component
from limes.ui.components import timeline as timeline_component

_EMPTY_RESULT = {"nodes": [], "edges": [], "counts": {"rows": 0, "nodes": 0, "edges": 0}}


def triggered_prop_id() -> str | None:
    """The triggered input's `prop_id` inside a callback, or None. The only
    place the dash callback context is read; tests stub this."""
    if not ctx.triggered:
        return None
    return str(ctx.triggered[0]["prop_id"])


def triggered_index(component_type: str) -> int | None:
    """The `index` of a pattern-matched component that triggered, decoded
    from the `prop_id`; None when the trigger is not of that type."""
    prop_id = triggered_prop_id()
    if not prop_id or not prop_id.startswith("{"):
        return None
    try:
        component_id = json.loads(prop_id.rsplit(".", 1)[0])
    except ValueError:
        return None
    if component_id.get("type") != component_type:
        return None
    index = component_id.get("index")
    return int(index) if isinstance(index, (int, float)) else None


def triggered_marker_entity_id() -> str | None:
    """The entity id of the map marker that triggered, decoded from the
    pattern id; None when the trigger is not a marker click."""
    prop_id = triggered_prop_id()
    if not prop_id or not prop_id.startswith("{"):
        return None
    try:
        component_id = json.loads(prop_id.rsplit(".", 1)[0])
    except ValueError:
        return None
    if component_id.get("type") != "map-marker":
        return None
    return str(component_id.get("index")) if component_id.get("index") is not None else None


def _node_selection(
    entity_id: str, label: str | None = None, type_name: str | None = None
) -> dict[str, Any]:
    return {
        "kind": "node",
        "entity": {"entity_id": entity_id, "label": label, "type": type_name},
    }


def _neighbor_filters(temporal_filter: dict[str, Any] | None) -> dict[str, Any]:
    """The temporal filter applied to a neighborhood expansion: the brush's
    `as_of` instant travels as the neighbors endpoint's `as_of` parameter —
    the API's sanctioned temporal read path (D-11)."""
    if not temporal_filter or not temporal_filter.get("as_of"):
        return {}
    return {"as_of": temporal_filter["as_of"]}


def node_tapped(
    tap_data: dict[str, Any] | None,
    current_result: dict[str, Any] | None,
    temporal_filter: dict[str, Any] | None,
) -> tuple[dict[str, Any] | Any, dict[str, Any] | Any]:
    """AC-27: a node tap selects the node and expands one hop through the
    neighbors endpoint, folding the neighborhood into the stored result —
    the original query is never re-run (the query callbacks are not
    involved). An expansion that fails still selects the node."""
    if not tap_data or not tap_data.get("entity_id"):
        raise PreventUpdate
    entity_id = str(tap_data["entity_id"])
    selection = _node_selection(entity_id, tap_data.get("label"), tap_data.get("type"))
    try:
        neighbors = api.get_entity_neighbors(entity_id, _neighbor_filters(temporal_filter))
    except Exception:
        return selection, no_update  # the API's answer stands; only the selection changes
    merged = network_component.merge_neighborhood(current_result or {}, neighbors)
    return selection, merged


def edge_tapped(tap_data: dict[str, Any] | None) -> dict[str, Any] | Any:
    """AC-28's selection half: an edge tap stores the full edge ref — the
    provenance panel then renders everything client-side, plus the
    originating sentence when the evidence document is available."""
    if not tap_data or not tap_data.get("edge"):
        raise PreventUpdate
    return {"kind": "edge", "edge": tap_data["edge"]}


def marker_tapped(
    n_clicks: list[Any] | None,
    current_result: dict[str, Any] | None,
) -> dict[str, Any] | Any:
    """A map marker click selects the node; the clicked marker is identified
    from the callback context, never from the click count order."""
    entity_id = triggered_marker_entity_id()
    if entity_id is None or not n_clicks:
        raise PreventUpdate
    selected = None
    for node in (current_result or {}).get("nodes", []):
        if str(node.get("entity_id")) == entity_id:
            selected = node
            break
    if selected is not None:
        return _node_selection(entity_id, selected.get("label"), selected.get("type"))
    return _node_selection(entity_id)


def render_panes(
    current_result: dict[str, Any] | None,
    selection: dict[str, Any] | None,
    temporal_filter: dict[str, Any] | None,
    builder_schema: dict[str, Any] | None,
) -> tuple[Any, Any, Any]:
    """The one interaction-cycle render: any change to the result or the
    selection re-renders all three panes (AC-29). The stored value is the
    query response envelope; a bare results dict is tolerated."""
    results = _EMPTY_RESULT
    if isinstance(current_result, dict):
        nested = current_result.get("results")
        results = nested if isinstance(nested, dict) else current_result
    return (
        network_component.render(results, selection),
        map_component.render(results, selection, builder_schema),
        timeline_component.render(results, selection, temporal_filter),
    )


def render_provenance(selection: dict[str, Any] | None) -> Any:
    """The provenance panel for the current selection (AC-28)."""
    return provenance_component.render(selection, api)


def register(app: Any) -> None:
    """Wire the selection callbacks into the Dash app."""

    @app.callback(  # type: ignore[untyped-decorator]
        Output("selection", "data"),
        Output("current-result", "data"),
        Input("network-graph", "tapNodeData"),
        State("current-result", "data"),
        State("temporal-filter", "data"),
    )
    def _node_tapped_wrapper(
        tap_data: dict[str, Any] | None,
        current: dict[str, Any] | None,
        temporal: dict[str, Any] | None,
    ) -> Any:
        return node_tapped(tap_data, current, temporal)

    @app.callback(  # type: ignore[untyped-decorator]
        Output("selection", "data"),
        Input("network-graph", "tapEdgeData"),
    )
    def _edge_tapped_wrapper(tap_data: dict[str, Any] | None) -> Any:
        return edge_tapped(tap_data)

    @app.callback(  # type: ignore[untyped-decorator]
        Output("selection", "data"),
        Input({"type": "map-marker", "index": ALL}, "n_clicks"),
        State("current-result", "data"),
    )
    def _marker_tapped_wrapper(n_clicks: list[Any] | None, current: dict[str, Any] | None) -> Any:
        return marker_tapped(n_clicks, current)

    @app.callback(  # type: ignore[untyped-decorator]
        Output("network-pane", "children"),
        Output("map-pane", "children"),
        Output("timeline-pane", "children"),
        Input("current-result", "data"),
        Input("selection", "data"),
        State("temporal-filter", "data"),
        State("builder-schema", "data"),
    )
    def _render_panes_wrapper(
        current: dict[str, Any] | None,
        selection: dict[str, Any] | None,
        temporal: dict[str, Any] | None,
        schema: dict[str, Any] | None,
    ) -> Any:
        return render_panes(current, selection, temporal, schema)

    @app.callback(  # type: ignore[untyped-decorator]
        Output("provenance-pane", "children"),
        Input("selection", "data"),
    )
    def _provenance_wrapper(selection: dict[str, Any] | None) -> Any:
        return render_provenance(selection)
