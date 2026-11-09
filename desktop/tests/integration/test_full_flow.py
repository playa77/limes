# desktop/tests/integration/test_full_flow.py | v1.1.0 | launcher full flow, in-process
"""The web desktop's full flow through the actual launcher, per AC-DC-1's
automatable core: the launcher FastAPI app (routes, bearer-proxy injection,
SPA serving) fronts the REAL API application over an in-process ASGI
transport — no server process — while the graph data comes from the
session-scoped disposable Neo4j container exactly like the root integration
suite (`tests/integration/conftest.py`). The browser-visible surface is
exercised verbatim: `/session`, `/api/*` proxy paths with launcher-injected
credentials, and the built-SPA index fallback against a fabricated dist.

Flow: health → session descriptor → search → entity → neighbors → query_nl
(OpenRouter stubbed at the composition root, the repo's no-paid-calls
invariant) → query_builder → query_cypher → save_query → delete_saved_query.
Every executed outcome carries a coverage report (AC-23); an empty result
carries the hop-level diagnosis instead of a bare empty set (AC-DC-3); the
NL outcome carries the generated, editable Cypher (AC-DC-2's data path).
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

# Shared fixtures live in the root suite (tests/fixtures, tests/integration/
# conftest.py); make them importable here by absolute path so the desktop
# tree stays self-contained under pytest's rootdir-based `tests` package.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_TESTING_PKG = str(_REPO_ROOT / "tests")
if _TESTING_PKG not in sys.path:
    sys.path.insert(0, _TESTING_PKG)

from fixtures.graph_data import (  # noqa: E402  (path bootstrap must precede)
    api_settings,
    load_corporation_graph,
    load_ontology_artifact,
    make_driver,
    wipe_graph,
)

_TOKEN = "test-api-token"

DIST_INDEX = b"<!doctype html><title>limes-web-desktop-integration</title>"


class StubClient:
    """The shape the NLQ service expects from its paid-inference client,
    with a canned Cypher reply — no OpenRouter, no ledger write."""

    def __init__(self) -> None:
        self.replies: list[str] = []
        self.calls: int = 0

    def complete(self, messages: Any, model_id: Any, purpose: Any, json_schema: Any = None):
        self.calls += 1
        return self.replies.pop(0), 10, 5

    def embed(self, texts: Any, model_id: Any):
        raise AssertionError("no embedding on the query path")


@pytest.fixture(scope="module", autouse=True)
def _fresh_graph(neo4j_instance: Any) -> Iterator[None]:
    """Reset the shared session container so this module is order-
    independent (the sanctioned fixture-teardown pattern)."""
    wipe_graph(neo4j_instance)
    yield


@pytest.fixture(scope="module")
def ids(neo4j_instance: Any) -> Iterator[dict[str, str]]:
    driver = make_driver(neo4j_instance)
    try:
        yield load_corporation_graph(driver, load_ontology_artifact())
    finally:
        driver.close()


@pytest.fixture()
def browser(
    neo4j_instance: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    """The SPA's browser: TestClient(LauncherApp) whose upstream transport is
    the real in-process API app. The API lifespan runs once (settings,
    ontology, driver, provision); the NLQ context is stubbed at `api.deps`
    before startup. The launcher proxy injects `_TOKEN` into every `/api/*`
    call — a missing or wrong credential is a 401 from the real middleware,
    so a 200 proves the injection happened."""
    from limes_desktop.config import ConnectionProfile, ProfileStore
    from limes_desktop.webapp import create_launcher_app

    from limes.api import deps
    from limes.api.main import create_app
    from limes.composition import NlqContext

    stub = StubClient()
    stub.replies = [
        "MATCH (a:Corporation {lei: 'LEI-ALPHA'})-[:SUBSIDIARY_OF]->(b) RETURN a, b",
        "MATCH (a:Corporation {lei: 'LEI-ALPHA'})-[:SUBSIDIARY_OF]->(b) RETURN a, b",
    ]

    original = deps.build_nlq_context

    def _stubbed(settings: Any, ontology: Any, driver: Any) -> NlqContext:
        ctx = original(settings, ontology, driver)
        return NlqContext(
            settings=ctx.settings,
            ontology=ctx.ontology,
            driver=ctx.driver,
            client=stub,
            recorder=ctx.recorder,
        )

    monkeypatch.setattr(deps, "build_nlq_context", _stubbed)

    api_app = create_app(api_settings(neo4j_instance, tmp_path))
    dist = tmp_path / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_bytes(DIST_INDEX)

    # one shared loop only for the AsyncClient teardown; requests run through
    # the launcher handlers' own portals, so no persistent loop binding exists
    import asyncio

    upstream = httpx.AsyncClient(
        transport=httpx.ASGITransport(api_app),
        base_url="http://disposable.test",
    )
    stack = ExitStack()
    try:
        api_probe = stack.enter_context(TestClient(api_app))  # runs the API lifespan
        response = api_probe.get("/health", headers={"Authorization": f"Bearer {_TOKEN}"})
        assert response.status_code == 200

        store = ProfileStore(config_dir=tmp_path / "xdg")
        store.save(ConnectionProfile(name="disposable", base_url="http://disposable.test"))
        store.set_active("disposable")

        launcher_app = create_launcher_app(
            dist_dir=dist,
            store=store,
            http=upstream,
            env_credential=(_TOKEN, "api"),
        )
        yield TestClient(launcher_app)
    finally:
        stack.close()
        asyncio.run(upstream.aclose())


def test_full_flow_search_to_saved_query(browser: TestClient, ids: dict[str, str]) -> None:
    # 0. session — the launcher descriptor without any secret material.
    descriptor = browser.get("/session").json()
    assert descriptor["token_kind"] == "api"  # /operations/capabilities 403s for the api token
    assert descriptor["profile"] == "disposable"

    # 1. search — a real hit over the seeded graph, through the proxy.
    hits = browser.get("/api/search", params={"q": "alpha", "kind": "entity"}).json()
    assert any(hit["id"] == ids["alpha"] for hit in hits), hits
    assert all(hit["score"] > 0 for hit in hits)

    # 2. entity — the full detail of the hit.
    detail = browser.get(f"/api/entity/{ids['alpha']}").json()
    assert detail["entity"]["entity_id"] == ids["alpha"]
    assert detail["entity"]["type"] == "Corporation"

    # 3. entity_neighbors — one hop with provenance.
    neighbors = browser.get(f"/api/entity/{ids['alpha']}/neighbors").json()
    neighbor_ids = {row["neighbor"]["entity_id"] for row in neighbors["neighbors"]}
    assert neighbor_ids == {ids["beta"], ids["hq"], ids["boss"]}
    assert all(row["edge"]["source_id"] for row in neighbors["neighbors"])

    # 4. query_nl — OpenRouter stubbed; the outcome carries the generated,
    #    editable Cypher (AC-DC-2's data path).
    nl = browser.post("/api/query/nl", json={"question": "What does Alpha own?"}).json()
    assert "LIMIT" in nl["cypher"]  # the generated query is bounded
    assert nl["coverage"]["relation_counts"] == {"SUBSIDIARY_OF": 1}
    assert nl["diagnosis"] is None
    assert nl["results"]["counts"]["rows"] == 1

    # 5. query_builder — structured spec, same coverage guarantees.
    builder = browser.post(
        "/api/query/builder",
        json={
            "start_type": "Corporation",
            "start_filters": {"lei": "LEI-ALPHA"},
            "hops": [
                {"relation": "SUBSIDIARY_OF", "direction": "out", "target_type": "Corporation"}
            ],
        },
    ).json()
    assert builder["coverage"]["relation_counts"] == {"SUBSIDIARY_OF": 1}
    assert builder["diagnosis"] is None
    assert builder["results"]["counts"]["rows"] == 1

    # 6. query_cypher — operator Cypher through the same pipeline.
    outcome = browser.post(
        "/api/query/cypher",
        json={"cypher": "MATCH (a:Corporation {lei: $lei}) RETURN a LIMIT 1",
              "params": {"lei": "LEI-ALPHA"}},
    ).json()
    assert outcome["results"]["counts"]["rows"] == 1
    assert outcome["coverage"] is not None

    # 7. saved queries — the desktop's library write path.
    before = browser.get("/api/saved-queries").json()
    made = browser.post(
        "/api/saved-queries",
        json={
            "question": "Alpha subsidiaries",
            "cypher": "MATCH (a:Corporation {lei: 'LEI-ALPHA'})-[:SUBSIDIARY_OF]->(b) RETURN a, b",
            "result_count": 0,
            "pinned": False,
        },
    ).json()
    qid = made["saved_query_id"]
    assert qid
    library = browser.get("/api/saved-queries").json()
    assert len(library) == len(before) + 1
    assert any(row["saved_query_id"] == qid for row in library)
    assert browser.delete(f"/api/saved-queries/{qid}").status_code == 200
    assert all(row["saved_query_id"] != qid for row in browser.get("/api/saved-queries").json())

    # 8. the SPA host itself — index fallback for deep links.
    assert browser.get("/").status_code == 200
    assert DIST_INDEX in browser.get("/ops/offices").content


def test_full_flow_empty_result_carries_diagnosis(browser: TestClient) -> None:
    """AC-DC-3: a query matching nothing returns the hop-level diagnosis —
    never a bare empty result."""
    outcome = browser.post(
        "/api/query/cypher",
        json={
            "cypher": "MATCH (a:Corporation {lei: 'LEI-NO-SUCH-ENTITY'}) RETURN a LIMIT 1",
            "params": {},
        },
    ).json()
    assert outcome["results"]["counts"]["rows"] == 0
    assert outcome["diagnosis"] is not None
    assert outcome["coverage"] is not None
