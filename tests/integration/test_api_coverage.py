# tests/integration/test_api_coverage.py | v1.0.0 | introduced by WP-35
"""`POST /coverage` per Doc 2 §6: a coverage report for a relation set or
for a query (its relation types extracted by the parser), 400 when
neither is supplied."""

from pathlib import Path

import pytest

from tests.fixtures.graph_data import (
    load_corporation_graph,
    load_ontology_artifact,
    make_api_client,
    make_driver,
)
from tests.integration.conftest import Neo4jInstance


@pytest.fixture(scope="module")
def seeded(neo4j_instance: Neo4jInstance) -> None:
    driver = make_driver(neo4j_instance)
    ontology = load_ontology_artifact()
    load_corporation_graph(driver, ontology)
    driver.close()


def test_coverage_by_relation_set(neo4j_instance: Neo4jInstance, tmp_path: Path, seeded: None):
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.post(
            "/coverage", json={"relation_types": ["SUBSIDIARY_OF", "DIRECTOR_OF"]}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["relation_counts"] == {"SUBSIDIARY_OF": 1, "DIRECTOR_OF": 1}
        assert body["contributing_sources"] == ["test-source"]


def test_coverage_by_query(neo4j_instance: Neo4jInstance, tmp_path: Path, seeded: None):
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.post(
            "/coverage",
            json={
                "query": "MATCH (a:Corporation)-[:SUBSIDIARY_OF]->(b) RETURN b",
                "params": {},
            },
        )
        assert response.status_code == 200
        assert response.json()["relation_counts"] == {"SUBSIDIARY_OF": 1}


def test_coverage_neither_input_is_400(neo4j_instance: Neo4jInstance, tmp_path: Path, seeded: None):
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.post("/coverage", json={})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "COVERAGE_REQUEST_INVALID"
