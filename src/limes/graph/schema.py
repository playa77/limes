# src/limes/graph/schema.py | v1.0.0 | introduced by WP-04
"""Idempotent Neo4j schema provisioning per Technical Specification §5.3.

`provision` executes every constraint and index from §5.3 with `IF NOT
EXISTS`, so running twice produces no error and no duplicate index (AC-03).
Relationship-property indexes on `valid_from`, `valid_to`, `recorded_at` are
generated from the ontology for every `temporal: true` relation. It also
applies the ontology downgrade guard of §4.3: when the graph already carries
`:Entity` nodes stamped with a newer ontology version than the artifact,
provisioning raises `OntologyError` and startup fails (AC-01).
"""

from __future__ import annotations

from neo4j import Driver

from limes.errors import OntologyError
from limes.graph.driver import GraphDriver
from limes.ontology.model import Ontology

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
    """Provision constraints and indexes idempotently, and apply the ontology
    downgrade guard. Called by the composition root on every context build.

    One statement per transaction: Neo4j compiles schema changes in bounded
    windows and fails a single transaction that issues many of them with
    "Could not compile query due to insanely frequent schema changes". Each
    statement is idempotent (`IF NOT EXISTS`), so a partially provisioned
    database is never an error on the next run."""
    _check_ontology_version(driver._driver, ontology)

    statements = list(_SCHEMA_STATEMENTS)
    statements.append(_VECTOR_INDEX_TEMPLATE.format(dims=embedding_dimensions))
    statements.extend(_relationship_property_indexes(ontology))
    for statement in statements:
        driver.write_batch([(statement, {})])


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
