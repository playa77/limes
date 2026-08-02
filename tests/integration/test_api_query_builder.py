# tests/integration/test_api_query_builder.py | v1.0.0 | introduced by WP-35
"""`POST /query/builder` per Doc 2 §6: a structured spec executes through
the same validation, plan gate, and annotation path as operator Cypher,
and an invalid spec is rejected precisely (AC-24) — 400 with a message
naming the hop and the violation."""

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


def test_query_builder_executes_valid_spec(
    neo4j_instance: Neo4jInstance, tmp_path: Path, seeded: None
):
    spec = {
        "start_type": "Corporation",
        "start_filters": {"lei": "LEI-ALPHA"},
        "hops": [
            {
                "relation": "SUBSIDIARY_OF",
                "direction": "out",
                "target_type": "Corporation",
            }
        ],
    }
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.post("/query/builder", json=spec)
        assert response.status_code == 200
        body = response.json()
        assert "MATCH (n0:Corporation {lei: $n0_lei})" in body["cypher"]
        assert body["results"]["counts"]["rows"] == 1
        assert body["coverage"]["relation_counts"] == {"SUBSIDIARY_OF": 1}
        assert body["diagnosis"] is None


def test_query_builder_inbound_hop(neo4j_instance: Neo4jInstance, tmp_path: Path, seeded: None):
    spec = {
        "start_type": "Corporation",
        "start_filters": {"lei": "LEI-ALPHA"},
        "hops": [
            {
                "relation": "DIRECTOR_OF",
                "direction": "in",
                "target_type": "Person",
            }
        ],
    }
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.post("/query/builder", json=spec)
        assert response.status_code == 200
        body = response.json()
        assert body["results"]["counts"]["rows"] == 1
        types = {node["type"] for node in body["results"]["nodes"]}
        assert types == {"Corporation", "Person"}


def test_ac24_invalid_spec_rejected_precisely(
    neo4j_instance: Neo4jInstance, tmp_path: Path, seeded: None
):
    spec = {
        "start_type": "Corporation",
        "hops": [
            {
                "relation": "DIRECTOR_OF",
                "direction": "out",
                "target_type": "Corporation",
            }
        ],
    }
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.post("/query/builder", json=spec)
        assert response.status_code == 400
        error = response.json()["error"]
        assert error["code"] == "BUILDER_INVALID_SPEC"
        assert "DIRECTOR_OF" in error["message"]
        assert "subject" in error["message"]


def test_query_builder_temporal_qualifier_on_nontemporal_rejected(
    neo4j_instance: Neo4jInstance, tmp_path: Path, seeded: None
):
    spec = {
        "start_type": "LegalAct",
        "hops": [
            {
                "relation": "CITES",
                "direction": "out",
                "target_type": "LegalAct",
                "temporal_qualifier": "current",
            }
        ],
    }
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.post("/query/builder", json=spec)
        assert response.status_code == 400
        assert "non-temporal" in response.json()["error"]["message"]
