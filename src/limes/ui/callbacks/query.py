# src/limes/ui/callbacks/query.py | v1.0.1 | introduced by WP-36, repaired by WP-40
"""Query execution callbacks (Doc 1 §6.5): the three run paths (NL, Cypher,
builder), the boot load, search, and the saved-query actions.

Every run stores the full query response in `current-result` and what
produced it in `query-session` (the brush re-query consumes that), and
writes the executed Cypher into the console textarea — generated Cypher is
always displayed and editable (AC-26). The builder's construction callbacks
live in `ui/callbacks/builder.py`.
"""

from __future__ import annotations

from typing import Any

from dash import ALL, Input, Output, State
from dash.exceptions import PreventUpdate

from limes.ui import api_client as api
from limes.ui.callbacks.selection import _neighbor_filters, triggered_index
from limes.ui.components import network as network_component
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
