# tests/integration/test_cost_ledger.py | v1.0.0 | introduced by WP-06
"""Passive ledger persistence and period aggregation against a real database.
Legacy limits cannot refuse calls; process-local totals track run spend."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from limes.cost.governor import Governor
from limes.cost.ledger import read_period_spend, write_entry
from limes.graph.driver import GraphDriver
from limes.types import CostLedgerEntry
from tests.integration.conftest import Neo4jInstance


@pytest.fixture
def driver(neo4j_instance: Neo4jInstance) -> GraphDriver:
    d = GraphDriver(
        neo4j_instance.uri,
        neo4j_instance.user,
        neo4j_instance.password,
        neo4j_instance.database,
    )
    yield d
    d.close()


def _entry(ledger_id: str, cost_eur: Decimal, period: str) -> CostLedgerEntry:
    return CostLedgerEntry(
        ledger_id=ledger_id,
        period=period,
        run_id="run-1",
        purpose="extraction",
        model_id="test-model",
        input_tokens=100,
        output_tokens=50,
        cost_usd=cost_eur / Decimal("0.92"),
        cost_eur=cost_eur,
        created_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC),
    )


def test_write_entry_materializes_full_schema(driver: GraphDriver):
    period = "2026-08-schema"
    write_entry(driver, _entry("ledger-full", Decimal("1.25"), period))

    rows = driver.read(
        "MATCH (e:CostLedgerEntry {ledger_id: $id}) RETURN e",
        {"id": "ledger-full"},
        10,
    )
    assert len(rows) == 1
    node = rows[0]["e"]
    assert node["period"] == period
    assert node["run_id"] == "run-1"
    assert node["purpose"] == "extraction"
    assert node["model_id"] == "test-model"
    assert node["input_tokens"] == 100
    assert node["output_tokens"] == 50
    assert node["created_at"].year == 2026


def test_read_period_spend_sums_entries(driver: GraphDriver):
    period = "2026-08-sums"
    write_entry(driver, _entry("sum-a", Decimal("1.00"), period))
    write_entry(driver, _entry("sum-b", Decimal("2.50"), period))
    assert read_period_spend(driver, period) == Decimal("3.50")


def test_read_period_spend_separates_periods(driver: GraphDriver):
    write_entry(driver, _entry("period-a", Decimal("9.00"), "2026-07-sep"))
    write_entry(driver, _entry("period-b", Decimal("1.00"), "2026-08-sep"))
    assert read_period_spend(driver, "2026-07-sep") == Decimal("9.00")
    assert read_period_spend(driver, "2026-08-sep") == Decimal("1.00")


def test_write_entry_is_idempotent_on_ledger_id(driver: GraphDriver):
    write_entry(driver, _entry("idem", Decimal("2.00"), "2026-08-idem"))
    write_entry(driver, _entry("idem", Decimal("2.00"), "2026-08-idem"))
    rows = driver.read(
        "MATCH (e:CostLedgerEntry {ledger_id: 'idem'}) RETURN count(e) AS c",
        {},
        10,
    )
    assert rows[0]["c"] == 1


def test_passive_recorder_accepts_spend_above_legacy_limits(driver: GraphDriver):
    recorder = Governor(driver, Decimal("0"), 0.0, 0.92, envelope_eur=Decimal("0"))
    recorder.commit(_entry("passive-1", Decimal("25"), "2099-01-passive"))
    recorder.check(Decimal("100"))
    assert recorder.total_spend == Decimal("25")
    assert read_period_spend(driver, "2099-01-passive") == Decimal("25")
