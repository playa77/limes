# src/limes/graph/schema.py | v1.0.3 | introduced by WP-04, serialized by the
# architecture-consolidation repair (D-67, D-67b); guard moved under the lock
# by the review follow-up (D-68)
"""Idempotent Neo4j schema provisioning per Technical Specification §5.3.

`provision` executes every constraint and index from §5.3 with `IF NOT
EXISTS`, so running twice produces no error and no duplicate index (AC-03).
Relationship-property indexes on `valid_from`, `valid_to`, `recorded_at` are
generated from the ontology for every `temporal: true` relation. It also
applies the ontology downgrade guard of §4.3: when the graph already carries
`:Entity` nodes stamped with a newer ontology version than the artifact,
provisioning raises `OntologyError` and startup fails (AC-01).

Provisioning is serialized across processes (D-67, D-67b): the api startup
handler and the worker's first command both call it, and two concurrent
`IF NOT EXISTS` creations of the same index can fail server-side with
`EquivalentSchemaRuleAlreadyExists`. Provisioners queue on the existing
`:AdvisoryLock` node type (source_id `__ontology_provision__`), whose
uniqueness constraint turns a lost acquisition race into a loud error;
the loser polls until the holder releases or the lock goes stale.
"""

from __future__ import annotations

import random
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from neo4j import Driver

from limes.errors import GraphWriteError, LimesError, OntologyError
from limes.graph.driver import GraphDriver
from limes.ontology.model import Ontology

logger = structlog.get_logger(__name__)

# DDL from Doc 2 §5.3. Statement order matters only for readability; every
# statement is `IF NOT EXISTS` and therefore safe in any order on a fresh
# database and on re-runs.
_SCHEMA_STATEMENTS: list[str] = [
    "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (n:Entity) REQUIRE n.entity_id IS UNIQUE",
    "CREATE CONSTRAINT mention_id IF NOT EXISTS FOR (n:Mention) REQUIRE n.mention_id IS UNIQUE",
    "CREATE CONSTRAINT document_hash IF NOT EXISTS FOR (n:Document) REQUIRE n.content_hash IS UNIQUE",
    "CREATE CONSTRAINT corporation_lei IF NOT EXISTS FOR (n:Corporation) REQUIRE n.lei IS UNIQUE",
    "CREATE CONSTRAINT legalact_celex IF NOT EXISTS FOR (n:LegalAct) REQUIRE n.celex IS UNIQUE",
    "CREATE CONSTRAINT country_iso2 IF NOT EXISTS FOR (n:Country) REQUIRE n.iso2 IS UNIQUE",
    "CREATE CONSTRAINT region_nuts IF NOT EXISTS FOR (n:AdministrativeRegion) REQUIRE n.nuts_code IS UNIQUE",
    "CREATE CONSTRAINT contract_ted IF NOT EXISTS FOR (n:Contract) REQUIRE n.ted_notice_id IS UNIQUE",
    "CREATE CONSTRAINT asset_osm IF NOT EXISTS FOR (n:Asset) REQUIRE n.osm_id IS UNIQUE",
    "CREATE CONSTRAINT interestgroup_tr IF NOT EXISTS FOR (n:InterestGroup) REQUIRE n.transparency_register_id IS UNIQUE",
    "CREATE CONSTRAINT postal_code_key IF NOT EXISTS FOR (p:PostalCode) REQUIRE (p.country_code, p.postal_code) IS UNIQUE",
    "CREATE CONSTRAINT source_id IF NOT EXISTS FOR (n:Source) REQUIRE n.source_id IS UNIQUE",
    "CREATE CONSTRAINT run_id IF NOT EXISTS FOR (n:IngestionRun) REQUIRE n.run_id IS UNIQUE",
    "CREATE CONSTRAINT cache_key IF NOT EXISTS FOR (n:ExtractionCacheEntry) REQUIRE n.cache_key IS UNIQUE",
    "CREATE CONSTRAINT ledger_id IF NOT EXISTS FOR (n:CostLedgerEntry) REQUIRE n.ledger_id IS UNIQUE",
    "CREATE CONSTRAINT saved_query_id IF NOT EXISTS FOR (n:SavedQuery) REQUIRE n.saved_query_id IS UNIQUE",
    "CREATE CONSTRAINT lock_source IF NOT EXISTS FOR (n:AdvisoryLock) REQUIRE n.source_id IS UNIQUE",
    "CREATE CONSTRAINT event_match_review_id IF NOT EXISTS FOR (n:EventMatchReview) REQUIRE n.request_id IS UNIQUE",
    "CREATE INDEX event_match_case IF NOT EXISTS FOR (n:EventMatchReview) ON (n.investigation_id, n.recorded_at)",
    "CREATE INDEX news_investigation IF NOT EXISTS FOR (n:NewsClaim) ON (n.investigation_id)",
    "CREATE INDEX news_dispatch IF NOT EXISTS FOR (n:NewsDocument) ON (n.dispatch_id, n.publisher)",
    "CREATE INDEX news_subject IF NOT EXISTS FOR (n:NewsClaim) ON (n.subject_id)",
    "CREATE INDEX news_object IF NOT EXISTS FOR (n:NewsClaim) ON (n.object_id)",
    "CREATE INDEX entity_label IF NOT EXISTS FOR (n:Entity) ON (n.label)",
    "CREATE INDEX entity_wikidata IF NOT EXISTS FOR (n:Entity) ON (n.wikidata_qid)",
    "CREATE INDEX event_timestamp IF NOT EXISTS FOR (n:Event) ON (n.occurred_at)",
    "CREATE INDEX document_published IF NOT EXISTS FOR (n:Document) ON (n.published_at)",
    "CREATE INDEX topic_vocab_code IF NOT EXISTS FOR (n:Topic) ON (n.vocabulary, n.code)",
    "CREATE INDEX ledger_period IF NOT EXISTS FOR (n:CostLedgerEntry) ON (n.period)",
    "CREATE FULLTEXT INDEX document_text IF NOT EXISTS FOR (n:Document) ON EACH [n.title, n.body]",
    "CREATE FULLTEXT INDEX entity_names IF NOT EXISTS FOR (n:Entity) ON EACH [n.label, n.aliases]",
]

_VECTOR_INDEX_TEMPLATE = """
CREATE VECTOR INDEX entity_label_embedding IF NOT EXISTS
  FOR (n:Entity) ON (n.label_embedding)
  OPTIONS {{ indexConfig: {{ `vector.dimensions`: {dims}, `vector.similarity_function`: 'cosine' }} }}
""".strip()

_GRAPH_VERSION_QUERY = (
    "MATCH (n:Entity) WHERE n.ontology_version IS NOT NULL "
    "RETURN max(n.ontology_version) AS max_version"
)

# The serialization lock (D-67b). It reuses the sanctioned `:AdvisoryLock`
# node type and its existing uniqueness constraint (`lock_source`,
# §5.3) — no new schema objects — with a source_id reserved for provisioning.
# CREATE (not MERGE) plus that constraint means a lost acquisition race fails
# loudly instead of silently double-holding; the loser polls.
_PROVISION_LOCK_SOURCE_ID = "__ontology_provision__"
_PROVISION_LOCK_WAIT_S = 60.0
# A crashed holder must not wedge every future context build; provisioning
# takes seconds, so a much shorter staleness than the ingest lock's applies.
_PROVISION_LOCK_STALE_AFTER_S = 120.0

_LOCK_READ = "MATCH (l:AdvisoryLock {source_id: $source_id}) RETURN l.acquired_at AS acquired_at"
_LOCK_CREATE = (
    "CREATE (l:AdvisoryLock {source_id: $source_id, run_id: $run_id, acquired_at: $acquired_at})"
)
_LOCK_DELETE = "MATCH (l:AdvisoryLock {source_id: $source_id}) DELETE l"
_LOCK_DELETE_OWN = "MATCH (l:AdvisoryLock {source_id: $source_id, run_id: $run_id}) DELETE l"
# The lock's uniqueness backing. It must exist BEFORE any lock row is
# created, so acquisition bootstraps it first (see _ensure_lock_constraint):
# without it, two simultaneous CREATEs both succeed and silently double-hold.
_LOCK_CONSTRAINT = (
    "CREATE CONSTRAINT lock_source IF NOT EXISTS FOR (n:AdvisoryLock) REQUIRE n.source_id IS UNIQUE"
)


def _relationship_property_indexes(ontology: Ontology) -> list[str]:
    """Generate `valid_from`/`valid_to`/`recorded_at` indexes for every
    temporal relation, per Doc 2 §5.3."""
    statements: list[str] = []
    for relation in ontology.relation_types.values():
        if not relation.temporal:
            continue
        for prop in ("valid_from", "valid_to", "recorded_at"):
            statements.append(
                f"CREATE INDEX {relation.name.lower()}_{prop} IF NOT EXISTS "
                f"FOR ()-[r:{relation.name}]-() ON (r.{prop})"
            )
    return statements


def provision(driver: GraphDriver, ontology: Ontology, embedding_dimensions: int) -> None:
    """Provision constraints and indexes idempotently and apply the ontology
    downgrade guard. Called by the composition root on every context build.

    One statement per transaction: Neo4j compiles schema changes in bounded
    windows and fails a single transaction that issues many of them with
    "Could not compile query due to insanely frequent schema changes". Each
    statement is idempotent (`IF NOT EXISTS`), so a partially provisioned
    database is never an error on the next run.

    Concurrent invokers are serialized by the provisioning lock (D-67b):
    exactly one holder runs the DDL batch while the others poll; their
    `IF NOT EXISTS` statements therefore cannot interleave — the failure
    mode observed live on 2026-08-24 and reproduced deterministically by
    `test_concurrent_provision_is_serialized`. A waiter that exceeds
    `_PROVISION_LOCK_WAIT_S` fails loudly rather than hanging; a holder that
    died mid-provision is reclaimed after `_PROVISION_LOCK_STALE_AFTER_S`.

    The §4.3 downgrade guard is evaluated under that same lock (D-68): it
    reads ontology versions stamped on `:Entity` nodes, so checking it
    before acquisition would leave a window in which two provisioners
    carrying different artifacts both pass before either writes DDL.
    """
    statements = list(_SCHEMA_STATEMENTS)
    statements.append(_VECTOR_INDEX_TEMPLATE.format(dims=embedding_dimensions))
    statements.extend(_relationship_property_indexes(ontology))

    run_id = _acquire_provision_lock(driver)
    try:
        _check_ontology_version(driver._driver, ontology)
        for statement in statements:
            driver.write_batch([(statement, {})])
    finally:
        _release_provision_lock(driver, run_id)


def _ensure_lock_constraint(driver: GraphDriver, attempts: int = 5) -> None:
    """Create the lock's uniqueness constraint before any lock row exists.

    Bootstrap-only tolerance (D-67b): the serializer's own foundation is one
    DDL statement, and two processes reaching it simultaneously can hit the
    server-side equivalent-rule race the same as any other schema pair. The
    window is one statement wide; bounded retries close it deterministically,
    because every loser's next attempt finds the constraint present. Every
    other statement in the batch is protected by the lock this enables —
    nowhere else is an equivalent-rule error ever tolerated.
    """
    for attempt in range(1, attempts + 1):
        try:
            driver.write_batch([(_LOCK_CONSTRAINT, {})])
            return
        except GraphWriteError as exc:
            retryable = "EquivalentSchemaRuleAlreadyExists" in str(
                exc
            ) or "ConstraintCreationFailed" in str(exc)
            if not retryable or attempt == attempts:
                raise
            time.sleep(random.uniform(0.1, 0.3) * attempt)


def _acquire_provision_lock(driver: GraphDriver) -> str:
    """Take the provisioning lock, polling while another process holds it.

    The create is backed by the `lock_source` uniqueness constraint, so two
    simultaneous acquirers produce one winner and one loud
    constraint-violation loser — never two holders. Returns the holder's
    run_id so release deletes only its own row even after a reclaim."""
    # Foundation first: without the constraint, two simultaneous CREATEs
    # would both succeed and silently double-hold (reproduced live in test).
    _ensure_lock_constraint(driver)
    run_id = uuid.uuid4().hex
    params: dict[str, Any] = {
        "source_id": _PROVISION_LOCK_SOURCE_ID,
        "run_id": run_id,
        "acquired_at": datetime.now(UTC),
    }
    deadline = time.monotonic() + _PROVISION_LOCK_WAIT_S
    while True:
        rows = driver.read(_LOCK_READ, {"source_id": _PROVISION_LOCK_SOURCE_ID}, 10)
        if rows:
            held_since = rows[0]["acquired_at"]
            # The read returns the driver's DateTime; native for arithmetic.
            if hasattr(held_since, "to_native"):
                held_since = held_since.to_native()
            age = (datetime.now(UTC) - held_since).total_seconds()
            if age > _PROVISION_LOCK_STALE_AFTER_S:
                logger.warning(
                    "stale provisioning lock reclaimed",
                    stale_after_s=_PROVISION_LOCK_STALE_AFTER_S,
                    age_s=round(age, 1),
                )
                driver.write_batch([(_LOCK_DELETE, {"source_id": _PROVISION_LOCK_SOURCE_ID})])
            elif time.monotonic() > deadline:
                raise LimesError(
                    f"provisioning lock held by another process for "
                    f"{round(age, 1)} s; gave up after {_PROVISION_LOCK_WAIT_S} s"
                )
            else:
                time.sleep(random.uniform(0.05, 0.15))
            continue
        try:
            driver.write_batch([(_LOCK_CREATE, params)])
        except GraphWriteError as exc:
            # Lost the creation race to a concurrent acquirer; poll again.
            if "ConstraintValidationFailed" not in str(exc):
                raise
            time.sleep(random.uniform(0.05, 0.15))
            continue
        logger.info("provisioning lock acquired", run_id=run_id)
        return run_id


def _release_provision_lock(driver: GraphDriver, run_id: str) -> None:
    """Delete this holder's lock row. Idempotent: a missing row is a no-op,
    so a reclaim-and-release race cannot double-delete."""
    driver.write_batch(
        [(_LOCK_DELETE_OWN, {"source_id": _PROVISION_LOCK_SOURCE_ID, "run_id": run_id})]
    )
    logger.info("provisioning lock released", run_id=run_id)


def _version_tuple(version: str) -> tuple[int, int, int]:
    return tuple(int(part) for part in version.split("."))  # type: ignore[return-value]


def _check_ontology_version(driver: Driver, ontology: Ontology) -> None:
    """Reject an artifact older than the maximum `ontology_version` stamped
    on any `:Entity` node (Doc 2 §4.3). On a fresh database the guard passes.
    A newer artifact against an older graph is permitted: provisioning adds
    what is missing.

    Uses the raw driver session directly rather than `GraphDriver.read`
    because the guard must run even against the pre-provisioning schema, and
    it is the one read that happens before any write."""
    with driver.session(database="neo4j", default_access_mode="READ") as session:
        result = session.run(_GRAPH_VERSION_QUERY)
        row = result.single()
    stamped = row["max_version"] if row else None
    if stamped is not None and _version_tuple(ontology.version) < _version_tuple(stamped):
        raise OntologyError(
            f"ontology artifact version {ontology.version} is older than the "
            f"version {stamped} stamped in the graph"
        )
