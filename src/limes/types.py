# src/limes/types.py | v1.0.0 | introduced by WP-02
"""Core types per Technical Specification §5.5.

Defined once here; every module signature in §8 uses these names. The
distinction between `ExtractedAssertion` (pre-resolution, endpoints are
mentions) and `Assertion` (resolved, endpoints are identified) is load-bearing:
the extractor runs before resolution and cannot assign an `entity_id`. The
named converter is `resolution/resolve.py::resolve_assertions`.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from limes.news.models import ClaimQualifiers


class Mention(BaseModel):
    """An entity as named in text, before identity is assigned."""

    surface: str
    type: str  # inferred concrete ontology type
    deterministic_key: tuple[str, str] | None = None


class EntityEndpoint(BaseModel):
    """An entity with identity assigned. Everything the loader needs to
    materialize its node. Built by adapters (structured) or the resolver
    (extracted). Never inferred by the loader."""

    entity_id: str
    type: str
    label: str
    deterministic_key: tuple[str, str] | None = None
    aliases: list[str] = []


class Provenance(BaseModel):
    """Where an assertion came from and how much it is trusted."""

    source_id: str
    source_trust: float
    confidence: float
    extractor_model: str | None = None
    prompt_version: str | None = None
    schema_version: str | None = None
    ontology_version: str
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


class Validity(BaseModel):
    """Bitemporal interval: validity time and belief time, independently
    queryable (Doc 1 §5.6)."""

    valid_from: datetime
    valid_to: datetime | None = None
    recorded_at: datetime
    retracted_at: datetime | None = None


class ExtractedAssertion(BaseModel):
    """Pre-resolution. What the extractor returns. Endpoints are mentions."""

    qualifiers: ClaimQualifiers | None = None
    passage_index: int
    subject: Mention
    relation: str
    object: Mention
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    confidence: float
    evidence_start: int
    evidence_end: int


class Assertion(BaseModel):
    """Resolved. What the loader accepts. Endpoints are identified."""

    qualifiers: ClaimQualifiers | None = None
    assertion_id: str
    subject: EntityEndpoint
    relation: str
    object: EntityEndpoint
    validity: Validity
    provenance: Provenance


class LookupRow(BaseModel):
    """Reference data materialized as system nodes. Cross-process state per
    C-07; never module state, never a derived file."""

    kind: Literal["postal_code"]
    key: dict[str, str]
    value: dict[str, str]


class DocumentPayload(BaseModel):
    """A normalized document ready for gating and extraction."""

    news_metadata: dict[str, object] | None = None
    content_hash: str
    title: str
    body: str
    language: str
    published_at: datetime
    url: str | None = None


class Passage(BaseModel):
    """A selected passage within a document, with offsets into the original
    document text."""

    index: int
    text: str
    doc_start: int  # offset in the source document
    doc_end: int


class RawRecord(BaseModel):
    """A raw payload as fetched from a source."""

    acquisition_context: dict[str, object] | None = None
    payload: bytes
    content_type: str
    source_url: str | None = None
    fetched_at: datetime


class NormalizedRecord(BaseModel):
    """The adapter's normalized output: assertions plus entities that are
    named but appear in no relationship, plus reference data and optionally a
    document payload."""

    content_hash: str
    kind: Literal["structured", "document"]
    assertions: list[Assertion] = []
    entities: list[EntityEndpoint] = []  # named but in no relationship
    lookup_rows: list[LookupRow] = []
    document: DocumentPayload | None = None
    errors: int = 0  # counted partial normalization failures; checkpoint cannot advance


class NerSpan(BaseModel):
    """A named-entity recognition span."""

    text: str
    label: str
    start: int
    end: int


class GateDecision(BaseModel):
    """The gate's verdict on a document."""

    passed: bool
    reason: str
    passages: list[Passage]


class ValidationError(BaseModel):
    """One rejected assertion: its index in the input, the reason, and any
    detail the validator can provide."""

    assertion_index: int
    reason: str
    detail: dict[str, object]


class WriteResult(BaseModel):
    """Outcome counters for a batch of graph writes."""

    statements_executed: int
    nodes_created: int
    relationships_created: int
    properties_set: int


class PlanSummary(BaseModel):
    """A parsed query plan from `EXPLAIN`, used by the plan gate."""

    operators: list[str]
    max_estimated_rows: int
    total_estimated_rows: int
    has_cartesian_product: bool
    max_varlength_hops: int | None


class CostLedgerEntry(BaseModel):
    """One paid API call, recorded as a `:CostLedgerEntry` node."""

    ledger_id: str
    period: str  # YYYY-MM
    run_id: str | None = None
    purpose: Literal["extraction", "adjudication", "embedding", "nl2cypher"]
    model_id: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    cost_eur: Decimal
    created_at: datetime


class SourceRecord(BaseModel):
    """In-memory view of a `:Source` node, read by window resolution."""

    source_id: str
    name: str
    kind: Literal["structured", "unstructured"]
    trust_rank: float
    last_success_at: datetime | None = None
    last_run_id: str | None = None


class IngestionRunRecord(BaseModel):
    """The durable record of one ingestion run (`:IngestionRun` node)."""

    run_id: str
    source_id: str
    mode: Literal["ingest", "backfill", "reextract"]
    started_at: datetime
    finished_at: datetime | None = None
    window_from: datetime | None = None
    window_to: datetime | None = None
    records_fetched: int = 0
    nodes_created: int = 0
    nodes_matched: int = 0
    assertions_written: int = 0
    assertions_skipped: int = 0
    assertions_rejected: int = 0
    documents_gated_out: int = 0
    errors: int = 0
    cost_eur: Decimal = Decimal("0")
