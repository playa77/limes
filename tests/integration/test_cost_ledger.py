# tests/integration/test_cost_ledger.py | v1.0.0 | introduced by WP-06
"""Cost ledger integration tests against a disposable Neo4j container.

Covers the §5.8 node schema, period aggregation, and the governor's monthly
vs envelope metering against the real graph (AC-14 partial, AC-15 partial).

Each test writes into its own `YYYY-MM`-shaped period string so totals are
order-independent; the monthly governor test derives its expectations from
`remaining()` for the same reason.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from limes.cost.governor import Governor
from limes.cost.ledger import read_period_spend, write_entry
from limes.errors import BudgetExhausted
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


def test_monthly_governor_refuses_against_real_ledger(driver: GraphDriver):
    # Expectations derive from remaining(), so the test is independent of any
    # other spend committed into the real current month. The preseed goes into
    # that month because the governor meters `now`'s YYYY-MM period.
    current_period = datetime.now(UTC).strftime("%Y-%m")
    write_entry(driver, _entry("g-m-1", Decimal("9.00"), current_period))
    governor = Governor(driver, Decimal("10.00"), 0.95, 0.92)
    assert governor.remaining() == Decimal("0.50")
    governor.check(Decimal("0.50"))
    with pytest.raises(BudgetExhausted):
        governor.check(Decimal("0.51"))


def test_envelope_governor_ignores_monthly_spend(driver: GraphDriver):
    # AC-15: envelope spend is independent of the monthly ceiling.
    write_entry(driver, _entry("g-e-0", Decimal("100.00"), "2099-01-envelope"))
    governor = Governor(driver, Decimal("10.00"), 0.95, 0.92, envelope_eur=Decimal("3.00"))
    governor.commit(_entry("g-e-1", Decimal("2.00"), "2099-01-envelope"))
    with pytest.raises(BudgetExhausted):
        governor.check(Decimal("1.01"))
    governor.check(Decimal("1.00"))
