# tests/unit/test_ui_callbacks.py | v1.0.0 | introduced by WP-40
"""UI callback unit tests per Doc 2 §8.13.

The callbacks are split into pure functions (the `*_wrapper` bodies in
`register` forward to them) and the dash wiring. The pure functions are
tested directly with the API module and the dash callback context stubbed:
`api_client` attributes are monkeypatched per test, and the callback
context is set through `dash._callback_context.context_value` — the only
place `ctx.triggered` reads. `register` is exercised against a recording
fake app, which also captures the wrappers so their forwarding bodies can
be invoked.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from dash import _callback_context
from dash.exceptions import PreventUpdate

from limes.api.builder import project_for_builder
from limes.ontology.registry import load_ontology
from limes.ui import api_client as api_module
from limes.ui.api_client import ApiError
from limes.ui.callbacks import query as query_callbacks
from limes.ui.callbacks import selection as selection_callbacks
from limes.ui.callbacks import temporal as temporal_callbacks

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = project_for_builder(load_ontology(REPO_ROOT / "ontology" / "ontology.yaml"))

RESPONSE_OK = {
    "cypher": "MATCH (a) RETURN a LIMIT 500",
    "results": {"nodes": [], "edges": [], "counts": {"rows": 0, "nodes": 0, "edges": 0}},
}

HOP_EMPTY = {
    "relation": None,
    "direction": None,
    "target_type": None,
    "temporal_qualifier": None,
    "temporal_instant": None,
    "filters": {},
}

SPEC_ONE_HOP = {"start_type": "Corporation", "start_filters": {}, "hops": [dict(HOP_EMPTY)]}


@pytest.fixture(autouse=True)
def _empty_callback_context():
    """Every test starts with an empty dash callback context; a test that
    needs a trigger sets it explicitly. The value must be truthy — dash's
    `has_context` guard raises outside any callback context."""
    before = _callback_context.context_value.get()
    _callback_context.context_value.set(SimpleNamespace(triggered_inputs=[]))
    yield
    _callback_context.context_value.set(before)


def _set_trigger(component_type: str, index: Any, prop: str = "value") -> None:
    component_id = json.dumps({"type": component_type, "index": index})
    _callback_context.context_value.set(
        SimpleNamespace(triggered_inputs=[{"prop_id": f"{component_id}.{prop}", "value": None}])
    )


class _FakeApp:
    """A recording app: `callback` stores the decorated function so the
    wrapper bodies can be invoked directly."""

    def __init__(self) -> None:
        self.callbacks: list[Any] = []

    def callback(self, *args: Any, **kwargs: Any) -> Any:
        def decorator(fn: Any) -> Any:
            self.callbacks.append(fn)
            return fn

        return decorator


# --------------------------------------------------------------------------
# query callbacks
# --------------------------------------------------------------------------


def test_error_text_formats_api_and_unexpected_errors():
    assert query_callbacks._error_text(ApiError("NEO4J_UNREACHABLE", "down", 503)) == (
        "[NEO4J_UNREACHABLE] down"
    )
    assert "unexpected error" in query_callbacks._error_text(RuntimeError("boom"))


def test_run_response_handles_rejected_and_failed_outcomes():
    rejected = query_callbacks._run_response(
        {"results": None, "validation_errors": ["bad clause"], "cypher": "MATCH (a)"},
        {"path": "nl"},
    )
    assert rejected[3] == "bad clause"
    plan_rejected = query_callbacks._run_response(
        {
            "results": None,
            "validation_errors": [],
            "plan_rejection": {"reason": "rows", "note": "n", "operators": "x"},
            "cypher": "MATCH (a)",
        },
        {"path": "nl"},
    )
    assert plan_rejected[3] == "plan rejected: reason=rows"
    ok = query_callbacks._run_response(RESPONSE_OK, {"path": "cypher"})
    assert ok[3] == ""


def test_run_nl_guard_and_success_paths(monkeypatch: pytest.MonkeyPatch):
    with pytest.raises(PreventUpdate):
        query_callbacks.run_nl(None, None, "question")
    with pytest.raises(PreventUpdate):
        query_callbacks.run_nl(1, None, "   ")
    monkeypatch.setattr(api_module, "post_query_nl", lambda question: RESPONSE_OK)
    outcome = query_callbacks.run_nl(1, None, "question")
    assert outcome[0] is RESPONSE_OK
    assert outcome[1] == {"path": "nl", "question": "question"}
    monkeypatch.setattr(
        api_module, "post_query_nl", lambda question: (_ for _ in ()).throw(ApiError("E", "m", 400))
    )
    outcome = query_callbacks.run_nl(1, None, "question")
    assert outcome == (None, None, None, "[E] m")


def test_run_cypher_guard_and_success_paths(monkeypatch: pytest.MonkeyPatch):
    with pytest.raises(PreventUpdate):
        query_callbacks.run_cypher(None, "MATCH (a) RETURN a LIMIT 5")
    with pytest.raises(PreventUpdate):
        query_callbacks.run_cypher(1, "")
    monkeypatch.setattr(api_module, "post_query_cypher", lambda cypher, params=None: RESPONSE_OK)
    outcome = query_callbacks.run_cypher(1, "MATCH (a) RETURN a LIMIT 5")
    assert outcome[0] is RESPONSE_OK
    assert outcome[1] == {"path": "cypher", "cypher": "MATCH (a) RETURN a LIMIT 5"}
    monkeypatch.setattr(
        api_module,
        "post_query_cypher",
        lambda cypher, params=None: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    outcome = query_callbacks.run_cypher(1, "MATCH (a) RETURN a LIMIT 5")
    assert "unexpected error" in outcome[3]


def test_run_builder_guard_and_success_paths(monkeypatch: pytest.MonkeyPatch):
    with pytest.raises(PreventUpdate):
        query_callbacks.run_builder(None, SPEC_ONE_HOP)
    with pytest.raises(PreventUpdate):
        query_callbacks.run_builder(1, None)
    with pytest.raises(PreventUpdate):
        query_callbacks.run_builder(1, {"start_type": None, "hops": []})
    monkeypatch.setattr(api_module, "post_query_builder", lambda spec: RESPONSE_OK)
    outcome = query_callbacks.run_builder(1, SPEC_ONE_HOP)
    assert outcome[0] is RESPONSE_OK
    assert outcome[1]["path"] == "builder"
    monkeypatch.setattr(
        api_module,
        "post_query_builder",
        lambda spec: (_ for _ in ()).throw(ApiError("B", "bad", 400)),
    )
    outcome = query_callbacks.run_builder(1, SPEC_ONE_HOP)
    assert outcome[3] == "[B] bad"


def test_boot_loads_all_stores(monkeypatch: pytest.MonkeyPatch):
    with pytest.raises(PreventUpdate):
        query_callbacks.boot(None)
    monkeypatch.setattr(api_module, "get_builder_schema", lambda: {"version": "1.0.0"})
    monkeypatch.setattr(api_module, "get_cost_ledger", lambda: {"remaining_eur": "8"})
    monkeypatch.setattr(api_module, "get_saved_queries", lambda: [])
    monkeypatch.setattr(api_module, "get_sources", lambda: [])
    monkeypatch.setattr(api_module, "get_ingest_status", lambda: [])
    monkeypatch.setattr(api_module, "get_health", lambda: {"status": "ok"})
    schema, ledger, saved, system, health = query_callbacks.boot(1)
    assert schema["version"] == "1.0.0"
    assert system == {"sources": [], "runs": []}
    assert health["status"] == "ok"
    monkeypatch.setattr(
        api_module, "get_health", lambda: (_ for _ in ()).throw(RuntimeError("down"))
    )
    with pytest.raises(PreventUpdate):
        query_callbacks.boot(1)


def test_saved_hit_options_labels():
    hits = [{"id": "e1", "label": "Alpha", "kind": "Corporation"}, {"id": "e2"}]
    options = query_callbacks._saved_hit_options(hits)
    assert options[0] == {"label": "Alpha (Corporation)", "value": "e1"}
    assert options[1]["label"].startswith("e2")


def test_search_run_guard_and_hits(monkeypatch: pytest.MonkeyPatch):
    with pytest.raises(PreventUpdate):
        query_callbacks.search_run(None, None, "q")
    with pytest.raises(PreventUpdate):
        query_callbacks.search_run(1, None, "")
    monkeypatch.setattr(api_module, "search", lambda query, limit=50: [{"id": "e1", "label": "A"}])
    options, store = query_callbacks.search_run(1, None, "alpha")
    assert options == [{"label": "A ()", "value": "e1"}]
    assert store == {"hits": [{"id": "e1", "label": "A"}]}


def test_search_select_guard_and_merge(monkeypatch: pytest.MonkeyPatch):
    with pytest.raises(PreventUpdate):
        query_callbacks.search_select(None, None, None)
    monkeypatch.setattr(
        api_module, "get_entity_neighbors", lambda entity_id, filters: {"neighbors": []}
    )
    monkeypatch.setattr(
        "limes.ui.components.network.merge_neighborhood",
        lambda current, neighbors: {"merged": True},
    )
    merged, selection = query_callbacks.search_select("e1", None, {"as_of": "2026-01-01"})
    assert merged == {"merged": True}
    assert selection == {"kind": "node", "entity": {"entity_id": "e1"}}


def test_saved_load_guards_and_success(monkeypatch: pytest.MonkeyPatch):
    saved = [{"question": "q", "cypher": "c"}]
    with pytest.raises(PreventUpdate):
        query_callbacks.saved_load(None, saved)
    _set_trigger("saved-load", 0)
    with pytest.raises(PreventUpdate):
        query_callbacks.saved_load([None, None], saved)
    _set_trigger("saved-load", 1)
    with pytest.raises(PreventUpdate):
        query_callbacks.saved_load([None, 1], saved)  # index beyond the list
    _set_trigger("saved-load", 0)
    assert query_callbacks.saved_load([1], saved) == ("q", "c")


def test_saved_delete_guard_and_success(monkeypatch: pytest.MonkeyPatch):
    saved = [{"saved_query_id": "q1"}, {"saved_query_id": "q2"}]
    with pytest.raises(PreventUpdate):
        query_callbacks.saved_delete(None, saved)
    _set_trigger("saved-delete", 0)
    deleted = []
    monkeypatch.setattr(
        api_module, "delete_saved_query", lambda saved_query_id: deleted.append(saved_query_id)
    )
    remaining = query_callbacks.saved_delete([1], saved)
    assert deleted == ["q1"]
    assert remaining == [{"saved_query_id": "q2"}]


def test_builder_start_type_branches():
    with pytest.raises(PreventUpdate):
        query_callbacks.builder_start_type(None, "Corporation", None)
    spec, rendered = query_callbacks.builder_start_type(SCHEMA, None, SPEC_ONE_HOP)
    assert spec is SPEC_ONE_HOP
    assert rendered is not None
    spec, rendered = query_callbacks.builder_start_type(SCHEMA, None, None)
    assert spec["start_type"] is None
    new_spec, rendered = query_callbacks.builder_start_type(SCHEMA, "Corporation", None)
    assert new_spec["start_type"] == "Corporation"
    assert new_spec["hops"] == []


def _hop_call(control: str, value: Any, hop: dict[str, Any] | None = None):
    """Invoke builder_hop_change for one control with the given value."""
    _set_trigger(control, 0)
    spec = {"start_type": "Corporation", "start_filters": {}, "hops": [hop or dict(HOP_EMPTY)]}
    return query_callbacks.builder_hop_change(
        relation=value if control == "builder-rel" else None,
        direction=value if control == "builder-dir" else None,
        target=value if control == "builder-target" else None,
        qualifier=value if control == "builder-qualifier" else None,
        instant=value if control == "builder-instant" else None,
        filter_prop=value if control == "builder-filter-prop" else None,
        filter_value=value if control == "builder-filter-value" else None,
        remove=value if control == "builder-remove" else None,
        spec=spec,
        schema=SCHEMA,
    )


def test_builder_hop_change_guards():
    with pytest.raises(PreventUpdate):
        query_callbacks.builder_hop_change(
            None, None, None, None, None, None, None, None, None, None
        )
    with pytest.raises(PreventUpdate):
        query_callbacks.builder_hop_change(
            None, None, None, None, None, None, None, None, SPEC_ONE_HOP, None
        )
    with pytest.raises(PreventUpdate):
        query_callbacks.builder_hop_change(
            None, None, None, None, None, None, None, None, SPEC_ONE_HOP, SCHEMA
        )  # no trigger context -> control None
    _callback_context.context_value.set(
        SimpleNamespace(triggered_inputs=[{"prop_id": '{"broken.value'}])
    )
    with pytest.raises(PreventUpdate):
        query_callbacks.builder_hop_change(
            None, None, None, None, None, None, None, None, SPEC_ONE_HOP, SCHEMA
        )  # undecodable prop_id -> control None
    _set_trigger("builder-rel", 1)
    spec = {"start_type": "Corporation", "start_filters": {}, "hops": [dict(HOP_EMPTY)]}
    with pytest.raises(PreventUpdate):
        query_callbacks.builder_hop_change(
            "SUBSIDIARY_OF", None, None, None, None, None, None, None, spec, SCHEMA
        )  # index beyond hops
    _set_trigger("builder-rel", 1)
    two_hops = {
        "start_type": "Corporation",
        "start_filters": {},
        "hops": [dict(HOP_EMPTY), {**HOP_EMPTY, "target_type": None}],
    }
    with pytest.raises(PreventUpdate):
        query_callbacks.builder_hop_change(
            "SUBSIDIARY_OF", None, None, None, None, None, None, None, two_hops, SCHEMA
        )  # current_type None
    with pytest.raises(PreventUpdate):
        query_callbacks.builder_hop_change(
            None, None, None, None, None, None, None, None, {"start_type": None, "hops": []}, SCHEMA
        )  # current_type None via missing start_type guard


def test_builder_hop_change_relation_control():
    new_spec, rendered = _hop_call("builder-rel", "SUBSIDIARY_OF")
    hop = new_spec["hops"][0]
    assert hop["relation"] == "SUBSIDIARY_OF"
    assert hop["direction"] == "out"
    assert hop["target_type"] is None
    assert hop["temporal_qualifier"] is None
    new_spec, _ = _hop_call("builder-rel", None, {"relation": "SUBSIDIARY_OF"})
    assert new_spec["hops"][0]["relation"] is None
    assert new_spec["hops"][0]["filters"] == {}


def test_builder_hop_change_direction_control():
    hop = {**HOP_EMPTY, "relation": "SUBSIDIARY_OF", "direction": "out"}
    new_spec, _ = _hop_call("builder-dir", "in", hop)
    assert new_spec["hops"][0]["direction"] == "in"
    assert new_spec["hops"][0]["target_type"] is None
    new_spec, _ = _hop_call("builder-dir", "sideways", hop)
    assert new_spec["hops"][0]["direction"] == "out"


def test_builder_hop_change_target_control():
    hop = {**HOP_EMPTY, "relation": "SUBSIDIARY_OF", "direction": "out"}
    new_spec, _ = _hop_call("builder-target", "Corporation", hop)
    assert new_spec["hops"][0]["target_type"] == "Corporation"
    new_spec, _ = _hop_call("builder-target", "Sanction", hop)
    assert new_spec["hops"][0]["target_type"] is None
    hop_no_rel = {**HOP_EMPTY, "direction": "out"}
    with pytest.raises(PreventUpdate):
        _hop_call("builder-target", "Corporation", hop_no_rel)


def test_builder_hop_change_qualifier_and_instant_controls():
    new_spec, _ = _hop_call(
        "builder-qualifier", "current", {**HOP_EMPTY, "relation": "SUBSIDIARY_OF"}
    )
    assert new_spec["hops"][0]["temporal_qualifier"] == "current"
    hop = {**HOP_EMPTY, "temporal_qualifier": "as_of", "temporal_instant": "2026-01-01"}
    new_spec, _ = _hop_call("builder-qualifier", None, hop)
    assert new_spec["hops"][0]["temporal_qualifier"] is None
    assert new_spec["hops"][0]["temporal_instant"] is None
    hop = {**HOP_EMPTY, "temporal_qualifier": "as_of"}
    new_spec, _ = _hop_call("builder-instant", "2026-07-01", hop)
    assert new_spec["hops"][0]["temporal_instant"] == "2026-07-01"
    new_spec, _ = _hop_call(
        "builder-instant", "2026-07-01", {**HOP_EMPTY, "temporal_qualifier": None}
    )
    assert new_spec["hops"][0]["temporal_instant"] is None


def test_builder_hop_change_filter_controls():
    new_spec, _ = _hop_call("builder-filter-prop", "lei")
    assert new_spec["hops"][0]["filters"] == {"lei": ""}
    new_spec, _ = _hop_call("builder-filter-prop", None, {**HOP_EMPTY, "filters": {"lei": "X"}})
    assert new_spec["hops"][0]["filters"] == {}
    hop = {**HOP_EMPTY, "filters": {"lei": "X"}}
    new_spec, _ = _hop_call("builder-filter-value", "LEI-42", hop)
    assert new_spec["hops"][0]["filters"] == {"lei": "LEI-42"}
    new_spec, _ = _hop_call("builder-filter-value", "v", {**HOP_EMPTY, "filters": {}})
    assert new_spec["hops"][0]["filters"] == {}


def test_builder_hop_change_remove_control():
    new_spec, _ = _hop_call("builder-remove", 1)
    assert new_spec["hops"] == []
    new_spec, _ = _hop_call("builder-remove", None)
    assert len(new_spec["hops"]) == 1
    with pytest.raises(PreventUpdate):
        _hop_call("builder-unknown", "x")


def test_triggered_hop_control_decodes_the_context():
    with pytest.raises(PreventUpdate):
        query_callbacks.builder_add_hop(1, SPEC_ONE_HOP, None)
    with pytest.raises(PreventUpdate):
        query_callbacks.builder_add_hop(None, SPEC_ONE_HOP, SCHEMA)
    new_spec, rendered = query_callbacks.builder_add_hop(
        1, {"start_type": "Corporation", "start_filters": {}, "hops": []}, SCHEMA
    )
    assert len(new_spec["hops"]) == 1
    assert new_spec["hops"][0]["relation"] == "MEMBER_OF"
    assert rendered is not None
    # A spec whose last hop has no target yet has no current type: the new
    # hop cannot be constructed, so the append refuses.
    targetless = {
        "start_type": "Corporation",
        "start_filters": {},
        "hops": [{"relation": "SUBSIDIARY_OF", "target_type": None}],
    }
    with pytest.raises(PreventUpdate):
        query_callbacks.builder_add_hop(1, targetless, SCHEMA)


def test_render_system_status_and_saved_list():
    panel, badge, budget = query_callbacks._render_system_status(
        {"sources": [], "runs": []}, {"remaining_eur": "7.50"}, {"status": "ok"}
    )
    assert badge == "API: ok"
    assert budget == "€7.50 remaining"
    assert panel is not None
    panel, badge, budget = query_callbacks._render_system_status(None, None, None)
    assert badge == "API: unreachable"
    assert budget == "€? remaining"
    assert "No saved queries yet." in str(query_callbacks._render_saved_list(None))


# --------------------------------------------------------------------------
# selection callbacks
# --------------------------------------------------------------------------


def test_triggered_helpers_decode_pattern_ids():
    _set_trigger("saved-load", 3)
    assert selection_callbacks.triggered_prop_id() == '{"type": "saved-load", "index": 3}.value'
    assert selection_callbacks.triggered_index("saved-load") == 3
    assert selection_callbacks.triggered_index("other") is None
    _callback_context.context_value.set(
        SimpleNamespace(triggered_inputs=[{"prop_id": '{"broken.value'}])
    )
    assert selection_callbacks.triggered_index("saved-load") is None
    _callback_context.context_value.set(
        SimpleNamespace(
            triggered_inputs=[{"prop_id": '{"type": "saved-load", "index": "x"}.value'}]
        )
    )
    assert selection_callbacks.triggered_index("saved-load") is None
    _callback_context.context_value.set(SimpleNamespace(triggered_inputs=[]))
    assert selection_callbacks.triggered_prop_id() is None
    _set_trigger("map-marker", 7)
    assert selection_callbacks.triggered_marker_entity_id() == "7"
    _callback_context.context_value.set(SimpleNamespace(triggered_inputs=[{"prop_id": "x.value"}]))
    assert selection_callbacks.triggered_marker_entity_id() is None
    _callback_context.context_value.set(
        SimpleNamespace(triggered_inputs=[{"prop_id": '{"broken.value'}])
    )
    assert selection_callbacks.triggered_marker_entity_id() is None
    _callback_context.context_value.set(
        SimpleNamespace(triggered_inputs=[{"prop_id": '{"type": "saved-load", "index": 0}.value'}])
    )
    assert selection_callbacks.triggered_marker_entity_id() is None  # wrong component type
    _set_trigger("map-marker", None)
    assert selection_callbacks.triggered_marker_entity_id() is None


def test_node_tapped_selects_and_expands(monkeypatch: pytest.MonkeyPatch):
    with pytest.raises(PreventUpdate):
        selection_callbacks.node_tapped(None, None, None)
    monkeypatch.setattr(
        api_module, "get_entity_neighbors", lambda entity_id, filters: {"neighbors": []}
    )
    monkeypatch.setattr(
        "limes.ui.components.network.merge_neighborhood",
        lambda current, neighbors: {"merged": True},
    )
    selection, merged = selection_callbacks.node_tapped(
        {"entity_id": "e1", "label": "A", "type": "Corporation"}, {"nodes": []}, None
    )
    assert selection["entity"]["entity_id"] == "e1"
    assert merged == {"merged": True}
    monkeypatch.setattr(
        api_module,
        "get_entity_neighbors",
        lambda entity_id, filters: (_ for _ in ()).throw(RuntimeError("down")),
    )
    from dash import no_update

    selection, merged = selection_callbacks.node_tapped({"entity_id": "e1"}, None, None)
    assert selection["entity"]["entity_id"] == "e1"
    assert merged is no_update


def test_edge_tapped_guard_and_selection():
    with pytest.raises(PreventUpdate):
        selection_callbacks.edge_tapped(None)
    selection = selection_callbacks.edge_tapped({"edge": {"relation": "SUBSIDIARY_OF"}})
    assert selection["kind"] == "edge"


def test_marker_tapped_selects_from_the_store(monkeypatch: pytest.MonkeyPatch):
    with pytest.raises(PreventUpdate):
        selection_callbacks.marker_tapped([1], None)  # no trigger context
    _set_trigger("map-marker", "e1")
    with pytest.raises(PreventUpdate):
        selection_callbacks.marker_tapped(None, {"nodes": []})
    _set_trigger("map-marker", "e1")
    selection = selection_callbacks.marker_tapped(
        [1], {"nodes": [{"entity_id": "e1", "label": "A", "type": "Corporation"}]}
    )
    assert selection["entity"] == {"entity_id": "e1", "label": "A", "type": "Corporation"}
    _set_trigger("map-marker", "missing")
    selection = selection_callbacks.marker_tapped([1], {"nodes": []})
    assert selection["entity"] == {"entity_id": "missing", "label": None, "type": None}


def test_render_panes_tolerates_bare_results():
    network, map_pane, timeline = selection_callbacks.render_panes(
        {"results": {"nodes": [], "edges": [], "counts": {"rows": 0, "nodes": 0, "edges": 0}}},
        None,
        None,
        SCHEMA,
    )
    assert network is not None
    bare = selection_callbacks.render_panes({"nodes": [], "edges": []}, None, None, SCHEMA)
    assert bare[0] is not None
    assert selection_callbacks.render_provenance(None) is not None


# --------------------------------------------------------------------------
# temporal callbacks
# --------------------------------------------------------------------------


def test_normalize_instant_epoch_and_iso():
    from datetime import datetime

    assert temporal_callbacks._normalize_instant(1750000000000) == datetime.fromtimestamp(
        1750000000.0
    )
    assert temporal_callbacks._normalize_instant("2026-07-01T00:00:00") == datetime(2026, 7, 1)


def test_brush_changed_branches():
    with pytest.raises(PreventUpdate):
        temporal_callbacks.brush_changed(None, None)
    with pytest.raises(PreventUpdate):
        temporal_callbacks.brush_changed({"xaxis.range": ["bad", "2026-01-01"]}, None)
    brushed = temporal_callbacks.brush_changed(
        {"xaxis.range": ["2026-01-01T00:00:00", "2026-06-01T00:00:00"]}, None
    )
    assert brushed["as_of"] == "2026-06-01T00:00:00"
    assert brushed["range"] == ["2026-01-01T00:00:00", "2026-06-01T00:00:00"]
    with pytest.raises(PreventUpdate):
        temporal_callbacks.brush_changed(
            {"xaxis.range": ["2026-01-01T00:00:00", "2026-06-01T00:00:00"]}, brushed
        )  # identical window is a no-op
    with pytest.raises(PreventUpdate):
        temporal_callbacks.brush_changed({"xaxis.autorange": True}, None)
    assert temporal_callbacks.brush_changed({"xaxis.autorange": True}, {"as_of": "x"}) is None
    with pytest.raises(PreventUpdate):
        temporal_callbacks.brush_changed({"other": 1}, None)


def test_temporally_qualified_applies_only_to_temporal_relations():
    spec = {
        "start_type": "Corporation",
        "hops": [{"relation": "SUBSIDIARY_OF"}, {"relation": "AMENDS"}],
    }
    qualified = temporal_callbacks._temporally_qualified(spec, {"as_of": "2026-06-01"}, SCHEMA)
    assert qualified["hops"][0]["temporal_qualifier"] == "as_of"
    assert qualified["hops"][0]["temporal_instant"] == "2026-06-01"
    # The non-temporal relation is left exactly as carried.
    assert qualified["hops"][1] == {"relation": "AMENDS"}
    assert temporal_callbacks._temporally_qualified(spec, None, SCHEMA) == spec


def test_requery_paths(monkeypatch: pytest.MonkeyPatch):
    from dash import no_update

    with pytest.raises(PreventUpdate):
        temporal_callbacks.requery({"as_of": "x"}, None, SCHEMA)
    monkeypatch.setattr(api_module, "post_query_builder", lambda spec: RESPONSE_OK)
    qualified_spec = {
        "start_type": "Corporation",
        "start_filters": {},
        "hops": [{"relation": "SUBSIDIARY_OF", "direction": "out", "target_type": "Corporation"}],
    }
    builder_out = temporal_callbacks.requery(
        {"as_of": "2026-06-01"}, {"path": "builder", "spec": qualified_spec}, SCHEMA
    )
    assert builder_out[0] is RESPONSE_OK
    assert builder_out[2]["hops"][0]["temporal_qualifier"] == "as_of"
    assert builder_out[2]["hops"][0]["temporal_instant"] == "2026-06-01"
    assert builder_out[4] == ""
    monkeypatch.setattr(api_module, "post_query_nl", lambda question: RESPONSE_OK)
    nl_out = temporal_callbacks.requery({"as_of": "x"}, {"path": "nl", "question": "q"}, SCHEMA)
    assert nl_out[0] is RESPONSE_OK
    assert nl_out[2] is no_update
    monkeypatch.setattr(api_module, "post_query_cypher", lambda cypher, params=None: RESPONSE_OK)
    cypher_out = temporal_callbacks.requery(
        {"as_of": "x"}, {"path": "cypher", "cypher": "MATCH"}, SCHEMA
    )
    assert cypher_out[0] is RESPONSE_OK
    monkeypatch.setattr(
        api_module,
        "post_query_builder",
        lambda spec: (_ for _ in ()).throw(ApiError("E", "m", 400)),
    )
    failed = temporal_callbacks.requery(
        {"as_of": "2026-06-01"}, {"path": "builder", "spec": SPEC_ONE_HOP}, SCHEMA
    )
    assert failed[4] == "[E] m"
    with pytest.raises(PreventUpdate):
        temporal_callbacks.requery({"as_of": "x"}, {"path": "other"}, SCHEMA)


# --------------------------------------------------------------------------
# register() — the dash wiring and the forwarding wrapper bodies
# --------------------------------------------------------------------------


def test_register_wires_all_query_callbacks():
    app = _FakeApp()
    query_callbacks.register(app)
    assert len(app.callbacks) == 13
    with pytest.raises(PreventUpdate):
        app.callbacks[0](None, None, None)  # _run_nl_wrapper
    with pytest.raises(PreventUpdate):
        app.callbacks[1](None, None)  # _run_cypher_wrapper
    with pytest.raises(PreventUpdate):
        app.callbacks[2](None, None)  # _run_builder_wrapper
    with pytest.raises(PreventUpdate):
        app.callbacks[3](None)  # _boot_wrapper
    panel, badge, budget = app.callbacks[4](None, None, None)  # _status_wrapper
    assert badge == "API: unreachable"
    assert "No saved queries yet." in str(app.callbacks[5](None))  # _saved_list_wrapper
    with pytest.raises(PreventUpdate):
        app.callbacks[6](None, None, None)  # _search_run_wrapper
    with pytest.raises(PreventUpdate):
        app.callbacks[7](None, None, None)  # _search_select_wrapper
    with pytest.raises(PreventUpdate):
        app.callbacks[8](None, None)  # _saved_load_wrapper
    with pytest.raises(PreventUpdate):
        app.callbacks[9](None, None)  # _saved_delete_wrapper
    spec, rendered = app.callbacks[10](SCHEMA, None, None)  # _builder_start_wrapper
    assert spec["start_type"] is None
    with pytest.raises(PreventUpdate):
        app.callbacks[11](
            None, None, None, None, None, None, None, None, None, None
        )  # _builder_hop_wrapper
    with pytest.raises(PreventUpdate):
        app.callbacks[12](None, None, None)  # _builder_add_wrapper


def test_register_wires_all_selection_callbacks():
    app = _FakeApp()
    selection_callbacks.register(app)
    assert len(app.callbacks) == 5
    with pytest.raises(PreventUpdate):
        app.callbacks[0](None, None, None)  # _node_tapped_wrapper
    with pytest.raises(PreventUpdate):
        app.callbacks[1](None)  # _edge_tapped_wrapper
    with pytest.raises(PreventUpdate):
        app.callbacks[2](None, None)  # _marker_tapped_wrapper
    network, map_pane, timeline = app.callbacks[3](
        None, None, None, SCHEMA
    )  # _render_panes_wrapper
    assert network is not None
    assert app.callbacks[4](None) is not None  # _provenance_wrapper


def test_register_wires_all_temporal_callbacks():
    app = _FakeApp()
    temporal_callbacks.register(app)
    assert len(app.callbacks) == 2
    with pytest.raises(PreventUpdate):
        app.callbacks[0](None, None)  # _brush_wrapper
    with pytest.raises(PreventUpdate):
        app.callbacks[1](None, None, None)  # _requery_wrapper
