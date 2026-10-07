# src/limes/cost/governor.py | v2.0.0 | passive accounting (D-75)
"""Passive cost accounting; legacy constructor arguments are ignored.

Governor is retained as an import alias for older integrations. There is no
budget enforcement, no spend-dependent refusal, and no monthly lookup before
inference. New code should use CostRecorder.
"""
from __future__ import annotations

from decimal import Decimal

from limes.cost.ledger import write_entry
from limes.graph.driver import GraphDriver
from limes.types import CostLedgerEntry


class CostRecorder:
    """Write reported usage and track spend in this process for run totals."""

    def __init__(
        self,
        driver: GraphDriver,
        monthly_ceiling_eur: Decimal | None = None,
        soft_stop_fraction: float | None = None,
        usd_eur_rate: float = 0.92,
        envelope_eur: Decimal | None = None,
    ) -> None:
        self._driver = driver
        self.usd_eur_rate = usd_eur_rate
        self.total_spend = Decimal("0")

    def commit(self, actual: CostLedgerEntry) -> None:
        """Persist accounting before updating the process's run-cost total."""
        write_entry(self._driver, actual)
        self.total_spend += actual.cost_eur

    def check(self, estimated_cost_eur: Decimal) -> None:
        """Compatibility no-op. Inference never calls this method."""


Governor = CostRecorder
