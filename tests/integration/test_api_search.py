# tests/integration/test_api_search.py | v1.0.0 | introduced by WP-32
"""`GET /search` per Doc 2 §6: full-text over the `entity_names` index
(production-loaded entities). The `document_text` path runs without error;
no production path stamps `title`/`body` on `:Document` nodes (the loader
stamps label/aliases only), so the document side has nothing to match by
construction — asserted as empty, not fabricated."""

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
def ids(neo4j_instance: Neo4jInstance) -> dict[str, str]:
    driver = make_driver(neo4j_instance)
    ontology = load_ontology_artifact()
    result = load_corporation_graph(driver, ontology)
    driver.close()
    return result


def test_search_finds_entities_by_label(
    neo4j_instance: Neo4jInstance, tmp_path: Path, ids: dict[str, str]
):
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.get("/search", params={"q": "alpha"})
        assert response.status_code == 200
        hits = response.json()
        assert any(hit["kind"] == "entity" and hit["id"] == ids["alpha"] for hit in hits)
        assert all(hit["score"] > 0 for hit in hits)


def test_search_finds_entities_by_alias(
    neo4j_instance: Neo4jInstance, tmp_path: Path, ids: dict[str, str]
):
    # The loader stamps aliases; the entity_names index covers them.
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.get("/search", params={"q": "alias-corp-beta"})
        hits = response.json()
        assert any(hit["id"] == ids["beta"] for hit in hits)


def test_search_kind_filter_entity(neo4j_instance: Neo4jInstance, tmp_path: Path):
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.get("/search", params={"q": "alpha", "kind": "entity"})
        assert all(hit["kind"] == "entity" for hit in response.json())


def test_search_document_kind_returns_empty_without_error(
    neo4j_instance: Neo4jInstance, tmp_path: Path
):
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.get("/search", params={"q": "alpha", "kind": "document"})
        assert response.status_code == 200
        assert response.json() == []


def test_search_no_match_returns_empty(neo4j_instance: Neo4jInstance, tmp_path: Path):
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.get("/search", params={"q": "zzz-nonexistent-zzz"})
        assert response.status_code == 200
        assert response.json() == []
