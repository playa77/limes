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
from limes.data_scope import DATA_SCOPE_VERSION, DATA_START, scoped_window
from limes.sources.base import SourceAdapter
from limes.types import SourceRecord

if TYPE_CHECKING:
    from limes.pipeline.run import RunSpec


def checkpoint_anchored_backfill(spec: RunSpec, source_node: SourceRecord | None) -> bool:
    """Only GDELT's rolling backfill surface opts into oldest-prefix addressing."""
    return (spec.mode == "backfill" and spec.source_id == "gdelt"
            and spec.since is not None and spec.until is None
            and source_node is not None and source_node.last_success_at is not None
            and source_node.last_success_at < spec.since)


def _resolve_window(
    spec: RunSpec,
    adapter: SourceAdapter,
    source_node: SourceRecord | None,
    settings: Settings,
    now: datetime | None = None,
) -> tuple[datetime | None, datetime | None]:
    """The ingestion window `(since, until)` for one run (AC-42).

    An explicit `since` wins except for checkpoint-anchored GDELT backfill.
    Otherwise an incremental
    source starts at `Source.last_success_at` — or at
    `now − LIMES_BACKFILL_DAYS_UNSTRUCTURED` when the source has never run
    — and a non-incremental source observes the complete current snapshot.
    The public resolver applies the source-acquisition floor to every route.

    `settings` supplies the backfill-day cutoff the §8.6.2 signature cannot
    reach (D-40), and `now` is injectable for deterministic tests;
    production callers omit it.
    """
    if spec.since is not None:
        # Resolve after the locked checkpoint read, never in the CLI before locking.
        # Only GDELT opted into oldest-prefix backfill; other sources retain D-44.
        if checkpoint_anchored_backfill(spec, source_node):
            assert source_node is not None and source_node.last_success_at is not None
            cutoff = max(DATA_START, source_node.last_success_at)
            # A pre-scope checkpoint has not consumed the first eligible slot.
            first = (cutoff + timedelta(microseconds=1)
                     if source_node.last_success_at >= DATA_START else cutoff)
            return cutoff, adapter.bound_ingest_window(  # type: ignore[attr-defined]
                first, now or datetime.now(UTC))
        if spec.source_id == "gdelt" and spec.until is None:
            return spec.since, adapter.ingest_target(  # type: ignore[attr-defined]
                now or datetime.now(UTC))
        return spec.since, spec.until
    if not adapter.supports_incremental:
        return None, spec.until
    if getattr(adapter, "full_initial_load", False) and not (
        source_node is not None and source_node.corpus_complete
        and source_node.data_scope_version == DATA_SCOPE_VERSION
    ):
        # A legacy 90-day success is not evidence of initial corpus coverage.
        return None, spec.until
    if source_node is not None and source_node.last_success_at is not None:
        cutoff = max(DATA_START, source_node.last_success_at)
    elif source_node is not None and source_node.initial_window_from is not None:
        cutoff = max(DATA_START, source_node.initial_window_from)
    elif getattr(adapter, "full_initial_load", False):
        # Structured corpus acquisition must not inherit a news lookback.
        return None, spec.until
    else:
        cutoff = max(DATA_START, (now or datetime.now(UTC))
                     - timedelta(days=settings.backfill_days_unstructured))
    bound = getattr(adapter, "bound_ingest_window", None)
    if bound is not None:
        return cutoff, bound(cutoff, spec.until or now or datetime.now(UTC))
    return cutoff, spec.until


def resolve_window(
    spec: RunSpec,
    adapter: SourceAdapter,
    source_node: SourceRecord | None,
    settings: Settings,
    now: datetime | None = None,
) -> tuple[datetime, datetime | None]:
    """Resolve all run modes within the inclusive prototype corpus boundary."""
    start, end = scoped_window(spec.since, spec.until)
    bounded = spec.model_copy(update={"since": start if spec.since is not None else None,
                                      "until": end})
    return scoped_window(*_resolve_window(bounded, adapter, source_node, settings, now))
