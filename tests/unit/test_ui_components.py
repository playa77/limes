# tests/unit/test_ui_components.py | v1.0.0 | introduced by WP-40
"""Pure-render UI component tests per Doc 2 §8.13.

The components render from stores — they hold no type names, no relation
names, and no Cypher (NG-08); the render functions are pure, so each
branch is exercised by calling them directly with crafted store values.
The Dash layout and app construction are exercised here too: constructing
`layout()` and `create_app()` performs no HTTP and needs no server.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from limes.api.builder import project_for_builder
from limes.ontology.registry import load_ontology
from limes.ui import api_client as api_client_module
from limes.ui.app import create_app
from limes.ui.components import builder as builder_component
from limes.ui.components import coverage as coverage_component
from limes.ui.components import map as map_component
from limes.ui.components import network as network_component
from limes.ui.components import provenance as provenance_component
from limes.ui.components import timeline as timeline_component
from limes.ui.layout import layout, render_saved_queries, render_system_status

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"
SCHEMA = project_for_builder(load_ontology(ONTOLOGY_PATH))


# --------------------------------------------------------------------------
# The page layout
# --------------------------------------------------------------------------


def test_layout_constructs_the_full_screen():
    tree = layout()
    assert tree is not None


def test_render_saved_queries_empty_and_populated():
    empty = render_saved_queries(None)
    assert "No saved queries yet." in str(empty)
    populated = render_saved_queries(
        [
            {
                "question": "Who supplies BMW?",
                "cypher": "MATCH (a) RETURN a LIMIT 5",
                "result_count": 3,
                "created_at": "2026-08-01T10:00:00+00:00",
            }
        ]
    )
    assert "Who supplies BMW?" in str(populated)
    assert "3 rows" in str(populated)


def test_render_system_status_all_sections():
    panel = render_system_status(
        sources=[
            {"source_id": "gleif", "trust_rank": 0.9, "last_success_at": "2026-08-01T10:00:00"}
        ],
        runs=[
            {
                "source_id": "gleif",
                "mode": "ingest",
                "assertions_written": 5,
                "assertions_skipped": 1,
                "assertions_rejected": 0,
                "errors": 0,
            }
        ],
        ledger={"remaining_eur": "8.00", "spend_eur": "2.00", "period": "2026-08"},
        health={"status": "ok", "ontology_version": "1.0.0"},
    )
    text = str(panel)
    assert "API: ok" in text
    assert "Spend:" in text
    assert "gleif" in text
    assert "Latest runs" in text


def test_render_system_status_empty_state():
    assert "Div([])" in str(render_system_status(None, None, None, None))


# --------------------------------------------------------------------------
# The coverage panel
# --------------------------------------------------------------------------


def test_coverage_panel_empty_and_populated():
    empty = coverage_component.render(None)
    assert "No query executed yet." in str(empty)
    rendered = coverage_component.render(
        {
            "coverage": {
                "relation_counts": {"SUBSIDIARY_OF": 4},
                "contributing_sources": ["gleif"],
                "source_refresh": {"gleif": "2026-08-01T10:00:00"},
            },
            "diagnosis": {"clause_index": 1, "failing_clause": "MATCH (a)", "note": "no rows"},
            "notes": ["limit applied"],
        }
    )
    text = str(rendered)
    assert "SUBSIDIARY_OF: 4" in text
    assert "gleif (last refresh 2026-08-01T10:00:00)" in text
    assert "Failing clause 2" in text
    assert "no rows" in text
    assert "limit applied" in text


def test_coverage_panel_no_relations_and_missing_refresh():
    rendered = coverage_component.render(
        {
            "coverage": {"relation_counts": {}, "contributing_sources": ["fsd"]},
            "diagnosis": None,
            "notes": [],
        }
    )
    text = str(rendered)
    assert "No relations in the executed query." in text
    assert "fsd (last refresh never)" in text


# --------------------------------------------------------------------------
# Builder helpers and rendering
# --------------------------------------------------------------------------


def test_builder_directions_targets_and_temporality():
    assert "SUBSIDIARY_OF" in [
        e["relation"] for e in builder_component.relations_for(SCHEMA, "Corporation")
    ]
    directions = builder_component.directions_for(SCHEMA, "Corporation", "SUBSIDIARY_OF")
    assert set(directions) == {"out", "in"}
    assert builder_component.directions_for(SCHEMA, "Corporation", "REPEALS") == []
    assert builder_component.targets_for(SCHEMA, "Corporation", "SUBSIDIARY_OF", "out") == [
        "Corporation"
    ]
    assert builder_component.is_temporal(SCHEMA, "SUBSIDIARY_OF") is True
    assert builder_component.is_temporal(SCHEMA, "NOTHING") is False


def test_builder_property_helpers():
    assert builder_component.properties_for(SCHEMA, "Corporation")[:1][0]["name"] == "label"
    assert builder_component.properties_for(SCHEMA, "NoSuchType") == []
    assert builder_component.property_type(SCHEMA, "Corporation", "lei") == "string"
    assert builder_component.property_type(SCHEMA, "Corporation", "nope") == "string"
    assert builder_component.coerce_filter_value("float", "3.5") == 3.5
    assert builder_component.coerce_filter_value("float", "abc") == "abc"
    assert builder_component.coerce_filter_value("string", "abc") == "abc"
    assert builder_component.input_type_for("float") == "number"
    assert builder_component.input_type_for("string") == "text"
    assert builder_component.empty_spec("Corporation")["start_type"] == "Corporation"
    assert builder_component.empty_spec()["start_type"] is None


def test_builder_current_type_and_filters():
    from limes.ui.components.builder import _hop_filter, _start_filter, current_type

    spec = {"start_type": "Corporation", "start_filters": {"lei": "X"}, "hops": []}
    assert current_type(SCHEMA, spec, 0) == "Corporation"
    assert current_type(SCHEMA, None, 0) is None
    assert current_type(SCHEMA, {"start_type": None, "hops": []}, 0) is None
    properties = builder_component.properties_for(SCHEMA, "Corporation")
    assert _start_filter(properties, spec) == ("lei", "X")
    hop = {"filters": {"label": "BMW"}}
    assert _hop_filter(properties, hop) == ("label", "BMW")
    assert _start_filter(properties, {"start_filters": {}}) == ("", "")


def test_builder_render_without_schema():
    assert "Builder schema not loaded yet." in str(builder_component.render(None, None))


# --------------------------------------------------------------------------
# The panes
# --------------------------------------------------------------------------


def test_network_merge_neighborhood_accepts_a_bare_results_dict():
    # The stored value is the query envelope; a bare results dict is
    # tolerated (§8.13) and merged without an envelope wrapper.
    neighbors = {
        "neighbors": [
            {
                "neighbor": {"entity_id": "e2", "label": "Beta"},
                "edge": {"relation": "SUBSIDIARY_OF", "subject_id": "e1", "object_id": "e2"},
            }
        ]
    }
    merged = network_component.merge_neighborhood({"nodes": [], "edges": []}, neighbors)
    assert merged["nodes"][0]["entity_id"] == "e2"
    assert merged["edges"][0]["relation"] == "SUBSIDIARY_OF"
    assert "results" not in merged


def test_map_selection_highlights_edge_endpoints_and_missing_coords():
    selected = map_component._selected_entity_ids(
        {"kind": "edge", "edge": {"subject_id": "a", "object_id": ""}}
    )
    assert selected == {"a"}
    assert map_component._selected_entity_ids({"kind": "node", "entity": {"entity_id": "x"}}) == {
        "x"
    }
    assert map_component._selected_entity_ids(None) == set()
    assert map_component._selected_entity_ids({"kind": "other"}) == set()
    # A node without coordinates is not a map node (the map is a lookup,
    # never a geometry computation).
    assert (
        map_component._coordinate_nodes(
            {"nodes": [{"entity_id": "n", "type": "Corporation", "properties": {}}]},
            {"Corporation"},
        )
        == []
    )


def test_timeline_parse_instant_and_edge_branches():
    from datetime import UTC, datetime

    assert timeline_component._parse_instant("2026-08-01T10:00:00") == datetime(2026, 8, 1, 10, 0)
    assert timeline_component._parse_instant(None) is None
    assert timeline_component._parse_instant("not-an-instant") is None
    native = datetime(2026, 8, 1, tzinfo=UTC)
    assert timeline_component._parse_instant(native) is native


def test_timeline_figure_skips_edges_without_a_recorded_instant():
    fig = timeline_component.figure(
        {
            "nodes": [{"entity_id": "a", "type": "Corporation", "label": "A"}],
            "edges": [
                {
                    "relation": "SUBSIDIARY_OF",
                    "subject_id": "a",
                    "object_id": "b",
                    "valid_from": "2026-01-01",
                    "valid_to": "2026-06-01",
                    "recorded_at": None,
                },
                {
                    "relation": "SUBSIDIARY_OF",
                    "subject_id": "a",
                    "object_id": "b",
                    "valid_from": None,
                    "recorded_at": "bogus",
                },
            ],
        },
        None,
        None,
    )
    assert fig is not None


def test_timeline_figure_tolerates_a_malformed_filter_range():
    # A range that is truthy but not indexable to two values must not
    # kill the render — the brush state is operator-generated.
    fig = timeline_component.figure(
        {"nodes": [], "edges": []},
        None,
        {"range": ["2026-01-01"]},
    )
    assert fig is not None


# --------------------------------------------------------------------------
# Provenance
# --------------------------------------------------------------------------


def test_provenance_no_selection_and_node_selection(tmp_path):
    empty = provenance_component.render(None, api_client_module)
    assert "Select an edge or node." in str(empty)

    class _DetailApi:
        def __init__(self, detail: dict[str, Any] | None, error: bool = False) -> None:
            self._detail = detail or {}
            self._error = error

        def get_entity(self, entity_id: str) -> dict[str, Any]:
            if self._error:
                raise RuntimeError("boom")
            return self._detail

    detail_api = _DetailApi(
        {
            "entity": {
                "entity_id": "a",
                "label": "A",
                "type": "Corporation",
                "properties": {"lei": "X", "label_embedding": [1.0]},
            },
            "edge_summary": {"out": {"SUBSIDIARY_OF": 2}, "in": {}},
        }
    )
    rendered = provenance_component.render(
        {"kind": "node", "entity": {"entity_id": "a", "type": "Corporation"}}, detail_api
    )
    text = str(rendered)
    assert "lei" in text
    assert "out · SUBSIDIARY_OF" in text

    failing = provenance_component.render(
        {"kind": "node", "entity": {"entity_id": "a", "type": "Corporation"}},
        _DetailApi({}, error=True),
    )
    assert failing is not None


def test_provenance_originating_sentence():
    class _BodyApi:
        def __init__(self, body: str | None, error: bool = False) -> None:
            self._body = body
            self._error = error

        def get_entity(self, entity_id: str) -> dict[str, Any]:
            if self._error:
                raise RuntimeError("not available")
            return {"entity": {"properties": {"body": self._body}}}

    edge = {"evidence_document_id": "doc-1", "evidence_start": 1, "evidence_end": 6}
    sentence, note = provenance_component._originating_sentence(edge, _BodyApi("xhello!"))
    assert sentence == "hello"
    assert note is None
    assert provenance_component._originating_sentence({}, _BodyApi("x")) == (None, None)
    missing_body, note = provenance_component._originating_sentence(
        {"evidence_document_id": "doc-1", "evidence_start": 1, "evidence_end": 2},
        _BodyApi("x", error=True),
    )
    assert missing_body is None
    assert note == "evidence document not available through the API"
    no_body, note = provenance_component._originating_sentence(
        {"evidence_document_id": "doc-1", "evidence_start": 1, "evidence_end": 2}, _BodyApi(None)
    )
    assert no_body is None
    assert "no extractable body" in note


# --------------------------------------------------------------------------
# api_client — the remaining endpoint wrappers (respx-mocked, no network)
# --------------------------------------------------------------------------


@pytest.fixture
def api_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LIMES_API_BASE_URL", "https://ui-api.test")
    return "https://ui-api.test"


def test_api_client_endpoint_wrappers(api_env: str):
    import respx
    from httpx import Response

    with respx.mock(base_url=api_env) as router:
        router.get("/ontology").mock(return_value=Response(200, json={"version": "1.0.0"}))
        router.post("/query/nl").mock(
            return_value=Response(200, json={"cypher": "MATCH (a) RETURN a LIMIT 5"})
        )
        router.post("/query/builder").mock(return_value=Response(200, json={"cypher": "x"}))
        router.get("/search").mock(return_value=Response(200, json=[{"id": "e1"}]))
        router.post("/coverage").mock(return_value=Response(200, json={"relation_counts": {}}))
        router.post("/saved-queries").mock(return_value=Response(200, json={"id": "q1"}))
        router.delete("/saved-queries/q1").mock(return_value=Response(200, json={"deleted": True}))

        assert api_client_module.get_ontology()["version"] == "1.0.0"
        assert api_client_module.post_query_nl("question")["cypher"].startswith("MATCH")
        assert api_client_module.post_query_builder({"start_type": "Corporation"})["cypher"] == "x"
        hits = api_client_module.search("query", kind="Corporation", limit=10)
        assert hits == [{"id": "e1"}]
        assert (
            api_client_module.post_coverage(relation_types=["SUBSIDIARY_OF"])["relation_counts"]
            == {}
        )
        assert api_client_module.post_saved_query("q", "cypher")["id"] == "q1"
        assert api_client_module.delete_saved_query("q1") == {"deleted": True}


def test_api_client_raises_api_error_with_the_envelope(api_env: str):
    import respx
    from httpx import Response

    from limes.ui.api_client import ApiError

    with respx.mock(base_url=api_env) as router:
        router.get("/health").mock(
            return_value=Response(
                503,
                json={"error": {"code": "NEO4J_UNREACHABLE", "message": "down"}},
                headers={"content-type": "application/json"},
            )
        )
        with pytest.raises(ApiError) as excinfo:
            api_client_module.get_health()
        assert excinfo.value.code == "NEO4J_UNREACHABLE"
        assert excinfo.value.status == 503


# --------------------------------------------------------------------------
# The Dash application construction
# --------------------------------------------------------------------------


def test_create_app_builds_the_dash_application():
    app = create_app()
    assert app.title == "LIMES"
    assert app.layout is not None


def test_app_module_entry_point_runs_the_server(monkeypatch: pytest.MonkeyPatch):
    # `python -m limes.ui.app` executes the module as __main__; the server
    # call is stubbed (a real run blocks). runpy keeps the tracer on the
    # module entry-point lines.
    import runpy

    from dash import Dash

    monkeypatch.setattr(Dash, "run", lambda self, **kwargs: None)
    runpy.run_module("limes.ui.app", run_name="__main__")
