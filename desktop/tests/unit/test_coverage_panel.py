# desktop/tests/unit/test_coverage_panel.py | v0.1.0 | FR-DC-034/AC-DC-3 coverage panel
from __future__ import annotations

from typing import Any

from limes_desktop.api.models import CoverageReport, Diagnosis, GraphResult
from limes_desktop.state import QueryOutcomeBundle, SessionState
from limes_desktop.views.coverage_panel import CoveragePanel


def _coverage() -> CoverageReport:
    return CoverageReport.from_api(
        {
            "relation_counts": {"MEMBER_OF": 512, "DIRECTOR_OF": 87},
            "contributing_sources": ["gleif", "bundestag"],
            "source_refresh": {"gleif": "2026-09-01T00:00:00Z", "bundestag": None},
        }
    )


def test_empty_result_renders_one_row_per_diagnosis_hop_with_count(
    qtbot: Any,
) -> None:
    state = SessionState()
    panel = CoveragePanel(state)
    qtbot.addWidget(panel)

    diagnosis = Diagnosis.from_api(
        {
            "failing_clause": "MEMBER_OF",
            "clause_index": 0,
            "note": "hop 0 emptied the result set",
            "relation_counts": {"MEMBER_OF": 0, "HOLDS_OFFICE": 512},
        }
    )
    panel.set_diagnosis(diagnosis)
    panel.render(None)
    panel._show_diagnosis(diagnosis)

    table = panel.diagnosis_table
    rows = [
        table.item(r, c).text()
        for r in range(table.rowCount())
        for c in range(table.columnCount())
    ]
    # one row per hop relation with its graph-wide count
    assert "MEMBER_OF" in rows and "0" in rows
    assert "HOLDS_OFFICE" in rows and "512" in rows
    # which hop emptied the set
    assert any("hop 0" in cell or "MEMBER_OF" in cell for cell in rows)


def test_empty_state_never_shows_bare_no_results(qtbot: Any) -> None:
    state = SessionState()
    panel = CoveragePanel(state)
    qtbot.addWidget(panel)

    panel.set_diagnosis(
        Diagnosis.from_api(
            {
                "failing_clause": "MEMBER_OF",
                "clause_index": 0,
                "note": "hop 0 emptied the result set",
                "relation_counts": {"MEMBER_OF": 0},
            }
        )
    )
    panel.render(None)
    panel._show_diagnosis(
        Diagnosis.from_api(
            {
                "failing_clause": "MEMBER_OF",
                "clause_index": 0,
                "note": "hop 0 emptied the result set",
                "relation_counts": {"MEMBER_OF": 0},
            }
        )
    )

    text = " ".join(
        panel.diagnosis_table.item(r, c).text()
        for r in range(panel.diagnosis_table.rowCount())
        for c in range(panel.diagnosis_table.columnCount())
    )
    assert "no results" not in text.lower()
    assert "hop 0" in text


def test_empty_result_bundle_through_signal_drives_diagnosis_state(qtbot: Any) -> None:
    state = SessionState()
    panel = CoveragePanel(state)
    qtbot.addWidget(panel)

    panel.set_diagnosis(
        Diagnosis.from_api(
            {
                "failing_clause": "LOCATED_IN",
                "clause_index": 1,
                "note": "hop 1 emptied the result set",
                "relation_counts": {"LOCATED_IN": 0},
            }
        )
    )
    empty = GraphResult.from_api({"nodes": [], "edges": [], "counts": {}})
    state.publish(
        QueryOutcomeBundle(
            result=empty, coverage=CoverageReport.from_api({}), source="query"
        )
    )

    assert panel.is_showing_empty_state


def test_non_empty_coverage_renders_summary_counts_and_sources(qtbot: Any) -> None:
    state = SessionState()
    panel = CoveragePanel(state)
    qtbot.addWidget(panel)

    panel.render(_coverage())

    assert not panel.is_showing_empty_state
    text = panel.summary_text()
    assert "MEMBER_OF" in text and "512" in text
    assert "gleif" in text and "bundestag" in text
    assert not panel.summary_widget.isHidden()


def test_render_none_clears_panel(qtbot: Any) -> None:
    state = SessionState()
    panel = CoveragePanel(state)
    qtbot.addWidget(panel)

    panel.render(_coverage())
    panel.render(None)

    assert panel.summary_text() == ""
    assert not panel.is_showing_empty_state
