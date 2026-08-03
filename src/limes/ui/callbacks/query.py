# src/limes/ui/callbacks/query.py | v1.0.1 | introduced by WP-36, repaired by WP-40
"""Query execution callbacks (Doc 1 §6.5): the three run paths (NL, Cypher,
builder), the boot load, search, and the saved-query actions.

Every run stores the full query response in `current-result` and what
produced it in `query-session` (the brush re-query consumes that), and
writes the executed Cypher into the console textarea — generated Cypher is
always displayed and editable (AC-26). The builder's construction callbacks
live here too: the start-type callback renders the initial builder from the
schema store, and the pattern-matched hop callback applies whatever hop
control changed (identified from the callback context) and re-renders the
hop list from the updated spec, so the controls always show the spec.
"""

from __future__ import annotations

import json
from typing import Any

from dash import ALL, MATCH, Input, Output, State
from dash.exceptions import PreventUpdate

from limes.ui import api_client as api
from limes.ui.callbacks.selection import _neighbor_filters, triggered_index, triggered_prop_id
from limes.ui.components import builder as builder_component
from limes.ui.components import network as network_component
from limes.ui.components.builder import _current_type
from limes.ui.layout import render_saved_queries, render_system_status

_EMPTY_ENVELOPE = {
    "results": {"nodes": [], "edges": [], "counts": {"rows": 0, "nodes": 0, "edges": 0}}
}


def _error_text(exc: Exception) -> str:
    from limes.ui.api_client import ApiError

    if isinstance(exc, ApiError):
        return f"[{exc.code}] {exc.message}"
    return f"unexpected error: {exc}"


def _run_response(response: dict[str, Any], session: dict[str, Any]) -> tuple[Any, ...]:
    """The common output tuple for a successful run: the response, the
    session, the executed Cypher, and a clean error display. An NL outcome
    whose plan was rejected or validation failed has no results — its
    explanation is shown in the error display instead (AC-26)."""
    errors = response.get("validation_errors") or []
    rejection = response.get("plan_rejection")
    if response.get("results") is None:
        message = "; ".join(str(e) for e in errors)
        if rejection:
            details = ", ".join(
                f"{key}={value}"
                for key, value in rejection.items()
                if key not in ("operators", "note")
            )
            message = f"plan rejected: {details or rejection}"
        return response, session, response.get("cypher", ""), message
    return response, session, response.get("cypher", ""), ""


def run_nl(n_submit: int | None, n_clicks: int | None, question: str | None) -> tuple[Any, ...]:
    """The NL path: generate, validate, plan, execute (Trace 3). The
    generated Cypher lands in the textarea regardless of execution outcome."""
    if not n_clicks and not n_submit:
        raise PreventUpdate
    question = (question or "").strip()
    if not question:
        raise PreventUpdate
    try:
        response = api.post_query_nl(question)
    except Exception as exc:
        return (None, None, None, _error_text(exc))
    return _run_response(response, {"path": "nl", "question": question})


def run_cypher(n_clicks: int | None, cypher: str | None) -> tuple[Any, ...]:
    """The Cypher path: validate, plan, execute operator-supplied Cypher."""
    if not n_clicks:
        raise PreventUpdate
    cypher = (cypher or "").strip()
    if not cypher:
        raise PreventUpdate
    try:
        response = api.post_query_cypher(cypher)
    except Exception as exc:
        return (None, None, None, _error_text(exc))
    return response, {"path": "cypher", "cypher": cypher}, response.get("cypher", ""), ""


def run_builder(n_clicks: int | None, spec: dict[str, Any] | None) -> tuple[Any, ...]:
    """The builder path: execute the constructed spec."""
    if not n_clicks or not spec or not spec.get("start_type"):
        raise PreventUpdate
    try:
        response = api.post_query_builder(spec)
    except Exception as exc:
        return (None, None, None, _error_text(exc))
    return response, {"path": "builder", "spec": spec}, response.get("cypher", ""), ""


def boot(n_intervals: int | None) -> tuple[Any, ...]:
    """The boot load: builder schema, cost ledger, saved queries, source
    and run status, health. A failure raises PreventUpdate so the next
    interval tick retries (the interval fires a bounded number of times);
    a UI that cannot reach the API stays up and shows the empty states."""
    if not n_intervals:
        raise PreventUpdate
    try:
        schema = api.get_builder_schema()
        ledger = api.get_cost_ledger()
        saved = api.get_saved_queries()
        sources = api.get_sources()
        runs = api.get_ingest_status()
        health = api.get_health()
    except Exception:
        raise PreventUpdate from None
    return schema, ledger, saved, {"sources": sources, "runs": runs}, health


def _saved_hit_options(hits: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "label": f"{str(hit.get('label') or hit['id'])} ({hit.get('kind', '')})",
            "value": str(hit["id"]),
        }
        for hit in hits
    ]


def search_run(n_clicks: int | None, n_submit: int | None, query: str | None) -> tuple[Any, ...]:
    """Full-text search over entity labels; the hits land in the store and
    as dropdown options."""
    if not n_clicks and not n_submit:
        raise PreventUpdate
    query = (query or "").strip()
    if not query:
        raise PreventUpdate
    hits = api.search(query, limit=20)
    return _saved_hit_options(hits), {"hits": hits}


def search_select(
    value: str | None,
    current_result: dict[str, Any] | None,
    temporal_filter: dict[str, Any] | None,
) -> tuple[Any, Any]:
    """Selecting a search hit jumps into the graph: the entity's one-hop
    neighborhood is merged into the view and the entity is selected."""
    if not value:
        raise PreventUpdate
    neighbors = api.get_entity_neighbors(value, _neighbor_filters(temporal_filter))
    merged = network_component.merge_neighborhood(current_result or _EMPTY_ENVELOPE, neighbors)
    selection = {"kind": "node", "entity": {"entity_id": value}}
    return merged, selection


def saved_load(
    n_clicks: list[Any] | None, saved_queries: list[dict[str, Any]] | None
) -> tuple[Any, ...]:
    """Loading a saved query fills the question input and the Cypher
    textarea — the operator reviews and runs it."""
    index = triggered_index("saved-load")
    if (
        index is None
        or not n_clicks
        or not n_clicks[index]
        or not saved_queries
        or index >= len(saved_queries)
    ):
        raise PreventUpdate
    query = saved_queries[index]
    return query.get("question"), query.get("cypher")


def saved_delete(
    n_clicks: list[Any] | None, saved_queries: list[dict[str, Any]] | None
) -> list[dict[str, Any]] | Any:
    """Deleting a saved query removes it through the API and drops it from
    the store."""
    index = triggered_index("saved-delete")
    if (
        index is None
        or not n_clicks
        or not n_clicks[index]
        or not saved_queries
        or index >= len(saved_queries)
    ):
        raise PreventUpdate
    query = saved_queries[index]
    api.delete_saved_query(str(query["saved_query_id"]))
    return [q for i, q in enumerate(saved_queries) if i != index]


def builder_start_type(
    schema: dict[str, Any] | None,
    start_type: str | None,
    spec: dict[str, Any] | None,
) -> tuple[Any, Any]:
    """The builder's initial render (when the schema store arrives) and the
    start-type selection: choosing a type resets the hop list."""
    if not schema:
        raise PreventUpdate
    if start_type is None:
        return (
            spec if spec is not None else builder_component.empty_spec()
        ), builder_component.render(schema, spec)
    new_spec = builder_component.empty_spec(start_type)
    return new_spec, builder_component.render(schema, new_spec)


def builder_hop_change(
    relation: str | None,
    direction: str | None,
    target: str | None,
    qualifier: str | None,
    instant: str | None,
    filter_prop: str | None,
    filter_value: str | None,
    remove: int | None,
    spec: dict[str, Any] | None,
    schema: dict[str, Any] | None,
) -> tuple[Any, Any]:
    """The pattern-matched hop callback: applies whichever hop control
    changed (decoded from the callback context) to the spec and re-renders
    the builder, so the controls always mirror the store. Every branch is
    a pure function of (control, value, spec) — re-firing with unchanged
    values is idempotent, which is what keeps the children-rebuild fires
    from oscillating."""
    if not schema or not spec or not spec.get("start_type"):
        raise PreventUpdate
    control = _triggered_hop_control()
    # The index decodes from the same prop_id as the control type: the hop
    # controls carry ids like `{"type": "builder-rel", "index": 0}`, so the
    # exact decoded type — never the fixed "builder" prefix — is what
    # `triggered_index` must match (WP-40, found by the coverage exercise).
    index = triggered_index(control) if control is not None else None
    if control is None or index is None:
        raise PreventUpdate
    hops = [dict(h) for h in spec.get("hops", [])]
    if index >= len(hops):
        raise PreventUpdate
    hop = hops[index]
    current_type = _current_type(schema, spec, index)
    if current_type is None:
        raise PreventUpdate
    relation_name = hop.get("relation")
    direction_name = hop.get("direction")
    target_type = str(hop.get("target_type") or "")

    if control == "builder-rel":
        if not relation:
            hop.update(
                {
                    "relation": None,
                    "direction": None,
                    "target_type": None,
                    "temporal_qualifier": None,
                    "temporal_instant": None,
                    "filters": {},
                }
            )
        else:
            directions = builder_component.directions_for(schema, current_type, relation)
            hop.update(
                {
                    "relation": relation,
                    "direction": directions[0] if directions else None,
                    "target_type": None,
                    "temporal_qualifier": None,
                    "temporal_instant": None,
                    "filters": {},
                }
            )
    elif control == "builder-dir":
        if (
            relation_name
            and direction
            and direction in builder_component.directions_for(schema, current_type, relation_name)
        ):
            hop["direction"] = direction
            hop["target_type"] = None
    elif control == "builder-target":
        if not relation_name or not direction_name:
            raise PreventUpdate
        targets = builder_component.targets_for(schema, current_type, relation_name, direction_name)
        if target and target in targets:
            hop["target_type"] = target
    elif control == "builder-qualifier":
        hop["temporal_qualifier"] = qualifier or None
        if not qualifier:
            hop["temporal_instant"] = None
    elif control == "builder-instant":
        if hop.get("temporal_qualifier"):
            hop["temporal_instant"] = instant or None
    elif control == "builder-filter-prop":
        hop["filters"] = {filter_prop: ""} if filter_prop else {}
    elif control == "builder-filter-value":
        current_props = list(hop.get("filters", {}).keys())
        prop_name = current_props[0] if current_props else filter_prop
        if prop_name:
            hop["filters"] = {
                prop_name: builder_component.coerce_filter_value(
                    builder_component.property_type(schema, target_type, prop_name),
                    filter_value or "",
                )
            }
    elif control == "builder-remove":
        if remove:
            hops.pop(index)
    else:
        raise PreventUpdate
    new_spec = {**spec, "hops": hops}
    return new_spec, builder_component.render(schema, new_spec)


def _triggered_hop_control() -> str | None:
    """The hop-control type that triggered, from the callback context
    (`builder-rel`, `builder-remove`, …); None outside a hop interaction."""
    prop_id = triggered_prop_id()
    if not prop_id or not prop_id.startswith("{"):
        return None
    try:
        component_id = json.loads(prop_id.rsplit(".", 1)[0])
    except ValueError:
        return None
    component_type = component_id.get("type")
    return (
        str(component_type)
        if isinstance(component_type, str) and component_type.startswith("builder-")
        else None
    )


def builder_add_hop(
    n_clicks: int | None, spec: dict[str, Any] | None, schema: dict[str, Any] | None
) -> tuple[Any, Any]:
    """Appending a hop: the first admissible relation for the current type,
    its first direction, and the first admissible target — the new hop is
    always constructible."""
    if not n_clicks or not schema or not spec or not spec.get("start_type"):
        raise PreventUpdate
    hops = spec.get("hops", [])
    current_type = spec["start_type"] if not hops else hops[-1].get("target_type")
    relations = builder_component.relations_for(schema, current_type) if current_type else []
    if not relations:
        raise PreventUpdate
    relation = relations[0]["relation"]
    direction = relations[0]["directions"][0]
    targets = builder_component.targets_for(schema, current_type, relation, direction)
    hop: dict[str, Any] = {
        "relation": relation,
        "direction": direction,
        "target_type": targets[0] if targets else None,
        "filters": {},
        "temporal_qualifier": None,
        "temporal_instant": None,
    }
    new_spec = {**spec, "hops": [*hops, hop]}
    return new_spec, builder_component.render(schema, new_spec)


def _render_system_status(
    system: dict[str, Any] | None, ledger: dict[str, Any] | None, health: dict[str, Any] | None
) -> tuple[Any, ...]:
    """The header badge, budget indicator, and system-status panel from the
    boot stores."""
    sources = (system or {}).get("sources")
    runs = (system or {}).get("runs")
    panel = render_system_status(sources, runs, ledger, health)
    badge = "API: " + str((health or {}).get("status", "unreachable"))
    budget = f"€{(ledger or {}).get('remaining_eur', '?')} remaining"
    return panel, badge, budget


def _render_saved_list(saved_queries: list[dict[str, Any]] | None) -> Any:
    return render_saved_queries(saved_queries)


def register(app: Any) -> None:
    """Wire the query callbacks into the Dash app."""

    @app.callback(  # type: ignore[untyped-decorator]
        Output("current-result", "data"),
        Output("query-session", "data"),
        Output("cypher-textarea", "value"),
        Output("error-display", "children"),
        Input("nl-run", "n_clicks"),
        Input("nl-input", "n_submit"),
        State("nl-input", "value"),
    )
    def _run_nl_wrapper(n_clicks: int | None, n_submit: int | None, question: str | None) -> Any:
        return run_nl(n_submit, n_clicks, question)

    @app.callback(  # type: ignore[untyped-decorator]
        Output("current-result", "data"),
        Output("query-session", "data"),
        Output("cypher-textarea", "value"),
        Output("error-display", "children"),
        Input("cypher-run", "n_clicks"),
        State("cypher-textarea", "value"),
    )
    def _run_cypher_wrapper(n_clicks: int | None, cypher: str | None) -> Any:
        return run_cypher(n_clicks, cypher)

    @app.callback(  # type: ignore[untyped-decorator]
        Output("current-result", "data"),
        Output("query-session", "data"),
        Output("cypher-textarea", "value"),
        Output("error-display", "children"),
        Input("builder-run", "n_clicks"),
        State("builder-spec", "data"),
    )
    def _run_builder_wrapper(n_clicks: int | None, spec: dict[str, Any] | None) -> Any:
        return run_builder(n_clicks, spec)

    @app.callback(  # type: ignore[untyped-decorator]
        Output("builder-schema", "data"),
        Output("ledger", "data"),
        Output("saved-queries", "data"),
        Output("system-status", "data"),
        Output("health", "data"),
        Input("boot-interval", "n_intervals"),
    )
    def _boot_wrapper(n_intervals: int | None) -> Any:
        return boot(n_intervals)

    @app.callback(  # type: ignore[untyped-decorator]
        Output("system-status-panel", "children"),
        Output("health-badge", "children"),
        Output("budget-indicator", "children"),
        Input("system-status", "data"),
        Input("ledger", "data"),
        Input("health", "data"),
    )
    def _status_wrapper(
        system: dict[str, Any] | None, ledger: dict[str, Any] | None, health: dict[str, Any] | None
    ) -> Any:
        return _render_system_status(system, ledger, health)

    @app.callback(  # type: ignore[untyped-decorator]
        Output("saved-queries-list", "children"),
        Input("saved-queries", "data"),
    )
    def _saved_list_wrapper(saved_queries: list[dict[str, Any]] | None) -> Any:
        return _render_saved_list(saved_queries)

    @app.callback(  # type: ignore[untyped-decorator]
        Output("search-results-dropdown", "options"),
        Output("search-results", "data"),
        Input("search-run", "n_clicks"),
        Input("search-input", "n_submit"),
        State("search-input", "value"),
    )
    def _search_run_wrapper(n_clicks: int | None, n_submit: int | None, query: str | None) -> Any:
        return search_run(n_clicks, n_submit, query)

    @app.callback(  # type: ignore[untyped-decorator]
        Output("current-result", "data"),
        Output("selection", "data"),
        Input("search-results-dropdown", "value"),
        State("current-result", "data"),
        State("temporal-filter", "data"),
    )
    def _search_select_wrapper(
        value: str | None,
        current: dict[str, Any] | None,
        temporal: dict[str, Any] | None,
    ) -> Any:
        return search_select(value, current, temporal)

    @app.callback(  # type: ignore[untyped-decorator]
        Output("nl-input", "value"),
        Output("cypher-textarea", "value"),
        Input({"type": "saved-load", "index": ALL}, "n_clicks"),
        State("saved-queries", "data"),
    )
    def _saved_load_wrapper(
        n_clicks: list[Any] | None, saved_queries: list[dict[str, Any]] | None
    ) -> Any:
        return saved_load(n_clicks, saved_queries)

    @app.callback(  # type: ignore[untyped-decorator]
        Output("saved-queries", "data"),
        Input({"type": "saved-delete", "index": ALL}, "n_clicks"),
        State("saved-queries", "data"),
    )
    def _saved_delete_wrapper(
        n_clicks: list[Any] | None, saved_queries: list[dict[str, Any]] | None
    ) -> Any:
        return saved_delete(n_clicks, saved_queries)

    @app.callback(  # type: ignore[untyped-decorator]
        Output("builder-container", "children"),
        Output("builder-spec", "data"),
        Input("builder-schema", "data"),
        Input("builder-start-type", "value"),
        State("builder-spec", "data"),
    )
    def _builder_start_wrapper(
        schema: dict[str, Any] | None,
        start_type: str | None,
        spec: dict[str, Any] | None,
    ) -> Any:
        return builder_start_type(schema, start_type, spec)

    @app.callback(  # type: ignore[untyped-decorator]
        Output("builder-container", "children"),
        Output("builder-spec", "data"),
        Input({"type": "builder-rel", "index": MATCH}, "value"),
        Input({"type": "builder-dir", "index": MATCH}, "value"),
        Input({"type": "builder-target", "index": MATCH}, "value"),
        Input({"type": "builder-qualifier", "index": MATCH}, "value"),
        Input({"type": "builder-instant", "index": MATCH}, "date"),
        Input({"type": "builder-filter-prop", "index": MATCH}, "value"),
        Input({"type": "builder-filter-value", "index": MATCH}, "value"),
        Input({"type": "builder-remove", "index": MATCH}, "n_clicks"),
        State("builder-spec", "data"),
        State("builder-schema", "data"),
    )
    def _builder_hop_wrapper(
        relation: str | None,
        direction: str | None,
        target: str | None,
        qualifier: str | None,
        instant: str | None,
        filter_prop: str | None,
        filter_value: str | None,
        remove: int | None,
        spec: dict[str, Any] | None,
        schema: dict[str, Any] | None,
    ) -> Any:
        return builder_hop_change(
            relation,
            direction,
            target,
            qualifier,
            instant,
            filter_prop,
            filter_value,
            remove,
            spec,
            schema,
        )

    @app.callback(  # type: ignore[untyped-decorator]
        Output("builder-container", "children"),
        Output("builder-spec", "data"),
        Input("builder-add-hop", "n_clicks"),
        State("builder-spec", "data"),
        State("builder-schema", "data"),
    )
    def _builder_add_wrapper(
        n_clicks: int | None, spec: dict[str, Any] | None, schema: dict[str, Any] | None
    ) -> Any:
        return builder_add_hop(n_clicks, spec, schema)
