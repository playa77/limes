# src/limes/cli/ingest.py | v1.0.0 | introduced by WP-28
"""The `ingest` and `ingest-all` commands (Doc 2 §8.14, §15.3 Trace 1).

One run per command: `build_run_context` (WP-26) → advisory lock (WP-28) →
`execute_run` (WP-27) → release. The context's `needs_inference` follows
the source's kind — a structured source is a deterministic load and must
not pay for spaCy or an extractor (AC-41, the resource contract); an
unstructured source cannot run without them. The kind is inspected through
the sanctioned registry function (D-43).

`ingest-all` runs every ingestable source in sequence, skipping
enrichment-only sources — `wikidata`'s `fetch` raises `NotImplementedError`
(WP-18), which is not a `LimesError` and would surface as a traceback; the
roadmap names it as the enrichment-only source to skip. The list is the
named refresh point for any future enrichment-only source.
"""

from __future__ import annotations

import structlog
import typer

from limes.config import Settings, load_settings
from limes.logging_setup import configure_logging
from limes.pipeline.run import RunSpec

logger = structlog.get_logger(__name__)


def ingest_source(
    source: str = typer.Option(..., "--source", help="The source id to ingest (see ingest-all)"),
    since: str | None = typer.Option(
        None, "--since", help="ISO-8601 window start; overrides last-success anchoring"
    ),
    until: str | None = typer.Option(None, "--until", help="ISO-8601 window end"),
) -> None:
    """Ingest one source now — the manual ingestion path (Doc 1 §9.1)."""
    from limes.cli.main import parse_iso_datetime

    settings = load_settings()
    configure_logging(settings)
    _ingest_source(
        settings,
        source,
        RunSpec(
            source_id=source,
            mode="ingest",
            since=parse_iso_datetime(since, "--since"),
            until=parse_iso_datetime(until, "--until"),
        ),
    )
    typer.echo(f"ingest {source}: done")


def ingest_all() -> None:
    """Ingest every ingestable source in sequence, skipping
    enrichment-only sources (D-43). Each source runs under its own
    advisory lock; a failure aborts the sequence — the failed run's record
    is durable, and the remaining sources are not silently skipped."""
    settings = load_settings()
    configure_logging(settings)
    for source_id in _ingestable_source_ids():
        typer.echo(f"ingest-all: {source_id}")
        _ingest_source(
            settings,
            source_id,
            RunSpec(source_id=source_id, mode="ingest"),
        )
    typer.echo("ingest-all: complete")


def _ingest_source(settings: Settings, source_id: str, spec: RunSpec) -> None:
    """The shared run: context per kind, lock, execute, release."""
    from limes.errors import LimesError

    if source_id in ("wikipedia", "yahoo_finance"):
        raise LimesError("use enrich with reviewed entity selections")
    if source_id == "news":
        raise LimesError("use news-refresh with an investigation ID")
    from limes.cli.main import adapter_kind, run_with_lock
    from limes.composition import build_run_context

    ctx = build_run_context(
        settings,
        needs_inference=(adapter_kind(source_id) == "unstructured"),
    )
    try:
        record = run_with_lock(ctx, source_id, spec)
        typer.echo(
            f"ingest {source_id}: {record.records_fetched} records, "
            f"{record.assertions_written} assertions written, "
            f"{record.assertions_skipped} skipped, {record.errors} errors, "
            f"cost EUR {record.cost_eur}"
        )
    finally:
        ctx.driver.close()


def _ingestable_source_ids() -> list[str]:
    """The sources `ingest-all` runs: every registered source except
    enrichment-only ones. `wikidata` is the roadmap-named enrichment-only
    source (WP-18): its `fetch` raises `NotImplementedError`, which is not
    a `LimesError` and must never reach the run loop. Any future
    enrichment-only source extends this list — the single refresh point."""
    from limes.sources.registry import build_default_registry

    return [
        source_id
        for source_id in build_default_registry().source_ids()
        if source_id not in ("wikidata", "news", "wikipedia", "yahoo_finance")
    ]
