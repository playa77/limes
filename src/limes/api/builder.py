# src/limes/api/builder.py | v1.0.0 | introduced by WP-32, amended by WP-35
"""The builder's two halves per Doc 2 §6 and §8.12: the schema projection
the UI renders the builder from (FR-09), and the `BuilderSpec` → Cypher
translation the query router executes.

`project_for_builder` is a pure projection of the ontology — the builder is
generated at runtime, never authored (NG-08): the UI holds no type name and
no relation name itself, and the endpoint is the only place the projection
exists.

`translate_spec` renders a spec into a parameterized read-only query. Every
filter value and every temporal instant travels as a Cypher parameter; the
only operator-supplied text that reaches the query itself is a property
name, which is checked against an identifier pattern before use. The spec's
per-hop domain/range validity is checked with `Ontology.permits` before any
query text is produced — an invalid spec is rejected precisely (AC-24), not
sent to the database.

A temporal qualifier on a non-temporal relation is rejected: those relations
never carry `valid_to` (Doc 2 §5.1), so `currently()` would silently match
everything and the qualifier would be a lie.
"""

from __future__ import annotations

from typing import Any

from limes.api.models import BuilderSpec
from limes.config import Settings
from limes.errors import LimesError
from limes.graph.temporal import as_believed, as_believed_params, as_of, as_of_params
from limes.ontology.model import Ontology

_PROPERTY_NAME = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789")


class BuilderSpecRejected(LimesError):
    """A `BuilderSpec` the API refuses: an unknown type, a relation not
    permitted between the adjacent types, a temporal qualifier on a
    non-temporal relation, or a malformed property name. Maps to HTTP 400
    with a precise message (AC-24)."""


def project_for_builder(ontology: Ontology) -> dict[str, Any]:
    """The builder schema: every entity type with its properties and every
    relation with its domain, range, and temporal flag, projected from the
    loaded ontology at runtime."""
    return {
        "version": ontology.version,
        "entity_types": [
            {
                "name": spec.name,
                "supertype": spec.supertype,
                "identifying_keys": spec.identifying_keys,
                "properties": [property_spec.model_dump() for property_spec in spec.properties],
            }
            for spec in ontology.entity_types.values()
        ],
        "relation_types": [
            {
                "name": spec.name,
                "domain": spec.domain,
                "range": spec.range,
                "temporal": spec.temporal,
            }
            for spec in ontology.relation_types.values()
        ],
    }


def translate_spec(
    spec: BuilderSpec, ontology: Ontology, settings: Settings
) -> tuple[str, dict[str, Any]]:
    """Translate a validated spec into (cypher, params). Raises
    `BuilderSpecRejected` on the first invalid element with a message naming
    the hop and the violation."""
    if spec.start_type not in ontology.entity_types:
        raise BuilderSpecRejected(f"unknown start type: {spec.start_type!r}")
    _check_property_names("start", spec.start_filters)
    if not ontology.entity_types[spec.start_type].properties and spec.start_filters:
        raise BuilderSpecRejected(
            f"filters for start type {spec.start_type!r} match no declared property"
        )

    params: dict[str, Any] = {}
    fragments: list[str] = [
        "MATCH",
        f"(n0:{spec.start_type}{_filters('n0', spec.start_filters, params)})",
    ]
    conditions: list[str] = []
    prev_type = spec.start_type

    for index, hop in enumerate(spec.hops, start=1):
        relation = hop.relation
        if relation not in ontology.relation_types:
            raise BuilderSpecRejected(f"hop {index}: unknown relation {relation!r}")
        if hop.target_type not in ontology.entity_types:
            raise BuilderSpecRejected(f"hop {index}: unknown target type {hop.target_type!r}")
        relation_spec = ontology.relation_types[relation]
        if hop.temporal_qualifier is not None and not relation_spec.temporal:
            raise BuilderSpecRejected(
                f"hop {index}: relation {relation!r} is non-temporal and cannot carry a "
                f"temporal qualifier"
            )
        _check_property_names(f"hop {index}", hop.filters)
        if hop.filters and not ontology.entity_types[hop.target_type].properties:
            raise BuilderSpecRejected(
                f"hop {index}: filters for {hop.target_type!r} match no declared property"
            )

        subject_type, object_type = (
            (hop.target_type, prev_type) if hop.direction == "in" else (prev_type, hop.target_type)
        )
        if not ontology.permits(relation, subject_type, object_type):
            if not _admitted(ontology, relation_spec.domain, subject_type):
                raise BuilderSpecRejected(
                    f"hop {index}: {relation!r} does not admit {subject_type!r} as subject "
                    f"(domain: {', '.join(relation_spec.domain)})"
                )
            raise BuilderSpecRejected(
                f"hop {index}: {relation!r} does not admit {object_type!r} as object "
                f"(range: {', '.join(relation_spec.range)})"
            )

        node_var = f"n{index}"
        rel_var = f"r{index - 1}"
        target = f"{_filters(node_var, hop.filters, params)}"
        if hop.direction == "in":
            fragments.append(f"<-[:{relation}]-({node_var}:{hop.target_type}{target})")
        else:
            fragments.append(f"-[:{relation}]->({node_var}:{hop.target_type}{target})")

        if hop.temporal_qualifier is None:
            continue
        if hop.temporal_qualifier == "current":
            conditions.append(f"{rel_var}.valid_to IS NULL")
        elif hop.temporal_qualifier == "as_of":
            if hop.temporal_instant is None:
                raise BuilderSpecRejected(
                    f"hop {index}: temporal_qualifier 'as_of' needs temporal_instant"
                )
            conditions.append(as_of(rel_var, hop.temporal_instant))
            params.update(as_of_params(rel_var, hop.temporal_instant))
        else:
            if hop.temporal_instant is None:
                raise BuilderSpecRejected(
                    f"hop {index}: temporal_qualifier 'as_believed' needs temporal_instant"
                )
            conditions.append(as_believed(rel_var, hop.temporal_instant))
            params.update(as_believed_params(rel_var, hop.temporal_instant))

    query = " ".join(fragments)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    return query + f" RETURN * LIMIT {settings.query_default_limit}", params


def _filters(var: str, filters: dict[str, Any], params: dict[str, Any]) -> str:
    """Render a property-filter map as a parameterized node pattern body:
    `{prop: $var_prop, ...}`. Property names are the operator-supplied text
    that reaches the query; they are bounded to identifiers before use."""
    if not filters:
        return ""
    names: list[str] = []
    for name, value in filters.items():
        param = f"{var}_{name}"
        params[param] = value
        names.append(f"{name}: ${param}")
    return " {" + ", ".join(names) + "}"


def _check_property_names(where: str, filters: dict[str, Any]) -> None:
    for name in filters:
        if not name or any(char not in _PROPERTY_NAME for char in name):
            raise BuilderSpecRejected(
                f"{where}: property name {name!r} is not a valid Cypher identifier"
            )


def _admitted(ontology: Ontology, declared: list[str], actual: str) -> bool:
    """True when `actual` (or a supertype of it) is in `declared`. Mirrors
    `Ontology.permits`' supertype walk; `permits` cannot be reused here
    because it cannot attribute a failure to the subject side."""
    if actual in declared:
        return True
    current = ontology.entity_types[actual].supertype
    while current is not None:
        if current in declared:
            return True
        if current not in ontology.entity_types:
            break
        current = ontology.entity_types[current].supertype
    return False
