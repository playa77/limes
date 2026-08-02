# src/limes/ui/callbacks/temporal.py | v1.0.0 | introduced by WP-36
"""The timeline brush (Doc 1 §6.5, Doc 2 §8.13): the brush writes the
`temporal-filter` store, and the re-query callback re-runs the query that
produced the current view through the same API path (D-11).

The brush never filters client-side: the store change triggers a re-query,
so every pane keeps showing exactly what the graph returns. The re-query
uses `as_of` = the brush's right edge — the state at the end of the brushed
period — through the builder path's temporal qualifiers (on temporal
relations only, per the schema's `temporal` flag) and the neighbors
endpoint's `as_of` parameter for expansions. The NL and raw-Cypher paths
re-run their stored payload: the API has no temporal parameter for
arbitrary Cypher, and the UI must not author Cypher fragments.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from dash import Input, Output, State, no_update
from dash.exceptions import PreventUpdate

from limes.ui import api_client as api
from limes.ui.components import builder as builder_component


def _normalize_instant(value: Any) -> datetime:
    """A plotly relayout range endpoint (ISO string or epoch milliseconds)
    to a native datetime."""
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000.0)
    return datetime.fromisoformat(str(value))


def brush_changed(
    relayout: dict[str, Any] | None, temporal_filter: dict[str, Any] | None
) -> dict[str, Any] | Any:
    """The brush callback: a moved or drawn rangeslider window writes the
    filter; a reset (autorange) clears it. An identical window is a no-op,
    which is what breaks the re-render → relayout → re-query loop."""
    if not relayout:
        raise PreventUpdate
    range_value = relayout.get("xaxis.range")
    if isinstance(range_value, list) and len(range_value) == 2 and None not in range_value:
        try:
            start = _normalize_instant(range_value[0])
            end = _normalize_instant(range_value[1])
        except ValueError:
            raise PreventUpdate from None
        new_filter = {
            "as_of": end.isoformat(),
            "range": [start.isoformat(), end.isoformat()],
        }
        if temporal_filter == new_filter:
            raise PreventUpdate
        return new_filter
    if relayout.get("xaxis.autorange"):
        if temporal_filter is None:
            raise PreventUpdate
        return None
    raise PreventUpdate


def _temporally_qualified(
    spec: dict[str, Any], temporal_filter: dict[str, Any] | None, schema: dict[str, Any]
) -> dict[str, Any]:
    """The spec with an `as_of` qualifier on every hop whose relation the
    schema marks temporal. The API rejects a qualifier on a non-temporal
    relation, so the schema's flag — not a UI list — decides."""
    if not temporal_filter or not temporal_filter.get("as_of"):
        return spec
    instant = temporal_filter["as_of"]
    hops = []
    for hop in spec.get("hops", []):
        hop = dict(hop)
        relation = hop.get("relation")
        if relation and builder_component.is_temporal(schema, str(relation)):
            hop["temporal_qualifier"] = "as_of"
            hop["temporal_instant"] = instant
        hops.append(hop)
    return {**spec, "hops": hops}


def requery(
    temporal_filter: dict[str, Any] | None,
    query_session: dict[str, Any] | None,
    builder_schema: dict[str, Any] | None,
) -> tuple[Any, ...]:
    """The brush's re-query: re-runs the query that produced the current
    view through the same API path, with the temporal qualifier applied
    where the API supports it (D-11)."""
    if not query_session:
        raise PreventUpdate
    path = query_session.get("path")
    try:
        if path == "builder":
            spec = _temporally_qualified(
                query_session.get("spec") or {}, temporal_filter, builder_schema or {}
            )
            response = api.post_query_builder(spec)
            return (
                response,
                response.get("cypher", ""),
                spec,
                builder_component.render(builder_schema or {}, spec),
                "",
            )
        if path == "nl":
            response = api.post_query_nl(str(query_session.get("question", "")))
            return response, response.get("cypher", ""), no_update, no_update, ""
        if path == "cypher":
            response = api.post_query_cypher(str(query_session.get("cypher", "")))
            return response, response.get("cypher", ""), no_update, no_update, ""
    except Exception as exc:
        from limes.ui.callbacks.query import _error_text

        return no_update, no_update, no_update, no_update, _error_text(exc)
    raise PreventUpdate


def register(app: Any) -> None:
    """Wire the temporal callbacks into the Dash app."""

    @app.callback(  # type: ignore[untyped-decorator]
        Output("temporal-filter", "data"),
        Input("timeline-graph", "relayoutData"),
        State("temporal-filter", "data"),
    )
    def _brush_wrapper(
        relayout: dict[str, Any] | None, temporal_filter: dict[str, Any] | None
    ) -> Any:
        return brush_changed(relayout, temporal_filter)

    @app.callback(  # type: ignore[untyped-decorator]
        Output("current-result", "data"),
        Output("cypher-textarea", "value"),
        Output("builder-spec", "data"),
        Output("builder-container", "children"),
        Output("error-display", "children"),
        Input("temporal-filter", "data"),
        State("query-session", "data"),
        State("builder-schema", "data"),
    )
    def _requery_wrapper(
        temporal_filter: dict[str, Any] | None,
        query_session: dict[str, Any] | None,
        builder_schema: dict[str, Any] | None,
    ) -> Any:
        return requery(temporal_filter, query_session, builder_schema)
