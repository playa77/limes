"""Submit or resume operations without database credentials or host access."""

from __future__ import annotations

import json
import os
from uuid import UUID, uuid4

import httpx
import typer
from pydantic import ValidationError

from limes.operations.client import OperationsClient
from limes.operations.models import JobRequest

app = typer.Typer(no_args_is_help=True)


@app.command()
def run(
    command: str,
    source: str | None = None,
    investigation_id: str | None = None,
    after_document: str | None = None,
    selections: str | None = None,
    extract_context: bool | None = None,
    days: int | None = None,
    version: str | None = None,
    stage: str | None = None,
    evaluation: str | None = None,
    request_id: UUID | None = None,
    wait: bool = True,
    url: str = typer.Option("http://127.0.0.1:8000", envvar="LIMES_REMOTE_URL"),
) -> None:
    """Submit a bounded operation. Reuse --request-id after an uncertain response."""
    key = request_id or uuid4()
    typer.echo(f"request_id: {key}")
    try:
        request = JobRequest.model_validate(
            dict(
                request_id=key,
                command=command,
                source=source,
                investigation_id=investigation_id,
                after_document=after_document,
                selections=json.loads(selections) if selections is not None else None,
                extract_context=extract_context,
                days=days,
                version=version,
                stage=stage,
                evaluation=evaluation,
            )
        )
        client = OperationsClient(url, os.environ.get("LIMES_OPERATOR_TOKEN", ""))
        try:
            job = client.submit(request)
            typer.echo(f"job: {job.job_id} ({job.status})")
            if wait:
                job = client.wait(job.job_id, typer.echo)
                if job.status == "failed":
                    raise typer.Exit(1)
        finally:
            client.close()
    except (ValueError, ValidationError, httpx.HTTPError) as exc:
        typer.echo(
            f"error: {type(exc).__name__}; check endpoint, credential and parameters", err=True
        )
        raise typer.Exit(1) from exc


@app.command()
def status(
    job_id: UUID,
    wait: bool = False,
    url: str = typer.Option("http://127.0.0.1:8000", envvar="LIMES_REMOTE_URL"),
) -> None:
    """Inspect or follow an existing job; reconnecting never resubmits it."""
    try:
        client = OperationsClient(url, os.environ.get("LIMES_OPERATOR_TOKEN", ""))
        try:
            job = client.wait(job_id, typer.echo) if wait else client.get(job_id)
            typer.echo(job.model_dump_json(indent=2))
            if job.status == "failed":
                raise typer.Exit(1)
        finally:
            client.close()
    except (ValueError, httpx.HTTPError) as exc:
        typer.echo(f"error: {type(exc).__name__}; cannot read job status", err=True)
        raise typer.Exit(1) from exc
