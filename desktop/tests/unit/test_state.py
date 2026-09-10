# desktop/tests/unit/test_state.py | v0.1.0 | SessionState signal hub unit tests (FR-DC-043)
from limes_desktop.state import QueryOutcomeBundle, SessionState, TemporalFilter


def test_selection_signal(qtbot) -> None:
    state = SessionState()
    with qtbot.waitSignal(state.selection_changed) as blocker:
        state.set_selection("e-42")
    assert blocker.args == ["e-42"]


def test_publish_stores_history_and_emits(qtbot) -> None:
    state = SessionState()
    bundle = QueryOutcomeBundle(result=[], coverage=None, source="search",
                                cypher=None, nlq=None)
    with qtbot.waitSignal(state.result_arrived):
        state.publish(bundle)
    assert state.history()[-1] is bundle


def test_temporal_filter_propagates(qtbot) -> None:
    state = SessionState()
    f = TemporalFilter(validity_from=None, validity_to=None, belief_as_of="2025-03-01")
    with qtbot.waitSignal(state.temporal_filter_changed) as blocker:
        state.set_temporal_filter(f)
    assert blocker.args[0].belief_as_of == "2025-03-01"


def test_history_capped(qtbot) -> None:
    state = SessionState()
    for i in range(150):
        state.publish(QueryOutcomeBundle(result=i, coverage=None, source="t",
                                         cypher=None, nlq=None))
    assert len(state.history()) == 100
