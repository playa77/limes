# tests/unit/test_governor.py | v1.0.0 | introduced by WP-06
"""Passive accounting and compatibility guards for D-75. No spend-dependent refusal."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from limes.cost.governor import Governor
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


def test_legacy_budget_arguments_never_refuse_or_read_spend():
    stub = StubDriver(preseeded=Decimal("1000"))
    stub.read = lambda *args, **kwargs: pytest.fail("accounting must not read spend before calls")
    recorder = _governor(stub, envelope=Decimal("0"))
    recorder.check(Decimal("1000000"))
    recorder.commit(_entry(Decimal("50")))
    recorder.check(Decimal("1000000"))
    assert recorder.total_spend == Decimal("50")
    assert len(stub.committed) == 1


def test_failed_ledger_write_does_not_change_process_total():
    stub = StubDriver()
    recorder = _governor(stub)
    def fail(statements):
        raise RuntimeError("ledger unavailable")
    stub.write_batch = fail
    with pytest.raises(RuntimeError, match="ledger unavailable"):
        recorder.commit(_entry(Decimal("2")))
    assert recorder.total_spend == 0


def test_recorder_total_is_process_local_and_ledger_entries_preserved():
    stub = StubDriver(preseeded=Decimal("1000"))
    recorder = _governor(stub)
    recorder.commit(_entry(Decimal("2.50"), "first"))
    recorder.commit(_entry(Decimal("3.50"), "second"))
    assert recorder.total_spend == Decimal("6")
    assert [entry.ledger_id for entry in stub.committed] == ["first", "second"]
