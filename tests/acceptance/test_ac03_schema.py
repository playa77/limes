# tests/acceptance/test_ac03_schema.py | v1.0.0 | introduced by WP-39
"""AC-03: schema provisioning is idempotent — running it twice produces no
error and no duplicate index, against the real container.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from limes.graph.driver import GraphDriver
from limes.graph.schema import provision
from limes.ontology.registry import load_ontology
from tests.fixtures.graph_data import wipe_graph
from tests.integration.conftest import Neo4jInstance

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"

INDEX_COUNT = "SHOW INDEXES YIELD name RETURN count(*) AS c"


@pytest.fixture(scope="module", autouse=True)
def _fresh_graph(neo4j_instance: Neo4jInstance):
    wipe_graph(neo4j_instance)
    yield


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


def test_ac03_provisioning_twice_is_idempotent(driver: GraphDriver):
    ontology = load_ontology(ONTOLOGY_PATH)
    provision(driver, ontology, embedding_dimensions=1024)
    first = int(driver.read(INDEX_COUNT, {}, 60)[0]["c"])

    # A second provisioning run produces no error and no duplicate index.
    provision(driver, ontology, embedding_dimensions=1024)
    second = int(driver.read(INDEX_COUNT, {}, 60)[0]["c"])

    assert first == second
    assert first > 0
