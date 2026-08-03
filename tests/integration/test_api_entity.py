# tests/integration/test_api_entity.py | v1.0.0 | introduced by WP-32
"""`GET /entity/{id}` and `GET /entity/{id}/neighbors` per Doc 2 §6: entity
with properties and edge summary, one-hop expansion with relation and
temporal filters, 404 for unknown ids. Graph state is produced by the
loader (production path)."""

from pathlib import Path

import pytest

from tests.fixtures.graph_data import (
    load_closed_interval_graph,
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
def ids(neo4j_instance: Neo4jInstance) -> dict[str, str]:
    driver = make_driver(neo4j_instance)
    ontology = load_ontology_artifact()
    result = load_corporation_graph(driver, ontology)
    driver.close()
    return result


def test_entity_returns_properties_and_edge_summary(
    neo4j_instance: Neo4jInstance, tmp_path: Path, ids: dict[str, str]
):
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.get(f"/entity/{ids['alpha']}")
        assert response.status_code == 200
        body = response.json()
        entity = body["entity"]
        assert entity["entity_id"] == ids["alpha"]
        assert entity["type"] == "Corporation"
        assert entity["label"] == "Alpha Industries"
        assert entity["properties"]["lei"] == "LEI-ALPHA"
        assert entity["ontology_version"] == "1.0.0"
        summary = body["edge_summary"]
        assert summary["out"]["SUBSIDIARY_OF"] == 1
        assert summary["out"]["HEADQUARTERED_IN"] == 1
        assert summary["in"]["DIRECTOR_OF"] == 1


def test_entity_unknown_id_returns_404(neo4j_instance: Neo4jInstance, tmp_path: Path):
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.get("/entity/does-not-exist")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "ENTITY_NOT_FOUND"


def test_neighbors_one_hop_with_provenance(
    neo4j_instance: Neo4jInstance, tmp_path: Path, ids: dict[str, str]
):
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.get(f"/entity/{ids['alpha']}/neighbors")
        assert response.status_code == 200
        body = response.json()
        assert body["entity"]["entity_id"] == ids["alpha"]
        neighbors = {entry["neighbor"]["entity_id"] for entry in body["neighbors"]}
        assert neighbors == {ids["beta"], ids["hq"], ids["boss"]}
        # AC-28 (partial): the edge carries full provenance.
        directorship = next(
            entry for entry in body["neighbors"] if entry["edge"]["relation"] == "DIRECTOR_OF"
        )
        assert directorship["edge"]["source_id"] == "test-source"
        assert directorship["edge"]["assertion_id"] == "a3"


def test_neighbors_relation_filter(
    neo4j_instance: Neo4jInstance, tmp_path: Path, ids: dict[str, str]
):
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.get(
            f"/entity/{ids['alpha']}/neighbors", params={"relation": "SUBSIDIARY_OF"}
        )
        body = response.json()
        relations = {entry["edge"]["relation"] for entry in body["neighbors"]}
        assert relations == {"SUBSIDIARY_OF"}
        assert [entry["neighbor"]["entity_id"] for entry in body["neighbors"]] == [ids["beta"]]


def test_neighbors_as_of_temporal_filter(neo4j_instance: Neo4jInstance, tmp_path: Path):
    driver = make_driver(neo4j_instance)
    ontology = load_ontology_artifact()
    interval_ids = load_closed_interval_graph(driver, ontology)
    driver.close()

    with make_api_client(neo4j_instance, tmp_path) as client:
        # As of 2019 the 2018-2020 interval is current...
        response = client.get(
            f"/entity/{interval_ids['alpha']}/neighbors",
            params={"as_of": "2019-06-01T00:00:00Z"},
        )
        body = response.json()
        edges = [
            entry["edge"]
            for entry in body["neighbors"]
            if entry["edge"]["relation"] == "SUBSIDIARY_OF"
        ]
        assert len(edges) == 1
        assert edges[0]["valid_to"].startswith("2020")

        # ...and as of 2022 only the open interval remains.
        response = client.get(
            f"/entity/{interval_ids['alpha']}/neighbors",
            params={"as_of": "2022-06-01T00:00:00Z"},
        )
        body = response.json()
        edges = [
            entry["edge"]
            for entry in body["neighbors"]
            if entry["edge"]["relation"] == "SUBSIDIARY_OF"
        ]
        assert len(edges) == 1
        assert edges[0]["valid_to"] is None


def test_neighbors_believed_temporal_filter(
    neo4j_instance: Neo4jInstance, tmp_path: Path, ids: dict[str, str]
):
    # The belief instant restricts to relationships the graph knew by then;
    # a far-future instant admits everything the entity currently has.
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.get(
            f"/entity/{ids['alpha']}/neighbors",
            params={"believed": "2099-01-01T00:00:00Z"},
        )
        assert response.status_code == 200
        body = response.json()
        neighbors = {entry["neighbor"]["entity_id"] for entry in body["neighbors"]}
        assert neighbors == {ids["beta"], ids["hq"], ids["boss"]}


def test_neighbors_unknown_entity_returns_404(neo4j_instance: Neo4jInstance, tmp_path: Path):
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.get("/entity/does-not-exist/neighbors")
        assert response.status_code == 404
