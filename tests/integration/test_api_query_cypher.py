# tests/integration/test_api_query_cypher.py | v1.0.0 | introduced by WP-35
"""`POST /query/cypher` per Doc 2 §6: operator-supplied Cypher is
deterministically validated (400 on rejection), plan-gated (422), executed
read-only, and annotated with coverage and empty-result diagnosis."""

from pathlib import Path

import pytest

from tests.fixtures.graph_data import (
    load_corporation_graph,
    load_ontology_artifact,
    make_api_client,
    make_driver,
    wipe_graph,
)
from tests.integration.conftest import Neo4jInstance


@pytest.fixture(scope="module", autouse=True)
def _fresh_graph(neo4j_instance: Neo4jInstance):
    """Reset the shared session container before this module runs, so the
    module's absolute-count assertions are independent of earlier modules
    (the sanctioned fixture teardown)."""
    wipe_graph(neo4j_instance)
    yield


@pytest.fixture(scope="module")
def seeded(neo4j_instance: Neo4jInstance) -> None:
    driver = make_driver(neo4j_instance)
    ontology = load_ontology_artifact()
    load_corporation_graph(driver, ontology)
    driver.close()


def test_query_cypher_executes_and_attaches_coverage(
    neo4j_instance: Neo4jInstance, tmp_path: Path, seeded: None
):
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.post(
            "/query/cypher",
            json={"cypher": "MATCH (a:Corporation)-[:SUBSIDIARY_OF]->(b) RETURN a, b"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["cypher"].endswith("LIMIT 500")  # injected bound, editable
        assert body["results"]["counts"]["rows"] == 1
        labels = {node["label"] for node in body["results"]["nodes"]}
        assert labels == {"Alpha Industries", "Beta GmbH"}
        assert body["coverage"]["relation_counts"] == {"SUBSIDIARY_OF": 1}
        assert body["coverage"]["contributing_sources"] == ["test-source"]
        assert body["diagnosis"] is None


def test_query_cypher_params_travel_as_parameters(
    neo4j_instance: Neo4jInstance, tmp_path: Path, seeded: None
):
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.post(
            "/query/cypher",
            json={
                "cypher": "MATCH (a:Corporation {lei: $lei}) RETURN a",
                "params": {"lei": "LEI-ALPHA"},
            },
        )
        assert response.status_code == 200
        assert response.json()["results"]["counts"]["rows"] == 1


def test_query_cypher_write_attempt_is_rejected_400(
    neo4j_instance: Neo4jInstance, tmp_path: Path, seeded: None
):
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.post(
            "/query/cypher",
            json={"cypher": "MATCH (a:Corporation) DELETE a"},
        )
        assert response.status_code == 400
        error = response.json()["error"]
        assert error["code"] == "CYPHER_VALIDATION_FAILED"
        assert "WRITE_CLAUSE" in error["message"]


def test_query_cypher_plan_rejection_is_422(
    neo4j_instance: Neo4jInstance, tmp_path: Path, seeded: None
):
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.post(
            "/query/cypher",
            json={"cypher": "MATCH (a) MATCH (b) RETURN a, b"},
        )
        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "QUERY_PLAN_REJECTED"
        assert "CARTESIAN_PRODUCT" in error["message"]


def test_query_cypher_empty_result_produces_diagnosis(
    neo4j_instance: Neo4jInstance, tmp_path: Path, seeded: None
):
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.post(
            "/query/cypher",
            json={
                "cypher": (
                    "MATCH (a:Corporation {lei: 'LEI-ALPHA'}) "
                    "MATCH (a)-[:SUBSIDIARY_OF]->(b:Corporation {lei: 'LEI-NOPE'}) "
                    "RETURN b"
                )
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["results"]["counts"]["rows"] == 0
        diagnosis = body["diagnosis"]
        assert diagnosis is not None
        assert diagnosis["clause_index"] == 1
        assert diagnosis["relation_counts"] == {"SUBSIDIARY_OF": 1}
        assert response.headers["X-LIMES-Ontology-Version"] == "1.3.0"
