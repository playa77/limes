# src/limes/cli/backfill.py | v1.0.0 | introduced by WP-28
"""Backfill over an explicit time window with passive cost accounting.

The optional legacy --budget flag is ignored; --days fixes the requested window.
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
    """Backfill a source over the last `--days` days under an explicit
    budget envelope (Doc 1 §9.2)."""
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
        record = run_with_lock(
            ctx,
            source,
            RunSpec(source_id=source, mode="backfill", since=since, budget_eur=envelope),
        )
        typer.echo(
            f"backfill {source} (since {since.isoformat()}): "
            f"{record.records_fetched} records, {record.assertions_written} assertions "
            f"written, {record.assertions_skipped} skipped, {record.errors} errors, "
            f"cost EUR {record.cost_eur}"
        )
        if record.errors:
            from limes.errors import LimesError

            raise LimesError(f"backfill {source}: record errors; checkpoint unchanged")
    finally:
        ctx.driver.close()
