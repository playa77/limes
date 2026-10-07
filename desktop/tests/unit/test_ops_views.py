# desktop/tests/unit/test_ops_views.py | v0.1.0 | FR-DC-050/051/052: ops views
"""Read-only ops views (Task 10): IngestView, LedgerView, ReferencesView.

All behavior is exercised through the FakeOpsClient stub — no real HTTP, no
real API. The ingest auto-refresh timer (FR-DC-050) must only run while the
view is visible; ApiUnreachable must degrade without escaping (AC-DC-6).
"""

from __future__ import annotations

from typing import Any

from limes_desktop.api.errors import ApiError, ApiUnreachable
from limes_desktop.api.models import (
    CostEntry,
    CostLedger,
    HealthInfo,
    IngestRun,
    SourceInfo,
)
from limes_desktop.views.ops.ingest import COLUMN_ERRORS, IngestView
from limes_desktop.views.ops.ledger import LedgerView
from limes_desktop.views.ops.references import ReferencesView
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractItemView

_CANNED_RUNS = [
    IngestRun(
        source_id="gisco_nuts",
        mode="structured",
        run_id="r1",
        started_at="2026-09-01T10:00:00Z",
        finished_at="2026-09-01T10:05:00Z",
        records_fetched=2000,
        nodes_created=1800,
        nodes_matched=200,
        assertions_written=5000,
        assertions_skipped=10,
        assertions_rejected=2,
        documents_gated_out=0,
        errors=0,
        cost_eur=0.0,
    ),
    IngestRun(
        source_id="eurostat_backfill",
        mode="backfill",
        run_id="r2",
        started_at="2026-09-02T09:00:00Z",
        records_fetched=100,
        nodes_created=90,
        nodes_matched=10,
        assertions_written=400,
        assertions_skipped=0,
        assertions_rejected=1,
        documents_gated_out=3,
        errors=1,
        cost_eur=1.25,
    ),
]

_CANNED_ENTRIES = [
    CostEntry(
        ledger_id="l1",
        period="2026-09",
        run_id="r2",
        purpose="backfill",
        model_id="model/a",
        input_tokens=1000,
        output_tokens=500,
        cost_eur=0.75,
        created_at="2026-09-02T09:01:00Z",
    ),
    CostEntry(
        ledger_id="l2",
        period="2026-09",
        run_id="r2",
        purpose="backfill",
        model_id="model/b",
        input_tokens=800,
        output_tokens=200,
        cost_eur=0.50,
        created_at="2026-09-02T09:02:00Z",
    ),
    CostEntry(
        ledger_id="l3",
        period="2026-09",
        run_id=None,
        purpose="nlq",
        model_id="model/a",
        input_tokens=400,
        output_tokens=100,
        cost_eur=0.25,
        created_at="2026-09-03T12:00:00Z",
    ),
]

_CANNED_SOURCES = [
    SourceInfo(
        source_id="gisco_nuts",
        name="GISCO NUTS",
        kind="structured",
        trust_rank=0.95,
        supports_backfill=False,
        supports_incremental=True,
        last_success_at="2026-09-01T10:05:00Z",
        last_run_id="r1",
    ),
]

_CANNED_ONTOLOGY = {
    "version": "1.0.0",
    "supertypes": ["Actor"],
    "entity_types": {
        "Company": {
            "name": "Company",
            "supertype": "Actor",
            "identifying_keys": ["lei"],
            "properties": [],
        },
    },
    "relation_types": {
        "owns": {"name": "owns", "domain": ["Company"], "range": ["Company"], "temporal": True},
    },
    "vocabularies": [],
}

_CANNED_VERSIONS = ["1.0.0", "1.1.0"]


class FakeOpsClient:
    """Stub covering every surface the three ops views consume."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.ingest_calls = 0
        self.ledger_calls = 0
        self.sources_calls = 0
        self.ontology_calls = 0
        self.versions_calls = 0

    def _maybe_fail(self) -> None:
        if self.fail:
            raise ApiUnreachable("connection refused")

    def health(self) -> Any:
        if self.fail:
            raise ApiUnreachable("connection refused")
        return HealthInfo(status="ok", neo4j=True, ontology_version="1.0.0")

    def ingest_status(self) -> list[IngestRun]:
        self.ingest_calls += 1
        self._maybe_fail()
        return list(_CANNED_RUNS)

    def cost_ledger(self, period: str | None = None) -> CostLedger:
        self.ledger_calls += 1
        self._maybe_fail()
        return CostLedger(
            period="2026-09",
            spend_eur=1.50,
            entries=list(_CANNED_ENTRIES),
        )

    def sources(self) -> list[SourceInfo]:
        self.sources_calls += 1
        self._maybe_fail()
        return list(_CANNED_SOURCES)

    def ontology(self) -> dict[str, Any]:
        self.ontology_calls += 1
        self._maybe_fail()
        return dict(_CANNED_ONTOLOGY)

    def ontology_versions(self) -> list[str]:
        self.versions_calls += 1
        self._maybe_fail()
        return list(_CANNED_VERSIONS)

    def close(self) -> None:
        pass


class ApiErrorClient(FakeOpsClient):
    """Degraded (reachable but erroring) variant."""

    def _maybe_fail(self) -> None:
        raise ApiError(500, "boom")


# -- IngestView (FR-DC-050) ---------------------------------------------------


def test_ingest_view_renders_canned_runs(qtbot: Any) -> None:
    view = IngestView(FakeOpsClient)
    qtbot.addWidget(view)
    view.show()
    qtbot.waitUntil(lambda: view.table.rowCount() == 2, timeout=2000)

    assert view.table.item(0, 0).text() == "gisco_nuts"
    assert view.table.item(0, 2).text() == "r1"
    assert view.table.item(1, 0).text() == "eurostat_backfill"
    assert view.table.item(1, 2).text() == "r2"
    assert view.table.item(1, COLUMN_ERRORS).text() == "1"
    assert not view.error_pane.isVisible()


def test_ingest_view_refresh_timer_runs_only_while_visible(qtbot: Any) -> None:
    view = IngestView(FakeOpsClient)
    qtbot.addWidget(view)
    # speed the timer up so waitUntil observes ticks quickly
    view._timer.setInterval(10)

    view.show()
    qtbot.waitUntil(lambda: view._ticks > 0, timeout=2000)

    view.hide()
    ticks_at_hide = view._ticks
    QTest.qWait(120)
    assert view._ticks == ticks_at_hide, "timer must not tick while hidden"


def test_ingest_view_show_starts_and_hide_stops_timer(qtbot: Any) -> None:
    view = IngestView(FakeOpsClient)
    qtbot.addWidget(view)

    assert not view._timer.isActive()
    view.show()
    assert view._timer.isActive()
    view.hide()
    assert not view._timer.isActive()


def test_ingest_view_unreachable_shows_degraded_without_exception(qtbot: Any) -> None:
    view = IngestView(lambda: FakeOpsClient(fail=True))
    qtbot.addWidget(view)
    view.show()
    qtbot.waitUntil(lambda: view.error_pane.isVisible(), timeout=2000)
    assert "connection refused" in view.error_pane.text()
    assert view.table.rowCount() == 0
    # auto-refresh pauses while unreachable (FR-DC-050 + AC-DC-6)
    assert not view._timer.isActive()


def test_ingest_view_api_error_also_degrades(qtbot: Any) -> None:
    view = IngestView(ApiErrorClient)
    qtbot.addWidget(view)
    view.show()
    qtbot.waitUntil(lambda: view.error_pane.isVisible(), timeout=2000)
    assert "boom" in view.error_pane.text()
    assert not view._timer.isActive()


# -- LedgerView (FR-DC-051) ---------------------------------------------------


def test_ledger_view_renders_entries_and_running_total(qtbot: Any) -> None:
    view = LedgerView(FakeOpsClient)
    qtbot.addWidget(view)
    view.show()
    qtbot.waitUntil(lambda: view.entries_table.rowCount() == 3, timeout=2000)

    assert view.entries_table.item(0, 0).text() == "l1"
    assert view.entries_table.item(0, 4).text() == "model/a"
    assert view.entries_table.item(2, 5).text() == "0.25"
    # running total of all entry costs, client-side
    assert abs(view.running_total() - 1.50) < 1e-9
    assert "1.50" in view.total_label.text()


def test_ledger_view_groups_spend_by_model(qtbot: Any) -> None:
    view = LedgerView(FakeOpsClient)
    qtbot.addWidget(view)
    view.show()
    qtbot.waitUntil(lambda: view.entries_table.rowCount() == 3, timeout=2000)

    by_model = view.spend_by_model()
    assert abs(by_model["model/a"] - 1.00) < 1e-9
    assert abs(by_model["model/b"] - 0.50) < 1e-9


def test_ledger_view_groups_spend_by_run(qtbot: Any) -> None:
    view = LedgerView(FakeOpsClient)
    qtbot.addWidget(view)
    view.show()
    qtbot.waitUntil(lambda: view.entries_table.rowCount() == 3, timeout=2000)

    by_run = view.spend_by_run()
    assert abs(by_run["r2"] - 1.25) < 1e-9
    # entries without a run_id group under a sentinel, never a literal run id
    assert abs(by_run["(no run)"] - 0.25) < 1e-9


def test_ledger_view_shows_period_spend(qtbot: Any) -> None:
    view = LedgerView(FakeOpsClient)
    qtbot.addWidget(view)
    view.show()
    qtbot.waitUntil(lambda: view.entries_table.rowCount() == 3, timeout=2000)
    assert "1.50" in view.period_label.text()


def test_ledger_view_unreachable_degrades_without_exception(qtbot: Any) -> None:
    view = LedgerView(lambda: FakeOpsClient(fail=True))
    qtbot.addWidget(view)
    view.show()
    qtbot.waitUntil(lambda: view.error_pane.isVisible(), timeout=2000)
    assert view.entries_table.rowCount() == 0
    assert view.running_total() == 0.0


def test_ledger_view_has_no_write_controls(qtbot: Any) -> None:
    """FR-DC-051 strict read-only: no button of any kind on the ledger view."""
    view = LedgerView(FakeOpsClient)
    qtbot.addWidget(view)
    from PySide6.QtWidgets import QPushButton

    assert not view.findChildren(QPushButton)


# -- ReferencesView (FR-DC-052) ------------------------------------------------


def test_references_view_renders_sources_ontology_versions(qtbot: Any) -> None:
    view = ReferencesView(FakeOpsClient)
    qtbot.addWidget(view)
    view.show()
    qtbot.waitUntil(lambda: view.sources_table.rowCount() == 1, timeout=2000)
    qtbot.waitUntil(lambda: view.relations_table.rowCount() == 1, timeout=2000)

    assert view.sources_table.item(0, 0).text() == "gisco_nuts"
    assert view.sources_table.item(0, 3).text() == "0.95"
    # relation catalog with domain/range, rendered from DATA not literals
    assert view.relations_table.item(0, 0).text() == "owns"
    assert view.relations_table.item(0, 1).text() == "Company"
    assert view.relations_table.item(0, 2).text() == "Company"
    # version list
    assert view.versions_list.count() == 2
    assert view.versions_list.item(0).text() == "1.0.0"
    assert view.versions_list.item(1).text() == "1.1.0"


def test_references_view_renders_entity_type_catalog(qtbot: Any) -> None:
    view = ReferencesView(FakeOpsClient)
    qtbot.addWidget(view)
    view.show()
    qtbot.waitUntil(lambda: view.entity_types_table.rowCount() == 1, timeout=2000)
    assert view.entity_types_table.item(0, 0).text() == "Company"
    assert view.entity_types_table.item(0, 1).text() == "Actor"


def test_references_view_unreachable_degrades_without_exception(qtbot: Any) -> None:
    view = ReferencesView(lambda: FakeOpsClient(fail=True))
    qtbot.addWidget(view)
    view.show()
    qtbot.waitUntil(lambda: view.error_pane.isVisible(), timeout=2000)
    assert view.sources_table.rowCount() == 0
    assert view.relations_table.rowCount() == 0


def test_ops_views_selection_bar_visible(qtbot: Any) -> None:
    """Tables are read-only: selection allowed, editing not."""
    view = IngestView(FakeOpsClient)
    qtbot.addWidget(view)
    view.show()
    qtbot.waitUntil(lambda: view.table.rowCount() == 2, timeout=2000)
    assert view.table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
