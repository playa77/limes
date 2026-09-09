# desktop/tests/integration/test_full_flow.py | v0.1.0 | AC-DC-1/3: desktop client over the real API
"""The desktop client's full flow, in-process, per AC-DC-1's automatable
core: the real FastAPI application runs inside the ApiClient's httpx
transport (`ASGITransport`) — no server process — while the graph data
comes from the session-scoped disposable Neo4j container exactly like the
root integration suite (`tests/integration/conftest.py`).

Flow: search → entity → entity_neighbors → query_nl (OpenRouter stubbed at
the composition root, the repo's no-paid-calls invariant) → query_builder →
query_cypher → save_query → delete_saved_query. Every executed outcome
carries a coverage report (AC-23), an empty result carries the hop-level
diagnosis instead of a bare empty set (AC-DC-3), and the NL outcome carries
the generated, editable Cypher (AC-DC-2's data path).
"""

from __future__ import annotations

import asyncio
import sys
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest

# Shared fixtures live in the root suite (tests/fixtures, tests/integration/
# conftest.py); make them importable here by absolute path so the desktop
# tree stays self-contained under pytest's rootdir-based `tests` package.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_TESTS_PKG = str(_REPO_ROOT / "tests")
if _TESTS_PKG not in __import__("sys").path:
    sys.path.insert(0, _TESTS_PKG)

from fixtures.graph_data import (  # noqa: E402  (path bootstrap must precede)
    api_settings,
    load_corporation_graph,
    load_ontology_artifact,
    make_driver,
    wipe_graph,
)


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


class _SyncLifespan:
    """Drives the app's async lifespan context on a background event loop
    so the sync test body — and the sync `httpx.Client` inside the
    ApiClient — see a fully started application (settings, ontology,
    driver, provision), the equivalent of TestClient's startup."""

    def __init__(self, app: Any) -> None:
        self._app = app
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._stop: asyncio.Event | None = None

    def __enter__(self) -> Any:
        started = threading.Event()
        loop_ready = threading.Event()

        async def _run() -> None:
            stop = asyncio.Event()
            self._stop = stop
            loop_ready.set()
            async with self._app.router.lifespan_context(self._app):
                loop = asyncio.get_running_loop()
                loop.call_soon_threadsafe(started.set)
                await stop.wait()

        loop = asyncio.new_event_loop()
        self._loop = loop
        thread = threading.Thread(target=loop.run_until_complete, args=(_run(),), daemon=True)
        self._thread = thread
        thread.start()
        loop_ready.wait()
        started.wait(timeout=120)
        return self._app

    def __exit__(self, *exc: Any) -> None:
        if self._loop is not None and self._stop is not None:
            self._loop.call_soon_threadsafe(self._stop.set)
        if self._thread is not None:
            self._thread.join(timeout=60)
        if self._loop is not None:
            self._loop.close()


@pytest.fixture()
def client_factory(
    neo4j_instance: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Builds an ApiClient whose httpx transport is the real in-process
    FastAPI app. The OpenRouter stub is wired through `api.deps` — the
    composition-root seam the root suite's NLQ tests use — before the app
    starts."""
    from limes_desktop.api.client import ApiClient

    from limes.api import deps
    from limes.api.main import create_app
    from limes.composition import NlqContext

    created: list[ApiClient] = []
    lifespans: list[_SyncLifespan] = []

    def make(stub: StubClient | None = None) -> ApiClient:
        if stub is not None:
            original = deps.build_nlq_context

            def _stubbed(settings: Any, ontology: Any, driver: Any) -> NlqContext:
                ctx = original(settings, ontology, driver)
                return NlqContext(
                    settings=ctx.settings,
                    ontology=ctx.ontology,
                    driver=ctx.driver,
                    client=stub,
                    governor=ctx.governor,
                )

            monkeypatch.setattr(deps, "build_nlq_context", _stubbed)

        lifespan = _SyncLifespan(create_app(api_settings(neo4j_instance, tmp_path)))
        app = lifespan.__enter__()
        lifespans.append(lifespan)

        client = ApiClient.__new__(ApiClient)
        client._client = httpx.Client(
            base_url="http://limes.test",
            transport=httpx.ASGITransport(app=app),
            timeout=httpx.Timeout(30.0),
        )
        created.append(client)
        return client

    yield make

    for c in created:
        c.close()
    for lifespan in lifespans:
        lifespan.__exit__(None, None, None)


def test_full_flow_search_to_saved_query(client_factory: Any, ids: dict[str, str]) -> None:
    from limes_desktop.api.client import ApiClient
    from limes_desktop.api.models import GraphNeighbors

    client: ApiClient = client_factory()

    # 1. search — a real hit over the seeded graph.
    hits = client.search("alpha", kind="entity")
    assert any(hit.id == ids["alpha"] for hit in hits)
    assert all(hit.score > 0 for hit in hits)

    # 2. entity — the full detail of the hit.
    detail = client.entity(ids["alpha"])
    assert detail.entity.entity_id == ids["alpha"]
    assert detail.entity.type == "Corporation"

    # 3. entity_neighbors — one hop with provenance.
    neighbors: GraphNeighbors = client.entity_neighbors(ids["alpha"])
    neighbor_ids = {row.neighbor.entity_id for row in neighbors.neighbors}
    assert neighbor_ids == {ids["beta"], ids["hq"], ids["boss"]}
    assert all(row.edge.source_id for row in neighbors.neighbors)

    # 4. query_nl — OpenRouter stubbed; the outcome carries the generated,
    #    editable Cypher (AC-DC-2's data path).
    stub = StubClient()
    stub.replies = ["MATCH (a:Corporation {lei: 'LEI-ALPHA'})-[:SUBSIDIARY_OF]->(b) RETURN a, b"]
    nl = client.query_nl("What does Alpha own?")
    assert stub.calls == 1
    assert "LIMIT" in nl.cypher  # the generated query is bounded
    assert nl.coverage.relation_counts == {"SUBSIDIARY_OF": 1}
    assert nl.diagnosis is None
    assert nl.results.counts["rows"] == 1

    # 5. query_builder — structured spec, same coverage guarantees.
    builder = client.query_builder(
        {
            "start_type": "Corporation",
            "start_filters": {"lei": "LEI-ALPHA"},
            "hops": [
                {"relation": "SUBSIDIARY_OF", "direction": "out", "target_type": "Corporation"}
            ],
        }
    )
    assert builder.coverage.relation_counts == {"SUBSIDIARY_OF": 1}
    assert builder.diagnosis is None
    assert builder.results.counts["rows"] == 1

    # 6. query_cypher — operator Cypher through the same pipeline.
    outcome = client.query_cypher(
        "MATCH (a:Corporation {lei: $lei}) RETURN a LIMIT 1", {"lei": "LEI-ALPHA"}
    )
    assert outcome.results.counts["rows"] == 1
    assert outcome.coverage is not None

    # 7. save_query / delete_saved_query — the desktop's library write path.
    before = client.saved_queries()
    qid = client.save_query(
        "Alpha subsidiaries",
        "MATCH (a:Corporation {lei: 'LEI-ALPHA'})-[:SUBSIDIARY_OF]->(b) RETURN a, b",
        {},
    )
    assert qid
    library = client.saved_queries()
    assert len(library) == len(before) + 1
    assert any(q.saved_query_id == qid and "Alpha subsidiaries" in q.question for q in library)
    client.delete_saved_query(qid)
    assert all(q.saved_query_id != qid for q in client.saved_queries())


def test_full_flow_empty_result_carries_diagnosis(client_factory: Any) -> None:
    """AC-DC-3: a query matching nothing returns the hop-level diagnosis —
    never a bare empty result."""
    client = client_factory()
    outcome = client.query_cypher(
        "MATCH (a:Corporation {lei: 'LEI-NO-SUCH-ENTITY'}) RETURN a LIMIT 1"
    )
    assert outcome.results.counts["rows"] == 0
    assert outcome.diagnosis is not None
    assert outcome.coverage is not None
