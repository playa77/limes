# src/limes/ui/components/timeline.py | v1.0.0 | introduced by WP-36
"""The timeline pane (Doc 1 §6.5): a plotly Gantt-like view of the current
result's edges with a brush.

The brush triggers a re-query, never client-side filtering (Doc 2 §8.13):
the pane renders exactly what the API returned, and the brush only writes
the `temporal-filter` store, which the temporal callbacks turn into a
re-query. Edges with a validity interval are drawn as bars from
`valid_from` to `valid_to` (open intervals to the present); edges without
one are drawn as markers at `recorded_at`. The rangeslider carries the
brush; its range is restored from the `temporal-filter` store when the
figure re-renders after a re-query, so the operator's window survives.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from dash import dcc
from plotly import graph_objects as go  # type: ignore[import-untyped]

from limes.ui.components.network import edge_key

_SELECTED_COLOR = "#c0392b"
_UNSELECTED_COLOR = "#4a7ba6"


def _row_label(edge: dict[str, Any], labels: dict[str, str]) -> str:
    relation = str(edge.get("relation") or "?")
    subject = labels.get(str(edge.get("subject_id", "")), str(edge.get("subject_id", "?")))
    object_ = labels.get(str(edge.get("object_id", "")), str(edge.get("object_id", "?")))
    return f"{relation} · {subject} → {object_}"


def _ordered_edges(result: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The result's edges in a stable order for the row axis: by validity
    start when present, else by belief time."""
    edges = list((result or {}).get("edges", []))

    def sort_key(edge: dict[str, Any]) -> str:
        start = edge.get("valid_from") or edge.get("recorded_at") or ""
        return str(start)

    return sorted(edges, key=sort_key)


def _parse_instant(value: Any) -> datetime | None:
    """An ISO instant (as the API serializes) to a native datetime; a
    non-temporal value is not an instant and passes through as None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def figure(
    result: dict[str, Any] | None,
    selection: dict[str, Any] | None,
    temporal_filter: dict[str, Any] | None,
) -> go.Figure:
    """The timeline figure for one result. `temporal_filter` supplies the
    brush window to restore on re-render. The selected edge's row is drawn
    in the selection color; a selected node highlights the rows of its
    incident edges — the timeline's half of AC-29's selection sync."""
    labels = {
        str(node["entity_id"]): str(node.get("label") or node["entity_id"])
        for node in (result or {}).get("nodes", [])
    }
    edges = _ordered_edges(result)
    selected = None
    selected_node = None
    if selection:
        if selection.get("kind") == "edge":
            selected = edge_key(selection.get("edge") or {})
        elif selection.get("kind") == "node":
            entity = selection.get("entity")
            if entity:
                selected_node = str(entity.get("entity_id"))

    bar_rows: list[str] = []
    bar_bases: list[Any] = []
    bar_widths: list[Any] = []
    bar_colors: list[str] = []
    bar_hover: list[str] = []
    point_rows: list[str] = []
    point_x: list[Any] = []
    point_colors: list[str] = []
    point_hover: list[str] = []

    now = datetime.now(UTC)
    for edge in edges:
        valid_from = _parse_instant(edge.get("valid_from"))
        label = _row_label(edge, labels)
        hover = label
        if edge.get("source_id"):
            hover += f"<br>source: {edge['source_id']}"
        touches = selected_node is not None and (
            str(edge.get("subject_id", "")) == selected_node
            or str(edge.get("object_id", "")) == selected_node
        )
        is_selected = selected is not None and edge_key(edge) == selected
        color = _SELECTED_COLOR if (is_selected or touches) else _UNSELECTED_COLOR
        if valid_from is not None:
            valid_to = _parse_instant(edge.get("valid_to"))
            bar_rows.append(label)
            bar_bases.append(valid_from)
            bar_widths.append((valid_to or now) - valid_from)
            bar_colors.append(color)
            bar_hover.append(hover)
        else:
            recorded = _parse_instant(edge.get("recorded_at"))
            if recorded is None:
                continue
            point_rows.append(label)
            point_x.append(recorded)
            point_colors.append(color)
            point_hover.append(hover)

    fig = go.Figure()
    if bar_rows:
        fig.add_trace(
            go.Bar(
                orientation="h",
                y=bar_rows,
                base=bar_bases,
                x=bar_widths,
                marker_color=bar_colors,
                hovertemplate="%{customdata}<extra></extra>",
                customdata=bar_hover,
                showlegend=False,
            )
        )
    if point_rows:
        fig.add_trace(
            go.Scatter(
                mode="markers",
                y=point_rows,
                x=point_x,
                marker_color=point_colors,
                hovertemplate="%{customdata}<extra></extra>",
                customdata=point_hover,
                showlegend=False,
            )
        )
    layout: dict[str, Any] = {
        "height": 280,
        "margin": {"l": 8, "r": 8, "t": 24, "b": 8},
        "yaxis": {"autorange": "reversed", "showticklabels": False},
        "xaxis": {"rangeslider": {"visible": True}},
        "hovermode": "closest",
    }
    if not bar_rows and not point_rows:
        layout["annotations"] = [
            {
                "text": "No edges in the current result.",
                "xref": "paper",
                "yref": "paper",
                "showarrow": False,
                "font": {"color": "#666", "family": "italic"},
            }
        ]
    if temporal_filter and temporal_filter.get("range"):
        try:
            layout["xaxis"]["range"] = [
                str(temporal_filter["range"][0]),
                str(temporal_filter["range"][1]),
            ]
        except (KeyError, IndexError, TypeError):
            pass
    fig.update_layout(layout)
    return fig


def render(
    result: dict[str, Any] | None,
    selection: dict[str, Any] | None,
    temporal_filter: dict[str, Any] | None,
) -> dcc.Graph:
    """The timeline component for one result."""
    return dcc.Graph(id="timeline-graph", figure=figure(result, selection, temporal_filter))
