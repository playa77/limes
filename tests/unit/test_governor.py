# tests/unit/test_governor.py | v1.0.0 | introduced by WP-06
"""Governor arithmetic per Doc 2 §8.9.

The stub driver emulates the ledger's behavior (a commit raises the spend a
subsequent monthly read returns), so these tests exercise the governor's
decisions, not the graph. Ledger-vs-graph behavior is covered by the
integration tests.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from limes.cost.governor import Governor
from limes.errors import BudgetExhausted
from limes.types import CostLedgerEntry

PERIOD = "2026-08"
CEILING = Decimal("10.00")
SOFT_STOP = 0.95


class StubDriver:
    """Fake `GraphDriver` whose ledger reads reflect prior commits, like a
    real database would."""

    def __init__(self, preseeded: Decimal = Decimal("0")) -> None:
        self._period_spend = preseeded
        self.committed: list[CostLedgerEntry] = []

    def read(self, cypher: str, params: dict, timeout_s: int) -> list[dict]:
        if "sum(e.cost_eur)" in cypher:
            return [{"total": float(self._period_spend)}]
        return []

    def write_batch(self, statements: list[tuple[str, dict]]) -> object:
        for _, params in statements:
            entry = CostLedgerEntry(
                ledger_id=params["ledger_id"],
                period=params["period"],
                purpose="extraction",
                model_id=params["model_id"],
                input_tokens=params["input_tokens"],
                output_tokens=params["output_tokens"],
                cost_usd=Decimal(str(params["cost_usd"])),
                cost_eur=Decimal(str(params["cost_eur"])),
                created_at=params["created_at"],
            )
            self.committed.append(entry)
            self._period_spend += entry.cost_eur
        return None


def _entry(cost_eur: Decimal, ledger_id: str = "e1") -> CostLedgerEntry:
    return CostLedgerEntry(
        ledger_id=ledger_id,
        period=PERIOD,
        purpose="extraction",
        model_id="test-model",
        input_tokens=100,
        output_tokens=50,
        cost_usd=cost_eur / Decimal("0.92"),
        cost_eur=cost_eur,
        created_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC),
    )


def _governor(stub: StubDriver, envelope: Decimal | None = None) -> Governor:
    return Governor(stub, CEILING, SOFT_STOP, 0.92, envelope_eur=envelope)


def test_check_passes_below_soft_stop_threshold():
    governor = _governor(StubDriver())
    governor.check(Decimal("1.00"))  # far below 9.50 threshold


def test_check_raises_above_soft_stop_threshold():
    governor = _governor(StubDriver())
    with pytest.raises(BudgetExhausted):
        governor.check(Decimal("9.51"))


def test_check_refuses_at_threshold_not_at_ceiling():
    # Soft stop: refusal at 10.00 * 0.95 = 9.50, not at the 10.00 ceiling.
    governor = _governor(StubDriver())
    governor.check(Decimal("9.50"))  # exactly at threshold: passes
    with pytest.raises(BudgetExhausted):
        governor.check(Decimal("9.51"))


def test_monthly_check_sees_preseeded_period_spend():
    governor = _governor(StubDriver(preseeded=Decimal("9.00")))
    governor.check(Decimal("0.49"))  # 9.49 projected: passes
    with pytest.raises(BudgetExhausted):
        governor.check(Decimal("0.51"))  # 9.51 projected: refused


def test_monthly_check_sees_own_commits():
    stub = StubDriver()
    governor = _governor(stub)
    governor.commit(_entry(Decimal("9.00")))
    with pytest.raises(BudgetExhausted):
        governor.check(Decimal("0.60"))
    governor.check(Decimal("0.49"))


def test_commit_writes_entry_to_ledger():
    stub = StubDriver()
    governor = _governor(stub)
    governor.commit(_entry(Decimal("2.50"), ledger_id="ledger-1"))
    assert len(stub.committed) == 1
    assert stub.committed[0].ledger_id == "ledger-1"
    assert stub.committed[0].cost_eur == Decimal("2.50")


def test_envelope_mode_meters_against_envelope():
    stub = StubDriver(preseeded=Decimal("100.00"))  # monthly spend is irrelevant
    governor = _governor(stub, envelope=Decimal("3.00"))
    governor.commit(_entry(Decimal("2.00"), ledger_id="envelope-1"))
    governor.check(Decimal("1.00"))  # 3.00 projected against 3.00: passes
    with pytest.raises(BudgetExhausted):
        governor.check(Decimal("1.01"))


def test_envelope_mode_ignores_monthly_ceiling():
    # AC-15: backfill meters against its envelope and never draws on the
    # monthly ceiling, even when that ceiling is already exhausted.
    stub = StubDriver(preseeded=Decimal("20.00"))
    governor = _governor(stub, envelope=Decimal("3.00"))
    governor.check(Decimal("3.00"))  # monthly would refuse; envelope passes


def test_remaining_monthly():
    stub = StubDriver(preseeded=Decimal("1.00"))
    governor = _governor(stub)
    assert governor.remaining() == CEILING * Decimal(str(SOFT_STOP)) - Decimal("1.00")


def test_remaining_envelope_never_negative():
    governor = _governor(StubDriver(), envelope=Decimal("2.00"))
    governor.commit(_entry(Decimal("5.00"), ledger_id="over"))
    assert governor.remaining() == Decimal("0")
