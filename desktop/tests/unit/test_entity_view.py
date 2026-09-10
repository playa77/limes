# desktop/tests/unit/test_entity_view.py | v0.1.0 | FR-DC-020/021/022, AC-DC-2 entity view
from __future__ import annotations

from typing import Any

from limes_desktop.api.models import (
    EntityDetail,
    GraphNeighbors,
    NeighborRow,
)
from limes_desktop.state import QueryOutcomeBundle, SessionState
from limes_desktop.views.entity import EntityView

# canned payloads shaped exactly like the real API responses (AC-DC-7 mirrors)


def _entity_payload() -> dict[str, Any]:
    return {
        "entity": {
            "entity_id": "p1",
            "type": "Person",
            "label": "Jane Doe",
            "properties": {
                "label": "Jane Doe",
                "wikidata_qid": "Q42",
                "valid_from": "2020-01-01T00:00:00Z",
                "recorded_at": "2026-08-30T12:00:00Z",
            },
            "ontology_version": "1.0.0",
            "created_at": "2020-01-01T00:00:00Z",
        },
        "edge_summary": {"out": {"MEMBER_OF": 3}, "in": {}},
    }


def _neighbor_payload() -> dict[str, Any]:
    return {
        "entity": _entity_payload()["entity"],
        "neighbors": [
            {
                "edge": {
                    "relation": "MEMBER_OF",
                    "subject_id": "p1",
                    "object_id": "org1",
                    "source_id": "bundestag",
                    "source_trust": 0.95,
                    "confidence": 0.98,
                    "recorded_at": "2026-08-30T12:00:00Z",
                    "valid_from": "2021-10-01T00:00:00Z",
                    "valid_to": None,
                    "retracted_at": None,
                    "assertion_id": "a-77",
                    "ontology_version": "1.0.0",
                    "extractor_model": "test-model",
                    "prompt_version": "2.1.0",
                    "schema_version": "2.0.0",
                    "evidence_document_id": "doc9",
                    "evidence_start": 0,
                    "evidence_end": 84,
                },
                "neighbor": {
                    "entity_id": "org1",
                    "type": "PublicBody",
                    "label": "Bundestag",
                    "properties": {"label": "Bundestag"},
                    "ontology_version": "1.0.0",
                    "created_at": "2020-01-01T00:00:00Z",
                },
            },
            {
                "edge": {
                    "relation": "DIRECTOR_OF",
                    "subject_id": "p1",
                    "object_id": "corp1",
                    "source_id": "gleif",
                    "source_trust": 0.9,
                    "confidence": 0.91,
                    "recorded_at": "2026-01-15T00:00:00Z",
                    "valid_from": "2024-01-01T00:00:00Z",
                    "valid_to": None,
                    "retracted_at": None,
                    "assertion_id": "a-80",
                    "ontology_version": "1.0.0",
                    "extractor_model": None,
                    "prompt_version": None,
                    "schema_version": None,
                    "evidence_document_id": None,
                    "evidence_start": None,
                    "evidence_end": None,
                },
                "neighbor": {
                    "entity_id": "corp1",
                    "type": "Corporation",
                    "label": "Acme GmbH",
                    "properties": {"label": "Acme GmbH"},
                    "ontology_version": "1.0.0",
                    "created_at": "2020-01-01T00:00:00Z",
                },
            },
        ],
    }


# The real GET /ontology response: ontology.model_dump(mode="json")
def _ontology_payload() -> dict[str, Any]:
    return {
        "version": "1.0.0",
        "supertypes": ["Agent", "Place", "Artifact"],
        "entity_types": [
            {
                "name": "Person",
                "supertype": "Agent",
                "identifying_keys": ["wikidata_qid"],
                "properties": [{"name": "label", "type": "string", "required": True}],
            },
            {
                "name": "PublicBody",
                "supertype": "Agent",
                "identifying_keys": ["wikidata_qid"],
                "properties": [{"name": "label", "type": "string", "required": True}],
            },
            {
                "name": "Corporation",
                "supertype": "Agent",
                "identifying_keys": ["lei"],
                "properties": [{"name": "label", "type": "string", "required": True}],
            },
        ],
        "relation_types": [
            {
                "name": "MEMBER_OF",
                "domain": ["Person"],
                "range": ["PublicBody"],
                "temporal": True,
            },
            {
                "name": "DIRECTOR_OF",
                "domain": ["Person"],
                "range": ["Corporation"],
                "temporal": True,
            },
        ],
    }


def _make_view(qtbot: Any, client: Any | None = None) -> tuple[EntityView, SessionState]:
    state = SessionState()
    view = EntityView(state, client_factory=(lambda: client) if client else None)
    qtbot.addWidget(view)
    view.set_ontology(_ontology_payload())
    return view, state


# -- FR-DC-020 / AC-DC-2: bitemporal rows under distinct labels ---------------


def test_bitemporal_properties_render_under_distinct_labels(qtbot: Any) -> None:
    view, _ = _make_view(qtbot)
    detail = EntityDetail.from_api(_entity_payload())
    view.show_entity(detail)

    table = view.property_table
    labels = [table.item(r, 0).text() for r in range(table.rowCount())]
    values = [table.item(r, 1).text() for r in range(table.rowCount())]

    assert "VALIDITY" in labels, "valid_from must be under a VALIDITY label"
    assert "BELIEF" in labels, "recorded_at must be under a BELIEF label"
    v_row = labels.index("VALIDITY")
    b_row = labels.index("BELIEF")
    assert "2020-01-01" in values[v_row]
    assert "2026-08-30" in values[b_row]
    assert v_row != b_row


def test_non_temporal_properties_render_without_temporal_label(qtbot: Any) -> None:
    view, _ = _make_view(qtbot)
    view.show_entity(EntityDetail.from_api(_entity_payload()))

    labels = [view.property_table.item(r, 0).text() for r in range(view.property_table.rowCount())]
    assert "wikidata_qid" in labels
    # temporal rows get dedicated labels, plain rows keep property names


# -- FR-DC-021: assertions list, confidence badge, provenance expander --------


def test_assertions_list_shows_confidence_badge(qtbot: Any) -> None:
    view, _ = _make_view(qtbot)
    rows = [NeighborRow.from_api(r) for r in _neighbor_payload()["neighbors"]]
    view.show_assertions(rows)

    model = view.assertion_model
    assert model.rowCount() == 2
    texts = [model.index(i, 0).data() or "" for i in range(model.rowCount())]
    assert any("0.98" in t for t in texts), "confidence badge 0.98 missing"
    assert any("0.91" in t for t in texts), "confidence badge 0.91 missing"


def test_clicking_assertion_row_reveals_source_and_sentence(qtbot: Any) -> None:
    view, _ = _make_view(qtbot)
    rows = [NeighborRow.from_api(r) for r in _neighbor_payload()["neighbors"]]
    view.show_assertions(rows)

    view._on_assertion_clicked(view.assertion_model.index(0, 0))

    text = view.provenance_text()
    assert "bundestag" in text, "source id missing from provenance"
    assert "doc9" in text, "evidence document missing from provenance"


def test_provenance_sentence_extracted_from_document_body(qtbot: Any) -> None:
    doc_client = type(
        "C",
        (),
        {
            "entity": lambda self, _id: {
                "entity": {
                    "entity_id": "doc9",
                    "type": "Document",
                    "label": "doc9",
                    "properties": {
                        "body": "x" * 10 + "Jane Doe joined the party in 2021." + "y" * 5
                    },
                    "ontology_version": "1.0.0",
                    "created_at": None,
                },
                "edge_summary": {},
            }
        },
    )()
    view, _ = _make_view(qtbot, client=doc_client)
    rows = [NeighborRow.from_api(r) for r in _neighbor_payload()["neighbors"]]
    view.show_assertions(rows)
    view._on_assertion_clicked(view.assertion_model.index(0, 0))

    text = view.provenance_text()
    assert "Jane Doe joined the party in 2021." in text


# -- FR-DC-022: neighbors table, ontology-driven filter, re-centering --------


def test_neighbor_filter_combo_populated_from_ontology_payload(qtbot: Any) -> None:
    view, _ = _make_view(qtbot)
    items = [view.relation_filter.itemText(i) for i in range(view.relation_filter.count())]
    assert items == ["(all relations)", "MEMBER_OF", "DIRECTOR_OF"]


def test_relation_filter_uses_cached_neighbors(qtbot: Any) -> None:
    client_calls: list[dict[str, Any]] = []

    class C:
        def entity_neighbors(
            self, entity_id: str, filters: dict[str, Any] | None = None
        ) -> GraphNeighbors:
            client_calls.append({"id": entity_id, **(filters or {})})
            return GraphNeighbors.from_api(_neighbor_payload())

    view, _ = _make_view(qtbot, client=C())
    view.show_neighbors(GraphNeighbors.from_api(_neighbor_payload()))

    assert view.neighbors_table.rowCount() == 2
    view.relation_filter.setCurrentIndex(1)  # MEMBER_OF
    assert view.neighbors_table.rowCount() == 1
    assert client_calls == [], "filter must re-filter cached rows, not refetch"


def test_neighbor_click_recenters_selection(qtbot: Any) -> None:
    view, state = _make_view(qtbot)
    selections: list[str | None] = []
    state.selection_changed.connect(selections.append)

    view.show_neighbors(GraphNeighbors.from_api(_neighbor_payload()))
    view._on_neighbor_clicked(view.neighbors_model.index(0, 0))

    assert selections == ["org1"]


def test_neighbor_table_clicked_signal_recenters_selection(qtbot: Any) -> None:
    view, state = _make_view(qtbot)
    selections: list[str | None] = []
    state.selection_changed.connect(selections.append)
    neighbor_selected: list[str] = []
    view.neighbor_selected.connect(neighbor_selected.append)

    view.show_neighbors(GraphNeighbors.from_api(_neighbor_payload()))
    view.neighbors_table.clicked.emit(view.neighbors_model.index(0, 0))

    assert selections == ["org1"]
    assert neighbor_selected == ["org1"]


def test_assertion_list_clicked_signal_reveals_provenance(qtbot: Any) -> None:
    view, _ = _make_view(qtbot)
    rows = [NeighborRow.from_api(r) for r in _neighbor_payload()["neighbors"]]
    view.show_assertions(rows)

    view.assertion_list.clicked.emit(view.assertion_model.index(0, 0))

    text = view.provenance_text()
    assert "bundestag" in text, "source id missing from provenance"
    assert "doc9" in text, "evidence document missing from provenance"


# -- wiring: entity bundle through SessionState drives the view ---------------


def test_entity_bundle_signal_renders_view(qtbot: Any) -> None:
    view, state = _make_view(qtbot)
    detail = EntityDetail.from_api(_entity_payload())
    state.publish(QueryOutcomeBundle(result=detail, coverage=None, source="entity"))

    labels = [view.property_table.item(r, 0).text() for r in range(view.property_table.rowCount())]
    values = [view.property_table.item(r, 1).text() for r in range(view.property_table.rowCount())]
    assert "Jane Doe" in values
    assert labels  # table populated


def test_entity_view_holds_no_ontology_literals() -> None:
    import ast
    from pathlib import Path

    module = Path(__import__("limes_desktop.views.entity", fromlist=["x"]).__file__)
    tree = ast.parse(module.read_text())
    forbidden = {"Person", "PublicBody", "Corporation", "MEMBER_OF", "DIRECTOR_OF"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert node.value not in forbidden, f"ontology literal {node.value!r} in entity.py"
