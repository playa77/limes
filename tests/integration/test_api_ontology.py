# tests/integration/test_api_ontology.py | v1.0.0 | introduced by WP-32
"""`GET /ontology`, `GET /ontology/versions`, and `GET /builder/schema` per
Doc 2 §6: the full serialized ontology, the versions stamped in the graph,
and the runtime-rendered builder projection (FR-09, NG-08)."""

from pathlib import Path

from tests.fixtures.graph_data import load_corporation_graph, make_api_client
from tests.integration.conftest import Neo4jInstance


def test_ontology_returns_full_serialized_ontology(neo4j_instance: Neo4jInstance, tmp_path: Path):
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.get("/ontology")
        assert response.status_code == 200
        body = response.json()
        assert body["version"] == "1.0.0"
        assert len(body["entity_types"]) == 17
        assert len(body["relation_types"]) == 30
        assert "Corporation" in body["entity_types"]
        assert "DIRECTOR_OF" in body["relation_types"]
        assert response.headers["X-LIMES-Ontology-Version"] == "1.0.0"


def test_ontology_versions_reports_graph_versions(neo4j_instance: Neo4jInstance, tmp_path: Path):
    from tests.fixtures.graph_data import load_ontology_artifact, make_driver

    driver = make_driver(neo4j_instance)
    ontology = load_ontology_artifact()
    load_corporation_graph(driver, ontology)
    driver.close()

    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.get("/ontology/versions")
        assert response.status_code == 200
        versions = {entry["version"]: entry["count"] for entry in response.json()}
        assert versions.get("1.0.0", 0) >= 4  # alpha, beta, hq, boss


def test_builder_schema_is_rendered_from_ontology(neo4j_instance: Neo4jInstance, tmp_path: Path):
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.get("/builder/schema")
        assert response.status_code == 200
        body = response.json()
        corporation = next(
            entry for entry in body["entity_types"] if entry["name"] == "Corporation"
        )
        property_names = {p["name"] for p in corporation["properties"]}
        assert {"label", "lei", "legal_form"} <= property_names
        directorship = next(
            entry for entry in body["relation_types"] if entry["name"] == "DIRECTOR_OF"
        )
        assert directorship["domain"] == ["Person"]
        assert directorship["range"] == ["Corporation"]
