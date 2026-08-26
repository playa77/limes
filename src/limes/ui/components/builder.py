# src/limes/ui/components/builder.py | v1.0.1 | introduced by WP-36;
# current_type promoted to public for the callbacks split's cross-module use
# (review follow-up, D-71)
"""The generated query builder (Doc 1 §6.5, Doc 2 §8.13, FR-09).

The builder is rendered from `/builder/schema` at runtime and contains no
type name, relation name, or Cypher fragment (G2). Every dropdown's options
are computed here from the schema projection: selecting a type offers only
relations whose domain/range admit it, selecting a relation offers only
types its other side admits, temporal qualifiers appear only on temporal
relations — so the UI cannot construct a spec the API would reject (AC-24;
the API's rejection remains as defense in depth). Supertype entries in a
relation's domain/range (e.g. a range of `Agent`) are expanded to all
concrete subtypes transitively.

The hop controls use Dash pattern-matching ids keyed by hop index; the
single interaction callback (`callbacks.query.builder_hop_change`) applies
whatever control changed and re-renders. One property filter per hop keeps
the control set bounded; the console covers richer filters.
"""

from __future__ import annotations

from typing import Any, Literal

from dash import dcc, html

HOP_MAX_FILTERS = 1

_QUALIFIER_OPTIONS = [
    {"label": "current", "value": "current"},
    {"label": "as of", "value": "as_of"},
    {"label": "as believed", "value": "as_believed"},
]


def entity_types(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Concrete entity types by name, from the schema projection."""
    return {str(entry["name"]): entry for entry in schema.get("entity_types", [])}


def relation_types(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Relation types by name, from the schema projection."""
    return {str(entry["name"]): entry for entry in schema.get("relation_types", [])}


def _supertype_chain(schema: dict[str, Any], type_name: str) -> list[str]:
    """The supertype chain above `type_name`, outermost last."""
    chain: list[str] = []
    supertypes = {t["name"]: t.get("supertype") for t in schema.get("entity_types", [])}
    current = supertypes.get(type_name)
    while current is not None:
        chain.append(current)
        current = supertypes.get(current)
    return chain


def _admitted(schema: dict[str, Any], declared: list[str], type_name: str) -> bool:
    """True when `type_name` (or a supertype of it) is in `declared` —
    the schema-side mirror of `Ontology.permits`' supertype walk."""
    if type_name in declared:
        return True
    return any(supertype in declared for supertype in _supertype_chain(schema, type_name))


def admitted_types(schema: dict[str, Any], relation: str, side: str) -> list[str]:
    """The concrete types a relation's domain (`side="domain"`) or range
    (`side="range"`) admits: the declared names plus every concrete subtype,
    transitively. Declared supertype names are expanded, never offered."""
    declared = relation_types(schema).get(relation, {}).get(side, [])
    concrete = entity_types(schema)
    admitted: list[str] = []
    for name in declared:
        if name in concrete and name not in admitted:
            admitted.append(name)
        for candidate in concrete:
            if candidate not in admitted and name in _supertype_chain(schema, candidate):
                admitted.append(candidate)
    return admitted


def relations_for(schema: dict[str, Any], type_name: str) -> list[dict[str, str]]:
    """Every relation admitting `type_name`, with the direction(s) the type
    can take: "out" when it is admissible as subject (domain), "in" when
    admissible as object (range)."""
    result: list[dict[str, Any]] = []
    for relation, spec in relation_types(schema).items():
        directions = []
        if _admitted(schema, spec.get("domain", []), type_name):
            directions.append("out")
        if _admitted(schema, spec.get("range", []), type_name):
            directions.append("in")
        if directions:
            result.append({"relation": relation, "directions": directions})
    return result


def directions_for(schema: dict[str, Any], type_name: str, relation: str) -> list[str]:
    """The directions a type can take on a relation (empty when it cannot
    take it at all)."""
    for entry in relations_for(schema, type_name):
        if entry["relation"] == relation:
            return list(entry["directions"])
    return []


def targets_for(schema: dict[str, Any], type_name: str, relation: str, direction: str) -> list[str]:
    """The admissible target types for a hop: the relation's other side,
    expanded to concrete types."""
    side = "range" if direction == "out" else "domain"
    return admitted_types(schema, relation, side)


def is_temporal(schema: dict[str, Any], relation: str) -> bool:
    """Whether the relation carries validity intervals (the schema's
    `temporal` flag — never a UI-side list)."""
    return bool(relation_types(schema).get(relation, {}).get("temporal"))


def properties_for(schema: dict[str, Any], type_name: str) -> list[dict[str, Any]]:
    """The declared properties of a type, from the schema."""
    entry = entity_types(schema).get(type_name)
    properties = entry.get("properties") if entry else None
    return list(properties) if isinstance(properties, list) else []


def property_type(schema: dict[str, Any], type_name: str, property_name: str) -> str:
    """The declared property type (string/float/datetime), or "string"."""
    for property_spec in properties_for(schema, type_name):
        if property_spec.get("name") == property_name:
            return str(property_spec.get("type") or "string")
    return "string"


def coerce_filter_value(property_type_name: str, raw: str) -> Any:
    """The filter value by its declared property type. A float property
    filters numerically; everything else travels as text (a datetime
    property cannot be string-matched by the API's parameter passing, so
    datetime filters are offered but documented to match nothing)."""
    if property_type_name == "float":
        try:
            return float(raw)
        except ValueError:
            return raw
    return raw


def input_type_for(property_type_name: str) -> Literal["text", "number"]:
    """The HTML input kind for a declared property type. A datetime
    property's filter value is typed as text — it travels as an ISO string
    (the API's parameter passing cannot string-match a datetime property,
    so date-picking would promise a match the API cannot deliver)."""
    return "number" if property_type_name == "float" else "text"


def empty_spec(start_type: str | None = None) -> dict[str, Any]:
    """A spec with no hops: the builder's initial state."""
    return {"start_type": start_type, "start_filters": {}, "hops": []}


def _type_options(schema: dict[str, Any]) -> list[dict[str, str]]:
    return [{"label": name, "value": name} for name in entity_types(schema)]


def _property_options(properties: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [{"label": str(p["name"]), "value": str(p["name"])} for p in properties]


def current_type(schema: dict[str, Any], spec: dict[str, Any] | None, hop_index: int) -> str | None:
    """The entity type a hop starts from: the start type for hop 0, the
    previous hop's target beyond."""
    if not spec:
        return None
    if hop_index == 0:
        return spec.get("start_type")
    previous = (
        spec.get("hops", [])[hop_index - 1] if hop_index - 1 < len(spec.get("hops", [])) else None
    )
    return previous.get("target_type") if previous else None


def _start_filter(properties: list[dict[str, Any]], spec: dict[str, Any]) -> tuple[str, str]:
    """The rendered (property, value) pair of the start filter, from the
    spec's `start_filters` map."""
    for property_spec in properties:
        name = str(property_spec["name"])
        if name in spec.get("start_filters", {}):
            return name, str(spec["start_filters"][name])
    return "", ""


def _hop_filter(properties: list[dict[str, Any]], hop: dict[str, Any]) -> tuple[str, str]:
    for property_spec in properties:
        name = str(property_spec["name"])
        if name in hop.get("filters", {}):
            return name, str(hop["filters"][name])
    return "", ""


def render(schema: dict[str, Any] | None, spec: dict[str, Any] | None) -> html.Div:
    """The builder component tree for one (schema, spec). Pure: the values
    shown are the spec's values, so the controls stay consistent with the
    store after every interaction."""
    if not schema:
        return html.Div("Builder schema not loaded yet.", style={"color": "#666"})
    current_spec = spec or empty_spec()
    start_type = current_spec.get("start_type")
    start_properties = properties_for(schema, start_type) if start_type else []
    filter_prop, filter_value = _start_filter(start_properties, current_spec)
    filter_input_type = (
        input_type_for(property_type(schema, start_type or "", filter_prop))
        if filter_prop
        else "text"
    )

    children: list[Any] = [
        html.H4("Query builder", style={"margin": "0 0 8px 0", "font-size": "14px"}),
        html.Label("Start type", style={"font-size": "12px"}),
        dcc.Dropdown(
            id="builder-start-type",
            options=_type_options(schema),
            value=start_type,
            placeholder="choose an entity type",
        ),
        html.Div(
            [
                dcc.Dropdown(
                    id="builder-start-filter-prop",
                    options=_property_options(start_properties),
                    value=filter_prop or None,
                    placeholder="filter property",
                    style={"width": "46%", "display": "inline-block", "margin-right": "4%"},
                ),
                dcc.Input(
                    id="builder-start-filter-value",
                    type=filter_input_type,
                    value=filter_value or "",
                    placeholder="value",
                    style={"width": "48%", "display": "inline-block"},
                ),
            ],
            style={"margin": "6px 0"},
        ),
    ]

    for index, hop in enumerate(current_spec.get("hops", [])):
        hop_type = current_type(schema, spec, index)
        relation = hop.get("relation")
        direction = hop.get("direction")
        target_type = hop.get("target_type")
        directions = directions_for(schema, hop_type, relation) if hop_type and relation else []
        targets = (
            targets_for(schema, hop_type, relation, direction)
            if hop_type and relation and direction
            else []
        )
        target_properties = properties_for(schema, target_type) if target_type else []
        hop_filter_prop, hop_filter_value = _hop_filter(target_properties, hop)
        hop_filter_type = (
            input_type_for(property_type(schema, target_type, hop_filter_prop))
            if hop_filter_prop
            else "text"
        )
        temporal = bool(hop_type and relation and is_temporal(schema, relation))
        qualifier = hop.get("temporal_qualifier")
        instant = hop.get("temporal_instant")
        instant = instant.split("T")[0] if isinstance(instant, str) and "T" in instant else instant

        controls: list[Any] = [
            html.Div(
                f"Hop {index + 1}",
                style={"font-size": "12px", "font-weight": "600", "margin": "10px 0 4px 0"},
            ),
            html.Div(
                [
                    dcc.Dropdown(
                        id={"type": "builder-rel", "index": index},
                        options=[
                            {
                                "label": f"{entry['relation']} ({'/'.join(entry['directions'])})",
                                "value": entry["relation"],
                            }
                            for entry in (relations_for(schema, hop_type) if hop_type else [])
                        ],
                        value=relation,
                        placeholder="relation",
                        style={"width": "64%", "display": "inline-block", "margin-right": "4%"},
                    ),
                    dcc.Dropdown(
                        id={"type": "builder-dir", "index": index},
                        options=[{"label": d, "value": d} for d in directions],
                        value=direction
                        if direction in directions
                        else (directions[0] if directions else None),
                        placeholder="direction",
                        style={"width": "30%", "display": "inline-block"},
                    ),
                ]
            ),
            html.Div(
                [
                    dcc.Dropdown(
                        id={"type": "builder-target", "index": index},
                        options=[{"label": name, "value": name} for name in targets],
                        value=target_type if target_type in targets else None,
                        placeholder="target type",
                    ),
                ],
                style={"margin": "6px 0"},
            ),
            html.Div(
                [
                    dcc.Dropdown(
                        id={"type": "builder-filter-prop", "index": index},
                        options=_property_options(target_properties),
                        value=hop_filter_prop or None,
                        placeholder="filter property",
                        style={"width": "46%", "display": "inline-block", "margin-right": "4%"},
                    ),
                    dcc.Input(
                        id={"type": "builder-filter-value", "index": index},
                        type=hop_filter_type,
                        value=hop_filter_value or "",
                        placeholder="value",
                        style={"width": "48%", "display": "inline-block"},
                    ),
                ],
                style={"margin": "6px 0"},
            ),
        ]
        if temporal:
            controls.append(
                html.Div(
                    [
                        dcc.Dropdown(
                            id={"type": "builder-qualifier", "index": index},
                            options=_QUALIFIER_OPTIONS,
                            value=qualifier,
                            placeholder="temporal qualifier",
                            style={"width": "64%", "display": "inline-block", "margin-right": "4%"},
                        ),
                        dcc.DatePickerSingle(
                            id={"type": "builder-instant", "index": index},
                            date=instant,
                            placeholder="instant",
                            style={"width": "30%", "display": "inline-block"},
                        ),
                    ],
                    style={"margin": "6px 0"},
                )
            )
        controls.append(
            html.Button(
                "Remove hop",
                id={"type": "builder-remove", "index": index},
                n_clicks=0,
                style={"font-size": "11px", "padding": "2px 8px"},
            )
        )
        children.append(
            html.Div(
                controls,
                style={
                    "border": "1px solid #ddd",
                    "border-radius": "4px",
                    "padding": "6px",
                    "margin": "4px 0",
                },
            )
        )

    children.append(
        html.Div(
            [
                html.Button(
                    "Add hop", id="builder-add-hop", n_clicks=0, style={"font-size": "12px"}
                ),
                html.Button(
                    "Run builder query",
                    id="builder-run",
                    n_clicks=0,
                    style={"font-size": "12px", "margin-left": "8px"},
                ),
            ],
            style={"margin": "8px 0"},
        )
    )
    return html.Div(children, id="builder-root")
