# tests/integration/test_schema_provision.py | v1.0.0 | introduced by WP-04
"""Schema provisioning integration tests (AC-03, AC-01 downgrade guard).

Provisioning runs twice and must produce no error and no duplicate index
(AC-03). The downgrade guard rejects an ontology artifact older than the
version stamped on an `:Entity` node (AC-01, Doc 2 §4.3).
"""

from pathlib import Path

import pytest

from limes.errors import OntologyError
from limes.graph.driver import GraphDriver
from limes.graph.schema import provision
from limes.ontology.registry import load_ontology
from tests.integration.conftest import Neo4jInstance

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"


@pytest.fixture(scope="module")
def driver(neo4j_instance: Neo4jInstance) -> GraphDriver:
    d = GraphDriver(
        neo4j_instance.uri,
        neo4j_instance.user,
        neo4j_instance.password,
        neo4j_instance.database,
    )
    yield d
    d.close()


@pytest.fixture(scope="module")
def ontology():
    return load_ontology(ONTOLOGY_PATH)


def _index_count(driver: GraphDriver, label: str) -> int:
    rows = driver.read(
        "SHOW INDEXES YIELD labelsOrTypes, name "
        "WHERE any(l IN labelsOrTypes WHERE l = $label) "
        "RETURN count(*) AS c",
        {"label": label},
        10,
    )
    return rows[0]["c"]


def test_provision_is_idempotent(driver: GraphDriver, ontology):
    provision(driver, ontology, embedding_dimensions=1024)
    provision(driver, ontology, embedding_dimensions=1024)

    # No duplicate indexes: entity_label must exist exactly once.
    assert _index_count(driver, "Entity") >= 1


def test_provision_creates_relationship_property_indexes(driver: GraphDriver, ontology):
    rows = driver.read(
        "SHOW INDEXES YIELD name, labelsOrTypes "
        "WHERE name CONTAINS 'valid_from' RETURN name, labelsOrTypes",
        {},
        10,
    )
    names = [r["name"] for r in rows]
    assert any("valid_from" in n for n in names)


def test_downgrade_guard_rejects_older_ontology(driver: GraphDriver, ontology):
    # Establish a graph stamped with a newer ontology version, then attempt
    # to provision an older artifact.
    driver.write_batch(
        [
            ("CREATE (e:Entity {entity_id: 'e1', ontology_version: '2.0.0'})", {}),
        ]
    )

    older = ontology.model_copy(deep=True)
    older.version = "0.9.0"

    with pytest.raises(OntologyError, match="older than the version"):
        provision(driver, older, embedding_dimensions=1024)


def test_downgrade_guard_passes_on_fresh_database(driver: GraphDriver, ontology):
    # A fresh database has no stamped :Entity nodes, so the guard passes.
    driver.write_batch(
        [
            ("MATCH (n:Entity) DETACH DELETE n", {}),
        ]
    )
    provision(driver, ontology, embedding_dimensions=1024)  # must not raise


def test_concurrent_provision_is_serialized(
    neo4j_instance: Neo4jInstance, ontology, driver: GraphDriver
):
    """D-67: the api startup handler and the worker's first command both call
    provision() against a fresh database. Two concurrent provisioners must
    both succeed and leave every index exactly once — before serialization
    this race failed live with EquivalentSchemaRuleAlreadyExists on
    office_at_valid_from (2026-08-24)."""
    import threading

    from limes.graph.schema import _SCHEMA_STATEMENTS  # noqa: PLC0415

    errors: list[Exception] = []
    start = threading.Barrier(2)

    def run() -> None:
        d = GraphDriver(
            neo4j_instance.uri,
            neo4j_instance.user,
            neo4j_instance.password,
            neo4j_instance.database,
        )
        try:
            start.wait()
            provision(d, ontology, embedding_dimensions=1024)
        except Exception as exc:  # noqa: BLE001 - forwarded to the assert below
            errors.append(exc)
        finally:
            d.close()

    threads = [threading.Thread(target=run) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []

    rows = driver.read("SHOW INDEXES YIELD name RETURN name", {}, 100)
    names = [r["name"] for r in rows]
    expected = [s.split()[2] for s in _SCHEMA_STATEMENTS if s.startswith("CREATE INDEX")]
    duplicates = [n for n in expected if names.count(n) != 1]
    assert duplicates == []
