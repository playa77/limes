# src/limes/graph/loader.py | v1.2.0 | introduced by WP-07, amended by WP-25a, WP-28 repair
"""The sole writer of ontology-typed nodes, relationships, and lookup rows
(Technical Specification §15.2, DD-19).

`load` applies the §5.6 merge semantics in transactions of at most 500
assertions and at most 500 lookup rows: materialize endpoint nodes (grouped
by label set from `Ontology.labels_for`), materialize lookup rows, then merge
relationships bitemporally — idempotent by `assertion_id`, interval closure
scoped to the same `source_id`, non-destructive re-merge (AC-05, AC-06,
AC-08, AC-09).
An assertion whose endpoint lacks an `entity_id` is rejected as
`ENDPOINT_UNIDENTIFIED`, counted, never written (AC-10).

Since WP-25a, the §5.6 merge stamp includes `label_embedding = embed(label)`
on node creation — the property that populates the §5.3 vector index. The
embedder is injected as a plain callable so the loader stays free of any
inference dependency: `load` computes which endpoints have no node yet (one
read per batch), embeds exactly those labels, and normalizes defensively
(L2 — the index declares cosine). Endpoints whose node already exists are
never re-embedded; without an embedder the omission is logged, and the
one-shot `stamp_missing_embeddings` backfill is the only path that fills a
null embedding (nodes created before the stamp existed).

The batch transaction runs through the driver's underlying session rather
than `GraphDriver.write_batch` because honest per-statement outcomes
(written/skipped/closed) are required, and `write_batch` returns only
aggregated counters. The pattern is the same as the downgrade guard in
schema.py: `GraphDriver._driver` is the only seam into the raw driver.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import structlog
from neo4j.exceptions import Neo4jError
from pydantic import BaseModel

from limes.errors import GraphWriteError
from limes.graph import queries
from limes.graph.driver import GraphDriver
from limes.graph.embeddings import normalize_embedding
from limes.ontology.model import Ontology
from limes.ontology.validator import validate_assertions
from limes.sources.base import hash_entity_id
from limes.types import Assertion, DocumentPayload, EntityEndpoint, LookupRow, ValidationError

BATCH_SIZE = 500
REASON_ENDPOINT_UNIDENTIFIED = "ENDPOINT_UNIDENTIFIED"

# LookupRow carries no source attribution (§5.5), while the :PostalCode node
# schema requires `source_id` (§5.8). The producing source per kind is fixed
# by the source table (§8.5.2): the postal-code correspondence is emitted by
# gisco_nuts and by no other adapter.
_LOOKUP_ROW_SOURCES: dict[str, str] = {"postal_code": "gisco_nuts"}

logger = structlog.get_logger(__name__)


class LoadResult(BaseModel):
    """Outcome counters for one `load` call (Doc 2 §8.3)."""

    nodes_created: int = 0
    nodes_matched: int = 0
    lookup_rows_written: int = 0
    written: int = 0
    skipped: int = 0
    closed_intervals: int = 0
    rejected: int = 0


def load(
    driver: GraphDriver,
    assertions: list[Assertion],
    ontology: Ontology,
    standalone_entities: list[EntityEndpoint] | None = None,
    lookup_rows: list[LookupRow] | None = None,
    embedder: Callable[[list[str]], list[list[float]]] | None = None,
) -> LoadResult:
    """Validate, partition, and write one batch of assertions bitemporally.

    Rejections are counted and logged with their reason, never silently
    dropped. Assertions are processed in transactions of at most
    `BATCH_SIZE`; standalone entities ride with the first batch's
    transaction. Lookup rows are chunked at the same size: chunk *i* rides
    with assertion batch *i*, and any overflow chunks each run in their own
    transaction — a record's whole lookup list can exceed any transaction
    (the GISCO postcode correspondence is ~300k rows; a single transaction
    of them blows the §13.4 caps, which is why batching here is load-bearing
    and not an optimization).

    The embedder contract (WP-25a): `embedder(labels)` returns one vector
    per input text, in order, each exactly `LIMES_EMBEDDING_DIMENSIONS`
    long and intended for the §5.3 cosine index. The loader re-normalizes
    every vector defensively; a length mismatch between labels and vectors
    is a programming error and raises. When `embedder` is None — or an
    endpoint's node already exists — no embedding is computed or stamped,
    and the omission is logged.
    """
    result = LoadResult()
    valid, rejected = _partition(assertions, ontology)
    for error in rejected:
        logger.warning(
            "assertion rejected",
            reason=error.reason,
            assertion_index=error.assertion_index,
            detail=error.detail,
        )
    result.rejected = len(rejected)

    standalone = list(standalone_entities or [])
    # Validate every property before any batch can commit.
    validate_entity_properties(_distinct_endpoints(valid, standalone), ontology)
    lookup = list(lookup_rows or [])
    batches = [valid[i : i + BATCH_SIZE] for i in range(0, len(valid), BATCH_SIZE)]
    if not batches:
        batches = [[]]
    lookup_chunks = [lookup[i : i + BATCH_SIZE] for i in range(0, len(lookup), BATCH_SIZE)]

    for index, batch in enumerate(batches):
        _load_batch(
            driver,
            batch,
            ontology,
            standalone if index == 0 else [],
            lookup_chunks[index] if index < len(lookup_chunks) else [],
            embedder,
            result,
        )
    for chunk in lookup_chunks[len(batches) :]:
        _load_batch(driver, [], ontology, [], chunk, embedder, result)
    return result


def stamp_missing_embeddings(
    driver: GraphDriver,
    embedder: Callable[[list[str]], list[list[float]]],
    batch_size: int = 500,
) -> int:
    """One-shot backfill: stamp `label_embedding` on every `:Entity` whose
    embedding is null (nodes created before the §5.6 merge stamp existed, or
    by a `load` without an embedder).

    Pages over the nulls in `batch_size` chunks, embeds each page's labels
    in one call, and stamps. Idempotent: a second run finds no nulls and
    returns zero. This is the only path that fills a null embedding; the
    merge statement itself never touches a matched node's embedding.
    """
    stamped = 0
    while True:
        rows = driver.read(queries.MISSING_EMBEDDINGS_READ, {"batch_size": batch_size}, 60)
        if not rows:
            break
        labels = [str(row["label"]) for row in rows]
        vectors = embedder(labels)
        if len(vectors) != len(labels):
            raise ValueError(f"embedder returned {len(vectors)} vectors for {len(labels)} labels")
        statements = [
            (
                queries.EMBEDDING_STAMP,
                {"entity_id": str(row["entity_id"]), "label_embedding": normalize_embedding(v)},
            )
            for row, v in zip(rows, vectors, strict=True)
        ]
        driver.write_batch(statements)
        stamped += len(rows)
        logger.info(
            "embedding backfill stamped",
            stamped_in_page=len(rows),
            total=stamped,
        )
        if len(rows) < batch_size:
            break
    return stamped


def retract(driver: GraphDriver, assertion_ids: list[str], at: datetime) -> int:
    """Set `retracted_at` on the given assertions. Returns the number of
    relationships retracted; already-retracted assertions are left alone."""
    with driver._driver.session(default_access_mode="WRITE") as session:
        try:
            with session.begin_transaction() as tx:
                result = tx.run(queries.RETRACT_STATEMENT, assertion_ids=assertion_ids, at=at)
                records = list(result)
                return records[0]["retracted"] if records else 0
        except Neo4jError as exc:
            raise GraphWriteError(f"retraction failed: {exc}") from exc


def _partition(
    assertions: list[Assertion], ontology: Ontology
) -> tuple[list[Assertion], list[ValidationError]]:
    """Partition into writable assertions and rejections. Reuses the
    ontology validator's checks (relation, domain, range, non-temporal
    `valid_to`) and adds the loader's own: endpoint identification (AC-10)."""
    accepted, rejected = validate_assertions(assertions, ontology)
    accepted_ids = {id(a) for a in accepted}

    valid: list[Assertion] = []
    for index, assertion in enumerate(assertions):
        if id(assertion) not in accepted_ids:
            continue
        if not assertion.subject.entity_id or not assertion.object.entity_id:
            rejected.append(
                ValidationError(
                    assertion_index=index,
                    reason=REASON_ENDPOINT_UNIDENTIFIED,
                    detail={"relation": assertion.relation},
                )
            )
            continue
        valid.append(assertion)
    return valid, rejected


def _distinct_endpoints(
    assertions: list[Assertion], standalone: list[EntityEndpoint]
) -> list[EntityEndpoint]:
    """Every endpoint of every assertion plus every standalone entity, one
    entry per `entity_id`. First occurrence wins; the loader never merges a
    node twice within a batch, so `nodes_matched` counts stay exact."""
    seen: dict[str, EntityEndpoint] = {}
    for assertion in assertions:
        for endpoint in (assertion.subject, assertion.object):
            seen.setdefault(endpoint.entity_id, endpoint)
    for endpoint in standalone:
        seen.setdefault(endpoint.entity_id, endpoint)
    return list(seen.values())


def _key_property(endpoint: EntityEndpoint, ontology: Ontology) -> str | None:
    """The deterministic key's property name, returned only when the key
    name is declared for the endpoint's type. Property names cannot be
    parameterized; bounding the name by the ontology keeps source data out
    of the query text (Doc 2 §5.6)."""
    if endpoint.deterministic_key is None:
        return None
    key_name, key_value = endpoint.deterministic_key
    if not key_value:
        return None
    spec = ontology.entity_types[endpoint.type]
    if key_name not in spec.identifying_keys:
        logger.warning(
            "deterministic key not declared for type; key not stamped",
            key_name=key_name,
            type=endpoint.type,
            entity_id=endpoint.entity_id,
        )
        return None
    return key_name


def validate_entity_properties(endpoints: list[EntityEndpoint], ontology: Ontology) -> None:
    """Check ontology property types before source processing or any batch commit."""
    for endpoint in endpoints:
        _entity_properties(endpoint, ontology)


def _entity_properties(endpoint: EntityEndpoint, ontology: Ontology) -> dict[str, Any]:
    """Only declared, typed properties; immutable on re-merge like the source version."""
    specs = {p.name: p.type for p in ontology.entity_types[endpoint.type].properties}
    protected = {"entity_id", "label", "aliases", "ontology_version", "created_at",
                 "label_embedding", *ontology.entity_types[endpoint.type].identifying_keys}
    checked: dict[str, Any] = {}
    for key, value in endpoint.properties.items():
        if key in protected:
            # Identifying keys have a separate validated stamping path.
            if endpoint.deterministic_key == (key, value):
                continue
            raise ValueError(f"protected entity property: {key}")
        kind = specs.get(key)
        valid = value is None or (
            (kind == "string" and isinstance(value, str))
            or (kind == "integer" and isinstance(value, int) and not isinstance(value, bool))
            or (kind == "float" and isinstance(value, (int, float))
                and not isinstance(value, bool) and math.isfinite(value))
            or (kind == "boolean" and isinstance(value, bool))
            or (kind == "datetime" and isinstance(value, datetime) and value.tzinfo is not None)
        )
        if kind is None or not valid:
            raise ValueError(f"undeclared or invalid entity property: {endpoint.type}.{key}")
        checked[key] = value
    return checked


def _relationship_properties(assertion: Assertion, temporal: bool) -> dict[str, Any]:
    """Every §5.6 metadata property. `recorded_at` comes from the
    assertion's validity, never the wall clock: sources like OffeneRegister
    publish their own vintage, and stamping ingestion time would make
    multi-year-stale data look current (Doc 1 §5.8). Non-temporal relations
    never carry `valid_to` (Doc 2 §5.1)."""
    provenance = assertion.provenance
    validity = assertion.validity
    props: dict[str, Any] = {
        "assertion_id": assertion.assertion_id,
        "valid_from": validity.valid_from,
        "recorded_at": validity.recorded_at,
        "retracted_at": validity.retracted_at,
        "source_id": provenance.source_id,
        "source_trust": provenance.source_trust,
        "confidence": provenance.confidence,
        "extractor_model": provenance.extractor_model,
        "prompt_version": provenance.prompt_version,
        "schema_version": provenance.schema_version,
        "ontology_version": provenance.ontology_version,
        "evidence_document_id": provenance.evidence_document_id,
        "evidence_start": provenance.evidence_start,
        "evidence_end": provenance.evidence_end,
        "evidence_channel": provenance.evidence_channel,
        "evidence_member": provenance.evidence_member,
        "evidence_row": provenance.evidence_row,
        "source_event_id": provenance.source_event_id,
        "source_url": provenance.source_url,
        "report_url": provenance.report_url,
        "source_recorded_at": provenance.source_recorded_at,
        "article_text_available": provenance.article_text_available,
    }
    if temporal and validity.valid_to is not None:
        props["valid_to"] = validity.valid_to
    return props


def _load_batch(
    driver: GraphDriver,
    batch: list[Assertion],
    ontology: Ontology,
    standalone: list[EntityEndpoint],
    lookup_rows: list[LookupRow],
    embedder: Callable[[list[str]], list[list[float]]] | None,
    result: LoadResult,
) -> None:
    """One batch in one transaction: nodes, lookup rows, relationships, and
    interval closure (Doc 2 §5.6). A partial batch can leave neither an edge
    without endpoints nor an endpoint without its justifying edge (Doc 1
    §5.7)."""
    now = datetime.now(UTC)
    endpoints = _distinct_endpoints(batch, standalone)
    embeddings = _embeddings_for(driver, endpoints, embedder)

    by_labels: dict[tuple[str, ...], list[EntityEndpoint]] = {}
    for endpoint in endpoints:
        labels = tuple(ontology.labels_for(endpoint.type))
        by_labels.setdefault(labels, []).append(endpoint)

    statements: list[tuple[str, dict[str, Any]]] = []
    for labels, group in by_labels.items():
        for endpoint in group:
            key_prop = _key_property(endpoint, ontology)
            key_value = (
                endpoint.deterministic_key[1] if endpoint.deterministic_key is not None else None
            )
            params: dict[str, Any] = {
                "entity_properties": _entity_properties(endpoint, ontology),
                "entity_id": endpoint.entity_id,
                "label": endpoint.label,
                "aliases": endpoint.aliases,
                "label_embedding": embeddings.get(endpoint.entity_id),
                "ontology_version": ontology.version,
                "created_at": now,
                "key_value": key_value,
            }
            statements.append((queries.merge_entity(list(labels), key_prop), params))

    for row in lookup_rows:
        source_id = _LOOKUP_ROW_SOURCES.get(row.kind)
        if source_id is None:
            logger.warning("lookup row kind has no declared source; skipped", kind=row.kind)
            continue
        if row.kind == "postal_code":
            statements.append(
                (
                    queries.POSTAL_CODE_MERGE,
                    {**row.key, **row.value, "source_id": source_id, "recorded_at": now},
                )
            )
            result.lookup_rows_written += 1

    for assertion in batch:
        relation_spec = ontology.relation_types[assertion.relation]
        statements.append(
            (
                queries.create_relationship(assertion.relation),
                {
                    "subject_id": assertion.subject.entity_id,
                    "object_id": assertion.object.entity_id,
                    "assertion_id": assertion.assertion_id,
                    "props": _relationship_properties(assertion, relation_spec.temporal),
                },
            )
        )
        if relation_spec.temporal:
            statements.append(
                (
                    queries.close_interval(assertion.relation),
                    {
                        "subject_id": assertion.subject.entity_id,
                        "object_id": assertion.object.entity_id,
                        "source_id": assertion.provenance.source_id,
                        "evidence_channel": assertion.provenance.evidence_channel,
                        "valid_from": assertion.validity.valid_from,
                    },
                )
            )

    with driver._driver.session(default_access_mode="WRITE") as session:
        tx = session.begin_transaction()
        try:
            created_in_batch = 0
            for cypher, params in statements:
                tx_result = tx.run(cypher, **params)
                records = list(tx_result)
                counters = tx_result.consume().counters
                created_in_batch += counters.nodes_created or 0
                result.written += counters.relationships_created or 0
                for record in records:
                    if record.get("outcome") == "skipped":
                        result.skipped += 1
                    closed = record.get("closed")
                    if closed:
                        result.closed_intervals += int(closed)
            tx.commit()
        except Neo4jError as exc:
            tx.rollback()
            raise GraphWriteError(f"graph load failed: {exc}") from exc

    result.nodes_created += created_in_batch
    result.nodes_matched += max(0, len(endpoints) - created_in_batch)


def _embeddings_for(
    driver: GraphDriver,
    endpoints: list[EntityEndpoint],
    embedder: Callable[[list[str]], list[list[float]]] | None,
) -> dict[str, list[float]]:
    """`entity_id -> label_embedding` for the endpoints whose node does not
    exist yet (WP-25a §5.6 stamp).

    One read per batch establishes which ids are absent; existing nodes are
    never re-embedded (their embedding is immutable on re-merge). The
    embedder output is normalized defensively — the §5.3 index declares
    cosine, and the loader is the merge choke point that must not stamp an
    unnormalized vector. Without an embedder, new nodes get a null embedding
    and the omission is logged with the entity count — visible, never
    silent; `stamp_missing_embeddings` is the backfill for exactly this
    case."""
    if embedder is None:
        if endpoints:
            logger.info(
                "load without embedder; new nodes carry null label_embedding",
                entities=len(endpoints),
            )
        return {}
    ids = [endpoint.entity_id for endpoint in endpoints]
    rows = driver.read(queries.MISSING_ENTITY_IDS, {"ids": ids}, 60)
    existing = {str(row["entity_id"]) for row in rows}
    missing = [endpoint for endpoint in endpoints if endpoint.entity_id not in existing]
    if not missing:
        return {}
    vectors = embedder([endpoint.label for endpoint in missing])
    if len(vectors) != len(missing):
        raise ValueError(f"embedder returned {len(vectors)} vectors for {len(missing)} labels")
    return {
        endpoint.entity_id: normalize_embedding(vector)
        for endpoint, vector in zip(missing, vectors, strict=True)
    }


def save_document(driver: GraphDriver, doc: DocumentPayload, ontology: Ontology) -> None:
    metadata = doc.news_metadata or {}
    props = {
        "entity_id": doc.content_hash,
        "document_id": doc.content_hash,
        "label": doc.title,
        "body": doc.body,
        "url": doc.url,
        "published_at": doc.published_at if metadata.get("publication_known") else None,
        "recorded_at": datetime.now(UTC),
        "metadata": json.dumps(metadata, sort_keys=True),
        "investigation_id": metadata.get("investigation_id"),
        "dispatch_id": metadata.get("dispatch_id") or None,
        "publisher": metadata.get("publisher"),
        "feed_hash": metadata.get("feed_hash"),
        "article_text_available": bool(metadata.get("text_available", False)),
        "ontology_version": ontology.version,
    }
    labels = ":".join(ontology.labels_for("NewsDocument"))
    driver.write_batch(
        [
            (
                f"OPTIONAL MATCH (old:NewsDocument) "
                "WHERE old.dispatch_id=$dispatch AND old.publisher=$publisher "
                "AND old.document_id <> $id "
                "WITH old ORDER BY old.recorded_at DESC LIMIT 1 "
                f"MERGE (d:{labels} {{entity_id: $id}}) "
                "ON CREATE SET d += $props, d.previous_document_id=old.document_id, "
                "d.correction_status='unknown', d.evaluation_status='unreviewed'",
                {
                    "id": doc.content_hash,
                    "props": props,
                    "dispatch": metadata.get("dispatch_id") or None,
                    "publisher": metadata.get("publisher"),
                },
            )
        ]
    )


def news_claim_id(assertion: Assertion, doc: DocumentPayload) -> str:
    assert assertion.qualifiers is not None
    return hash_entity_id(
        "claim",
        doc.content_hash,
        assertion.subject.entity_id,
        assertion.relation,
        assertion.object.entity_id,
        str(assertion.provenance.evidence_start),
        str(assertion.provenance.evidence_end),
        (
            assertion.validity.valid_from.isoformat()
            if assertion.qualifiers.time_precision != "unknown"
            else "unknown"
        ),
        str(assertion.validity.valid_to),
        assertion.qualifiers.model_dump_json(),
        str(assertion.provenance.prompt_version),
        str(assertion.provenance.schema_version),
        str(assertion.provenance.extractor_model),
    )


def save_claims(
    driver: GraphDriver, assertions: list[Assertion], doc: DocumentPayload, ontology: Ontology
) -> LoadResult:
    statements = []
    metadata = doc.news_metadata or {}
    labels = ":".join(ontology.labels_for("NewsClaim"))
    for assertion in assertions:
        q = assertion.qualifiers
        if q is None:
            raise ValueError("news claim has no qualifiers")
        key = news_claim_id(assertion, doc)
        props = {
            "entity_id": key,
            "label": f"{q.modality}: {assertion.relation}",
            "claim_id": key,
            "subject_id": assertion.subject.entity_id,
            "subject_label": assertion.subject.label,
            "object_id": assertion.object.entity_id,
            "object_label": assertion.object.label,
            "relation": assertion.relation,
            **q.model_dump(),
            "evidence_document_id": doc.content_hash,
            "evidence_start": assertion.provenance.evidence_start,
            "evidence_end": assertion.provenance.evidence_end,
            "source_id": assertion.provenance.source_id,
            "source_trust": assertion.provenance.source_trust,
            "confidence": assertion.provenance.confidence,
            "recorded_at": assertion.validity.recorded_at,
            "valid_from": assertion.validity.valid_from if q.time_precision != "unknown" else None,
            "valid_to": assertion.validity.valid_to,
            "retracted_at": None,
            "ontology_version": ontology.version,
            "prompt_version": assertion.provenance.prompt_version,
            "schema_version": assertion.provenance.schema_version,
            "extractor_model": assertion.provenance.extractor_model,
            "investigation_id": metadata.get("investigation_id"),
            "dispatch_id": metadata.get("dispatch_id") or None,
            "publisher": metadata.get("publisher"),
            "report_url": doc.url,
            # A shared dispatch is dependent reporting; never count it as corroboration.
            "syndication_key": hash_entity_id(
                "dispatch",
                str(metadata.get("publisher")),
                str(metadata.get("dispatch_id") or doc.content_hash),
            ),
        }
        statements.append(
            (
                f"MERGE (c:{labels} {{entity_id: $id}}) ON CREATE SET c += $props",
                {"id": key, "props": props},
            )
        )
    if not statements:
        return LoadResult()
    written = driver.write_batch(statements).nodes_created
    return LoadResult(written=written, skipped=len(statements) - written)


def save_news_review(driver: GraphDriver, document_id: str, review_json: str) -> None:
    """Persist operator-supplied evaluation labels; these never assess graph truth."""
    driver.write_batch(
        [
            (
                "MATCH (d:NewsDocument {document_id:$id}) "
                "SET d.evaluation_status='reviewed', d.evaluation_review=$review",
                {"id": document_id, "review": review_json},
            )
        ]
    )


def save_event_match_review(
    driver: GraphDriver, investigation_id: str, review: dict[str, object]
) -> None:
    """Immutable operator hypotheses; never merge events, rewrite claims or assess truth."""
    driver.write_batch(
        [
            (
                "MERGE (r:EventMatchReview {request_id:$id}) "
                "ON CREATE SET r += $props, r.recorded_at=datetime()",
                {
                    "id": review["request_id"],
                    "props": {**review, "investigation_id": investigation_id},
                },
            )
        ]
    )



def save_enrichment_check(driver: GraphDriver, snapshot_id: str, manifest_hash: str,
                          checked_at: datetime) -> int:
    """Acquisition history is distinct from immutable source versions and factual edges."""
    return driver.write_batch([(
        "MERGE (c:EnrichmentCheck {check_id:$id}) ON CREATE SET "
        "c.snapshot_id=$snapshot, c.manifest_hash=$manifest, c.checked_at=$at",
        {"id": hash_entity_id("source-check", snapshot_id, manifest_hash),
         "snapshot": snapshot_id, "manifest": manifest_hash, "at": checked_at},
    )]).nodes_created
