"""Unit: ApiClient request handling — parsing, error mapping. FR-DC-002."""

import httpx
import pytest
import respx
from limes_desktop.api.client import ApiClient
from limes_desktop.api.errors import ApiError, ApiUnreachable

# Fixtures mirror the real router response shapes (src/limes/api/routers/).
_GraphResultJSON = {
    "nodes": [
        {
            "entity_id": "e1",
            "type": "Organization",
            "label": "ACME",
            "properties": {"country": "DE"},
            "ontology_version": "1.0.0",
            "created_at": "2026-01-01T00:00:00Z",
        }
    ],
    "edges": [
        {
            "relation": "LOCATED_IN",
            "subject_id": "e1",
            "object_id": "e2",
            "source_id": "gleif",
            "confidence": 0.99,
        }
    ],
    "counts": {"rows": 1, "nodes": 1, "edges": 1},
}

_QueryResponseJSON = {
    "cypher": "MATCH (n) RETURN n",
    "results": _GraphResultJSON,
    "coverage": {"relation_counts": {}, "contributing_sources": [], "source_refresh": {}},
    "diagnosis": None,
    "notes": [],
}


@respx.mock
def test_health_parses_payload() -> None:
    respx.get("http://x.test/health").mock(
        return_value=httpx.Response(
            200, json={"status": "ok", "neo4j": True, "ontology_version": "1.0.0"}
        )
    )
    info = ApiClient("http://x.test").health()
    assert info.status == "ok" and info.ontology_version == "1.0.0"


@respx.mock
def test_search_parses_hits() -> None:
    respx.get("http://x.test/search").mock(
        return_value=httpx.Response(
            200,
            json=[{"kind": "entity", "id": "e1", "label": "ACME", "score": 0.9}],
        )
    )
    hits = ApiClient("http://x.test").search("acme")
    assert hits[0].id == "e1" and hits[0].kind == "entity"


@respx.mock
def test_query_cypher_parses_outcome() -> None:
    respx.post("http://x.test/query/cypher").mock(
        return_value=httpx.Response(200, json=_QueryResponseJSON)
    )
    outcome = ApiClient("http://x.test").query_cypher("MATCH (n) RETURN n")
    assert outcome.cypher == "MATCH (n) RETURN n"
    assert outcome.results is not None
    assert outcome.results.nodes[0].entity_id == "e1"
    assert outcome.results.edges[0].relation == "LOCATED_IN"
    assert outcome.coverage.relation_counts == {}


@respx.mock
def test_query_nl_parses_outcome_with_coverage() -> None:
    respx.post("http://x.test/query/nl").mock(
        return_value=httpx.Response(
            200,
            json={
                "question": "who is acme?",
                "cypher": "MATCH (n) RETURN n",
                "results": _GraphResultJSON,
                "validation_errors": [],
                "plan_rejection": None,
                "notes": [],
                "coverage": {
                    "relation_counts": {"LOCATED_IN": 3},
                    "contributing_sources": ["gleif"],
                    "source_refresh": {"gleif": "2026-01-02T00:00:00Z"},
                },
                "diagnosis": {
                    "failing_clause": "MATCH (n:Nothing)",
                    "clause_index": 0,
                    "relation_counts": {},
                    "note": "empty",
                },
            },
        )
    )
    outcome = ApiClient("http://x.test").query_nl("who is acme?")
    assert outcome.results is not None
    assert outcome.coverage.contributing_sources == ["gleif"]
    assert outcome.diagnosis is not None
    assert outcome.diagnosis.clause_index == 0


@respx.mock
def test_entity_parses_detail() -> None:
    respx.get("http://x.test/entity/e1").mock(
        return_value=httpx.Response(
            200,
            json={
                "entity": {
                    "entity_id": "e1",
                    "type": "Organization",
                    "label": "ACME",
                    "properties": {},
                    "ontology_version": "1.0.0",
                    "created_at": None,
                },
                "edge_summary": {"out": {"LOCATED_IN": 1}, "in": {}},
            },
        )
    )
    detail = ApiClient("http://x.test").entity("e1")
    assert detail.entity.entity_id == "e1"
    assert detail.edge_summary["out"]["LOCATED_IN"] == 1


@respx.mock
def test_entity_neighbors_parses_graph() -> None:
    respx.get("http://x.test/entity/e1/neighbors").mock(
        return_value=httpx.Response(
            200,
            json={
                "entity": {
                    "entity_id": "e1",
                    "type": "Organization",
                    "label": "ACME",
                    "properties": {},
                },
                "neighbors": [
                    {
                        "edge": {"relation": "LOCATED_IN", "subject_id": "e1", "object_id": "e2"},
                        "neighbor": {
                            "entity_id": "e2",
                            "type": "Place",
                            "label": "DE",
                            "properties": {},
                        },
                    }
                ],
            },
        )
    )
    result = ApiClient("http://x.test").entity_neighbors("e1")
    assert result.entity.entity_id == "e1"
    assert result.neighbors[0].neighbor.entity_id == "e2"


@respx.mock
def test_coverage_posts_request_body() -> None:
    route = respx.post("http://x.test/coverage").mock(
        return_value=httpx.Response(
            200,
            json={
                "relation_counts": {"ACTS_FOR": 2},
                "contributing_sources": [],
                "source_refresh": {},
            },
        )
    )
    report = ApiClient("http://x.test").coverage({"relation_types": ["ACTS_FOR"]})
    assert report.relation_counts == {"ACTS_FOR": 2}
    assert route.calls.last.request.read() == b'{"relation_types":["ACTS_FOR"]}'


@respx.mock
def test_saved_queries_round_trip() -> None:
    respx.get("http://x.test/saved-queries").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "saved_query_id": "abc",
                    "question": "q",
                    "cypher": "MATCH (n) RETURN n",
                    "ontology_version": "1.0.0",
                    "result_count": 1,
                    "created_at": "2026-01-01T00:00:00",
                    "pinned": False,
                }
            ],
        )
    )
    respx.post("http://x.test/saved-queries").mock(
        return_value=httpx.Response(200, json={"saved_query_id": "abc"})
    )
    respx.delete("http://x.test/saved-queries/abc").mock(
        return_value=httpx.Response(200, json={"deleted": "abc"})
    )
    client = ApiClient("http://x.test")
    saved = client.saved_queries()
    assert saved[0].saved_query_id == "abc"
    assert client.save_query("q", "cypher", {}) == "abc"
    assert client.delete_saved_query("abc") is None


@respx.mock
def test_cost_ledger_parses() -> None:
    respx.get("http://x.test/cost/ledger").mock(
        return_value=httpx.Response(
            200,
            json={
                "period": "2026-09",
                "spend_eur": 1.5,
                "remaining_eur": 8.5,
                "entries": [
                    {
                        "ledger_id": "l1",
                        "period": "2026-09",
                        "run_id": None,
                        "purpose": "extract",
                        "model_id": "m",
                        "input_tokens": 10,
                        "output_tokens": 20,
                        "cost_eur": 1.5,
                        "created_at": "2026-09-01T00:00:00",
                    }
                ],
            },
        )
    )
    ledger = ApiClient("http://x.test").cost_ledger()
    assert ledger.spend_eur == 1.5
    assert ledger.entries[0].model_id == "m"


@respx.mock
def test_ingest_status_parses() -> None:
    respx.get("http://x.test/ingest/status").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "source_id": "gleif",
                    "mode": "incremental",
                    "run_id": "r1",
                    "started_at": "2026-09-01T00:00:00",
                    "finished_at": None,
                    "records_fetched": 5,
                    "errors": 0,
                    "last_success_at": None,
                }
            ],
        )
    )
    runs = ApiClient("http://x.test").ingest_status()
    assert runs[0].run_id == "r1" and runs[0].records_fetched == 5


@respx.mock
def test_sources_and_ontology_versions() -> None:
    respx.get("http://x.test/sources").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "source_id": "gleif",
                    "name": "GLEIF",
                    "kind": "structured",
                    "trust_rank": 0.9,
                    "supports_backfill": True,
                    "supports_incremental": True,
                    "last_success_at": None,
                    "last_run_id": None,
                }
            ],
        )
    )
    respx.get("http://x.test/ontology/versions").mock(
        return_value=httpx.Response(
            200, json=[{"version": "1.0.0", "count": 42}]
        )
    )
    client = ApiClient("http://x.test")
    assert client.sources()[0].source_id == "gleif"
    assert client.ontology_versions() == ["1.0.0"]


@respx.mock
def test_redirect_followed_and_final_200_parsed() -> None:
    respx.get("http://x.test/health").mock(
        return_value=httpx.Response(
            307, headers={"Location": "http://x.test/health/v2"}
        )
    )
    respx.get("http://x.test/health/v2").mock(
        return_value=httpx.Response(
            200, json={"status": "ok", "neo4j": True, "ontology_version": "1.0.0"}
        )
    )
    info = ApiClient("http://x.test").health()
    assert info.status == "ok" and info.ontology_version == "1.0.0"


@respx.mock
def test_timeout_raises_api_unreachable() -> None:
    respx.get("http://x.test/health").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(ApiUnreachable):
        ApiClient("http://x.test").health()


@respx.mock
def test_unreachable_raises_api_unreachable() -> None:
    respx.get("http://x.test/health").mock(side_effect=httpx.ConnectError("refused"))
    try:
        ApiClient("http://x.test").health()
    except ApiUnreachable:
        pass
    else:
        raise AssertionError("expected ApiUnreachable")


@respx.mock
def test_error_body_preserved_verbatim() -> None:
    respx.post("http://x.test/query/cypher").mock(
        return_value=httpx.Response(400, json={"detail": "write clause refused"})
    )
    try:
        ApiClient("http://x.test").query_cypher("MERGE (n)")
    except ApiError as exc:
        assert exc.status == 400 and "write clause refused" in exc.detail
    else:
        raise AssertionError("expected ApiError")


@respx.mock
def test_error_non_json_body_falls_back_to_raw_text() -> None:
    respx.get("http://x.test/health").mock(
        return_value=httpx.Response(500, text="boom")
    )
    try:
        ApiClient("http://x.test").health()
    except ApiError as exc:
        assert exc.status == 500 and exc.detail == "boom"
    else:
        raise AssertionError("expected ApiError")
