# src/limes/cost/governor.py | v1.0.0 | introduced by WP-06
"""Budget governor per Technical Specification §8.9, Doc 1 §4.9, §9.3.

Every paid call passes `check` before issue and `commit` after. Two metering
scopes exist: the monthly ceiling (refuses a call when projected spend
exceeds the soft-stop fraction of the ceiling) and a per-run envelope
(backfill and re-extraction meter against it and never draw on the monthly
ceiling — AC-15).

Monthly-mode spend is read from the graph on every check so a fresh process
sees what other processes committed (C-07). Envelope spend is tracked in
process memory: an envelope exists for one run in one process, and a crashed
run is simply over. `commit` both writes the ledger node and updates the
in-process running total.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from limes.cost.ledger import read_period_spend, write_entry
from limes.errors import BudgetExhausted
from limes.graph.driver import GraphDriver
from limes.types import CostLedgerEntry


class Governor:
    """Refuses paid calls past the metered ceiling and records every one."""

    def __init__(
        self,
        driver: GraphDriver,
        monthly_ceiling_eur: Decimal,
        soft_stop_fraction: float,
        usd_eur_rate: float,
        envelope_eur: Decimal | None = None,
    ) -> None:
        self._driver = driver
        self._monthly_ceiling = monthly_ceiling_eur
        self._soft_stop_fraction = soft_stop_fraction
        self._usd_eur_rate = usd_eur_rate
        self._envelope = envelope_eur
        self._running_total = Decimal("0")

    @property
    def usd_eur_rate(self) -> float:
        """Rate the OpenRouter client (WP-22) uses to price calls in EUR."""
        return self._usd_eur_rate

    def _threshold(self) -> Decimal:
        """The refusal threshold for the active metering scope: the envelope
        itself, or the soft-stop fraction of the monthly ceiling."""
        if self._envelope is not None:
            return self._envelope
        return self._monthly_ceiling * Decimal(str(self._soft_stop_fraction))

    def _scope_name(self) -> str:
        return "envelope" if self._envelope is not None else "monthly ceiling"

    def _spent(self) -> Decimal:
        if self._envelope is not None:
            return self._running_total
        period = datetime.now(UTC).strftime("%Y-%m")
        return read_period_spend(self._driver, period)

    def check(self, estimated_cost_eur: Decimal) -> None:
        """Refuse a call whose projected spend would breach the active scope.
        Reads, never writes. Raises `BudgetExhausted` so the run can close
        cleanly with remaining work marked queued (AC-14)."""
        projected = self._spent() + estimated_cost_eur
        if projected > self._threshold():
            raise BudgetExhausted(
                f"{self._scope_name()} budget exhausted: {projected:.2f} EUR "
                f"projected against a threshold of {self._threshold():.2f} EUR"
            )

    def commit(self, actual: CostLedgerEntry) -> None:
        """Record one paid call in the ledger and the in-process running
        total. Callers pass token usage reported by the provider; ledger
        entries are written only for attempts that returned usage (§8.7.6)."""
        write_entry(self._driver, actual)
        self._running_total += actual.cost_eur

    def remaining(self) -> Decimal:
        """Budget left in the active metering scope, floored at zero."""
        return max(Decimal("0"), self._threshold() - self._spent())
