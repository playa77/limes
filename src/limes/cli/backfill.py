# src/limes/cli/backfill.py | v1.0.0 | introduced by WP-28
"""Backfill over an explicit time window with passive cost accounting.

The optional legacy --budget flag is ignored. GDELT consumes an older checkpoint
before the requested fresh window, continuing prefixes through the safe target.
Relative-day requests preserve the original pinned window after interruption.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import structlog
import typer

from limes.config import load_settings
from limes.logging_setup import configure_logging
from limes.pipeline.run import RunSpec

logger = structlog.get_logger(__name__)


def backfill_source(
    source: str = typer.Option(..., "--source", help="The source id to backfill"),
    days: int = typer.Option(..., "--days", min=1, help="How many days back to fetch"),
    budget: float | None = typer.Option(
        None, "--budget", min=0, help="Deprecated compatibility option; ignored"
    ),
) -> None:
    """Backfill the requested days, or GDELT's oldest outstanding bounded prefix."""
    from limes.cli.main import adapter_kind, run_with_lock
    from limes.composition import build_run_context

    settings = load_settings()
    configure_logging(settings)

    envelope = Decimal(str(budget)) if budget is not None else None
    since = datetime.now(UTC) - timedelta(days=days)
    ctx = build_run_context(
        settings,
        needs_inference=(adapter_kind(source) == "unstructured"),
        budget_eur=envelope,
    )
    try:
        from limes.errors import LimesError, SourceSliceEnded

        target = datetime.now(UTC)
        target = getattr(ctx.registry.get(source), "ingest_target", lambda value: value)(target)
        previous = None
        while True:
            try:
                record = run_with_lock(
                    ctx, source,
                    RunSpec(source_id=source, mode="backfill", since=since, budget_eur=envelope,
                            relative_days=days),
                )
            except SourceSliceEnded as exc:
                typer.echo(f"backfill {source}: {exc}")
                continue
            typer.echo(
                f"backfill {source} (since {(record.window_from or since).isoformat()}): "
                f"{record.records_fetched} records, {record.assertions_written} assertions "
                f"written, {record.assertions_skipped} skipped, {record.errors} errors, "
                f"cost EUR {record.cost_eur}"
            )
            if record.errors:
                raise LimesError(f"backfill {source}: record errors; checkpoint unchanged")
            if record.window_to is None or record.window_to >= target:
                break
            if previous is not None and record.window_to <= previous:
                raise LimesError(f"backfill {source}: backlog did not advance; incomplete")
            previous = record.window_to
            typer.echo(
                f"backfill {source}: backlog remains through {target.isoformat()}; continuing"
            )
    finally:
        ctx.driver.close()
