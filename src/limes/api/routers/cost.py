# src/limes/api/routers/cost.py | v1.0.0 | introduced by WP-32
"""Cost ledger endpoint per Technical Specification §6: period spend read
from the graph (the ledger's own `read_period_spend` — C-07 makes the
graph the only state that survives between processes), the remaining
budget (null; enforcement was removed), and the period's entries."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from limes.api.deps import get_driver
from limes.api.models import native_datetime
from limes.cost.ledger import read_period_spend
from limes.graph.driver import GraphDriver

router = APIRouter(tags=["cost"])


def _current_period() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


_ENTRIES_QUERY = """
MATCH (e:CostLedgerEntry)
WHERE e.period = $period
RETURN e
ORDER BY e.created_at DESC
LIMIT $limit
"""


class LedgerEntryView(BaseModel):
    """One ledger entry as returned to the operator."""

    ledger_id: str
    period: str
    run_id: str | None = None
    purpose: str
    model_id: str
    input_tokens: int
    output_tokens: int
    cost_eur: float
    created_at: str


class LedgerView(BaseModel):
    """The ledger for one period: total spend, remaining budget, entries."""

    period: str
    spend_eur: float
    remaining_eur: float | None = None
    entries: list[LedgerEntryView]


@router.get("/cost/ledger")
def cost_ledger(
    driver: Annotated[GraphDriver, Depends(get_driver)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    period: Annotated[
        str,
        Query(
            pattern=r"^\d{4}-\d{2}$",
            description="YYYY-MM period; the current month by default",
        ),
    ] = _current_period(),
) -> LedgerView:
    """Period spend, remaining budget, and the period's entries."""
    spend = read_period_spend(driver, period)
    entries = []
    for row in driver.read(_ENTRIES_QUERY, {"period": period, "limit": limit}, 30):
        entry = row["e"]
        created = native_datetime(entry["created_at"])
        entries.append(
            LedgerEntryView(
                ledger_id=str(entry["ledger_id"]),
                period=str(entry["period"]),
                run_id=entry.get("run_id"),
                purpose=str(entry["purpose"]),
                model_id=str(entry["model_id"]),
                input_tokens=int(entry["input_tokens"]),
                output_tokens=int(entry["output_tokens"]),
                cost_eur=float(entry["cost_eur"]),
                created_at=created.isoformat() if created is not None else "",
            )
        )
    return LedgerView(
        period=period,
        spend_eur=float(spend),
        remaining_eur=None,
        entries=entries,
    )
