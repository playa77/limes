# tests/integration/test_api_query_nl.py | v1.0.0 | introduced by WP-35
"""`POST /query/nl` per Doc 2 §6 and §15.3 Trace 3: the four-stage service
behind the endpoint, with coverage attached, diagnosis on empty results,
and every executed query persisted as a `:SavedQuery` (FR-14, AC-30). The
paid-inference client is stubbed via the application's `NlqContext` — the
composition-root seam — so no live call, no ledger write."""

from pathlib import Path

import pytest

from tests.fixtures.graph_data import (
    load_corporation_graph,
    load_ontology_artifact,
    make_driver,
    wipe_graph,
)
from tests.integration.conftest import Neo4jInstance


class StubClient:
    def __init__(self) -> None:
        self.replies: list[str] = []
        self.calls: int = 0

    def complete(self, messages, model_id, purpose, json_schema=None):
        self.calls += 1
        return self.replies.pop(0), 10, 5

    def embed(self, texts, model_id):
        raise AssertionError("no embedding on the query path")


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


def _stub_client(monkeypatch: pytest.MonkeyPatch, client: StubClient) -> None:
    """Replace the `NlqContext` the API builds with one carrying the stub
    client — the dependency-injection seam, exercised through
    `api/deps.py`."""
    from limes.api import deps
    from limes.composition import NlqContext

    original = deps.build_nlq_context

    def _stubbed(settings, ontology, driver):
        ctx = original(settings, ontology, driver)
        return NlqContext(
            settings=ctx.settings,
            ontology=ctx.ontology,
            driver=ctx.driver,
            client=client,
            recorder=ctx.recorder,
        )

    monkeypatch.setattr(deps, "build_nlq_context", _stubbed)


def _clear_saved_queries(client) -> None:
    """Reset the self-accreting library via the API's own delete endpoint —
    the production path — so tests are independent of the shared
    container's order."""
    for entry in client.get("/saved-queries").json():
        response = client.delete(f"/saved-queries/{entry['saved_query_id']}")
        assert response.status_code == 200


def test_query_nl_runs_trace_3_end_to_end(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    seeded: None,
    monkeypatch: pytest.MonkeyPatch,
):
    from tests.fixtures.graph_data import make_api_client

    client = StubClient()
    client.replies = ["MATCH (a:Corporation {lei: 'LEI-ALPHA'})-[:SUBSIDIARY_OF]->(b) RETURN a, b"]
    _stub_client(monkeypatch, client)

    with make_api_client(neo4j_instance, tmp_path) as api:
        _clear_saved_queries(api)
        response = api.post("/query/nl", json={"question": "What does Alpha own?"})
        assert response.status_code == 200
        body = response.json()
        assert client.calls == 1
        assert body["question"] == "What does Alpha own?"
        assert "LIMIT" in body["cypher"]  # editable, bounded (AC-26)
        assert body["validation_errors"] == []
        assert body["results"]["counts"]["rows"] == 1
        assert body["coverage"]["relation_counts"] == {"SUBSIDIARY_OF": 1}
        assert body["diagnosis"] is None
        assert response.headers["X-LIMES-Ontology-Version"] == "1.0.0"

        # AC-30: the executed query is persisted with question, Cypher,
        # ontology version, and result count.
        saved = api.get("/saved-queries").json()
        assert len(saved) == 1
        assert saved[0]["question"] == "What does Alpha own?"
        assert saved[0]["cypher"] == body["cypher"]
        assert saved[0]["ontology_version"] == "1.0.0"
        assert saved[0]["result_count"] == 1


def test_query_nl_validation_failure_persists_nothing(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    seeded: None,
    monkeypatch: pytest.MonkeyPatch,
):
    from tests.fixtures.graph_data import make_api_client

    client = StubClient()
    client.replies = ["MATCH (a:NotAType) RETURN a", "CREATE (x:Corporation)"]
    _stub_client(monkeypatch, client)

    with make_api_client(neo4j_instance, tmp_path) as api:
        _clear_saved_queries(api)
        response = api.post("/query/nl", json={"question": "Who?"})
        assert response.status_code == 200
        body = response.json()
        assert body["results"] is None
        # The final attempt's errors are reported (the regeneration
        # replaced the first attempt's UNKNOWN_LABEL with its WRITE_CLAUSE).
        assert any("WRITE_CLAUSE" in error for error in body["validation_errors"])
        assert body["coverage"] is None
        assert api.get("/saved-queries").json() == []


def test_query_nl_empty_result_attaches_diagnosis(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    seeded: None,
    monkeypatch: pytest.MonkeyPatch,
):
    from tests.fixtures.graph_data import make_api_client

    client = StubClient()
    client.replies = ["MATCH (a:Corporation {lei: 'LEI-NOPE'}) RETURN a"]
    _stub_client(monkeypatch, client)

    with make_api_client(neo4j_instance, tmp_path) as api:
        _clear_saved_queries(api)
        response = api.post("/query/nl", json={"question": "Who is missing?"})
        assert response.status_code == 200
        body = response.json()
        assert body["results"]["counts"]["rows"] == 0
        assert body["diagnosis"] is not None
        assert body["diagnosis"]["clause_index"] == 0
        # An executed (empty) query is still persisted with its result
        # count of zero — the newest entry of the library.
        saved = api.get("/saved-queries").json()
        assert saved[0]["result_count"] == 0
        assert saved[0]["question"] == "Who is missing?"
