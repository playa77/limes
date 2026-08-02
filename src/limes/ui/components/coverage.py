# src/limes/ui/components/coverage.py | v1.0.0 | introduced by WP-36
"""The coverage panel (Doc 1 §6.5, AC-23): renders the coverage report and
the empty-result diagnosis that every executed query carries. All values
come from the stored query response — the panel renders, it never computes
coverage itself (coverage is graph-wide and only the API can measure it).
"""

from __future__ import annotations

from typing import Any

from dash import html


def render(response: dict[str, Any] | None) -> html.Div:
    """The coverage panel for one stored query response."""
    if not response:
        return html.Div("No query executed yet.", style={"color": "#666", "font-size": "12px"})
    coverage = response.get("coverage") or {}
    diagnosis = response.get("diagnosis")
    notes = response.get("notes") or []

    rows: list[Any] = []
    relation_counts = coverage.get("relation_counts") or {}
    if relation_counts:
        rows.append(
            html.Div(
                "Relation counts (graph-wide)", style={"font-weight": "600", "font-size": "12px"}
            )
        )
        for relation, count in sorted(relation_counts.items()):
            rows.append(html.Div(f"{relation}: {count}", style={"font-size": "12px"}))
    else:
        rows.append(
            html.Div(
                "No relations in the executed query.", style={"color": "#666", "font-size": "12px"}
            )
        )

    contributing = coverage.get("contributing_sources") or []
    if contributing:
        rows.append(
            html.Div(
                "Contributing sources",
                style={"font-weight": "600", "font-size": "12px", "margin-top": "8px"},
            )
        )
        for source_id in contributing:
            refreshed = (coverage.get("source_refresh") or {}).get(source_id)
            refresh_text = str(refreshed) if refreshed else "never"
            rows.append(
                html.Div(f"{source_id} (last refresh {refresh_text})", style={"font-size": "12px"})
            )

    if diagnosis:
        rows.append(
            html.Div(
                "Empty-result diagnosis",
                style={"font-weight": "600", "font-size": "12px", "margin-top": "8px"},
            )
        )
        rows.append(
            html.Div(
                "Failing clause "
                f"{diagnosis.get('clause_index', -1) + 1}: {diagnosis.get('failing_clause', '')}",
                style={"font-size": "12px"},
            )
        )
        rows.append(
            html.Div(diagnosis.get("note", ""), style={"font-size": "12px", "font-style": "italic"})
        )

    for note in notes:
        rows.append(
            html.Div(note, style={"font-size": "12px", "color": "#7a5b00", "margin-top": "6px"})
        )

    return html.Div(
        [
            html.H4("Coverage", style={"margin": "0 0 8px 0", "font-size": "14px"}),
            *rows,
        ]
    )
