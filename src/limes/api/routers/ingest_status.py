# src/limes/api/routers/ingest_status.py | v1.0.0 | introduced by WP-32
"""Ingestion status per Technical Specification §6: the latest
`:IngestionRun` per source with all its counters — the durable surface
where nothing is silently dropped, per §10 and §11 — plus each source's
`last_success_at` from `:Source`."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from limes.api.deps import get_driver
from limes.api.models import native_datetime
from limes.graph.driver import GraphDriver

router = APIRouter(tags=["ingest"])

_LAST_RUN_PER_SOURCE = """
MATCH (r:IngestionRun)
WITH r ORDER BY r.started_at DESC
WITH r.source_id AS source_id, collect(r)[0] AS latest
RETURN latest
"""

_SOURCE_STATE_QUERY = """
MATCH (s:Source)
RETURN s.source_id AS source_id, s.last_success_at AS last_success_at
"""


class RunStatus(BaseModel):
    """The latest ingestion run for one source, with the source's last
    success timestamp alongside."""

    source_id: str
    mode: str
    run_id: str
    started_at: str
    finished_at: str | None = None
    records_fetched: int = 0
    nodes_created: int = 0
    nodes_matched: int = 0
    assertions_written: int = 0
    assertions_skipped: int = 0
    assertions_rejected: int = 0
    documents_gated_out: int = 0
    errors: int = 0
    cost_eur: float = 0.0
    last_success_at: str | None = None


@router.get("/ingest/status")
def ingest_status(driver: Annotated[GraphDriver, Depends(get_driver)]) -> list[RunStatus]:
    """The latest run per source with counts and errors; a source that has
    never run is absent from the list (its `:Source` node appears on the
    `/sources` endpoint instead)."""
    statuses: list[RunStatus] = []
    for row in driver.read(_LAST_RUN_PER_SOURCE, {}, 30):
        run = row["latest"]
        started = native_datetime(run["started_at"])
        finished = native_datetime(run["finished_at"])
        statuses.append(
            RunStatus(
                source_id=str(run["source_id"]),
                mode=str(run["mode"]),
                run_id=str(run["run_id"]),
                started_at=started.isoformat() if started is not None else "",
                finished_at=finished.isoformat() if finished is not None else None,
                records_fetched=int(run.get("records_fetched") or 0),
                nodes_created=int(run.get("nodes_created") or 0),
                nodes_matched=int(run.get("nodes_matched") or 0),
                assertions_written=int(run.get("assertions_written") or 0),
                assertions_skipped=int(run.get("assertions_skipped") or 0),
                assertions_rejected=int(run.get("assertions_rejected") or 0),
                documents_gated_out=int(run.get("documents_gated_out") or 0),
                errors=int(run.get("errors") or 0),
                cost_eur=float(run.get("cost_eur") or 0.0),
            )
        )
    success: dict[str, str | None] = {}
    for row in driver.read(_SOURCE_STATE_QUERY, {}, 30):
        last = native_datetime(row["last_success_at"])
        success[str(row["source_id"])] = last.isoformat() if last is not None else None
    for status in statuses:
        status.last_success_at = success.get(status.source_id)
    return statuses
