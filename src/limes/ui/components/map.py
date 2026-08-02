# src/limes/ui/components/map.py | v1.0.0 | introduced by WP-36
"""The map pane (Doc 1 §6.5): a dash-leaflet map rendering the coordinate-
bearing nodes of the current result.

Which nodes are coordinate-bearing is derived from the builder schema at
runtime, never from a type name: the coordinate property names are the
ontology's declared property names (`latitude`/`longitude` are property
names, not type names — the forbidden list is type names, relation names,
and Cypher fragments), and the pane renders every node whose `type` is one
of the schema types declaring both. When the ontology renames or moves
those properties, the schema projection changes and this pane follows
without an edit.

Markers are `CircleMarker`s with pattern-matched ids so a click maps back
to the entity id (the ALL callback reads the triggered index). The selected
entity's marker changes color — the pane's half of AC-29's selection sync.
"""

from __future__ import annotations

from typing import Any

import dash_leaflet as dl  # type: ignore[import-untyped]
from dash import html

_COORDINATE_PROPERTIES = ("latitude", "longitude")
_UNSELECTED_COLOR = "#4a7ba6"
_SELECTED_COLOR = "#c0392b"

_DEFAULT_CENTER = [52.0, 10.0]
_DEFAULT_ZOOM = 5


def coordinate_types(schema: dict[str, Any] | None) -> set[str]:
    """The concrete entity types whose declared properties include the
    coordinate pair, derived from the `/builder/schema` projection."""
    types = set()
    for entry in (schema or {}).get("entity_types", []):
        names = {p.get("name") for p in entry.get("properties", [])}
        if set(_COORDINATE_PROPERTIES) <= names:
            types.add(str(entry["name"]))
    return types


def _coordinate_nodes(result: dict[str, Any] | None, types: set[str]) -> list[dict[str, Any]]:
    """Nodes whose concrete type is coordinate-bearing and whose properties
    carry both coordinates."""
    nodes: list[dict[str, Any]] = []
    for node in (result or {}).get("nodes", []):
        if str(node.get("type")) not in types:
            continue
        properties = node.get("properties") or {}
        latitude = properties.get(_COORDINATE_PROPERTIES[0])
        longitude = properties.get(_COORDINATE_PROPERTIES[1])
        if latitude is None or longitude is None:
            continue
        nodes.append(node)
    return nodes


def _selected_entity_ids(selection: dict[str, Any] | None) -> set[str]:
    """The entity ids the selection highlights: the selected node itself,
    or both endpoints of the selected edge — the map's half of AC-29's
    selection sync."""
    if not selection:
        return set()
    if selection.get("kind") == "node":
        entity = selection.get("entity")
        return {str(entity["entity_id"])} if entity and entity.get("entity_id") else set()
    if selection.get("kind") == "edge":
        edge = selection.get("edge") or {}
        ids = {str(edge.get("subject_id", "")), str(edge.get("object_id", ""))}
        return {entity_id for entity_id in ids if entity_id}
    return set()


def render(
    result: dict[str, Any] | None, selection: dict[str, Any] | None, schema: dict[str, Any] | None
) -> dl.Map:
    """The leaflet map for one result. Nodes without coordinates are simply
    not points — the pane shows an empty-state notice instead of nothing."""
    points = _coordinate_nodes(result, coordinate_types(schema))
    highlighted = _selected_entity_ids(selection)
    markers: list[dl.CircleMarker] = []
    for node in points:
        entity_id = str(node["entity_id"])
        properties = node.get("properties") or {}
        latitude = float(properties[_COORDINATE_PROPERTIES[0]])
        longitude = float(properties[_COORDINATE_PROPERTIES[1]])
        markers.append(
            dl.CircleMarker(
                id={"type": "map-marker", "index": entity_id},
                center=[latitude, longitude],
                radius=8,
                color=_SELECTED_COLOR if entity_id in highlighted else _UNSELECTED_COLOR,
                fillOpacity=0.9,
                n_clicks=0,
                children=[dl.Tooltip(f"{node.get('label') or entity_id}")],
            )
        )
    children: list[Any] = [dl.TileLayer()]
    if points:
        children.extend(markers)
    else:
        children.append(
            html.Div(
                "No coordinate-bearing nodes in the current result.",
                style={"padding": "12px", "color": "#666", "font-style": "italic"},
            )
        )
    return dl.Map(
        id="graph-map",
        center=_DEFAULT_CENTER,
        zoom=_DEFAULT_ZOOM,
        style={"width": "100%", "height": "320px"},
        children=children,
    )
