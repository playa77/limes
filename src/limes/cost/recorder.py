# src/limes/cost/recorder.py | v1.1.0 | passive inference accounting
"""Record provider-reported costs without enforcing spending limits."""

from decimal import Decimal

from limes.cost.ledger import write_entry
from limes.graph.driver import GraphDriver
from limes.types import CostLedgerEntry


class CostRecorder:
    """One process's spend; the durable ledger remains the source of totals."""

    def __init__(self, driver: GraphDriver) -> None:
        self._driver = driver
        self.spent_eur = Decimal("0")

    def commit(self, actual: CostLedgerEntry) -> None:
        write_entry(self._driver, actual)
        self.spent_eur += actual.cost_eur
