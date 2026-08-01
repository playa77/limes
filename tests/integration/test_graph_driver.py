# tests/integration/test_graph_driver.py | v1.0.0 | introduced by WP-04
"""GraphDriver integration tests against a disposable Neo4j container.

Covers the §8.3 contract: read access mode refuses writes client-side,
`write_batch` runs one transaction, and `explain` parses a PlanSummary.
"""

import pytest
from neo4j.exceptions import Neo4jError

from limes.errors import GraphWriteError
from limes.graph.driver import GraphDriver
from limes.types import PlanSummary
from tests.integration.conftest import Neo4jInstance


@pytest.fixture
def driver(neo4j_instance: Neo4jInstance) -> GraphDriver:
    d = GraphDriver(
        neo4j_instance.uri,
        neo4j_instance.user,
        neo4j_instance.password,
        neo4j_instance.database,
    )
    yield d
    d.close()


def test_read_returns_rows_as_dicts(driver: GraphDriver):
    driver.write_batch(
        [
            ("CREATE (n:TestNode {id: $id})", {"id": "x1"}),
        ]
    )
    rows = driver.read("MATCH (n:TestNode) RETURN n.id AS id", {}, 10)
    assert {"id": "x1"} in rows


def test_read_mode_refuses_write_statement(driver: GraphDriver):
    with pytest.raises(Neo4jError):
        driver.read("CREATE (n:TestNode {id: 'should-not-exist'})", {}, 10)


def test_write_batch_executes_multiple_statements_in_one_transaction(
    driver: GraphDriver,
):
    result = driver.write_batch(
        [
            ("CREATE (a:TestNode {id: 'a'})", {}),
            ("CREATE (b:TestNode {id: 'b'})", {}),
            ("MATCH (a:TestNode {id: 'a'}), (b:TestNode {id: 'b'}) CREATE (a)-[:LINKED]->(b)", {}),
        ]
    )
    assert result.statements_executed == 3
    assert result.nodes_created == 2
    assert result.relationships_created == 1


def test_write_batch_rolls_back_on_failure(driver: GraphDriver):
    # A statement-level failure surfaces as GraphWriteError (Doc 2 §11: never
    # retried more than once) and the whole transaction is rolled back.
    with pytest.raises(GraphWriteError):
        driver.write_batch(
            [
                ("CREATE (a:TestNode {id: 'rollback-a'})", {}),
                ("CREATE (b:TestNode {id: 'rollback-b'})", {}),
                ("THIS IS NOT CYPHER", {}),
            ]
        )
    rows = driver.read(
        "MATCH (n:TestNode) WHERE n.id STARTS WITH 'rollback-' RETURN count(n) AS c", {}, 10
    )
    assert rows[0]["c"] == 0


def test_explain_returns_plansummary(driver: GraphDriver):
    driver.write_batch(
        [
            ("CREATE (n:TestNode {id: 'x'})", {}),
        ]
    )
    summary: PlanSummary = driver.explain("MATCH (n:TestNode) WHERE n.id = 'x' RETURN n", {})
    assert isinstance(summary, PlanSummary)
    assert summary.operators
    assert summary.max_estimated_rows >= 0
    assert summary.total_estimated_rows >= 0
    assert summary.has_cartesian_product is False
