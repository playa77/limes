# tests/integration/test_api_saved_queries.py | v1.0.0 | introduced by WP-35
"""`GET/POST/DELETE /saved-queries` per Doc 2 §6 and §7.3: the
self-accreting query library, with 409 on duplicate (question, cypher)
pairs and 404 on unknown ids. The writes are two of the API's three
enumerated write paths."""

from pathlib import Path

import pytest

from tests.fixtures.graph_data import make_api_client, wipe_graph
from tests.integration.conftest import Neo4jInstance


@pytest.fixture(scope="module", autouse=True)
def _fresh_graph(neo4j_instance: Neo4jInstance):
    """Reset the shared session container before this module runs, so the
    module's absolute-count assertions are independent of earlier modules
    (the sanctioned fixture teardown)."""
    wipe_graph(neo4j_instance)
    yield


def test_saved_queries_crud_cycle(neo4j_instance: Neo4jInstance, tmp_path: Path):
    with make_api_client(neo4j_instance, tmp_path) as client:
        created = client.post(
            "/saved-queries",
            json={
                "question": "Who owns Alpha?",
                "cypher": "MATCH (a:Corporation) RETURN a LIMIT 10",
                "result_count": 3,
            },
        )
        assert created.status_code == 200
        saved_query_id = created.json()["saved_query_id"]
        assert saved_query_id

        listed = client.get("/saved-queries").json()
        assert len(listed) == 1
        assert listed[0]["saved_query_id"] == saved_query_id
        assert listed[0]["question"] == "Who owns Alpha?"
        assert listed[0]["result_count"] == 3
        assert listed[0]["ontology_version"] == "1.1.0"

        deleted = client.delete(f"/saved-queries/{saved_query_id}")
        assert deleted.status_code == 200
        assert client.get("/saved-queries").json() == []


def test_saved_queries_duplicate_is_409(neo4j_instance: Neo4jInstance, tmp_path: Path):
    payload = {
        "question": "Same question",
        "cypher": "MATCH (n) RETURN n LIMIT 1",
    }
    with make_api_client(neo4j_instance, tmp_path) as client:
        assert client.post("/saved-queries", json=payload).status_code == 200
        duplicate = client.post("/saved-queries", json=payload)
        assert duplicate.status_code == 409
        assert duplicate.json()["error"]["code"] == "DUPLICATE_SAVED_QUERY"

        # A different question with the same Cypher is not a duplicate.
        other = client.post(
            "/saved-queries",
            json={
                "question": "Different question",
                "cypher": payload["cypher"],
            },
        )
        assert other.status_code == 200


def test_saved_queries_delete_unknown_is_404(neo4j_instance: Neo4jInstance, tmp_path: Path):
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.delete("/saved-queries/does-not-exist")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "SAVED_QUERY_NOT_FOUND"
