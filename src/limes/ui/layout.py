# src/limes/ui/layout.py | v1.0.0 | introduced by WP-36
"""The page layout (Doc 1 §6.5): one exploration screen, three synchronized
panes over a shared selection, with the supporting elements — NL input,
editable Cypher console, generated builder, coverage panel, provenance
panel, saved-query list, budget indicator.

All state lives in `dcc.Store`s (Doc 2 §8.13): `current-result` (the full
query response: results, coverage, diagnosis, notes), `selection`,
`temporal-filter`, `builder-spec`, plus the supporting stores `builder-schema`,
`query-session` (what produced the current view, for the brush re-query),
`search-results`, `saved-queries`, `system-status`, `ledger`, and `health`.
The builder and pane contents are rendered by callbacks, never authored
here; this module holds no type name, relation name, or Cypher fragment.
"""

from __future__ import annotations

from typing import Any

from dash import dcc, html

from limes.ui.components import console as console_component

_HEADER_STYLE = {
    "background": "#22303c",
    "color": "#e8eef2",
    "padding": "10px 16px",
    "display": "flex",
    "alignItems": "center",
    "gap": "16px",
}

_COLUMN_STYLE = {"padding": "12px", "boxSizing": "border-box"}

_PANE_CARD = {
    "border": "1px solid #d8dee3",
    "borderRadius": "6px",
    "padding": "10px",
    "margin": "8px 0",
    "background": "#fff",
}


def _pane(title: str, pane_id: str) -> html.Div:
    return html.Div(
        [
            html.Div(
                title, style={"font-size": "13px", "font-weight": "600", "margin-bottom": "6px"}
            ),
            html.Div(id=pane_id),
        ],
        style=_PANE_CARD,
    )


def render_saved_queries(queries: list[dict[str, Any]] | None) -> html.Div:
    """The saved-query list: question and Cypher per entry, with load and
    delete actions. Rendered from the store; the buttons carry pattern ids
    indexed by list position."""
    if not queries:
        return html.Div("No saved queries yet.", style={"color": "#666", "font-size": "12px"})
    entries: list[Any] = []
    for index, query in enumerate(queries):
        question = str(query.get("question") or "—")
        cypher = str(query.get("cypher") or "")
        entries.append(
            html.Div(
                [
                    html.Div(
                        question,
                        style={
                            "font-size": "12px",
                            "font-weight": "600",
                            "word-break": "break-word",
                        },
                    ),
                    html.Div(
                        f"{query.get('result_count', 0)} rows · "
                        f"{str(query.get('created_at') or '')[:19]}",
                        style={"font-size": "11px", "color": "#777"},
                    ),
                    html.Div(
                        [
                            html.Button(
                                "Load",
                                id={"type": "saved-load", "index": index},
                                n_clicks=0,
                                style={"font-size": "11px", "margin-right": "6px"},
                            ),
                            html.Button(
                                "Delete",
                                id={"type": "saved-delete", "index": index},
                                n_clicks=0,
                                style={"font-size": "11px"},
                            ),
                        ]
                    ),
                    html.Pre(
                        cypher,
                        style={
                            "font-size": "10px",
                            "white-space": "pre-wrap",
                            "background": "#f4f6f8",
                            "padding": "4px",
                            "max-height": "80px",
                            "overflow": "auto",
                        },
                    ),
                ],
                style={
                    "border": "1px solid #e2e7ec",
                    "borderRadius": "4px",
                    "padding": "6px",
                    "margin": "4px 0",
                },
            )
        )
    return html.Div(entries)


def render_system_status(
    sources: list[dict[str, Any]] | None,
    runs: list[dict[str, Any]] | None,
    ledger: dict[str, Any] | None,
    health: dict[str, Any] | None,
) -> html.Div:
    """The system status panel: health, budget indicator, per-source last
    refresh, and latest run counters — the durable surfaces of §10, read
    through the API."""
    rows: list[Any] = []
    if health:
        status = health.get("status", "unknown")
        rows.append(
            html.Div(
                f"API: {status} (ontology {health.get('ontology_version', '?')})",
                style={"font-size": "12px"},
            )
        )
    if ledger:
        rows.append(
            html.Div(
                f"Spend: €{ledger.get('spend_eur', '?')} in {ledger.get('period', '?')}",
                style={"font-size": "12px"},
            )
        )
    if sources:
        rows.append(
            html.Div(
                "Sources", style={"font-weight": "600", "margin-top": "6px", "font-size": "12px"}
            )
        )
        for source in sources:
            refreshed = str(source.get("last_success_at") or "never")[:19]
            rows.append(
                html.Div(
                    f"{source.get('source_id')} (trust {source.get('trust_rank')}, "
                    f"refresh {refreshed})",
                    style={"font-size": "12px"},
                )
            )
    if runs:
        rows.append(
            html.Div(
                "Latest runs",
                style={"font-weight": "600", "margin-top": "6px", "font-size": "12px"},
            )
        )
        for run in runs[:5]:
            rows.append(
                html.Div(
                    f"{run.get('source_id')} · {run.get('mode')}: "
                    f"written {run.get('assertions_written')}, "
                    f"skipped {run.get('assertions_skipped')}, "
                    f"rejected {run.get('assertions_rejected')}, errors {run.get('errors')}",
                    style={"font-size": "12px"},
                )
            )
    return html.Div(rows)


def layout() -> html.Div:
    """The exploration screen. Pane contents and the builder render from
    stores; only the containers are fixed here."""
    return html.Div(
        [
            *[
                dcc.Store(store_id, data=None)
                for store_id in (
                    "current-result",
                    "selection",
                    "temporal-filter",
                    "builder-spec",
                    "builder-schema",
                    "query-session",
                    "search-results",
                    "saved-queries",
                    "system-status",
                    "ledger",
                    "health",
                )
            ],
            dcc.Interval(id="boot-interval", interval=1500, max_intervals=3, n_intervals=0),
            html.Div(
                [
                    html.Span("LIMES", style={"font-size": "18px", "font-weight": "700"}),
                    html.Span(id="health-badge", style={"font-size": "12px"}),
                    html.Span(id="budget-indicator", style={"font-size": "12px"}),
                ],
                style=_HEADER_STYLE,
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                "Search",
                                style={
                                    "font-size": "13px",
                                    "font-weight": "600",
                                    "margin-bottom": "6px",
                                },
                            ),
                            dcc.Input(
                                id="search-input",
                                type="text",
                                placeholder="full-text entity search",
                                n_submit=0,
                                style={"width": "100%", "boxSizing": "border-box"},
                            ),
                            html.Button(
                                "Search",
                                id="search-run",
                                n_clicks=0,
                                style={"margin": "4px 0", "font-size": "12px"},
                            ),
                            dcc.Dropdown(id="search-results-dropdown", placeholder="results"),
                            console_component.render(),
                            html.Div(
                                "Builder",
                                style={
                                    "font-size": "13px",
                                    "font-weight": "600",
                                    "margin": "8px 0 4px 0",
                                },
                            ),
                            html.Div(id="builder-container"),
                        ],
                        style={**_COLUMN_STYLE, "width": "26%"},
                    ),
                    html.Div(
                        [
                            _pane("Network", "network-pane"),
                            _pane("Map", "map-pane"),
                            _pane("Timeline", "timeline-pane"),
                        ],
                        style={**_COLUMN_STYLE, "width": "48%"},
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        "System",
                                        style={
                                            "font-size": "13px",
                                            "font-weight": "600",
                                            "margin-bottom": "6px",
                                        },
                                    ),
                                    html.Div(id="system-status-panel"),
                                ],
                                style=_PANE_CARD,
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        "Saved queries",
                                        style={
                                            "font-size": "13px",
                                            "font-weight": "600",
                                            "margin-bottom": "6px",
                                        },
                                    ),
                                    html.Div(id="saved-queries-list"),
                                ],
                                style=_PANE_CARD,
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        "Coverage",
                                        style={
                                            "font-size": "13px",
                                            "font-weight": "600",
                                            "margin-bottom": "6px",
                                        },
                                    ),
                                    html.Div(id="coverage-pane"),
                                ],
                                style=_PANE_CARD,
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        "Provenance",
                                        style={
                                            "font-size": "13px",
                                            "font-weight": "600",
                                            "margin-bottom": "6px",
                                        },
                                    ),
                                    html.Div(id="provenance-pane"),
                                ],
                                style=_PANE_CARD,
                            ),
                        ],
                        style={**_COLUMN_STYLE, "width": "26%"},
                    ),
                ],
                style={"display": "flex", "alignItems": "flex-start", "maxWidth": "1600px"},
            ),
        ],
        style={
            "fontFamily": "-apple-system, Segoe UI, Roboto, sans-serif",
            "background": "#eef1f4",
            "minHeight": "100vh",
        },
    )
