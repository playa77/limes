"""DC-16 request ownership, source inspection and distinct time semantics."""

from types import SimpleNamespace

from limes_desktop.views.developments import DevelopmentPanel


def response(key="case"):
    return {
        "investigation_id": key,
        "evidence": [
            {
                "evidence_id": "claim:c",
                "kind": "claim",
                "subject_id": "a",
                "object_id": "b",
                "subject_label": "Alpha",
                "object_label": "Beta",
                "relation": "from-api",
                "properties": {
                    "modality": "denied",
                    "event_status": "denied",
                    "claim_id": "c",
                    "time_precision": "unknown",
                    "valid_from": "2026-10-01T00:00:00Z",
                    "recorded_at": "2026-10-02T00:00:00Z",
                    "evidence_document_id": "doc",
                    "evidence_start": 0,
                    "evidence_end": 12,
                },
                "dependency_key": "shared-dispatch",
            }
        ],
        "candidates": [],
        "reviews": [],
        "coverage": {"claim": 1},
        "locations": [{"entity_id": "a", "label": "Alpha", "latitude": 52.5, "longitude": 13.4}],
        "truncated": False,
        "diagnosis": ["Independent corroboration unknown."],
    }


def test_network_timeline_inspection_and_unknown_time(qtbot):
    client = SimpleNamespace(
        news_developments=lambda key, **kw: response(key),
        news_document=lambda key: {"body": "Alpha denies", "article_text_available": False},
    )
    panel = DevelopmentPanel(lambda: client, lambda action, done: done(action()))
    qtbot.addWidget(panel)
    panel.set_case("case")
    panel.load()
    assert panel.timeline.rowCount() == 1  # Unknown event time never gets a validity point.
    assert panel.timeline.item(0, 0).text() == "recorded"
    assert "denied" in panel.timeline.item(0, 4).text()
    panel.select_time(0, 0)
    assert "Alpha denies" in panel.detail.toPlainText()
    assert "causation" in panel.detail.toPlainText()
    assert panel.scene.items()
    assert any(
        "Alpha" in item.toPlainText()
        for item in panel.map_scene.items()
        if hasattr(item, "toPlainText")
    )
    panel.evidence_list.setCurrentRow(-1)
    marker = next(item for item in panel.map_scene.items() if item.data(0) == "a")
    marker.setSelected(True)
    assert panel.evidence_list.currentRow() == 0
    panel.valid.setText("2026-10-01T00:00:00Z")
    assert not panel.rows and panel.timeline.rowCount() == 0


def test_old_investigation_reply_and_failure_cannot_replace_new_results(qtbot):
    callbacks = []
    panel = DevelopmentPanel(lambda: None, lambda action, done: callbacks.append(done))
    qtbot.addWidget(panel)
    panel.set_case("old")
    panel.load()
    old = callbacks[-1]
    panel.set_case("new")
    panel.load()
    callbacks[-1](response("new"))
    old(response("old"))
    assert panel.rows and panel.key == "new"
    panel.set_case(None)
    callbacks[-1](response("new"))
    assert not panel.rows


def test_api_failure_clears_old_evidence_and_is_visible(qtbot):
    def unavailable(*a, **kw):
        raise RuntimeError("offline")

    client = SimpleNamespace(news_developments=unavailable)
    panel = DevelopmentPanel(lambda: client, lambda action, done: done(action()))
    qtbot.addWidget(panel)
    panel.set_case("case")
    panel.render_developments(response())
    panel.load()
    assert panel.rows == [] and panel.timeline.rowCount() == 0
    assert "offline" in panel.status.text() and "unavailable" in panel.status.text()
