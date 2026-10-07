# src/limes/cli/main.py | v1.0.0 | introduced by WP-28
"""The CLI application and advisory lock per Technical Specification §8.14.

The operator surface (Doc 1 §6.6): `ingest`, `ingest-all`, `backfill`,
`reextract`, `select-models`, `evaluate`, `migrate`, `backup`. Every
ingestion command follows the same shape: `load_settings` →
`configure_logging` → `build_run_context` (WP-26) → advisory lock →
`execute_run` (WP-27) → release lock. Nothing is constructed here beyond
what the composition root provides (AC-40): the driver the lock uses comes
from the context.

The advisory lock (`:AdvisoryLock`, §5.8) is this module's node type
(§15.2): `acquire_lock` refuses a second concurrent run on the same source,
reclaiming a stale lock first with a warning; `release_lock` deletes the
node; `reclaim_stale_lock` is the aged-lock janitor. The staleness horizon
is a module constant — the named refresh point, since §4.2 has no run-timeout
key. One advisory lock per source is the §9 concurrency answer: a single
writer holds it for the duration of a run.

All errors surface as `LimesError` → exit 1 with the message on stderr;
usage errors (missing required parameters, unknown options) exit 2 via typer. The
app runs as `python -m limes.cli.main` today; the `limes` console script is
registered with the package install by WP-38 (out of this WP's file scope).
"""

from __future__ import annotations

import functools
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal

import structlog
import typer

from limes.errors import LimesError
from limes.graph.driver import GraphDriver
from limes.pipeline.run import execute_run

if TYPE_CHECKING:
    from limes.pipeline.run import RunSpec
    from limes.resolution.resolve import RunContext
    from limes.types import IngestionRunRecord

logger = structlog.get_logger(__name__)

# Refresh point: a lock older than this is presumed dead (a crashed or
# killed run holds it forever otherwise) and is reclaimed on the next
# acquire. §4.2 has no run-timeout key; this constant is the single place.
LOCK_STALE_AFTER_SECONDS = 4 * 3600

_LOCK_READ = """
MATCH (l:AdvisoryLock {source_id: $source_id})
RETURN l.run_id AS run_id, l.acquired_at AS acquired_at
"""

_LOCK_CREATE = """
CREATE (l:AdvisoryLock {
    source_id: $source_id,
    run_id: $run_id,
    acquired_at: $acquired_at
})
"""

_LOCK_DELETE = """
MATCH (l:AdvisoryLock {source_id: $source_id})
DELETE l
"""

_LOCK_STALE_READ = """
MATCH (l:AdvisoryLock {source_id: $source_id})
WHERE l.acquired_at < $cutoff
RETURN l.run_id AS run_id, l.acquired_at AS acquired_at
"""

_LOCK_STALE_DELETE = """
MATCH (l:AdvisoryLock {source_id: $source_id})
WHERE l.acquired_at < $cutoff
DELETE l
"""


def acquire_lock(driver: GraphDriver, source_id: str, run_id: str) -> None:
    """Create the `:AdvisoryLock` for one source, refusing a concurrent run.

    A stale lock is reclaimed first (with a warning); a fresh one raises
    `LimesError` — the refusal that prevents two runs on the same source.
    """
    reclaim_stale_lock(driver, source_id, LOCK_STALE_AFTER_SECONDS)
    rows = driver.read(_LOCK_READ, {"source_id": source_id}, timeout_s=30)
    if rows:
        held = rows[0]
        raise LimesError(
            f"advisory lock held for source '{source_id}' by run {held['run_id']!r} "
            f"since {held['acquired_at']}"
        )
    driver.write_batch(
        [
            (
                _LOCK_CREATE,
                {
                    "source_id": source_id,
                    "run_id": run_id,
                    "acquired_at": datetime.now(UTC),
                },
            )
        ]
    )
    logger.info("advisory lock acquired", source_id=source_id, run_id=run_id)


def release_lock(driver: GraphDriver, source_id: str) -> None:
    """Delete the source's lock. Idempotent: a missing lock is a no-op."""
    driver.write_batch([(_LOCK_DELETE, {"source_id": source_id})])
    logger.info("advisory lock released", source_id=source_id)


def reclaim_stale_lock(driver: GraphDriver, source_id: str, run_timeout: int) -> None:
    """Delete a lock older than `run_timeout` seconds, with a warning — a
    crashed run must not block the next one (Doc 2 §8.14)."""
    cutoff = datetime.now(UTC) - timedelta(seconds=run_timeout)
    rows = driver.read(
        _LOCK_STALE_READ,
        {"source_id": source_id, "cutoff": cutoff},
        timeout_s=30,
    )
    if not rows:
        return
    driver.write_batch([(_LOCK_STALE_DELETE, {"source_id": source_id, "cutoff": cutoff})])
    logger.warning(
        "stale advisory lock reclaimed",
        source_id=source_id,
        run_id=rows[0]["run_id"],
        acquired_at=rows[0]["acquired_at"],
        run_timeout_seconds=run_timeout,
    )


def parse_iso_datetime(raw: str | None, name: str) -> datetime | None:
    """An ISO-8601 CLI value as an aware UTC datetime, or None. A naive
    value is assumed UTC — the sources all work in UTC. A value that does
    not parse is a `ConfigurationError`: a typoed window must fail fast,
    not silently widen or narrow the run."""
    if raw is None:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise LimesError(f"{name}: not an ISO-8601 timestamp: {raw!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def adapter_kind(source_id: str) -> Literal["structured", "unstructured"]:
    """The adapter's `kind`, inspected through the sanctioned registry
    population function (D-43): the CLI must know whether a source needs
    the inference context before it can build one, and
    `build_default_registry` is the only sanctioned way to ask (AC-40
    leaves the constructor in composition.py — the registry built here is
    used for inspection only, never for a run)."""
    from limes.sources.registry import build_default_registry

    return build_default_registry().get(source_id).kind


def run_with_lock(
    ctx: RunContext,
    source_id: str,
    spec: RunSpec,
) -> IngestionRunRecord:
    """Acquire the source's advisory lock, run, release — the §9 single-
    writer contract every ingestion command honors. The lock's `run_id`
    identifies this CLI invocation (the `:IngestionRun` node carries its
    own id, generated by `execute_run`); both are logged."""
    run_id = uuid.uuid4().hex
    acquire_lock(ctx.driver, source_id, run_id)
    try:
        return execute_run(spec, ctx)
    finally:
        release_lock(ctx.driver, source_id)


def _run(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap a command so every `LimesError` becomes a one-line stderr
    message and exit code 1 — the CLI's error surface is the §11 hierarchy,
    never a traceback."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except LimesError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(1) from exc

    return wrapper


app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="LIMES — ontology-driven knowledge graph for German and European "
    "policy analysis. Ingestion is manual (Doc 1 §6.6); backfill and "
    "reextract record passive usage; remote operations need an operator token.",
)

# The command modules import `parse_iso_datetime`, `adapter_kind`, and
# `run_with_lock` from this module, so this import block must stay below
# their definitions — the cli modules load while this module is partially
# initialized, and a name moved below this block would not exist for them.
from limes.cli.backfill import backfill_source  # noqa: E402
from limes.cli.backup import backup  # noqa: E402
from limes.cli.evaluate import evaluate  # noqa: E402
from limes.cli.ingest import ingest_all, ingest_source  # noqa: E402
from limes.cli.migrate import migrate  # noqa: E402
from limes.cli.reextract import reextract_source  # noqa: E402
from limes.cli.select_models import select_models  # noqa: E402

app.command("ingest")(_run(ingest_source))
app.command("ingest-all")(_run(ingest_all))
app.command("backfill")(_run(backfill_source))
app.command("reextract")(_run(reextract_source))
app.command("select-models")(_run(select_models))
app.command("evaluate")(_run(evaluate))
app.command("migrate")(_run(migrate))
app.command("backup")(_run(backup))


from limes.cli.remote import app as remote_app  # noqa: E402

app.add_typer(remote_app, name="remote")


@app.command("stamp-embeddings")
@_run
def stamp_embeddings() -> None:
    from limes.composition import build_run_context, embedder_for
    from limes.config import load_settings
    from limes.graph.loader import stamp_missing_embeddings

    settings = load_settings()
    ctx = build_run_context(settings, needs_inference=True)
    try:
        embedder = embedder_for(settings, ctx.client)
        if embedder is None:
            raise LimesError("embedding model is not configured")
        count = stamp_missing_embeddings(ctx.driver, embedder)
        typer.echo(f"stamp-embeddings: {count} entities stamped")
    finally:
        ctx.driver.close()


def main() -> None:
    """Console entry point: `python -m limes.cli.main` (the `limes` console
    script is registered at install time by WP-38)."""
    app()


if __name__ == "__main__":
    main()
