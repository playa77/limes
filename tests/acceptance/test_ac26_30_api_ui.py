# tests/acceptance/test_ac26_30_api_ui.py | v1.0.0 | introduced by WP-39
"""AC-26…AC-30: the query API and the UI's interaction contract.

AC-26: generated Cypher is returned by the API and lands in the editable
console for every NL query, including failed ones (validation failure and
plan rejection).
AC-27: a node click expands one hop and merges into the current view
without re-running the original query.
AC-28: an edge selection displays full provenance including the
originating sentence.
AC-29: all three panes react to a selection change and to a timeline
brush within one interaction cycle.
AC-30: every executed query is persisted with question, Cypher, ontology
version, and result count.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import respx
from httpx import Response

from limes.ui import api_client
from limes.ui.callbacks.query import run_nl
from limes.ui.callbacks.selection import edge_tapped, node_tapped, render_panes
from limes.ui.callbacks.temporal import brush_changed, requery
from limes.ui.components import provenance as provenance_component
from tests.acceptance.conftest import CATALOGUE, CATALOGUE_URL, COMPLETIONS_URL
from tests.fixtures.graph_data import (
    load_corporation_graph,
    load_ontology_artifact,
    make_api_client,
    make_driver,
    wipe_graph,
)
from tests.integration.conftest import Neo4jInstance

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"

DOC_HASH = "d" * 64
SENTENCE = "Alpha Industries acquired Beta GmbH in full."


def _flatten(component: Any) -> list[str]:
    """Every string leaf of a Dash component tree — the text a pane would
    render."""
    from dash.development.base_component import Component

    texts: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, Component):
            children = node.children or []
            if isinstance(children, str):
                texts.append(children)
                return
            for child in children:
                walk(child)
        elif isinstance(node, str):
            texts.append(node)
        elif isinstance(node, (list, tuple)):
            for child in node:
                walk(child)

    walk(component)
    return texts


def _recording_fake(monkeypatch: pytest.MonkeyPatch, name: str, response: Any) -> list[Any]:
    """Replace one `api_client` function with a recorder returning a fixed
    response; returns the call log."""
    calls: list[Any] = []

    def fake(*args: Any, **kwargs: Any) -> Any:
        calls.append((args, kwargs))
        return response

    monkeypatch.setattr(api_client, name, fake)
    return calls


def _nl_response(cypher: str, **extra: Any) -> dict[str, Any]:
    return {
        "question": "q",
        "cypher": cypher,
        "results": {"nodes": [], "edges": [], "counts": {"rows": 0, "nodes": 0, "edges": 0}},
        "validation_errors": [],
        "plan_rejection": None,
        "notes": [],
        "coverage": {"relation_counts": {}, "contributing_sources": [], "source_refresh": {}},
        "diagnosis": None,
        **extra,
    }


@pytest.fixture(scope="module", autouse=True)
def _fresh_graph(neo4j_instance: Neo4jInstance):
    wipe_graph(neo4j_instance)
    yield


def test_ac26_generated_cypher_is_returned_displayed_and_editable(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
):
    """The API returns the generated Cypher on success, on validation
    failure, and on plan rejection; the console renders it in the editable
    textarea."""
    from limes.ui.components import console as console_component

    wipe_graph(neo4j_instance)
    with make_api_client(neo4j_instance, tmp_path) as client:
        with respx.mock:
            respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=CATALOGUE))
            respx.post(COMPLETIONS_URL).mock(
                return_value=Response(
                    200,
                    json={
                        "choices": [
                            {"message": {"content": "MATCH (c:Corporation) RETURN c LIMIT 5"}}
                        ],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
                    },
                )
            )
            response = client.post("/query/nl", json={"question": "Which corporations exist?"})
        assert response.status_code == 200, response.text
        body = response.json()
        assert "MATCH (c:Corporation) RETURN c LIMIT 5" in body["cypher"]
        assert body["results"] is not None

        # The failed forms still return the Cypher (AC-26).
        with respx.mock:
            respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=CATALOGUE))
            respx.post(COMPLETIONS_URL).mock(
                return_value=Response(
                    200,
                    json={
                        "choices": [{"message": {"content": "MATCH (n:NotAThing) RETURN n"}}],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
                    },
                )
            )
            failed = client.post("/query/nl", json={"question": "broken question"})
        assert failed.status_code == 200, failed.text
        failed_body = failed.json()
        assert "NotAThing" in failed_body["cypher"]
        assert failed_body["validation_errors"]

    # The console is the editable display: the textarea is a Dash input
    # the run callback writes the Cypher into.
    from dash.development.base_component import Component

    rendered = console_component.render()
    ids: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, Component):
            node_id = getattr(node, "id", None)
            if node_id is not None:
                ids.append(str(node_id))
            for child in getattr(node, "children", None) or []:
                walk(child)

    walk(rendered)
    assert "cypher-textarea" in ids, "the console must render the editable Cypher textarea"


def test_ac26_nl_callback_writes_cypher_into_the_editable_console(
    monkeypatch: pytest.MonkeyPatch,
):
    """The UI half: `run_nl` puts the returned Cypher into the textarea
    output — for a successful outcome and for a failed one alike."""
    good = _nl_response("MATCH (c:Corporation) RETURN c LIMIT 5")
    bad = _nl_response(
        "MATCH (n:NotAThing) RETURN n",
        results=None,
        validation_errors=["UNKNOWN_LABEL: 'NotAThing'"],
    )
    calls: list[str] = []

    def fake_post(question: str) -> dict[str, Any]:
        calls.append(question)
        return bad if "broken" in question else good

    monkeypatch.setattr(api_client, "post_query_nl", fake_post)

    _result, _session, cypher_out, error_out = run_nl(1, None, "Which corporations exist?")
    assert cypher_out == "MATCH (c:Corporation) RETURN c LIMIT 5"
    assert error_out == ""

    _result, _session, cypher_out, error_out = run_nl(1, None, "a broken question")
    assert cypher_out == "MATCH (n:NotAThing) RETURN n"  # still displayed
    assert "UNKNOWN_LABEL" in error_out  # the failure is explained


def test_ac27_node_click_expands_one_hop_without_rerunning_the_query(
    monkeypatch: pytest.MonkeyPatch,
):
    """The expansion callback fetches the neighborhood and merges it; the
    query callbacks are never invoked — the original query is not re-run."""
    current = {
        "results": {
            "nodes": [
                {"entity_id": "corp-alpha", "label": "Alpha Industries", "type": "Corporation"}
            ],
            "edges": [],
            "counts": {"rows": 1, "nodes": 1, "edges": 0},
        }
    }
    neighbors = {
        "entity": {"entity_id": "corp-alpha", "label": "Alpha Industries", "type": "Corporation"},
        "neighbors": [
            {
                "neighbor": {
                    "entity_id": "corp-beta",
                    "label": "Beta GmbH",
                    "type": "Corporation",
                },
                "edge": {
                    "source": "corp-alpha",
                    "target": "corp-beta",
                    "relation": "SUBSIDIARY_OF",
                    "subject_id": "corp-alpha",
                    "object_id": "corp-beta",
                    "assertion_id": "n1",
                    "source_id": "feeds",
                },
            },
            {
                "neighbor": {
                    "entity_id": "hq-berlin",
                    "label": "Berlin HQ",
                    "type": "Location",
                },
                "edge": {
                    "source": "corp-alpha",
                    "target": "hq-berlin",
                    "relation": "HEADQUARTERED_IN",
                    "subject_id": "corp-alpha",
                    "object_id": "hq-berlin",
                    "assertion_id": "n2",
                    "source_id": "gleif",
                },
            },
        ],
    }
    neighbor_calls = _recording_fake(monkeypatch, "get_entity_neighbors", neighbors)

    def _forbidden_factory(forbidden: str):
        def _forbidden(*_a, **_k):
            raise AssertionError(f"{forbidden} must not be re-run on a node tap")

        return _forbidden

    for forbidden in ("post_query_cypher", "post_query_nl", "post_query_builder"):
        monkeypatch.setattr(api_client, forbidden, _forbidden_factory(forbidden))

    selection, merged = node_tapped(
        {"entity_id": "corp-alpha", "label": "Alpha Industries", "type": "Corporation"},
        current,
        None,
    )

    assert selection["kind"] == "node"
    assert selection["entity"]["entity_id"] == "corp-alpha"
    merged_result = merged["results"]  # the envelope the panes consume
    assert merged_result["nodes"] == [
        {"entity_id": "corp-alpha", "label": "Alpha Industries", "type": "Corporation"},
        {"entity_id": "corp-beta", "label": "Beta GmbH", "type": "Corporation"},
        {"entity_id": "hq-berlin", "label": "Berlin HQ", "type": "Location"},
    ]
    assert len(merged_result["edges"]) == 2
    assert len(neighbor_calls) == 1  # exactly one expansion, no query re-run


def test_ac28_edge_selection_displays_full_provenance_with_sentence():
    """The provenance panel renders the full §5.6 metadata of the selected
    edge plus the originating sentence from the evidence document's body."""
    edge = {
        "relation": "SUBSIDIARY_OF",
        "subject_id": "corp-alpha",
        "object_id": "corp-beta",
        "source_id": "feeds",
        "source_trust": 0.6,
        "confidence": 0.95,
        "valid_from": "2026-07-01",
        "valid_to": None,
        "recorded_at": "2026-08-01T12:00:00Z",
        "retracted_at": None,
        "extractor_model": "test/extractor",
        "prompt_version": "1.0.0",
        "schema_version": "1.0.0",
        "ontology_version": "1.0.0",
        "assertion_id": "news-1",
        "evidence_document_id": DOC_HASH,
        "evidence_start": 0,
        "evidence_end": len(SENTENCE),
    }
    selection = edge_tapped({"edge": edge})
    assert selection["kind"] == "edge"

    class _FakeApi:
        def get_entity(self, entity_id: str) -> dict[str, Any]:
            assert entity_id == DOC_HASH
            return {
                "entity": {
                    "entity_id": DOC_HASH,
                    "properties": {"body": SENTENCE},
                }
            }

    rendered = provenance_component.render(selection, _FakeApi())  # type: ignore[arg-type]
    text = "\n".join(_flatten(rendered))
    assert "Originating sentence" in text
    assert SENTENCE in text  # the evidence span of the body
    assert "feeds" in text
    assert "0.6" in text  # source trust
    assert "news-1" in text  # assertion id


def test_ac29_all_three_panes_react_to_selection_and_brush(
    monkeypatch: pytest.MonkeyPatch,
):
    """One interaction cycle: a selection change re-renders all three
    panes; a timeline brush writes the filter and re-queries through the
    same API path, after which the panes re-render again."""
    result = {
        "results": {
            "nodes": [{"entity_id": "corp-alpha", "label": "Alpha", "type": "Corporation"}],
            "edges": [],
            "counts": {"rows": 1, "nodes": 1, "edges": 0},
        }
    }
    no_selection = render_panes(result, None, None, None)
    selection = {
        "kind": "node",
        "entity": {"entity_id": "corp-alpha", "label": "Alpha", "type": "Corporation"},
    }
    with_selection = render_panes(result, selection, None, None)
    assert len(no_selection) == 3 and len(with_selection) == 3
    assert any("selected-node" in str(component) for component in with_selection), (
        "the selected node must be visually marked in the network pane"
    )

    # The brush: a drawn rangeslider window writes the temporal filter.
    from datetime import UTC, datetime

    end = datetime(2026, 8, 1, tzinfo=UTC)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    relayout = {"xaxis.range": [start.isoformat(), end.isoformat()]}
    brush = brush_changed(relayout, None)
    assert brush["as_of"] == end.isoformat()

    # The brush re-queries the same query path (no NL generation — the
    # session remembers the question) and the panes re-render in one cycle.
    query_calls: list[tuple] = []
    monkeypatch.setattr(
        api_client,
        "post_query_nl",
        lambda question: (
            query_calls.append(question) or _nl_response("MATCH (c:Corporation) RETURN c LIMIT 5")
        ),
    )
    refreshed, _cypher, _spec, _builder, error = requery(
        brush, {"path": "nl", "question": "Which corporations?"}, None
    )
    assert error == ""
    assert query_calls == ["Which corporations?"]
    panes = render_panes(refreshed, selection, brush, None)
    assert len(panes) == 3


def test_ac30_executed_query_is_persisted_with_full_metadata(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
):
    """An executed NL query lands in `/saved-queries` with the question,
    the Cypher, the ontology version, and the result count."""
    driver = make_driver(neo4j_instance)
    ontology = load_ontology_artifact()
    try:
        wipe_graph(neo4j_instance)
        load_corporation_graph(driver, ontology)
    finally:
        driver.close()

    with make_api_client(neo4j_instance, tmp_path) as client:
        with respx.mock:
            respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=CATALOGUE))
            respx.post(COMPLETIONS_URL).mock(
                return_value=Response(
                    200,
                    json={
                        "choices": [
                            {"message": {"content": "MATCH (n:Corporation) RETURN n LIMIT 5"}}
                        ],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
                    },
                )
            )
            response = client.post("/query/nl", json={"question": "All corporations?"})
        assert response.status_code == 200, response.text

        saved = client.get("/saved-queries")
        assert saved.status_code == 200, saved.text
        entries = saved.json()
        assert entries, "the executed query must be persisted"
        latest = entries[0]
        assert latest["question"] == "All corporations?"
        assert "MATCH (n:Corporation) RETURN n LIMIT 5" in latest["cypher"]
        assert latest["ontology_version"] == ontology.version
        assert latest["result_count"] >= 2  # the seeded corporation graph
