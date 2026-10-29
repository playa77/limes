# desktop/tests/integration/test_full_flow.py | v0.1.1 | sync TestClient owns API lifespan
"""The desktop client's full flow, in-process, per AC-DC-1's automatable
core: the real FastAPI application runs inside the ApiClient's httpx
transport (`TestClient`) — no server process — while the graph data
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

import sys
from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

# Shared fixtures live in the root suite (tests/fixtures, tests/integration/
# conftest.py); make them importable here by absolute path so the desktop
# tree stays self-contained under pytest's rootdir-based `tests` package.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_TESTS_PKG = str(_REPO_ROOT / "tests")
if _TESTS_PKG not in sys.path:
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


@pytest.fixture()
def client_factory(neo4j_instance: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Builds an ApiClient whose httpx transport is the real in-process
    FastAPI app. The OpenRouter stub is wired through `api.deps` — the
    composition-root seam the root suite's NLQ tests use — before the app
    starts."""
    from limes_desktop.api.client import ApiClient

    from limes.api import deps
    from limes.api.main import create_app
    from limes.composition import NlqContext

    stack = ExitStack()

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
                    recorder=ctx.recorder,
                )

            monkeypatch.setattr(deps, "build_nlq_context", _stubbed)

        transport = stack.enter_context(
            TestClient(
                create_app(api_settings(neo4j_instance, tmp_path)),
                headers={"Authorization": "Bearer test-api-token"},
            )
        )
        client = ApiClient.__new__(ApiClient)
        client._client = transport
        return client

    with stack:
        yield make


def test_full_flow_search_to_saved_query(client_factory: Any, ids: dict[str, str]) -> None:
    from limes_desktop.api.client import ApiClient
    from limes_desktop.api.models import GraphNeighbors

    stub = StubClient()
    stub.replies = ["MATCH (a:Corporation {lei: 'LEI-ALPHA'})-[:SUBSIDIARY_OF]->(b) RETURN a, b"]
    client: ApiClient = client_factory(stub)

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


def test_real_widgets_complete_api_workflow(
    qtbot: Any, client_factory: Any, ids: dict[str, str], tmp_path: Path
) -> None:
    """DC-14: drive actual controls through the API and disposable graph."""
    from limes_desktop.config import ProfileStore
    from limes_desktop.state import SessionState
    from limes_desktop.views.main_window import MainWindow

    stub = StubClient()
    stub.replies = ["MATCH (a:Corporation {lei: 'LEI-ALPHA'})-[:SUBSIDIARY_OF]->(b) RETURN a, b"]
    client = client_factory(stub)
    stub.replies = stub.replies * 2
    state = SessionState()
    win = MainWindow(state, ProfileStore(tmp_path / "profiles"), lambda: client)
    qtbot.addWidget(win)
    win.show()
    qtbot.waitUntil(lambda: win.banner.status_text() == "ok")
    win._run_search("alpha")
    assert any(hit.id == ids["alpha"] for hit in win.search_bar._hits)
    state.set_selection(ids["alpha"])
    assert win.entity_view.assertion_model.rowCount() >= 1
    win.entity_view._on_assertion_clicked(win.entity_view.assertion_model.index(0, 0))
    assert "validity:" in win.entity_view.provenance_text()
    assert "belief (recorded at):" in win.entity_view.provenance_text()
    win._expand_neighbors(ids["alpha"])
    assert win.network_view._last_graph().nodes
    win.nlq_view.question_edit.setText("DC-14 workflow: What does Alpha own?")
    win.nlq_view.submit_button.click()
    win.nlq_view.submit_button.click()  # repeated execution must not fail automatic history
    assert (
        len(
            [
                row
                for row in client.saved_queries()
                if row.question == "DC-14 workflow: What does Alpha own?"
            ]
        )
        == 2
    )
    assert stub.calls == 2
    assert win.nlq_view.cypher_edit.toPlainText()
    win.nlq_view.run_button.click()
    assert state.history()[-1].coverage is not None
    win.builder_view.reload_schema()
    win.builder_view.start_type_combo.setCurrentText("Corporation")
    row = win.builder_view.hop_rows[0]
    row.relation_combo.setCurrentText("SUBSIDIARY_OF")
    row.direction_combo.setCurrentIndex(row.direction_combo.findData("out"))
    row.target_combo.setCurrentText("Corporation")
    win.builder_view.submit_button.click()
    assert state.history()[-1].source == "builder"
    assert state.history()[-1].coverage is not None
    win.cypher_console.editor.setPlainText("MATCH (n:Corporation) RETURN n LIMIT 1")
    win.cypher_console.run_button.click()
    assert state.history()[-1].coverage is not None
    win.stack.setCurrentWidget(win.cypher_console)
    panel = win.saved_queries_panel
    win.stack.setCurrentWidget(panel)
    panel.name_edit.setText("DC-14 widget query")
    panel.save_button.click()
    assert any("DC-14 widget query" in row.question for row in client.saved_queries())
    saved = next(row for row in client.saved_queries() if row.question == "DC-14 widget query")
    panel.refresh_queries()
    index = next(i for i, row in enumerate(panel._rows) if row[0] == saved.saved_query_id)
    panel.list_widget.setCurrentRow(index)
    panel.delete_button.click()
    assert all(row.saved_query_id != saved.saved_query_id for row in client.saved_queries())
    win.cypher_console.editor.setPlainText("MATCH (a:Corporation {lei:'absent'}) RETURN a LIMIT 1")
    win.cypher_console.run_button.click()
    assert win.coverage_panel.is_showing_empty_state
    win.close()
