# src/limes/ui/components/network.py | v1.0.0 | introduced by WP-36
"""The network pane (Doc 1 §6.5): a dash-cytoscape graph built from the
current result, plus the AC-27 neighborhood merge.

Node click expansion (AC-27) never re-runs the original query: the callback
fetches `/entity/{id}/neighbors` and `merge_neighborhood` folds the returned
neighborhood into the stored result. Edge and node `data` carry the entity
ids (and the full edge ref) so the selection callbacks need no lookup —
`tapNodeData`/`tapEdgeData` are the cytoscape tap events.

The pane is schema-free: node `type` values and edge `relation` values are
rendered as opaque data from the API response, never consulted here.
"""

from __future__ import annotations

from typing import Any

import dash_cytoscape as cyto  # type: ignore[import-untyped]

# Legibility-only styling (Doc 2 §2: theming beyond legibility is out of
# scope): distinct node colors by the degree of the entity's role in the
# current view is deliberately avoided — the stylesheet is static so the
# pane never encodes data semantics.
_STYLESHEET = [
    {
        "selector": "node",
        "style": {
            "label": "data(label)",
            "background-color": "#4a7ba6",
            "text-valign": "bottom",
            "font-size": "11px",
            "color": "#222",
            "width": 24,
            "height": 24,
        },
    },
    {
        "selector": "node:selected",
        "style": {"background-color": "#c0392b", "border-width": 3, "border-color": "#8b1a10"},
    },
    {
        "selector": "edge",
        "style": {
            "label": "data(label)",
            "curve-style": "bezier",
            "target-arrow-shape": "triangle",
            "line-color": "#999",
            "font-size": "10px",
            "color": "#555",
            "text-rotation": "autorotate",
        },
    },
    {
        "selector": "edge:selected",
        "style": {"line-color": "#c0392b", "width": 4},
    },
]


def edge_key(edge: dict[str, Any]) -> str:
    """The dedup key for one edge ref: the assertion id when present,
    otherwise the structural triple. The API's serialized edges have no
    element id, so the merge dedup is over what the API returns."""
    assertion_id = edge.get("assertion_id")
    if assertion_id:
        return str(assertion_id)
    return "|".join(
        [
            str(edge.get("subject_id", "")),
            str(edge.get("relation", "")),
            str(edge.get("object_id", "")),
        ]
    )


def elements(result: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Cytoscape elements for the result's nodes and edges. Edge data embeds
    the full edge ref so the provenance panel has everything client-side
    (AC-28); node data carries the entity id and label for tap events."""
    nodes = (result or {}).get("nodes", [])
    edges = (result or {}).get("edges", [])
    elements_out: list[dict[str, Any]] = []
    for node in nodes:
        elements_out.append(
            {
                "data": {
                    "id": str(node["entity_id"]),
                    "entity_id": str(node["entity_id"]),
                    "label": str(node.get("label") or node["entity_id"]),
                    "type": str(node.get("type") or ""),
                }
            }
        )
    for edge in edges:
        elements_out.append(
            {
                "data": {
                    "id": edge_key(edge),
                    "source": str(edge["subject_id"]),
                    "target": str(edge["object_id"]),
                    "label": str(edge.get("relation") or ""),
                    "relation": str(edge.get("relation") or ""),
                    "edge": edge,
                }
            }
        )
    return elements_out


def selected_node_id(selection: dict[str, Any] | None) -> str | None:
    """The selected node's entity id, when the selection is a node."""
    if not selection:
        return None
    entity = selection.get("entity")
    if selection.get("kind") == "node" and entity:
        return str(entity.get("entity_id"))
    return None


def selected_edge_key(selection: dict[str, Any] | None) -> str | None:
    """The selected edge's dedup key, when the selection is an edge."""
    if not selection or selection.get("kind") != "edge":
        return None
    return edge_key(selection.get("edge") or {})


def render(result: dict[str, Any] | None, selection: dict[str, Any] | None) -> cyto.Cytoscape:
    """The cytoscape component for one result, with the selection styled."""
    result_nodes = (result or {}).get("nodes", [])
    if not result_nodes:
        return cyto.Cytoscape(
            id="network-graph",
            elements=[],
            layout={"name": "cose"},
            stylesheet=_STYLESHEET,
            style={"width": "100%", "height": "420px"},
        )
    node_selection = selected_node_id(selection)
    edge_selection = selected_edge_key(selection)
    edge_data = elements(result)
    for element in edge_data:
        data = element["data"]
        if node_selection is not None and data.get("entity_id") == node_selection:
            element["classes"] = "selected-node"
        elif edge_selection is not None and edge_key(data.get("edge") or {}) == edge_selection:
            element["classes"] = "selected-edge"
    style_out = _STYLESHEET + [
        {"selector": ".selected-node", "style": {"background-color": "#c0392b"}},
        {"selector": ".selected-edge", "style": {"line-color": "#c0392b", "width": 4}},
    ]
    return cyto.Cytoscape(
        id="network-graph",
        elements=edge_data,
        layout={"name": "cose"},
        stylesheet=style_out,
        style={"width": "100%", "height": "420px"},
    )


def merge_neighborhood(current: dict[str, Any], neighbors: dict[str, Any]) -> dict[str, Any]:
    """Fold a `/entity/{id}/neighbors` response into the stored result.

    The stored value is the query response envelope (`results` plus coverage
    and diagnosis); `current` may also be a bare results dict. Nodes are
    deduplicated by `entity_id`, edges by `edge_key`; row counts are kept as
    the original query produced them, node/edge counts are recomputed so the
    store stays truthful. This is the whole of AC-27's merge — no query is
    re-run, only the returned neighborhood is added.
    """
    if isinstance(current, dict) and "results" in current:
        envelope = current
        results = current["results"]
    else:
        envelope = None
        results = current or {}
    existing_nodes = {str(n["entity_id"]) for n in results.get("nodes", [])}
    existing_edges = {edge_key(e) for e in results.get("edges", [])}
    nodes = list(results.get("nodes", []))
    edges = list(results.get("edges", []))
    for neighbor in neighbors.get("neighbors", []):
        node = neighbor.get("neighbor")
        if node and str(node.get("entity_id")) not in existing_nodes:
            nodes.append(node)
            existing_nodes.add(str(node["entity_id"]))
        edge = neighbor.get("edge")
        if edge and edge_key(edge) not in existing_edges:
            edges.append(edge)
            existing_edges.add(edge_key(edge))
    merged = {
        "nodes": nodes,
        "edges": edges,
        "counts": {**results.get("counts", {}), "nodes": len(nodes), "edges": len(edges)},
    }
    if envelope is not None:
        return {**envelope, "results": merged}
    return merged
