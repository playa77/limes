# desktop/src/limes_desktop/api/models.py | v0.1.0 | mirrored API response models (AC-DC-7)
"""Client-side mirrors of the API's response models (src/limes/api/models.py
and the router view models). Field parity with the live API models is pinned
by `desktop/tests/contract/test_model_parity.py` (AC-DC-7); these mirrors
deliberately keep timestamps as the strings the JSON carries, so the client
never needs pydantic to parse an API payload."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Self


@dataclass(frozen=True, slots=True)
class EntityRef:
    entity_id: str
    type: str
    label: str
    properties: dict[str, Any] = field(default_factory=dict)
    ontology_version: str | None = None
    created_at: str | None = None

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Self:
        return cls(
            entity_id=str(d["entity_id"]),
            type=str(d["type"]),
            label=str(d["label"]),
            properties=dict(d.get("properties") or {}),
            ontology_version=d.get("ontology_version"),
            created_at=d.get("created_at"),
        )


@dataclass(frozen=True, slots=True)
class EdgeRef:
    relation: str
    subject_id: str
    object_id: str
    source_id: str | None = None
    source_trust: float | None = None
    confidence: float | None = None
    recorded_at: str | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    retracted_at: str | None = None
    assertion_id: str | None = None
    ontology_version: str | None = None
    extractor_model: str | None = None
    prompt_version: str | None = None
    schema_version: str | None = None
    evidence_document_id: str | None = None
    evidence_start: int | None = None
    evidence_end: int | None = None

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Self:
        return cls(
            relation=str(d["relation"]),
            subject_id=str(d["subject_id"]),
            object_id=str(d["object_id"]),
            source_id=d.get("source_id"),
            source_trust=d.get("source_trust"),
            confidence=d.get("confidence"),
            recorded_at=d.get("recorded_at"),
            valid_from=d.get("valid_from"),
            valid_to=d.get("valid_to"),
            retracted_at=d.get("retracted_at"),
            assertion_id=d.get("assertion_id"),
            ontology_version=d.get("ontology_version"),
            extractor_model=d.get("extractor_model"),
            prompt_version=d.get("prompt_version"),
            schema_version=d.get("schema_version"),
            evidence_document_id=d.get("evidence_document_id"),
            evidence_start=d.get("evidence_start"),
            evidence_end=d.get("evidence_end"),
        )


@dataclass(frozen=True, slots=True)
class GraphResult:
    nodes: list[EntityRef] = field(default_factory=list)
    edges: list[EdgeRef] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Self:
        return cls(
            nodes=[EntityRef.from_api(n) for n in d.get("nodes") or []],
            edges=[EdgeRef.from_api(e) for e in d.get("edges") or []],
            counts=dict(d.get("counts") or {}),
        )


@dataclass(frozen=True, slots=True)
class CoverageReport:
    relation_counts: dict[str, int] = field(default_factory=dict)
    contributing_sources: list[str] = field(default_factory=list)
    source_refresh: dict[str, str | None] = field(default_factory=dict)

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Self:
        return cls(
            relation_counts=dict(d.get("relation_counts") or {}),
            contributing_sources=list(d.get("contributing_sources") or []),
            source_refresh=dict(d.get("source_refresh") or {}),
        )


@dataclass(frozen=True, slots=True)
class Diagnosis:
    note: str = ""
    relation_counts: dict[str, int] = field(default_factory=dict)
    failing_clause: str = ""
    clause_index: int = -1

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Self:
        return cls(
            failing_clause=str(d["failing_clause"]),
            clause_index=int(d["clause_index"]),
            relation_counts=dict(d.get("relation_counts") or {}),
            note=str(d["note"]),
        )


@dataclass(frozen=True, slots=True)
class NlqOutcome:
    question: str
    cypher: str
    results: GraphResult | None = None
    validation_errors: list[str] = field(default_factory=list)
    plan_rejection: dict[str, Any] | None = None
    notes: list[str] = field(default_factory=list)

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Self:
        return cls(
            question=str(d["question"]),
            cypher=str(d["cypher"]),
            results=GraphResult.from_api(d["results"]) if d.get("results") is not None else None,
            validation_errors=list(d.get("validation_errors") or []),
            plan_rejection=d.get("plan_rejection"),
            notes=list(d.get("notes") or []),
        )


@dataclass(frozen=True, slots=True)
class BuilderHop:
    relation: str
    direction: Literal["out", "in"]
    target_type: str
    filters: dict[str, Any] = field(default_factory=dict)
    temporal_qualifier: Literal["current", "as_of", "as_believed"] | None = None
    temporal_instant: str | None = None

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Self:
        return cls(
            relation=str(d["relation"]),
            direction=d["direction"],
            target_type=str(d["target_type"]),
            filters=dict(d.get("filters") or {}),
            temporal_qualifier=d.get("temporal_qualifier"),
            temporal_instant=d.get("temporal_instant"),
        )


@dataclass(frozen=True, slots=True)
class BuilderSpec:
    start_type: str
    start_filters: dict[str, Any] = field(default_factory=dict)
    hops: list[BuilderHop] = field(default_factory=list)

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Self:
        return cls(
            start_type=str(d["start_type"]),
            start_filters=dict(d.get("start_filters") or {}),
            hops=[BuilderHop.from_api(h) for h in d.get("hops") or []],
        )


@dataclass(frozen=True, slots=True)
class HealthInfo:
    """GET /health: `{"status": "ok", "neo4j": true, "ontology_version": "..."}`."""

    status: str
    neo4j: bool
    ontology_version: str

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Self:
        return cls(
            status=str(d["status"]),
            neo4j=bool(d["neo4j"]),
            ontology_version=str(d["ontology_version"]),
        )


@dataclass(frozen=True, slots=True)
class SearchHit:
    """GET /search: `{"kind": "entity"|"document", "id", "label", "score"}`."""

    kind: str
    id: str
    label: str
    score: float

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Self:
        return cls(
            kind=str(d["kind"]),
            id=str(d["id"]),
            label=str(d["label"]),
            score=float(d["score"]),
        )


@dataclass(frozen=True, slots=True)
class EntityDetail:
    """GET /entity/{id}: the entity plus its per-relation edge summary."""

    entity: EntityRef
    edge_summary: dict[str, dict[str, int]] = field(default_factory=dict)

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Self:
        return cls(
            entity=EntityRef.from_api(d["entity"]),
            edge_summary={
                direction: {rel: int(count) for rel, count in counts.items()}
                for direction, counts in (d.get("edge_summary") or {}).items()
            },
        )


@dataclass(frozen=True, slots=True)
class NeighborRow:
    """One row of GET /entity/{id}/neighbors: edge with provenance + neighbor."""

    edge: EdgeRef
    neighbor: EntityRef

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Self:
        return cls(edge=EdgeRef.from_api(d["edge"]), neighbor=EntityRef.from_api(d["neighbor"]))


@dataclass(frozen=True, slots=True)
class GraphNeighbors:
    """The full GET /entity/{id}/neighbors response."""

    entity: EntityRef
    neighbors: list[NeighborRow] = field(default_factory=list)

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Self:
        return cls(
            entity=EntityRef.from_api(d["entity"]),
            neighbors=[NeighborRow.from_api(r) for r in d.get("neighbors") or []],
        )


@dataclass(frozen=True, slots=True)
class SavedQuery:
    """GET /saved-queries row (`SavedQueryView`): created_at is an ISO string."""

    saved_query_id: str
    question: str
    cypher: str
    ontology_version: str
    result_count: int
    created_at: str
    pinned: bool

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Self:
        return cls(
            saved_query_id=str(d["saved_query_id"]),
            question=str(d["question"]),
            cypher=str(d["cypher"]),
            ontology_version=str(d["ontology_version"]),
            result_count=int(d["result_count"]),
            created_at=str(d.get("created_at") or ""),
            pinned=bool(d.get("pinned") or False),
        )


@dataclass(frozen=True, slots=True)
class SourceInfo:
    """GET /sources row (`SourceView`)."""

    source_id: str
    name: str
    kind: str
    trust_rank: float
    supports_backfill: bool
    supports_incremental: bool
    last_success_at: str | None = None
    last_run_id: str | None = None

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Self:
        return cls(
            source_id=str(d["source_id"]),
            name=str(d["name"]),
            kind=str(d["kind"]),
            trust_rank=float(d["trust_rank"]),
            supports_backfill=bool(d["supports_backfill"]),
            supports_incremental=bool(d["supports_incremental"]),
            last_success_at=d.get("last_success_at"),
            last_run_id=d.get("last_run_id"),
        )


@dataclass(frozen=True, slots=True)
class CostEntry:
    """GET /cost/ledger row (`LedgerEntryView`)."""

    ledger_id: str
    period: str
    run_id: str | None
    purpose: str
    model_id: str
    input_tokens: int
    output_tokens: int
    cost_eur: float
    created_at: str

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Self:
        return cls(
            ledger_id=str(d["ledger_id"]),
            period=str(d["period"]),
            run_id=d.get("run_id"),
            purpose=str(d["purpose"]),
            model_id=str(d["model_id"]),
            input_tokens=int(d["input_tokens"]),
            output_tokens=int(d["output_tokens"]),
            cost_eur=float(d["cost_eur"]),
            created_at=str(d.get("created_at") or ""),
        )


@dataclass(frozen=True, slots=True)
class CostLedger:
    """GET /cost/ledger (`LedgerView`)."""

    period: str
    spend_eur: float
    entries: list[CostEntry] = field(default_factory=list)

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Self:
        return cls(
            period=str(d["period"]),
            spend_eur=float(d["spend_eur"]),
            entries=[CostEntry.from_api(e) for e in d.get("entries") or []],
        )


@dataclass(frozen=True, slots=True)
class IngestRun:
    """GET /ingest/status row (`RunStatus`)."""

    source_id: str
    mode: str
    run_id: str
    started_at: str
    finished_at: str | None = None
    records_fetched: int = 0
    nodes_created: int = 0
    nodes_matched: int = 0
    assertions_written: int = 0
    assertions_skipped: int = 0
    assertions_rejected: int = 0
    documents_gated_out: int = 0
    errors: int = 0
    cost_eur: float = 0.0
    last_success_at: str | None = None

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Self:
        return cls(
            source_id=str(d["source_id"]),
            mode=str(d["mode"]),
            run_id=str(d["run_id"]),
            started_at=str(d.get("started_at") or ""),
            finished_at=d.get("finished_at"),
            records_fetched=int(d.get("records_fetched") or 0),
            nodes_created=int(d.get("nodes_created") or 0),
            nodes_matched=int(d.get("nodes_matched") or 0),
            assertions_written=int(d.get("assertions_written") or 0),
            assertions_skipped=int(d.get("assertions_skipped") or 0),
            assertions_rejected=int(d.get("assertions_rejected") or 0),
            documents_gated_out=int(d.get("documents_gated_out") or 0),
            errors=int(d.get("errors") or 0),
            cost_eur=float(d.get("cost_eur") or 0.0),
            last_success_at=d.get("last_success_at"),
        )


# The executed-query outcome shared by /query/cypher and /query/builder
# (`QueryResponse`): the outcome is a plain dataclass because it fuses the
# NlqOutcome fields with the coverage/diagnosis the routers attach.
@dataclass(frozen=True, slots=True)
class QueryOutcome:
    cypher: str
    results: GraphResult
    coverage: CoverageReport
    diagnosis: Diagnosis | None
    notes: list[str] = field(default_factory=list)

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Self:
        return cls(
            cypher=str(d["cypher"]),
            results=GraphResult.from_api(d["results"]),
            coverage=CoverageReport.from_api(d.get("coverage") or {}),
            diagnosis=(
                Diagnosis.from_api(d["diagnosis"]) if d.get("diagnosis") is not None else None
            ),
            notes=list(d.get("notes") or []),
        )


@dataclass(frozen=True, slots=True)
class OperationRequest:
    request_id: str
    command: str
    source: str | None = None
    days: int | None = None
    version: str | None = None
    stage: str | None = None
    evaluation: str | None = None

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Self:
        return cls(**d)


@dataclass(frozen=True, slots=True)
class OperationJob:
    job_id: str
    request: OperationRequest
    status: str
    created_at: str
    updated_at: str
    output: str = ""
    exit_code: int | None = None

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Self:
        return cls(**{**d, "request": OperationRequest.from_api(d["request"])})
