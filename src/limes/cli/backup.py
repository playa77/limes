"""Request a clean physical backup from the private Neo4j lifecycle owner."""

from __future__ import annotations

import httpx
import typer

from limes.config import load_settings
from limes.errors import LimesError


def backup() -> None:
    settings = load_settings()
    token = settings.backup_token.get_secret_value()
    if not token:
        raise LimesError("LIMES_BACKUP_TOKEN is required by the worker")
    typer.echo("backup: stopping, dumping and restarting Neo4j")
    try:
        response = httpx.post(
            settings.backup_base_url.rstrip("/") + "/backup",
            headers={"Authorization": f"Bearer {token}"},
            timeout=1200,
            # This is a private service-to-service request, never an egress call.
            trust_env=False,
        )
        response.raise_for_status()
        name = response.json()["dump_name"]
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        detail = (
            f"HTTP {exc.response.status_code}"
            if isinstance(exc, httpx.HTTPStatusError)
            else type(exc).__name__
        )
        raise LimesError(
            f"Backup failed ({detail}); inspect job status and database health before retrying"
        ) from exc
    typer.echo(f"backup: complete ({name})")
