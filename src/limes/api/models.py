# src/limes/api/models.py | v1.0.0 | introduced by WP-32
"""API response models per Technical Specification §6.

`GraphResult`, `CoverageReport`, `Diagnosis`, `EntityRef`, `EdgeRef`,
`NlqOutcome`, and `BuilderSpec` are defined here — they compose the §5.5
core types — and are consumed by the routers of WP-32/WP-35, by the
NL-to-Cypher service (WP-33), and by the coverage module (WP-34), so a
response shape changes in exactly one place.

`GraphResult.from_rows` is the one conversion from raw driver output to the
response shape: rows carry `Node`/`Relationship`/`Path` objects (and the
dict projections an operator may return), and every node or edge that
appears is deduplicated into `nodes`/`edges`. The concrete entity type of a
node is derived from its labels against the ontology — labels like `Agent`
and `Entity` are structural, so the concrete type is the label that names
an ontology entity type.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from neo4j.graph import Node, Path, Relationship
from pydantic import BaseModel

from limes.ontology.model import Ontology
from limes.types import PlanSummary

# Entity properties carried in dedicated fields (or excluded entirely —
# `label_embedding` is 1024 floats of index noise that no pane renders).
_NODE_FIELD_PROPERTIES = frozenset(
    {"entity_id", "label", "label_embedding", "created_at", "ontology_version"}
)


def _node_properties(node: Node) -> dict[str, Any]:
    """The node's properties minus the dedicated fields, with driver time
    values converted to native datetimes so the response serializes."""
    properties: dict[str, Any] = {}
    for key, value in node.items():
        if key in _NODE_FIELD_PROPERTIES:
            continue
        properties[key] = native_datetime(value) if _is_time_value(value) else value
    return properties


def _is_time_value(value: Any) -> bool:
    return hasattr(value, "to_native")


class EntityRef(BaseModel):
    """One entity as returned to the UI: identity, label, concrete type,
    its remaining properties, and the loader's stamps."""

    entity_id: str
    type: str
    label: str
    properties: dict[str, Any] = {}
    ontology_version: str | None = None
    created_at: datetime | None = None


class EdgeRef(BaseModel):
    """One relationship as returned to the UI, carrying the full §5.6
    assertion metadata — provenance and bitemporal interval included, so
    the provenance panel (WP-36) has everything client-side (AC-28)."""

    relation: str
    subject_id: str
    object_id: str
    source_id: str | None = None
    source_trust: float | None = None
    confidence: float | None = None
    recorded_at: datetime | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    retracted_at: datetime | None = None
    assertion_id: str | None = None
    ontology_version: str | None = None
    extractor_model: str | None = None
    prompt_version: str | None = None
    schema_version: str | None = None
    evidence_document_id: str | None = None
    evidence_start: int | None = None
    evidence_end: int | None = None
    evidence_channel: str | None = None
    evidence_member: str | None = None
    evidence_row: int | None = None
    source_event_id: str | None = None
    source_url: str | None = None
    report_url: str | None = None
    source_recorded_at: datetime | None = None
    article_text_available: bool | None = None


class GraphResult(BaseModel):
    """The normalized result of one executed query: deduplicated nodes and
    edges plus counts. `counts["rows"]` is the raw row count — a query can
    return scalar rows with no nodes, and the saved-query result count
    (AC-30) records rows, not nodes."""

    nodes: list[EntityRef] = []
    edges: list[EdgeRef] = []
    counts: dict[str, int] = {}

    @classmethod
    def from_rows(cls, rows: list[dict[str, Any]], ontology: Ontology) -> GraphResult:
        """Convert driver rows into a deduplicated result. Nodes and
        relationships are recognized by their driver types; dict projections
        are recognized by their `entity_id`/`assertion_id` keys. Everything
        else is ignored — a row is a mixed bag of scalars and graph values,
        and the UI renders the graph values."""
        nodes: list[EntityRef] = []
        edges: list[EdgeRef] = []
        seen_nodes: set[str] = set()
        seen_edges: set[str] = set()

        def add_node(node: Node | dict[str, Any]) -> None:
            if isinstance(node, dict):
                if "entity_id" not in node:
                    return
                entity_id = str(node["entity_id"])
                if entity_id in seen_nodes:
                    return
                seen_nodes.add(entity_id)
                nodes.append(
                    EntityRef(
                        entity_id=entity_id,
                        type=_concrete_type(set(), ontology),
                        label=str(node.get("label") or entity_id),
                        properties={
                            k: v for k, v in node.items() if k not in _NODE_FIELD_PROPERTIES
                        },
                        ontology_version=_str_or_none(node.get("ontology_version")),
                        created_at=native_datetime(node.get("created_at")),
                    )
                )
                return
            entity_id = str(node.get("entity_id") or node.element_id)
            if entity_id in seen_nodes:
                return
            seen_nodes.add(entity_id)
            nodes.append(
                EntityRef(
                    entity_id=entity_id,
                    type=_concrete_type(set(node.labels), ontology),
                    label=str(node.get("label") or entity_id),
                    properties=_node_properties(node),
                    ontology_version=_str_or_none(node.get("ontology_version")),
                    created_at=native_datetime(node.get("created_at")),
                )
            )

        def add_edge(rel: Relationship) -> None:
            edge_id = rel.element_id
            if edge_id in seen_edges:
                return
            seen_edges.add(edge_id)
            edges.append(edge_ref(rel))

        def collect(value: Any) -> None:
            if isinstance(value, Node):
                add_node(value)
            elif isinstance(value, Relationship):
                add_edge(value)
            elif isinstance(value, Path):
                for node in value.nodes:
                    add_node(node)
                for rel in value.relationships:
                    add_edge(rel)
            elif isinstance(value, dict):
                if "entity_id" in value or isinstance(value.get("entity_id"), str):
                    add_node(value)
                elif "assertion_id" in value:
                    # A relationship projected to a dict loses its endpoints;
                    # keep it out of `edges` rather than fabricate ids.
                    return
            elif isinstance(value, list):
                for item in value:
                    collect(item)

        for row in rows:
            for value in row.values():
                collect(value)

        return cls(
            nodes=nodes,
            edges=edges,
            counts={"rows": len(rows), "nodes": len(nodes), "edges": len(edges)},
        )


class CoverageReport(BaseModel):
    """What every result carries (§8.11): graph-wide edge counts for the
    relations involved, the sources that contributed them, and each
    contributing source's last successful refresh (AC-23)."""

    relation_counts: dict[str, int] = {}
    contributing_sources: list[str] = []
    source_refresh: dict[str, datetime | None] = {}


class Diagnosis(BaseModel):
    """The empty-result diagnosis (§8.11, Doc 1 §6.3): the first decomposed
    `MATCH` clause that returns nothing, graph-wide counts for the relations
    it involves, and a plain-language note (AC-22). `clause_index` is -1
    when no clause can be named."""

    failing_clause: str
    clause_index: int
    relation_counts: dict[str, int] = {}
    note: str


class NlqOutcome(BaseModel):
    """The result of one natural-language query (WP-33 `answer`): the
    generated Cypher is always present and editable (AC-26), results are
    present only when the query executed, and either validation errors or a
    plan rejection explain a missing execution."""

    question: str
    cypher: str
    results: GraphResult | None = None
    validation_errors: list[str] = []
    plan_rejection: PlanSummary | None = None
    notes: list[str] = []


class BuilderHop(BaseModel):
    """One ordered hop of a `BuilderSpec`. The direction is relative to the
    previous node: "out" continues with `(prev)-[:R]->(next)`, "in" with
    `(prev)<-[:R]-(next)`. `temporal_qualifier` restricts the hop's
    relationship to the current interval (`currently()`), a validity
    instant (`as_of`), or a belief instant (`as_believed`), each of which
    needs the matching `temporal_instant`."""

    relation: str
    direction: Literal["out", "in"]
    target_type: str
    filters: dict[str, Any] = {}
    temporal_qualifier: Literal["current", "as_of", "as_believed"] | None = None
    temporal_instant: datetime | None = None


class BuilderSpec(BaseModel):
    """The structured query the builder constructs (Doc 2 §6): a starting
    type with property filters plus an ordered hop list. The API rejects
    any spec whose relation is not permitted between adjacent types, making
    an invalid query unrepresentable rather than merely rejected (AC-24)."""

    start_type: str
    start_filters: dict[str, Any] = {}
    hops: list[BuilderHop] = []


def native_datetime(value: Any) -> datetime | None:
    """Convert a driver DateTime/Date (or native datetime) to a native
    datetime; None passes through. A non-temporal value raises — a malformed
    shape must not silently become null in a response."""
    if value is None:
        return None
    to_native = getattr(value, "to_native", None)
    if to_native is not None:
        converted = to_native()
        if isinstance(converted, datetime):
            return converted
        raise TypeError(f"unexpected time value from the driver: {type(value).__name__}")
    if isinstance(value, datetime):
        return value
    raise TypeError(f"unexpected time value from the driver: {type(value).__name__}")


def entity_ref(node: Node, ontology: Ontology) -> EntityRef:
    """One `EntityRef` from a driver node, with driver time values converted
    and the embedding vector excluded. Used by the entity router and by
    `GraphResult.from_rows`."""
    return EntityRef(
        entity_id=str(node.get("entity_id") or node.element_id),
        type=_concrete_type(set(node.labels), ontology),
        label=str(node.get("label") or node.get("entity_id") or node.element_id),
        properties=_node_properties(node),
        ontology_version=_str_or_none(node.get("ontology_version")),
        created_at=native_datetime(node.get("created_at")),
    )


def edge_ref(rel: Relationship) -> EdgeRef:
    """One `EdgeRef` from a driver relationship, carrying the full §5.6
    assertion metadata with driver time values converted. Used by the
    entity router and by `GraphResult.from_rows`."""
    props = dict(rel.items())
    subject, object_ = rel.nodes
    return EdgeRef(
        relation=rel.type,
        subject_id=(
            str(subject.get("entity_id") or subject.element_id)
            if subject is not None
            else rel.element_id
        ),
        object_id=(
            str(object_.get("entity_id") or object_.element_id)
            if object_ is not None
            else rel.element_id
        ),
        source_id=_str_or_none(props.get("source_id")),
        source_trust=_float_or_none(props.get("source_trust")),
        confidence=_float_or_none(props.get("confidence")),
        recorded_at=native_datetime(props.get("recorded_at")),
        valid_from=native_datetime(props.get("valid_from")),
        valid_to=native_datetime(props.get("valid_to")),
        retracted_at=native_datetime(props.get("retracted_at")),
        assertion_id=_str_or_none(props.get("assertion_id")),
        ontology_version=_str_or_none(props.get("ontology_version")),
        extractor_model=_str_or_none(props.get("extractor_model")),
        prompt_version=_str_or_none(props.get("prompt_version")),
        schema_version=_str_or_none(props.get("schema_version")),
        evidence_document_id=_str_or_none(props.get("evidence_document_id")),
        evidence_start=_int_or_none(props.get("evidence_start")),
        evidence_end=_int_or_none(props.get("evidence_end")),
        evidence_channel=_str_or_none(props.get("evidence_channel")),
        evidence_member=_str_or_none(props.get("evidence_member")),
        evidence_row=_int_or_none(props.get("evidence_row")),
        source_event_id=_str_or_none(props.get("source_event_id")),
        source_url=_str_or_none(props.get("source_url")),
        report_url=_str_or_none(props.get("report_url")),
        source_recorded_at=native_datetime(props.get("source_recorded_at")),
        article_text_available=props.get("article_text_available")
        if isinstance(props.get("article_text_available"), bool)
        else None,
    )


def _concrete_type(labels: set[str], ontology: Ontology) -> str:
    """The concrete entity type of a node: the one label that names an
    ontology entity type. When several match (a node can carry labels from
    different types only through malformed data), the most specific wins —
    the label whose own supertype chain contains the others."""
    matching = [label for label in labels if label in ontology.entity_types]
    if not matching:
        return "Entity"
    if len(matching) == 1:
        return matching[0]

    def chain_length(name: str) -> int:
        length = 0
        current = ontology.entity_types[name].supertype
        while current is not None and current in ontology.entity_types:
            length += 1
            current = ontology.entity_types[current].supertype
        return length

    return max(matching, key=chain_length)


def _str_or_none(value: Any) -> str | None:
    return None if value is None else str(value)


def _float_or_none(value: Any) -> float | None:
    return None if value is None else float(value)


def _int_or_none(value: Any) -> int | None:
    return None if value is None else int(value)
