# desktop/tests/unit/test_main_window_wiring.py | v0.1.0 | fix wave: coverage, ontology, selection
from __future__ import annotations

from typing import Any

from limes_desktop.api.errors import ApiUnreachable
from limes_desktop.api.models import Diagnosis, GraphResult
from limes_desktop.config import ProfileStore
from limes_desktop.state import QueryOutcomeBundle, SessionState
from limes_desktop.views.main_window import MainWindow
from test_main_window_support import FakeClient


def _window(qtbot: Any, client: FakeClient) -> MainWindow:
    state = SessionState()
    win = MainWindow(state, ProfileStore(), lambda: client)  # type: ignore[arg-type]
    qtbot.addWidget(win)
    return win


def test_coverage_panel_instantiated_and_rendered_in_main_window(qtbot: Any) -> None:
    client = FakeClient()
    win = _window(qtbot, client)
    state = win._state

    # an empty GraphResult with a diagnosis renders diagnosis rows live
    diagnosis = Diagnosis.from_api(
        {
            "failing_clause": "MEMBER_OF",
            "clause_index": 0,
            "note": "hop 0 emptied the result set",
            "relation_counts": {"MEMBER_OF": 0, "HOLDS_OFFICE": 512},
        }
    )
    empty = GraphResult.from_api(
        {"nodes": [], "edges": [], "counts": {"rows": 0, "nodes": 0, "edges": 0}}
    )
    state.publish(
        QueryOutcomeBundle(
            result=empty, coverage=None, source="cypher", diagnosis=diagnosis
        )
    )

    panel = win.coverage_panel
    assert panel.is_showing_empty_state
    table = panel.diagnosis_table
    rows = [
        table.item(r, c).text()
        for r in range(table.rowCount())
        for c in range(table.columnCount())
        if table.item(r, c) is not None
    ]
    assert "MEMBER_OF" in rows and "512" in rows


def test_ontology_fetched_at_connect_and_populates_filter(qtbot: Any) -> None:
    client = FakeClient()
    win = _window(qtbot, client)

    assert client.ontology_calls == 1  # startup fetch
    items = [
        win.entity_view.relation_filter.itemText(i)
        for i in range(win.entity_view.relation_filter.count())
    ]
    assert "LOCATED_IN" in items and "MEMBER_OF" in items


def test_ontology_refetched_on_profile_change(qtbot: Any) -> None:
    client = FakeClient()
    win = _window(qtbot, client)
    assert client.ontology_calls == 1

    win._state.set_connection(None)  # triggers connection_changed wiring
    assert client.ontology_calls == 2


def test_ontology_fetch_failure_degrades_without_exception(qtbot: Any) -> None:
    client = FakeClient()
    client.fail = True
    win = _window(qtbot, client)  # constructor must not raise

    # the filter was never populated (no ontology literals in the view)
    items = [
        win.entity_view.relation_filter.itemText(i)
        for i in range(win.entity_view.relation_filter.count())
    ]
    assert items == []


def test_selection_fetches_entity_and_switches_stack(qtbot: Any) -> None:
    client = FakeClient()
    win = _window(qtbot, client)
    win.stack.setCurrentWidget(win.cypher_console)

    win._state.set_selection("e9")

    assert client.entity_calls == ["e9"]
    assert win.stack.currentWidget() is win.entity_view
    assert win.entity_view.property_table.rowCount() >= 1
    # the EntityDetail bundle reached the shared result surface
    assert win._state.history()[-1].source == "selection"


def test_selection_error_degrades_without_exception(qtbot: Any) -> None:
    client = FakeClient()
    win = _window(qtbot, client)
    win.stack.setCurrentWidget(win.cypher_console)

    win.banner.client_factory = lambda: (_ for _ in ()).throw(  # type: ignore[assignment]
        ApiUnreachable("down")
    )
    win._state.set_selection("e9")  # must not raise

    assert win.stack.currentWidget() is win.cypher_console
