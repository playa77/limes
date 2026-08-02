# src/limes/api/routers/sources.py | v1.0.0 | introduced by WP-32
"""The source registry with its live refresh state per Technical
Specification §6: the authoritative adapter list comes from
`build_default_registry()` — the single sanctioned population function
(D-43) — and `:Source.last_success_at`/`last_run_id` come from the graph,
so a source that has never run is visible with null refresh."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from limes.api.deps import get_driver
from limes.api.models import native_datetime
from limes.graph.driver import GraphDriver
from limes.sources.registry import build_default_registry

router = APIRouter(tags=["sources"])

_SOURCE_STATE_QUERY = """
MATCH (s:Source)
RETURN s.source_id AS source_id,
       s.last_success_at AS last_success_at,
       s.last_run_id AS last_run_id
"""


class SourceView(BaseModel):
    """One registered source: the registry's declarations plus the graph's
    last-refresh state. `last_success_at` is null for a source that has
    never run."""

    source_id: str
    name: str
    kind: str
    trust_rank: float
    supports_backfill: bool
    supports_incremental: bool
    last_success_at: str | None = None
    last_run_id: str | None = None


@router.get("/sources")
def sources(driver: Annotated[GraphDriver, Depends(get_driver)]) -> list[SourceView]:
    """Every registered source with its trust rank and last refresh."""
    registry = build_default_registry()
    state: dict[str, tuple[str | None, str | None]] = {}
    for row in driver.read(_SOURCE_STATE_QUERY, {}, 30):
        last = native_datetime(row["last_success_at"])
        state[str(row["source_id"])] = (
            last.isoformat() if last is not None else None,
            row["last_run_id"],
        )
    views: list[SourceView] = []
    for source_id in registry.source_ids():
        adapter = registry.get(source_id)
        last_success_at, last_run_id = state.get(source_id, (None, None))
        views.append(
            SourceView(
                source_id=source_id,
                name=adapter.name,
                kind=str(adapter.kind),
                trust_rank=adapter.trust_rank,
                supports_backfill=adapter.supports_backfill,
                supports_incremental=adapter.supports_incremental,
                last_success_at=last_success_at,
                last_run_id=last_run_id,
            )
        )
    return views
