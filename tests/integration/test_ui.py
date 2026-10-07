# tests/integration/test_ui.py | v1.0.0 | introduced by WP-36
"""UI tests per Doc 2 §8.13 and WP-36: the AC-27/28/29 interactions as
pure callback functions with recorded API fakes, the no-credentials /
no-database-access and no-ontology-literals guards, and the `api_client`
seam against a real API server process (a `subprocess` uvicorn — a real
process boundary, per Doc 2 §12.2 rule 2).

The callbacks are exercised directly (D-08): each interaction is a plain
function of its inputs, so AC-27 (expansion without re-running the
original query), AC-28 (full provenance including the originating
sentence), and AC-29 (one interaction cycle, all three panes) are
testable without a browser. Graph state is produced through the loader
(production path); the UI's only dependency — the API — is either a
recorded fake at the `api_client` seam or the real server process.
"""

from __future__ import annotations

import ast
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import pytest

from limes.ui import api_client
from limes.ui.components import builder as builder_component
from limes.ui.components import map as map_component
from tests.fixtures.graph_data import (
    assertion,
    endpoint,
    load_corporation_graph,
    load_ontology_artifact,
    make_driver,
    wipe_graph,
)
from tests.integration.conftest import Neo4jInstance

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"
UI_ROOT = REPO_ROOT / "src" / "limes" / "ui"

DOC_HASH = "d" * 64  # the content-hash shape of an evidence document id


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _flatten(component: Any) -> list[str]:
    """Every string leaf of a Dash component tree — the text a panel would
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
    response; returns the call log (args tuples)."""
    calls: list[Any] = []

    def fake(*args: Any, **kwargs: Any) -> Any:
        calls.append((args, kwargs))
        return response

    monkeypatch.setattr(api_client, name, fake)
    return calls


@pytest.fixture(scope="module", autouse=True)
def _fresh_graph(neo4j_instance: Neo4jInstance):
    """Reset the shared session container before this module runs (the
    sanctioned fixture teardown)."""
    wipe_graph(neo4j_instance)
    yield


@pytest.fixture(scope="module")
def seeded(neo4j_instance: Neo4jInstance) -> dict[str, str]:
    """The corporation graph plus a news-extracted-style assertion carrying
    evidence fields — the state AC-27/AC-28/AC-29 and the live api_client
    tests exercise. All written through the loader (production path)."""
    driver = make_driver(neo4j_instance)
    ontology = load_ontology_artifact()
    ids = load_corporation_graph(driver, ontology)
    news_subject = endpoint("news-org-1", "Corporation", "News Org One")
    news_object = endpoint("news-org-2", "Corporation", "News Org Two")
    news_edge = assertion(
        "news-1", news_subject, "SUBSIDIARY_OF", news_object, source_id="feeds", trust=0.6
    )
    news_edge.provenance.evidence_document_id = DOC_HASH
    news_edge.provenance.evidence_start = 10
    news_edge.provenance.evidence_end = 40
    from limes.graph.loader import load

    load(driver, [news_edge], ontology)
    driver.close()
    return ids


@pytest.fixture(scope="module")
def live_api(
    neo4j_instance: Neo4jInstance, seeded: None, tmp_path_factory: pytest.TempPathFactory
) -> str:
    """A real uvicorn process serving the real application against the
    disposable container — the API half of the UI's only HTTP boundary."""
    port = _free_port()
    tmp = tmp_path_factory.mktemp("ui-api")
    env = dict(os.environ)
    env.update(
        {
            "LIMES_API_TOKEN": "test-api-token",
            "LIMES_NEO4J_URI": neo4j_instance.uri,
            "LIMES_NEO4J_USER": neo4j_instance.user,
            "LIMES_NEO4J_PASSWORD": neo4j_instance.password,
            "LIMES_NEO4J_DATABASE": neo4j_instance.database,
            "LIMES_ONTOLOGY_PATH": str(ONTOLOGY_PATH),
            "LIMES_FEEDS_CONFIG_PATH": str(REPO_ROOT / "ontology" / "feeds.yaml"),
            "LIMES_GOLD_SET_PATH": str(tmp / "gold_set.jsonl"),
            "LIMES_BASELINE_PATH": str(tmp / "baseline.json"),
            "LIMES_ARCHIVE_PATH": str(tmp / "archive"),
            "LIMES_OPENROUTER_API_KEY": "sk-test",
            "LIMES_OPENROUTER_BASE_URL": "https://openrouter.test/api/v1",
            "LIMES_LOG_LEVEL": "WARNING",
            "PYTHONPATH": str(REPO_ROOT / "src"),
        }
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "--factory",
            "limes.api.main:create_app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        env=env,
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if process.poll() is not None:
            pytest.fail(f"api server exited early with code {process.returncode}")
        try:
            with httpx.Client(
                timeout=5, headers={"Authorization": "Bearer test-api-token"}
            ) as client:
                if client.get(f"{url}/health").status_code == 200:
                    break
        except httpx.HTTPError:
            pass
        time.sleep(1)
    else:
        process.terminate()
        pytest.fail("api server did not become healthy in time")
    yield url
    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _schema() -> dict[str, Any]:
    from limes.api.builder import project_for_builder

    return project_for_builder(load_ontology_artifact())


def _result() -> dict[str, Any]:
    """A small result envelope: two corporations, a coordinate-bearing
    node, two temporal edges and one non-temporal edge."""
    return {
        "cypher": "MATCH (n) RETURN n",
        "results": {
            "nodes": [
                {"entity_id": "n1", "label": "Alpha", "type": "Corporation", "properties": {}},
                {"entity_id": "n2", "label": "Beta", "type": "Corporation", "properties": {}},
                {
                    "entity_id": "hq",
                    "label": "HQ",
                    "type": "Location",
                    "properties": {"latitude": 52.52, "longitude": 13.4},
                },
            ],
            "edges": [
                {
                    "subject_id": "n1",
                    "object_id": "n2",
                    "relation": "SUBSIDIARY_OF",
                    "assertion_id": "a1",
                    "source_id": "test-source",
                    "valid_from": "2020-01-01T00:00:00Z",
                    "valid_to": None,
                },
                {
                    "subject_id": "hq",
                    "object_id": "n1",
                    "relation": "HEADQUARTERED_IN",
                    "assertion_id": "a2",
                    "source_id": "test-source",
                    "valid_from": "2015-01-01T00:00:00Z",
                    "valid_to": None,
                },
                {
                    "subject_id": "hq",
                    "object_id": "n2",
                    "relation": "HEADQUARTERED_IN",
                    "assertion_id": "a3",
                    "source_id": "test-source",
                    "recorded_at": "2020-01-02T00:00:00Z",
                },
            ],
            "counts": {"rows": 1, "nodes": 3, "edges": 3},
        },
        "coverage": {
            "relation_counts": {"SUBSIDIARY_OF": 1},
            "contributing_sources": [],
            "source_refresh": {},
        },
        "diagnosis": None,
        "notes": [],
    }


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------


def test_ui_holds_no_credentials_and_no_database_access():
    """G1: the UI performs no database access and holds no credentials —
    the WP-36 verification grep, as a test, case-insensitively."""
    forbidden = ("neo4j", "GraphDriver", "bolt://")
    ui_files = list(UI_ROOT.rglob("*.py"))
    assert ui_files
    for py_file in ui_files:
        source = py_file.read_text()
        for token in forbidden:
            assert token.lower() not in source.lower(), f"{py_file}: found {token!r}"


def test_ui_source_contains_no_ontology_literals():
    """G2: no UI module holds a type name or relation name as a literal —
    the builder and panes are schema-derived. Exact-match on string
    literals (comments and docstrings included) against every concrete
    entity type and relation name of the loaded ontology, and no literal
    carries a Cypher clause keyword (Doc 2 §8.13's no-fragments rule)."""
    ontology = load_ontology_artifact()
    names = set(ontology.entity_types) | set(ontology.relation_types)
    cypher_keywords = (
        "MATCH",
        "RETURN",
        "MERGE",
        "CREATE",
        "WHERE",
        "LIMIT",
        "UNWIND",
        "WITH",
        "DETACH",
        "SET",
        "REMOVE",
        "LOAD",
    )
    for py_file in UI_ROOT.rglob("*.py"):
        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert node.value not in names, f"{py_file.name}: literal {node.value!r}"
                assert not any(keyword in node.value for keyword in cypher_keywords), (
                    f"{py_file.name}: literal {node.value!r} contains a Cypher keyword"
                )


# ---------------------------------------------------------------------------
# Builder admissibility
# ---------------------------------------------------------------------------


def test_builder_options_are_schema_admissible():
    """AC-24's UI half: every relation, direction, and target the builder
    offers for a type is admitted by the ontology's own domain/range
    resolution — the generated builder cannot offer an invalid hop."""
    ontology = load_ontology_artifact()
    schema = _schema()
    for type_name in schema["entity_types"]:
        for entry in builder_component.relations_for(schema, type_name["name"]):
            relation = entry["relation"]
            for direction in entry["directions"]:
                targets = builder_component.targets_for(
                    schema, type_name["name"], relation, direction
                )
                assert targets, f"{type_name['name']} {relation} {direction}: no targets"
                for target in targets:
                    if direction == "out":
                        assert ontology.permits(relation, type_name["name"], target), (
                            f"out hop {type_name['name']} -[{relation}]-> {target} not permitted"
                        )
                    else:
                        assert ontology.permits(relation, target, type_name["name"]), (
                            f"in hop {target} -[{relation}]-> {type_name['name']} not permitted"
                        )


# ---------------------------------------------------------------------------
# AC-27: node click expansion
# ---------------------------------------------------------------------------


def test_ac27_node_click_expands_one_hop_without_rerunning_the_query(
    monkeypatch: pytest.MonkeyPatch,
):
    from limes.ui.callbacks import selection as selection_callbacks

    neighbors = {
        "entity": {"entity_id": "n1"},
        "neighbors": [
            {
                "edge": {
                    "subject_id": "n1",
                    "object_id": "n3",
                    "relation": "SUBSIDIARY_OF",
                    "assertion_id": "a9",
                    "source_id": "feeds",
                    "valid_from": "2020-01-01T00:00:00Z",
                },
                "neighbor": {
                    "entity_id": "n3",
                    "label": "Gamma",
                    "type": "Corporation",
                    "properties": {},
                },
            }
        ],
    }
    neighbors_calls = _recording_fake(monkeypatch, "get_entity_neighbors", neighbors)
    query_calls: list[str] = []
    for name in ("post_query_cypher", "post_query_nl", "post_query_builder"):
        monkeypatch.setattr(
            api_client,
            name,
            lambda *args, _name=name, **kwargs: query_calls.append(_name),
        )

    current = _result()
    selection, merged = selection_callbacks.node_tapped(
        {"entity_id": "n1", "label": "Alpha", "type": "Corporation"}, current, None
    )
    assert selection == {
        "kind": "node",
        "entity": {"entity_id": "n1", "label": "Alpha", "type": "Corporation"},
    }
    assert [node["entity_id"] for node in merged["results"]["nodes"]] == ["n1", "n2", "hq", "n3"]
    assert any(edge["assertion_id"] == "a9" for edge in merged["results"]["edges"])
    assert merged["results"]["counts"]["nodes"] == 4
    assert neighbors_calls == [(("n1", {}), {})]
    assert query_calls == [], "the original query must not be re-run"

    # Re-tapping the same node merges nothing new — dedup by id.
    _, merged_again = selection_callbacks.node_tapped(
        {"entity_id": "n1", "label": "Alpha", "type": "Corporation"}, merged, None
    )
    assert len(merged_again["results"]["nodes"]) == 4
    assert len(merged_again["results"]["edges"]) == 4


def test_ac27_expansion_carries_the_temporal_filter(monkeypatch: pytest.MonkeyPatch):
    """The brush's instant travels into the neighbors call's `as_of` — the
    expansion is temporal, not the original query re-run."""
    from limes.ui.callbacks import selection as selection_callbacks

    neighbors = {"entity": {}, "neighbors": []}
    neighbors_calls = _recording_fake(monkeypatch, "get_entity_neighbors", neighbors)
    temporal = {
        "as_of": "2020-06-01T00:00:00",
        "range": ["2020-01-01T00:00:00", "2020-06-01T00:00:00"],
    }
    selection_callbacks.node_tapped({"entity_id": "n1"}, _result(), temporal)
    assert neighbors_calls == [(("n1", {"as_of": "2020-06-01T00:00:00"}), {})]


# ---------------------------------------------------------------------------
# AC-28: provenance with the originating sentence
# ---------------------------------------------------------------------------


def test_ac28_edge_selection_displays_provenance_and_originating_sentence(
    monkeypatch: pytest.MonkeyPatch,
):
    from limes.ui.callbacks import selection as selection_callbacks

    body = "Berlin. Alpha Industries announced the acquisition of Beta GmbH yesterday."
    start = body.find("Alpha Industries")
    end = body.find("yesterday")
    document = {
        "entity": {"entity_id": "doc-1", "properties": {"body": body, "title": "News"}},
        "edge_summary": {},
    }
    document_calls = _recording_fake(monkeypatch, "get_entity", document)

    edge = {
        "relation": "SUBSIDIARY_OF",
        "subject_id": "n1",
        "object_id": "n2",
        "source_id": "feeds",
        "source_trust": 0.6,
        "confidence": 0.9,
        "recorded_at": "2026-08-01T00:00:00Z",
        "valid_from": "2020-01-01T00:00:00Z",
        "valid_to": None,
        "retracted_at": None,
        "assertion_id": "news-1",
        "ontology_version": "1.0.0",
        "extractor_model": "test-model",
        "prompt_version": "1.0.0",
        "schema_version": "1.0.0",
        "evidence_document_id": "doc-1",
        "evidence_start": start,
        "evidence_end": end,
    }
    selection = selection_callbacks.edge_tapped({"edge": edge})
    assert selection == {"kind": "edge", "edge": edge}

    panel = selection_callbacks.render_provenance(selection)
    text = " ".join(_flatten(panel))
    assert document_calls == [(("doc-1",), {})]
    assert "SUBSIDIARY_OF" in text
    assert "feeds" in text
    assert "0.6" in text
    assert "news-1" in text
    sentence = body[start:end]
    assert sentence in text, "the originating sentence must be displayed verbatim"
    assert "Originating sentence" in text


def test_ac28_evidence_document_absent_states_so(live_api: str, monkeypatch: pytest.MonkeyPatch):
    """Against the live API: the seeded news edge's evidence document has
    no `:Document` node (no production path creates one — WP-32's search
    test documents this), so `get_entity` 404s and the panel states the
    evidence coordinates instead of fabricating a sentence (D-10)."""
    monkeypatch.setenv("LIMES_API_BASE_URL", live_api)
    monkeypatch.setenv("LIMES_API_TOKEN", "test-api-token")
    from limes.ui.callbacks import selection as selection_callbacks

    edge = {
        "relation": "SUBSIDIARY_OF",
        "subject_id": "n1",
        "object_id": "n2",
        "source_id": "feeds",
        "assertion_id": "news-1",
        "evidence_document_id": DOC_HASH,
        "evidence_start": 10,
        "evidence_end": 40,
    }
    panel = selection_callbacks.render_provenance({"kind": "edge", "edge": edge})
    text = " ".join(_flatten(panel))
    assert DOC_HASH in text
    assert "10:40" in text
    assert "evidence document not available through the API" in text
    assert "Originating sentence" not in text


# ---------------------------------------------------------------------------
# AC-29: one interaction cycle, three panes
# ---------------------------------------------------------------------------


def test_ac29_all_three_panes_react_to_a_node_selection():
    from limes.ui.callbacks import selection as selection_callbacks

    schema = _schema()
    envelope = {"results": _result()["results"]}
    selection = {"kind": "node", "entity": {"entity_id": "hq", "label": "HQ", "type": "Location"}}
    network_pane, map_pane, timeline_pane = selection_callbacks.render_panes(
        envelope, None, None, schema
    )
    network_sel, map_sel, timeline_sel = selection_callbacks.render_panes(
        envelope, selection, None, schema
    )

    # Network: the selected node carries the highlight class.
    selected_node = next(
        element for element in network_sel.elements if element["data"]["entity_id"] == "hq"
    )
    assert selected_node.get("classes") == "selected-node"
    plain_node = next(
        element for element in network_pane.elements if element["data"]["entity_id"] == "hq"
    )
    assert plain_node.get("classes") is None

    # Map: the selected node's marker changes color.
    selected_marker = next(marker for marker in map_sel.children[1:] if marker.id["index"] == "hq")
    assert selected_marker.color == map_component._SELECTED_COLOR
    plain_marker = next(marker for marker in map_pane.children[1:] if marker.id["index"] == "hq")
    assert plain_marker.color == map_component._UNSELECTED_COLOR

    # Timeline: the incident temporal edge's row is highlighted.
    bar_colors = list(timeline_sel.figure.data[0].marker.color)
    assert map_component._SELECTED_COLOR in bar_colors
    assert list(timeline_pane.figure.data[0].marker.color) != bar_colors


def test_ac29_all_three_panes_react_to_an_edge_selection():
    from limes.ui.callbacks import selection as selection_callbacks

    schema = _schema()
    result = _result()
    envelope = {"results": result["results"]}
    edge = result["results"]["edges"][1]  # hq → n1, temporal
    selection = {"kind": "edge", "edge": edge}
    _, map_pane, timeline_pane = selection_callbacks.render_panes(envelope, None, None, schema)
    _, map_sel, timeline_sel = selection_callbacks.render_panes(envelope, selection, None, schema)

    # Map: the edge's endpoint marker is highlighted.
    highlighted = {
        marker.id["index"]
        for marker in map_sel.children[1:]
        if marker.color == map_component._SELECTED_COLOR
    }
    assert highlighted == {"hq"}
    assert {
        marker.id["index"]
        for marker in map_pane.children[1:]
        if marker.color == map_component._SELECTED_COLOR
    } == set()

    # Timeline: the selected edge's row is highlighted.
    selected_rows = [
        row
        for row, color in zip(
            timeline_sel.figure.data[0].y,
            timeline_sel.figure.data[0].marker.color,
            strict=True,
        )
        if color == map_component._SELECTED_COLOR
    ]
    assert any("HEADQUARTERED_IN" in row for row in selected_rows)
    assert all(
        color == map_component._UNSELECTED_COLOR
        for color in timeline_pane.figure.data[0].marker.color
    )


def test_ac29_timeline_brush_triggers_a_requery_not_client_side_filtering(
    monkeypatch: pytest.MonkeyPatch,
):
    """The brush writes the temporal-filter store; the re-query re-runs the
    producing query through the API with `as_of` on temporal hops — never a
    client-side interval filter (Doc 2 §8.13, D-11)."""
    from dash.exceptions import PreventUpdate

    from limes.ui.callbacks import temporal as temporal_callbacks
    from limes.ui.callbacks.selection import render_panes

    schema = _schema()
    brush = {"xaxis.range": ["2020-01-01", "2020-06-01"]}
    temporal_filter = temporal_callbacks.brush_changed(brush, None)
    assert temporal_filter == {
        "as_of": "2020-06-01T00:00:00",
        "range": ["2020-01-01T00:00:00", "2020-06-01T00:00:00"],
    }

    spec = {
        "start_type": "Corporation",
        "start_filters": {},
        "hops": [
            {
                "relation": "SUBSIDIARY_OF",
                "direction": "out",
                "target_type": "Corporation",
                "filters": {},
                "temporal_qualifier": None,
                "temporal_instant": None,
            },
            {
                "relation": "MENTIONS",
                "direction": "in",
                "target_type": "Document",
                "filters": {},
                "temporal_qualifier": None,
                "temporal_instant": None,
            },
        ],
    }
    recorded: list[dict[str, Any]] = []

    def fake_builder(spec_payload: dict[str, Any]) -> dict[str, Any]:
        recorded.append(spec_payload)
        return {
            "cypher": "MATCH (n) RETURN n LIMIT 500",
            "results": _result()["results"],
            "coverage": {},
            "diagnosis": None,
            "notes": [],
        }

    monkeypatch.setattr(api_client, "post_query_builder", fake_builder)
    response, cypher, new_spec, children, error = temporal_callbacks.requery(
        temporal_filter, {"path": "builder", "spec": spec}, schema
    )
    assert error == ""
    qualified = recorded[0]
    assert qualified["hops"][0]["temporal_qualifier"] == "as_of"
    assert qualified["hops"][0]["temporal_instant"] == "2020-06-01T00:00:00"
    assert qualified["hops"][1]["temporal_qualifier"] is None, (
        "non-temporal relations never qualify"
    )
    assert response["results"]["counts"]["rows"] == 1

    # The panes re-render from the re-queried response — one cycle.
    network, map_pane, timeline = render_panes(
        {"results": response["results"]}, None, temporal_filter, schema
    )
    assert network is not None and map_pane is not None and timeline is not None

    # The same window again is a no-op (loop guard); clearing resets.
    with pytest.raises(PreventUpdate):
        temporal_callbacks.brush_changed(brush, temporal_filter)
    assert temporal_callbacks.brush_changed({"xaxis.autorange": True}, temporal_filter) is None

    # The NL and Cypher paths re-run their stored payload unchanged.
    nl_response = {
        "cypher": "M",
        "results": _result()["results"],
        "coverage": {},
        "diagnosis": None,
        "notes": [],
        "validation_errors": [],
        "plan_rejection": None,
    }
    nl_calls = _recording_fake(monkeypatch, "post_query_nl", nl_response)
    temporal_callbacks.requery(
        temporal_filter, {"path": "nl", "question": "Who owns whom?"}, schema
    )
    assert nl_calls == [(("Who owns whom?",), {})]
    cy_response = {
        "cypher": "M",
        "results": _result()["results"],
        "coverage": {},
        "diagnosis": None,
        "notes": [],
    }
    cy_calls = _recording_fake(monkeypatch, "post_query_cypher", cy_response)
    temporal_callbacks.requery(
        temporal_filter, {"path": "cypher", "cypher": "MATCH (n) RETURN n"}, schema
    )
    assert cy_calls == [(("MATCH (n) RETURN n",), {})]


# ---------------------------------------------------------------------------
# Run paths and the boot load
# ---------------------------------------------------------------------------


def test_run_paths_store_the_executed_cypher_and_session(monkeypatch: pytest.MonkeyPatch):
    """AC-26: generated Cypher is displayed and editable in every outcome —
    the run callbacks write it into the console textarea alongside the
    session the brush re-query consumes."""
    from limes.ui.callbacks import query as query_callbacks

    response = {
        "cypher": "MATCH (n) RETURN n LIMIT 500",
        "results": _result()["results"],
        "coverage": {},
        "diagnosis": None,
        "notes": [],
    }
    nl_response = {**response, "question": "q", "validation_errors": [], "plan_rejection": None}
    _recording_fake(monkeypatch, "post_query_nl", nl_response)
    current, session, cypher, error = query_callbacks.run_nl(1, 0, "Which corporations?")
    assert cypher == "MATCH (n) RETURN n LIMIT 500"
    assert session == {"path": "nl", "question": "Which corporations?"}
    assert current["results"]["counts"]["rows"] == 1
    assert error == ""

    _recording_fake(monkeypatch, "post_query_cypher", response)
    current, session, cypher, error = query_callbacks.run_cypher(1, "MATCH (n) RETURN n")
    assert session == {"path": "cypher", "cypher": "MATCH (n) RETURN n"}
    assert cypher == "MATCH (n) RETURN n LIMIT 500"

    spec = {"start_type": "Corporation", "start_filters": {}, "hops": []}
    _recording_fake(monkeypatch, "post_query_builder", response)
    current, session, cypher, error = query_callbacks.run_builder(1, spec)
    assert session == {"path": "builder", "spec": spec}


def test_boot_loads_schema_ledger_saved_and_status(monkeypatch: pytest.MonkeyPatch):
    from limes.ui.callbacks import query as query_callbacks

    _recording_fake(monkeypatch, "get_builder_schema", _schema())
    _recording_fake(
        monkeypatch,
        "get_cost_ledger",
        {"period": "2026-08", "spend_eur": 0.5, "remaining_eur": 9.5, "entries": []},
    )
    _recording_fake(
        monkeypatch,
        "get_saved_queries",
        [
            {
                "saved_query_id": "sq1",
                "question": "q",
                "cypher": "C",
                "ontology_version": "1.0.0",
                "result_count": 1,
                "created_at": "2026-08-01T00:00:00",
                "pinned": False,
            }
        ],
    )
    _recording_fake(
        monkeypatch,
        "get_sources",
        [{"source_id": "gisco_nuts", "trust_rank": 1.0, "last_success_at": None}],
    )
    _recording_fake(monkeypatch, "get_ingest_status", [])
    _recording_fake(monkeypatch, "get_health", {"status": "ok", "ontology_version": "1.0.0"})

    schema, ledger, saved, system, health = query_callbacks.boot(1)
    assert schema["entity_types"]
    assert ledger["remaining_eur"] == 9.5
    assert saved[0]["saved_query_id"] == "sq1"
    assert system["sources"][0]["source_id"] == "gisco_nuts"
    assert health["status"] == "ok"


# ---------------------------------------------------------------------------
# api_client against the live API
# ---------------------------------------------------------------------------


def test_api_client_reaches_the_live_api(
    live_api: str, seeded: dict[str, str], monkeypatch: pytest.MonkeyPatch
):
    """The UI's only HTTP boundary, exercised as HTTP: every read function
    against the real server process, the error envelope on a 404, and the
    AC-28 evidence-document gap as the API actually answers it."""
    monkeypatch.setenv("LIMES_API_BASE_URL", live_api)
    monkeypatch.setenv("LIMES_API_TOKEN", "test-api-token")

    health = api_client.get_health()
    assert health["status"] == "ok"
    assert health["ontology_version"] == "1.0.0"

    schema = api_client.get_builder_schema()
    assert schema["entity_types"] and schema["relation_types"]

    response = api_client.post_query_cypher(
        "MATCH (a:Corporation)-[:SUBSIDIARY_OF]->(b) RETURN a, b"
    )
    assert response["results"]["counts"]["rows"] >= 1
    assert response["coverage"] is not None

    entity = api_client.get_entity(seeded["alpha"])
    assert entity["entity"]["entity_id"] == seeded["alpha"]
    neighbors = api_client.get_entity_neighbors(seeded["alpha"])
    assert neighbors["neighbors"]

    hits = api_client.search("alpha")
    assert any(hit["id"] == seeded["alpha"] for hit in hits)

    sources = api_client.get_sources()
    assert any(source["source_id"] == "gisco_nuts" for source in sources)
    ledger = api_client.get_cost_ledger()
    assert "spend_eur" in ledger
    assert "remaining_eur" not in ledger
    api_client.get_ingest_status()
    saved = api_client.get_saved_queries()
    assert isinstance(saved, list)

    with pytest.raises(api_client.ApiError) as exc_info:
        api_client.get_entity("no-such-entity")
    assert exc_info.value.status == 404

    with pytest.raises(api_client.ApiError):
        api_client.get_entity(DOC_HASH)  # no :Document node exists (D-10)
