# src/limes/cli/reextract.py | v1.0.0 | introduced by WP-28
"""Re-extract archived text under an explicit prompt/cache version.

Superseded assertions are retracted, never deleted. Legacy --budget is ignored.
"""

from __future__ import annotations

from decimal import Decimal

import structlog
import typer

from limes.config import Settings, load_settings
from limes.logging_setup import configure_logging
from limes.pipeline.run import RunSpec

logger = structlog.get_logger(__name__)


def reextract_source(
    prompt_version: str = typer.Option(..., "--prompt-version", help="The new prompt version"),
    source: str | None = typer.Option(
        None, "--source", help="Restrict re-extraction to one source (default: all unstructured)"
    ),
    budget: float | None = typer.Option(
        None, "--budget", min=0, help="Deprecated compatibility option; ignored"
    ),
) -> None:
    """Re-extract documents under a new prompt version, retracting
    superseded assertions — never deleting (Doc 1 §9.4)."""
    settings = load_settings()
    configure_logging(settings)
    envelope = Decimal(str(budget)) if budget is not None else None
    # Record the requested prompt version; reextract bypasses document cache
    # hits so a retry can finish replacement/retraction before caching.
    settings = settings.model_copy(update={"extraction_prompt_version": prompt_version})
    for source_id in _reextract_sources(source):
        _reextract_one(settings, source_id, envelope)


def _reextract_one(settings: Settings, source_id: str, envelope: Decimal | None) -> None:
    from limes.cli.main import adapter_kind, run_with_lock
    from limes.composition import build_run_context

    ctx = build_run_context(
        settings,
        needs_inference=(adapter_kind(source_id) == "unstructured"),
        budget_eur=envelope,
    )
    try:
        record = run_with_lock(
            ctx,
            source_id,
            RunSpec(source_id=source_id, mode="reextract", budget_eur=envelope),
        )
        typer.echo(
            f"reextract {source_id}: {record.records_fetched} records, "
            f"{record.assertions_written} assertions written, "
            f"{record.assertions_skipped} skipped, {record.errors} errors, "
            f"cost EUR {record.cost_eur}"
        )
    finally:
        ctx.driver.close()


def _reextract_sources(explicit: str | None) -> list[str]:
    """The sources a reextract run covers: the explicit `--source`, or every
    unstructured source — the document-producing ones (D-45). Structured
    sources hold no documents and nothing to retract."""
    from limes.cli.main import adapter_kind

    if explicit is not None:
        adapter_kind(explicit)  # fail fast on an unknown id (AC-38)
        return [explicit]
    from limes.sources.registry import build_default_registry

    return [
        source_id
        for source_id in build_default_registry().source_ids()
        if source_id != "news" and adapter_kind(source_id) == "unstructured"
    ]
