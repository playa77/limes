"""Bounded reviewed enrichment; CLI/worker share the existing archive pipeline."""

from __future__ import annotations

import json
from typing import Annotated, Literal

import typer
from pydantic import ValidationError

from limes.config import load_settings
from limes.enrichment.models import EnrichmentSelection
from limes.enrichment.service import prepare_targets
from limes.errors import LimesError
from limes.logging_setup import configure_logging
from limes.pipeline.run import RunSpec
from limes.sources.wikipedia import WikipediaAdapter
from limes.sources.yahoo_finance import YahooFinanceAdapter


def enrich(
    source: Annotated[Literal["wikipedia", "yahoo_finance"], typer.Option("--source")],
    selections: Annotated[str, typer.Option("--selections", help="JSON reviewed entity mappings")],
    extract_context: Annotated[bool, typer.Option("--extract-context")] = False,
) -> None:
    from limes.cli.main import run_with_lock
    from limes.composition import build_run_context

    try:
        values = json.loads(selections)
        if not isinstance(values, list) or not 1 <= len(values) <= 10:
            raise ValueError("select one to ten entities")
        selected = [EnrichmentSelection.model_validate(v) for v in values]
    except (ValueError, ValidationError) as exc:
        raise LimesError("invalid reviewed enrichment selections") from exc
    if extract_context and source != "wikipedia":
        raise LimesError("extraction is only supported for Wikipedia context")
    settings = load_settings().model_copy(
        update={
            "extraction_prompt_version": "2.0.0",
            "extraction_schema_version": "2.0.0",
        }
    )
    configure_logging(settings)
    ctx = build_run_context(settings, needs_inference=extract_context)
    try:
        targets = prepare_targets(ctx.driver, selected, source)
        adapter = ctx.registry.get(source)
        if isinstance(adapter, WikipediaAdapter):
            adapter.configure(targets, extract=extract_context)
        elif isinstance(adapter, YahooFinanceAdapter):
            adapter.configure(targets)
        record = run_with_lock(ctx, source, RunSpec(source_id=source, mode="ingest"))
        typer.echo(f"{source}: {record.records_fetched} sections; {record.errors} errors")
        if record.errors or record.assertions_rejected:
            raise LimesError("partial enrichment; inspect section evidence and replay manually")
    finally:
        ctx.driver.close()
