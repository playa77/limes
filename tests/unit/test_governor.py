# tests/unit/test_governor.py | v1.0.0 | introduced by WP-06
"""Governor arithmetic per Doc 2 §8.9.

The stub driver emulates the ledger's behavior (a commit raises the spend a
subsequent monthly read returns), so these tests exercise the governor's
decisions, not the graph. Ledger-vs-graph behavior is covered by the
integration tests.
"""

from datetime import UTC, datetime
from decimal import Decimal

from limes.cost.recorder import CostRecorder
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


def test_cost_recorder_never_reads_monthly_spend():
    stub = StubDriver(preseeded=Decimal("1000000"))
    recorder = CostRecorder(stub)
    recorder.commit(_entry(Decimal("200")))
    assert recorder.spent_eur == Decimal("200")
    assert stub.committed[0].cost_eur == Decimal("200")
    assert not hasattr(recorder, "check")
    assert not hasattr(recorder, "remaining")


def test_process_spend_accumulates_provider_costs():
    stub = StubDriver()
    recorder = CostRecorder(stub)
    recorder.commit(_entry(Decimal("2.50"), "first"))
    recorder.commit(_entry(Decimal("1.50"), "second"))
    assert recorder.spent_eur == Decimal("4.00")
    assert len(stub.committed) == 2
