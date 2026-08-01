# src/limes/graph/loader.py | v1.0.0 | introduced by WP-07
"""The sole writer of ontology-typed nodes, relationships, and lookup rows
(Technical Specification §15.2, DD-19).

`load` applies the §5.6 merge semantics in batches of at most 500 assertions
per transaction: materialize endpoint nodes (grouped by label set from
`Ontology.labels_for`), materialize lookup rows, then merge relationships
bitemporally — idempotent by `assertion_id`, interval closure scoped to the
same `source_id`, non-destructive re-merge (AC-05, AC-06, AC-08, AC-09).
An assertion whose endpoint lacks an `entity_id` is rejected as
`ENDPOINT_UNIDENTIFIED`, counted, never written (AC-10).

The batch transaction runs through the driver's underlying session rather
than `GraphDriver.write_batch` because honest per-statement outcomes
(written/skipped/closed) are required, and `write_batch` returns only
aggregated counters. The pattern is the same as the downgrade guard in
schema.py: `GraphDriver._driver` is the only seam into the raw driver.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from neo4j.exceptions import Neo4jError
from pydantic import BaseModel

from limes.errors import GraphWriteError
from limes.graph import queries
from limes.graph.driver import GraphDriver
from limes.ontology.model import Ontology
from limes.ontology.validator import validate_assertions
from limes.types import Assertion, EntityEndpoint, LookupRow, ValidationError

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
) -> LoadResult:
    """Validate, partition, and write one batch of assertions bitemporally.

    Rejections are counted and logged with their reason, never silently
    dropped. Assertions are processed in transactions of at most
    `BATCH_SIZE`; standalone entities and lookup rows ride with the first
    batch's transaction.
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
    lookup = list(lookup_rows or [])
    batches = [valid[i : i + BATCH_SIZE] for i in range(0, len(valid), BATCH_SIZE)]
    if not batches:
        batches = [[]]

    for index, batch in enumerate(batches):
        _load_batch(
            driver,
            batch,
            ontology,
            standalone if index == 0 else [],
            lookup if index == 0 else [],
            result,
        )
    return result


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
    result: LoadResult,
) -> None:
    """One batch in one transaction: nodes, lookup rows, relationships, and
    interval closure (Doc 2 §5.6). A partial batch can leave neither an edge
    without endpoints nor an endpoint without its justifying edge (Doc 1
    §5.7)."""
    now = datetime.now(UTC)
    endpoints = _distinct_endpoints(batch, standalone)

    by_labels: dict[tuple[str, ...], list[EntityEndpoint]] = {}
    for endpoint in endpoints:
        labels = tuple(ontology.labels_for(endpoint.type))
        by_labels.setdefault(labels, []).append(endpoint)

    statements: list[tuple[str, dict[str, Any]]] = []
    for labels, group in by_labels.items():
        for endpoint in group:
            key_prop = _key_property(endpoint, ontology)
            key_value = (
                endpoint.deterministic_key[1]
                if endpoint.deterministic_key is not None
                else None
            )
            params: dict[str, Any] = {
                "entity_id": endpoint.entity_id,
                "label": endpoint.label,
                "aliases": endpoint.aliases,
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
