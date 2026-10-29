"""One bounded acquisition cycle, invoked only by the operational worker or operator."""

from __future__ import annotations

import typer

from limes.config import load_settings
from limes.errors import LimesError
from limes.news.store import TrackingStore
from limes.news.targets import queries_for
from limes.pipeline.run import RunSpec
from limes.sources.news import NewsAdapter


def refresh(investigation_id: str = typer.Option(..., "--investigation-id")) -> None:
    from limes.cli.main import run_with_lock
    from limes.composition import build_run_context

    settings = load_settings().model_copy(
        update={
            "extraction_prompt_version": "2.0.0",
            "extraction_schema_version": "2.0.0",
        }
    )
    store = TrackingStore(settings.jobs_path)
    investigation = store.get_investigation(investigation_id)
    if investigation is None:
        raise LimesError("investigation not found")
    if not investigation.active:
        typer.echo("investigation paused; no acquisition")
        return
    ctx = build_run_context(settings, needs_inference=True)
    try:
        adapter = ctx.registry.get("news")
        assert isinstance(adapter, NewsAdapter)
        try:
            targets = queries_for(ctx.driver, investigation)
        except ValueError as exc:
            raise LimesError(str(exc)) from exc
        adapter.configure(investigation_id, investigation.revision, targets)
        record = run_with_lock(ctx, "news", RunSpec(source_id="news", mode="ingest"))
        typer.echo(f"news: {record.records_fetched} records, {record.errors} errors")
        if record.errors:
            raise LimesError("partial news acquisition; inspect evidence and replay manually")
    finally:
        ctx.driver.close()


def reextract(
    investigation_id: str = typer.Option(..., "--investigation-id"),
    prompt_version: str = typer.Option(..., "--prompt-version"),
    after_document: str = typer.Option("", "--after-document"),
) -> None:
    """Re-extract at most 200 archived reports; emit the next explicit page cursor."""
    import json
    from datetime import UTC, datetime

    from limes.cli.main import run_with_lock
    from limes.composition import build_run_context
    from limes.types import RawRecord

    settings = load_settings().model_copy(
        update={
            "extraction_prompt_version": prompt_version,
            "extraction_schema_version": "2.0.0",
        }
    )
    ctx = build_run_context(settings, needs_inference=True)
    try:
        rows = ctx.driver.read(
            "MATCH (d:NewsDocument {investigation_id:$id}) WHERE d.document_id > $after "
            "RETURN d.document_id AS id, d.metadata AS metadata "
            "ORDER BY d.document_id LIMIT 201",
            {"id": investigation_id, "after": after_document},
            30,
        )
        adapter = ctx.registry.get("news")
        assert isinstance(adapter, NewsAdapter)
        adapter.replay_records = [
            RawRecord(
                payload=ctx.archive.get(row["id"]),
                content_type="application/json",
                fetched_at=datetime.now(UTC),
                acquisition_context=json.loads(row["metadata"]),
            )
            for row in rows[:200]
        ]
        record = run_with_lock(ctx, "news", RunSpec(source_id="news", mode="reextract"))
        if record.errors:
            raise LimesError("partial re-extraction; retry the same page after inspection")
        typer.echo(f"news-reextract: {record.records_fetched} archived reports")
        if len(rows) > 200:
            typer.echo(f"next --after-document {rows[199]['id']}")
    finally:
        ctx.driver.close()
