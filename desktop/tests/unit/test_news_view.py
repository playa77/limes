"""Paired DC-15 analyst acceptance: investigation actions and honest qualified evidence."""

from types import SimpleNamespace

from limes_desktop.views.news import NewsView


def test_investigation_tracking_pause_and_failed_replay(qtbot):
    requests = []
    client = SimpleNamespace(
        track_news=lambda payload: requests.append(payload),
        news_investigations=lambda: [],
        news_claims=lambda **kw: [],
        replay_news=lambda key: requests.append(key),
    )
    view = NewsView(lambda: client)
    qtbot.addWidget(view)
    view.call = lambda action, done: done(action())
    view.selected_entity = "entity-1"
    view.title.setText("Supply investigation")
    view.track(False)
    request = requests[-1]
    assert request["entity_ids"] == ["entity-1"] and request["active"] is True
    view.render_investigations([{**request, "status": "failed", "last_success": None}])
    assert "failed" in view.status.text() and "none" in view.status.text()
    view.replay()
    assert request["investigation_id"] in requests
    view.render_investigations([{**request, "status": "succeeded", "last_success": "2026-10-28"}])
    view.pause()
    assert requests[-1]["active"] is False


def test_denial_and_correction_display_exact_evidence_and_uncertainty(qtbot):
    text = "Alpha denies supplying Beta."
    doc = {"body": text, "article_text_available": False, "previous_document_id": "prior-dispatch"}
    client = SimpleNamespace(news_document=lambda key: doc)
    view = NewsView(lambda: client)
    qtbot.addWidget(view)
    view.call = lambda action, done: done(action())
    claim = {
        "claim_id": "c",
        "subject_label": "Alpha",
        "object_label": "Beta",
        "relation": "SUPPLIES",
        "modality": "denied",
        "event_status": "denied",
        "time_precision": "unknown",
        "assessment": "unassessed",
        "attribution": "Alpha",
        "source_trust": 0.5,
        "confidence": 0.9,
        "evidence_document_id": "doc",
        "evidence_start": 0,
        "evidence_end": len(text),
    }
    view.render_claims([claim])
    view.list.setCurrentRow(0)
    rendered = view.evidence.toPlainText()
    assert "denied" in view.list.item(0).text()
    assert "completed" not in rendered
    assert text in rendered and "prior-dispatch" in rendered
    assert "unavailable" in rendered and "dependent reporting" in rendered
    assert "time precision: unknown" in rendered and "unassessed" in rendered
    assert "source trust: 0.5" in rendered and "confidence: 0.9" in rendered
    view.render_claims([])
    assert "empty feed proves no absence" in view.evidence.toPlainText()


def test_claim_timeline_does_not_fabricate_event_time():
    import json

    from limes_desktop.api.models import EntityRef, GraphResult
    from limes_desktop.state import QueryOutcomeBundle
    from limes_desktop.views.viz.bridge import network_payload, timeline_payload

    props = {
        "claim_id": "c",
        "modality": "denied",
        "relation": "SUPPLIES",
        "event_status": "denied",
        "time_precision": "unknown",
        "valid_from": "2026-10-27",
        "recorded_at": "2026-10-28",
        "subject_id": "a",
        "object_id": "b",
    }
    node = EntityRef(entity_id="c", type="artifact-from-api", label="denial", properties=props)
    bundle = QueryOutcomeBundle(result=GraphResult(nodes=[node]), coverage=None, source="news")
    timeline = json.loads(timeline_payload(bundle))
    assert timeline["validity"] == []
    assert timeline["belief"][0]["relation"] == "denied: SUPPLIES"
    network = json.loads(network_payload(bundle))
    assert network["edges"] == []
    assert network["nodes"][0]["claim"]["event_status"] == "denied"


def test_shell_loads_selectable_relation_evidence_for_tracking(qtbot):
    from limes_desktop.api.models import EdgeRef, EntityRef, GraphNeighbors, NeighborRow
    from limes_desktop.state import SessionState
    from limes_desktop.views.main_window import MainWindow
    from test_main_window_support import FakeClient

    client = FakeClient()
    graph = GraphNeighbors(
        entity=EntityRef(entity_id="a", type="from-api", label="Alpha"),
        neighbors=[
            NeighborRow(
                edge=EdgeRef(
                    relation="from-api", subject_id="a", object_id="b", assertion_id="assertion-1"
                ),
                neighbor=EntityRef(entity_id="b", type="from-api", label="Beta"),
            )
        ],
    )
    client.entity_neighbors = lambda _: graph
    state = SessionState()
    window = MainWindow(state, None, lambda: client)
    qtbot.addWidget(window)
    state.set_selection("a")
    assert window.entity_view.assertion_model.rowCount() == 1
    window.entity_view._on_assertion_clicked(window.entity_view.assertion_model.index(0, 0))
    assert window.news_view.selected_relation == "assertion-1"


def test_late_evidence_reply_cannot_overwrite_another_claim(qtbot):
    view = NewsView(lambda: None)
    qtbot.addWidget(view)
    callbacks = []
    view.call = lambda action, done: callbacks.append(done)

    def claim(key):
        return {
            "claim_id": key,
            "relation": "from-api",
            "modality": "reported",
            "evidence_document_id": key,
            "evidence_start": 0,
            "evidence_end": 12,
        }

    view.render_claims([claim("old")])
    view.list.setCurrentRow(0)
    old_reply = callbacks[-1]
    view.render_claims([claim("new")])
    view.list.setCurrentRow(0)
    new_reply = callbacks[-1]
    old_reply({"body": "old sentence"})
    assert "old sentence" not in view.evidence.toPlainText()
    new_reply({"body": "new sentence"})
    assert "new sentence" in view.evidence.toPlainText()
