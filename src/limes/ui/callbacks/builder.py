# src/limes/ui/callbacks/builder.py | v1.0.0 | extracted from query.py by the
# architecture-consolidation refactor; the builder callbacks originated in WP-36.
"""Builder construction callbacks (Doc 1 §6.5, Doc 2 §8.13): the start-type
render, the pattern-matched hop interaction, and hop appending.

The start-type callback renders the initial builder from the schema store,
and the pattern-matched hop callback applies whatever hop control changed
(identified from the callback context) and re-renders the hop list from the
updated spec, so the controls always show the spec. Split from
`ui/callbacks/query.py` because the run/search/saved paths and the spec-
manipulation paths are two jobs; this module touches no ontology names and
no HTTP (the UI-knows-nothing property), exactly as before the split.
"""

from __future__ import annotations

import json
from typing import Any

from dash import MATCH, Input, Output, State
from dash.exceptions import PreventUpdate

from limes.ui.callbacks.selection import triggered_index, triggered_prop_id
from limes.ui.components import builder as builder_component
from limes.ui.components.builder import _current_type


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


def register(app: Any) -> None:
    """Wire the builder callbacks into the Dash app."""

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
