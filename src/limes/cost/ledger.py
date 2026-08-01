# src/limes/cost/ledger.py | v1.0.0 | introduced by WP-06
"""Cost ledger writes and reads per Technical Specification §5.8, §8.9.

Every paid call is recorded as a `:CostLedgerEntry` node with all §5.8
properties; the monthly aggregate for a `YYYY-MM` period is summed from the
graph, never from process memory — C-07 makes the graph the only state that
survives between CLI invocations, and the API's governor must see spend that
the worker committed in another process.
"""

from __future__ import annotations

from decimal import Decimal

from limes.graph.driver import GraphDriver
from limes.types import CostLedgerEntry

_ENTRY_WRITE = """
MERGE (e:CostLedgerEntry {ledger_id: $ledger_id})
SET e.period = $period,
    e.run_id = $run_id,
    e.purpose = $purpose,
    e.model_id = $model_id,
    e.input_tokens = $input_tokens,
    e.output_tokens = $output_tokens,
    e.cost_usd = $cost_usd,
    e.cost_eur = $cost_eur,
    e.created_at = $created_at
"""

_PERIOD_SPEND = """
MATCH (e:CostLedgerEntry {period: $period})
RETURN coalesce(sum(e.cost_eur), 0) AS total
"""


def write_entry(driver: GraphDriver, entry: CostLedgerEntry) -> None:
    """Write one ledger entry. Parameterized, no operator input (Doc 2 §7.3).
    `MERGE` on the unique `ledger_id` (constraint from §5.3) makes a retried
    transaction idempotent instead of failing on the constraint."""
    driver.write_batch(
        [
            (
                _ENTRY_WRITE,
                {
                    "ledger_id": entry.ledger_id,
                    "period": entry.period,
                    "run_id": entry.run_id,
                    "purpose": entry.purpose,
                    "model_id": entry.model_id,
                    "input_tokens": entry.input_tokens,
                    "output_tokens": entry.output_tokens,
                    "cost_usd": float(entry.cost_usd),
                    "cost_eur": float(entry.cost_eur),
                    "created_at": entry.created_at,
                },
            )
        ]
    )


def read_period_spend(driver: GraphDriver, period: str) -> Decimal:
    """Total `cost_eur` for one `YYYY-MM` period, read from the graph. Neo4j
    stores the decimal as a float; `Decimal(str(...))` recovers the exact
    value written by `write_entry`."""
    rows = driver.read(_PERIOD_SPEND, {"period": period}, timeout_s=30)
    return Decimal(str(rows[0]["total"]))
