# src/limes/pipeline/window.py | v1.0.0 | introduced by WP-27
"""Ingestion window resolution per Technical Specification §8.6.2.

The window an ingestion run covers is a pure function of the run spec, the
adapter's incremental capability, and the source's durable last-success
mark — no graph reads here, `execute_run` supplies the `SourceRecord`.
This is the reason `supports_incremental` exists on the protocol and why
`Source.last_success_at` is read, not merely written (§8.6.2).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from limes.config import Settings
from limes.sources.base import SourceAdapter
from limes.types import SourceRecord

if TYPE_CHECKING:
    from limes.pipeline.run import RunSpec


def resolve_window(
    spec: RunSpec,
    adapter: SourceAdapter,
    source_node: SourceRecord | None,
    settings: Settings,
    now: datetime | None = None,
) -> tuple[datetime | None, datetime | None]:
    """The ingestion window `(since, until)` for one run (AC-42).

    An explicit `since` in the spec always wins. Otherwise an incremental
    source starts at `Source.last_success_at` — or at
    `now − LIMES_BACKFILL_DAYS_UNSTRUCTURED` when the source has never run
    — and a non-incremental source is a full load, `(None, None)`.

    `settings` supplies the backfill-day cutoff the §8.6.2 signature cannot
    reach (D-40), and `now` is injectable for deterministic tests;
    production callers omit it.
    """
    if spec.since is not None:
        return spec.since, spec.until
    if not adapter.supports_incremental:
        return None, None
    if source_node is not None and source_node.last_success_at is not None:
        return source_node.last_success_at, spec.until
    cutoff = (now or datetime.now(UTC)) - timedelta(days=settings.backfill_days_unstructured)
    return cutoff, spec.until
