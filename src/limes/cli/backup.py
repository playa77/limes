# src/limes/cli/backup.py | v1.0.0 | introduced by WP-28
"""The `backup` command (Doc 2 §13.6, Doc 1 §8.5).

Community Edition has no online backup (C-01): the procedure stops the
database, dumps offline, and restarts. The dump lands in the archive
volume with a timestamped filename — the archive is the system of record,
and a full re-ingest from it costs no paid inference while the version
triple is unchanged (Doc 1 §8.5).

The Neo4j container is stopped and started through the compose service
`neo4j` (§13.2 topology), and the dump runs inside a throwaway container
from the same image so it can see the stopped database's data volume. The
archive directory inside the container is `/data/archive` — the mount
point WP-37 wires for the `archive` volume; the constants here are the
named refresh points for that wiring. The 5.x `neo4j-admin database dump`
form is used (the `neo4j:2026.x` line); the dump is renamed to a
timestamped `limes-<ts>.dump` after the admin tool writes its fixed
`neo4j.dump` name. This command must run from the compose root — the
directory holding `docker-compose.yml` — because compose resolves its file
from the process working directory.
"""

from __future__ import annotations

import subprocess
import time
from datetime import UTC, datetime

import structlog
import typer

from limes.config import load_settings
from limes.errors import LimesError
from limes.graph.driver import GraphDriver
from limes.logging_setup import configure_logging

logger = structlog.get_logger(__name__)

# Refresh points for the WP-37 compose wiring: the §13.2 service name, the
# archive volume's mount inside the neo4j service, and the admin command
# (Neo4j 2026.x / 5.x form).
COMPOSE_SERVICE = "neo4j"
DUMP_CONTAINER_DIR = "/data/archive"
DUMP_ADMIN_COMMAND = (
    "neo4j-admin database dump neo4j --to-path=/data/archive --overwrite-destination=true"
)

# How long the restarted database may take to accept connections again.
BACKUP_RECONNECT_TIMEOUT_SECONDS = 180


def backup() -> None:
    """Stop Neo4j, dump offline to the archive volume, restart, verify
    reachability (Doc 2 §13.6)."""
    settings = load_settings()
    configure_logging(settings)
    from limes.composition import build_run_context

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    dump_name = f"limes-{timestamp}.dump"

    ctx = build_run_context(settings, needs_inference=False)
    try:
        typer.echo("backup: stopping Neo4j")
        _compose(["stop", COMPOSE_SERVICE])
        try:
            typer.echo("backup: dumping offline")
            _compose(
                [
                    "run",
                    "--rm",
                    "--no-deps",
                    COMPOSE_SERVICE,
                    "sh",
                    "-c",
                    f"{DUMP_ADMIN_COMMAND} && "
                    f"mv {DUMP_CONTAINER_DIR}/neo4j.dump {DUMP_CONTAINER_DIR}/{dump_name}",
                ]
            )
        finally:
            typer.echo("backup: restarting Neo4j")
            _compose(["start", COMPOSE_SERVICE])
        _wait_reachable(ctx.driver, BACKUP_RECONNECT_TIMEOUT_SECONDS)
        typer.echo(f"backup: complete ({dump_name})")
    finally:
        ctx.driver.close()


def _compose(args: list[str]) -> None:
    """Run one `docker compose` invocation, raising `LimesError` with the
    exit code on failure — a failed stop or dump must not be reported as a
    completed backup."""
    result = subprocess.run(
        ["docker", "compose", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        message = f"docker compose {' '.join(args)} failed (exit {result.returncode}): {detail}"
        raise LimesError(message)
    logger.info("docker compose step completed", command=" ".join(args))


def _wait_reachable(driver: GraphDriver, timeout_s: int) -> None:
    """Poll the driver until the restarted database accepts a read — the
    verification that the restart actually came back, not merely that the
    container started."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            driver.read("RETURN 1 AS ok", {}, timeout_s=10)
            return
        except Exception:
            time.sleep(2)
    raise LimesError(f"Neo4j did not become reachable within {timeout_s}s after restart")
