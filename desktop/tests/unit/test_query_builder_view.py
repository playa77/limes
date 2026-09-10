# desktop/tests/unit/test_query_builder_view.py | v0.1.0 | FR-DC-031: schema-driven builder
from __future__ import annotations

from typing import Any

from limes_desktop.api.errors import ApiError
from limes_desktop.api.models import BuilderHop, BuilderSpec, GraphResult, QueryOutcome
from limes_desktop.state import QueryOutcomeBundle, SessionState
from limes_desktop.views.query_builder import BuilderView
from PySide6.QtWidgets import QComboBox


# The canned schema mirrors the exact GET /builder/schema shape
# (`project_for_builder` in src/limes/api/builder.py): entity_types carry
# name/supertype/identifying_keys/properties, relation_types carry
# name/domain/range/temporal. All names are invented — the client must not
# know them (AC-DC-4); they exist only to prove options are schema data.
def _schema() -> dict[str, Any]:
    return {
        "version": "9.9.9-test",
        "entity_types": [
            {"name": "TypeA", "supertype": None, "identifying_keys": ["k"], "properties": []},
            {"name": "TypeB", "supertype": None, "identifying_keys": [], "properties": []},
            {"name": "TypeC", "supertype": "TypeB", "identifying_keys": [], "properties": []},
        ],
        "relation_types": [
            {"name": "RelAB", "domain": ["TypeA"], "range": ["TypeB"], "temporal": False},
            {"name": "RelBA", "domain": ["TypeB"], "range": ["TypeA"], "temporal": False},
        ],
    }


def _outcome_payload() -> dict[str, Any]:
    return {
        "cypher": "generated-for-test",
        "results": {"nodes": [], "edges": [], "counts": {}},
        "coverage": {"relation_counts": {"RelAB": 3}, "contributing_sources": ["src-x"]},
        "diagnosis": {
            "note": "hop 1 emptied the set",
            "relation_counts": {"RelAB": 3},
            "failing_clause": "RelAB",
            "clause_index": 1,
        },
        "notes": [],
    }


class FakeBuilderClient:
    """Records builder calls; canned builder outcome + schema."""

    def __init__(self, fail_detail: str | None = None) -> None:
        self.fail_detail = fail_detail
        self.builder_schema_calls = 0
        self.spec_calls: list[dict[str, Any]] = []

    def builder_schema(self) -> dict[str, Any]:
        self.builder_schema_calls += 1
        return _schema()

    def query_builder(self, spec: dict[str, Any]) -> QueryOutcome:
        self.spec_calls.append(spec)
        if self.fail_detail is not None:
            raise ApiError(400, self.fail_detail)
        return QueryOutcome.from_api(_outcome_payload())


def _combo_items(combo: QComboBox) -> list[Any]:
    return [combo.itemData(i) for i in range(combo.count())]


def _make_view(
    qtbot: Any, client: FakeBuilderClient | None = None
) -> tuple[BuilderView, FakeBuilderClient]:
    client = client or FakeBuilderClient()
    state = SessionState()
    view = BuilderView(state, client_factory=lambda: client)
    qtbot.addWidget(view)
    return view, client


def test_start_type_combo_populated_from_schema_entity_types(qtbot: Any) -> None:
    view, _ = _make_view(qtbot)
    view.set_schema(_schema())

    assert _combo_items(view.start_type_combo) == ["TypeA", "TypeB", "TypeC"]


def test_hop_triples_for_start_type_a_are_exactly_schema_admissible(qtbot: Any) -> None:
    view, _ = _make_view(qtbot)
    view.set_schema(_schema())
    view.start_type_combo.setCurrentText("TypeA")

    row = view.hop_rows[0]
    # TypeA is admissible as RelAB's subject (domain ⇒ out) and as RelBA's
    # object (range ⇒ in) — exactly relations_for() semantics
    assert _combo_items(row.relation_combo) == ["RelAB", "RelBA"]
    row.relation_combo.setCurrentText("RelAB")
    assert _combo_items(row.direction_combo) == ["out"]
    # range side expanded to concrete types, including the TypeB subtype
    assert _combo_items(row.target_combo) == ["TypeB", "TypeC"]


def test_hop_triples_for_start_type_b_include_both_directions(qtbot: Any) -> None:
    view, _ = _make_view(qtbot)
    view.set_schema(_schema())
    view.start_type_combo.setCurrentText("TypeB")

    row = view.hop_rows[0]
    assert _combo_items(row.relation_combo) == ["RelAB", "RelBA"]
    row.relation_combo.setCurrentText("RelAB")
    # TypeB sits in RelAB's range ⇒ incoming only
    assert _combo_items(row.direction_combo) == ["in"]
    assert _combo_items(row.target_combo) == ["TypeA"]
    row.relation_combo.setCurrentText("RelBA")
    # RelBA: domain TypeB (out), range TypeA — TypeB is subject only
    assert _combo_items(row.direction_combo) == ["out"]
    row.direction_combo.setCurrentText("out")
    assert _combo_items(row.target_combo) == ["TypeA"]


def test_hop_triples_are_exactly_the_schema_admissible_set(qtbot: Any) -> None:
    view, _ = _make_view(qtbot)
    view.set_schema(_schema())
    view.start_type_combo.setCurrentText("TypeA")
    row = view.hop_rows[0]

    triples: list[tuple[Any, Any, Any]] = []
    for i in range(row.relation_combo.count()):
        row.relation_combo.setCurrentIndex(i)
        for j in range(row.direction_combo.count()):
            row.direction_combo.setCurrentIndex(j)
            for _k in range(row.target_combo.count()):
                row.target_combo.setCurrentIndex(_k)
                triples.append(
                    (
                        row.relation_combo.currentData(),
                        row.direction_combo.currentData(),
                        row.target_combo.currentData(),
                    )
                )

    # TypeA: RelAB out→TypeB/TypeC (range, supertype-expanded);
    # RelBA in→TypeB/TypeC (direction "in" ⇒ the target takes the DOMAIN
    # side, per translate_spec: (target)-[rel]->(prev); TypeC is a TypeB
    # subtype so it expands too)
    assert set(triples) == {
        ("RelAB", "out", "TypeB"),
        ("RelAB", "out", "TypeC"),
        ("RelBA", "in", "TypeB"),
        ("RelBA", "in", "TypeC"),
    }


def test_non_admissible_triple_never_offered(qtbot: Any) -> None:
    view, _ = _make_view(qtbot)
    view.set_schema(_schema())
    view.start_type_combo.setCurrentText("TypeA")
    row = view.hop_rows[0]
    # RelBA admits TypeA only as object (direction "in"), never as subject;
    # RelAB with direction "in" would target RelAB's domain — not offered
    row.relation_combo.setCurrentText("RelAB")
    assert _combo_items(row.direction_combo) == ["out"]


def test_add_and_remove_hop(qtbot: Any) -> None:
    view, _ = _make_view(qtbot)
    view.set_schema(_schema())
    view.start_type_combo.setCurrentText("TypeA")

    assert len(view.hop_rows) == 1
    view.hop_rows[0].relation_combo.setCurrentText("RelAB")
    view.hop_rows[0].direction_combo.setCurrentText("out")
    view.hop_rows[0].target_combo.setCurrentText("TypeB")
    # after the target change, hop 2 chains off TypeB
    view.add_hop_button.click()
    assert _combo_items(view.hop_rows[1].relation_combo) == ["RelAB", "RelBA"]
    view.remove_hop_button.click()
    assert len(view.hop_rows) == 1
    view.remove_hop_button.click()
    assert len(view.hop_rows) == 1  # never below one


def test_submit_builds_expected_spec_and_calls_query_builder(qtbot: Any) -> None:
    view, client = _make_view(qtbot)
    view.set_schema(_schema())
    view.start_type_combo.setCurrentText("TypeA")
    view.hop_rows[0].relation_combo.setCurrentText("RelAB")
    view.hop_rows[0].direction_combo.setCurrentText("out")
    view.hop_rows[0].target_combo.setCurrentText("TypeB")

    view.submit_button.click()

    assert client.spec_calls == [
        {
            "start_type": "TypeA",
            "start_filters": {},
            "hops": [
                {"relation": "RelAB", "direction": "out", "target_type": "TypeB"}
            ],
        }
    ]
    # the spec dict must parse back into the mirrored BuilderSpec
    parsed = BuilderSpec.from_api(client.spec_calls[0])
    assert parsed.hops == [
        BuilderHop(relation="RelAB", direction="out", target_type="TypeB")
    ]


def test_submit_publishes_bundle_with_coverage_and_diagnosis(qtbot: Any) -> None:
    view, client = _make_view(qtbot)
    state = view._state
    published: list[QueryOutcomeBundle] = []
    state.result_arrived.connect(published.append)

    view.set_schema(_schema())
    view.start_type_combo.setCurrentText("TypeA")
    view.hop_rows[0].relation_combo.setCurrentText("RelAB")
    view.hop_rows[0].target_combo.setCurrentText("TypeB")
    view.submit_button.click()

    assert len(published) == 1
    bundle = published[0]
    assert bundle.source == "builder"
    assert bundle.cypher == "generated-for-test"
    # Task-7 invariant: coverage/diagnosis propagate, never None silently
    assert bundle.coverage is not None
    assert bundle.coverage.relation_counts == {"RelAB": 3}
    assert bundle.diagnosis is not None
    assert bundle.diagnosis.failing_clause == "RelAB"
    assert isinstance(bundle.result, GraphResult)


def test_submit_api_error_shown_verbatim_no_publish(qtbot: Any) -> None:
    client = FakeBuilderClient(fail_detail="hop 1: 'RelAB' does not admit …")
    view, _ = _make_view(qtbot, client)
    state = view._state
    published: list[QueryOutcomeBundle] = []
    state.result_arrived.connect(published.append)

    view.set_schema(_schema())
    view.start_type_combo.setCurrentText("TypeA")
    view.submit_button.click()

    assert view.error_text() == "hop 1: 'RelAB' does not admit …"
    assert published == []
    assert client.spec_calls  # the call happened and failed


def test_reload_schema_fetches_from_client_lazily(qtbot: Any) -> None:
    client = FakeBuilderClient()
    view, _ = _make_view(qtbot, client)

    assert client.builder_schema_calls == 0  # nothing fetched at construction
    view.reload_schema()
    assert client.builder_schema_calls == 1
    assert _combo_items(view.start_type_combo) == ["TypeA", "TypeB", "TypeC"]


def test_reload_schema_error_surfaces_without_exception(qtbot: Any) -> None:
    class FailingSchemaClient:
        def builder_schema(self) -> dict[str, Any]:
            raise ApiError(503, "schema unavailable")

    view, _ = _make_view(qtbot)  # type: ignore[arg-type]
    view._client_factory = FailingSchemaClient  # type: ignore[method-assign]

    view.reload_schema()  # must not raise

    assert "schema unavailable" in view.error_text()


def test_first_show_triggers_one_schema_fetch(qtbot: Any) -> None:
    client = FakeBuilderClient()
    view, _ = _make_view(qtbot, client)

    view.show()
    view.show()
    assert client.builder_schema_calls == 1
