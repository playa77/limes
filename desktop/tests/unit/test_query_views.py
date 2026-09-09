# desktop/tests/unit/test_query_views.py | v0.1.0 | FR-DC-030/032/033: NLQ, console, saved
from __future__ import annotations

from typing import Any

from limes_desktop.api.errors import ApiError
from limes_desktop.api.models import GraphResult, QueryOutcome
from limes_desktop.config import ProfileStore
from limes_desktop.state import QueryOutcomeBundle, SessionState
from limes_desktop.views.query_cypher import CypherConsole, HistoryStore
from limes_desktop.views.query_history import SavedQueriesPanel
from limes_desktop.views.query_nl import NlqView
from PySide6.QtWidgets import QPlainTextEdit


def _nl_payload() -> dict[str, Any]:
    return {
        "question": "Which companies did Jane direct?",
        "cypher": "MATCH (p:Person {label: 'Jane'})-[:DIRECTOR_OF]->(c) RETURN c",
        "results": {"nodes": [], "edges": [], "counts": {}},
        "validation_errors": [],
        "plan_rejection": None,
        "notes": ["resolved 'Jane' via label match"],
    }


def _cypher_payload() -> dict[str, Any]:
    return {
        "cypher": "MATCH (n) RETURN n LIMIT 5",
        "results": {"nodes": [], "edges": [], "counts": {}},
        "coverage": {"relation_counts": {"DIRECTOR_OF": 2}, "contributing_sources": []},
        "diagnosis": None,
        "notes": [],
    }


class FakeQueryClient:
    """Records query calls; canned NLQ + cypher outcomes."""

    def __init__(self, fail_detail: str | None = None) -> None:
        self.fail_detail = fail_detail
        self.nl_calls: list[str] = []
        self.cypher_calls: list[tuple[str, dict[str, Any] | None]] = []
        self.save_calls: list[tuple[str, str, dict[str, Any]]] = []
        self.delete_calls: list[str] = []

    def query_nl(self, question: str) -> QueryOutcome:
        self.nl_calls.append(question)
        if self.fail_detail is not None:
            raise ApiError(400, self.fail_detail)
        return QueryOutcome.from_api(_nl_payload())

    def query_cypher(
        self, cypher: str, params: dict[str, Any] | None = None
    ) -> QueryOutcome:
        self.cypher_calls.append((cypher, params))
        if self.fail_detail is not None:
            raise ApiError(400, self.fail_detail)
        return QueryOutcome.from_api(_cypher_payload())

    def save_query(self, name: str, surface: str, payload: dict[str, Any]) -> str:
        self.save_calls.append((name, surface, payload))
        return "sq-1"

    def delete_saved_query(self, saved_query_id: str) -> None:
        self.delete_calls.append(saved_query_id)


def _make_view(qtbot: Any, client: Any) -> tuple[NlqView, SessionState]:
    state = SessionState()
    view = NlqView(state, client_factory=lambda: client)
    qtbot.addWidget(view)
    return view, state


# -- FR-DC-030: NLQ result shows generated Cypher in an EDITABLE pane ---------


def test_nlq_submit_fills_editable_cypher_pane(qtbot: Any) -> None:
    client = FakeQueryClient()
    view, state = _make_view(qtbot, client)

    view.question_edit.setText("Which companies did Jane direct?")
    view._submit()

    assert client.nl_calls == ["Which companies did Jane direct?"]
    assert isinstance(view.cypher_edit, QPlainTextEdit)
    assert view.cypher_edit.toPlainText() == _nl_payload()["cypher"]
    # NlqOutcome metadata is displayed beside the editor
    assert "resolved 'Jane'" in view.metadata_text()


def test_nlq_run_button_reexecutes_edited_cypher(qtbot: Any) -> None:
    client = FakeQueryClient()
    view, _ = _make_view(qtbot, client)
    view.question_edit.setText("Which companies did Jane direct?")
    view._submit()

    edited = "MATCH (c:Corporation) RETURN c LIMIT 1"
    view.cypher_edit.setPlainText(edited)
    view._run_cypher()

    assert client.cypher_calls == [(edited, None)]


def test_nlq_publishes_bundle_with_nlq_metadata(qtbot: Any) -> None:
    client = FakeQueryClient()
    view, state = _make_view(qtbot, client)
    bundles: list[QueryOutcomeBundle] = []
    state.result_arrived.connect(bundles.append)

    view.question_edit.setText("q")
    view._submit()

    assert len(bundles) == 1
    b = bundles[0]
    assert b.source == "nlq"
    assert b.cypher == _nl_payload()["cypher"]
    assert b.nlq is not None and b.nlq.question == "q"
    assert isinstance(b.result, GraphResult)


def test_write_clause_rejection_surfaces_detail_verbatim(qtbot: Any) -> None:
    client = FakeQueryClient(fail_detail="write clause refused")
    view, _ = _make_view(qtbot, client)
    view.question_edit.setText("q")
    view._submit()

    assert view.error_text() == "write clause refused"


# -- FR-DC-032: Cypher console, history combo, verbatim errors -----------------


def _make_console(
    qtbot: Any, client: Any, store: HistoryStore | None = None
) -> tuple[CypherConsole, SessionState]:
    state = SessionState()
    console = CypherConsole(state, client_factory=lambda: client, history_store=store)
    qtbot.addWidget(console)
    return console, state


def test_console_run_publishes_cypher_source(qtbot: Any) -> None:
    client = FakeQueryClient()
    console, state = _make_console(qtbot, client)
    bundles: list[QueryOutcomeBundle] = []
    state.result_arrived.connect(bundles.append)

    console.editor.setPlainText("MATCH (n) RETURN n")
    console._run()

    assert client.cypher_calls == [("MATCH (n) RETURN n", None)]
    assert bundles[0].source == "cypher"


def test_console_history_combo_filters_to_cypher_and_nlq_run(qtbot: Any) -> None:
    client = FakeQueryClient()
    console, state = _make_console(qtbot, client)
    state.publish(QueryOutcomeBundle(result=GraphResult(), coverage=None, source="search"))
    state.publish(
        QueryOutcomeBundle(
            result=GraphResult(), coverage=None, source="cypher", cypher="MATCH (a) RETURN a"
        )
    )
    state.publish(
        QueryOutcomeBundle(
            result=GraphResult(), coverage=None, source="nlq-run", cypher="MATCH (b) RETURN b"
        )
    )

    console.refresh_history()

    items = [console.history.itemText(i) for i in range(console.history.count())]
    assert items == ["MATCH (a) RETURN a", "MATCH (b) RETURN b"]
    # picking a history entry loads its cypher into the editor
    console.history.setCurrentIndex(0)
    console._on_history_pick(console.history.currentIndex())
    assert console.editor.toPlainText() == "MATCH (a) RETURN a"


def test_console_error_detail_verbatim(qtbot: Any) -> None:
    client = FakeQueryClient(fail_detail="write clause refused")
    console, _ = _make_console(qtbot, client)
    console.editor.setPlainText("CREATE (n)")
    console._run()
    assert console.error_text() == "write clause refused"


def test_console_history_persists_to_history_json_when_enabled(qtbot: Any, tmp_path: Any) -> None:
    store = HistoryStore(config_dir=tmp_path)
    client = FakeQueryClient()
    console, state = _make_console(qtbot, client, store=store)
    console.persist_checkbox.setChecked(True)

    console.editor.setPlainText("MATCH (n) RETURN n")
    console._run()

    assert (tmp_path / "history.json").exists()
    # a fresh console over the same store reloads the persisted entry
    console2, _ = _make_console(qtbot, client, store=store)
    console2._on_persist_toggled(True)
    items = [console2.history.itemText(i) for i in range(console2.history.count())]
    assert items == ["MATCH (n) RETURN n"]


def test_console_history_off_by_default(qtbot: Any, tmp_path: Any) -> None:
    store = HistoryStore(config_dir=tmp_path)
    client = FakeQueryClient()
    console, _ = _make_console(qtbot, client, store=store)
    assert console.persist_checkbox.isChecked() is False
    console.editor.setPlainText("MATCH (n) RETURN n")
    console._run()
    assert not (tmp_path / "history.json").exists()


# -- FR-DC-033: saved queries ---------------------------------------------------


def test_saved_query_save_captures_name_surface_and_text(qtbot: Any) -> None:
    client = FakeQueryClient()
    state = SessionState()
    current = {"text": "MATCH (n) RETURN n"}
    panel = SavedQueriesPanel(
        state, client_factory=lambda: client, query_text=lambda: current["text"]
    )
    qtbot.addWidget(panel)

    panel.name_edit.setText("all nodes")
    panel._save()

    assert client.save_calls == [
        ("all nodes", "MATCH (n) RETURN n", {"result_count": 0, "pinned": False})
    ]


def test_saved_query_delete_calls_client(qtbot: Any) -> None:
    client = FakeQueryClient()
    state = SessionState()
    panel = SavedQueriesPanel(state, client_factory=lambda: client, query_text=lambda: "")
    qtbot.addWidget(panel)
    panel.set_queries([("sq-1", "all nodes", "MATCH (n) RETURN n")])
    panel.list_widget.setCurrentRow(0)

    panel._delete()

    assert client.delete_calls == ["sq-1"]


# -- MainWindow registration ----------------------------------------------------


def test_main_window_registers_query_views(qtbot: Any) -> None:
    from limes_desktop.views.main_window import MainWindow
    from test_main_window_support import FakeClient

    state = SessionState()
    win = MainWindow(state, ProfileStore(), lambda: FakeClient())
    qtbot.addWidget(win)

    assert win.stack.widget(0) is win.entity_view
    assert any(win.stack.widget(i) is win.nlq_view for i in range(win.stack.count()))
    assert any(win.stack.widget(i) is win.cypher_console for i in range(win.stack.count()))


# -- no ontology literals in the new modules ------------------------------------


def test_query_views_hold_no_ontology_literals() -> None:
    import ast
    from pathlib import Path

    forbidden = {"Person", "PublicBody", "Corporation", "MEMBER_OF", "DIRECTOR_OF"}
    for name in ("query_nl", "query_cypher", "query_history"):
        module = Path(__import__(f"limes_desktop.views.{name}", fromlist=["x"]).__file__)
        tree = ast.parse(module.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert node.value not in forbidden, f"ontology literal {node.value!r} in {name}.py"
