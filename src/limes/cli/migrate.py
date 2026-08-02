# src/limes/cli/migrate.py | v1.0.0 | introduced by WP-31
"""The `migrate` command (Doc 2 §8.14, Doc 1 §9.6).

Ontology changes: an additive change (same major version) requires no
migration — existing data remains valid under its stamped version; a
breaking change (major bump) requires a numbered migration that rewrites
the `ontology_version` stamp on affected nodes and edges. The migration
scripts live next to the ontology artifact in `ontology/migrations/`, run
in numbered order, and each declares the `TO_VERSION` it brings the graph
to and an `upgrade(driver) -> None` that does the rewriting.

The version the graph is at is read from the stamps the loader wrote — the
maximum over `:Entity` nodes and over relationships (the §4.3 guard reads
nodes only; the CLI reads both so an edge-only migration is not missed).
`migrate --ontology-version <v>` loads the artifact, verifies the artifact
version equals the requested one, and routes: already at target → no-op;
same major → additive, nothing to migrate; older graph with a major bump →
find and run the migration whose `TO_VERSION` is the target, reporting the
affected node and edge counts before and after. A downgrade is refused by
the §4.3 guard at context build — and re-checked here over both stamp
surfaces.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import structlog
import typer

from limes.config import load_settings
from limes.errors import LimesError
from limes.graph.driver import GraphDriver
from limes.logging_setup import configure_logging

logger = structlog.get_logger(__name__)

_NODE_STAMP_QUERY = """
MATCH (n:Entity) WHERE n.ontology_version IS NOT NULL
RETURN max(n.ontology_version) AS max_version
"""

_EDGE_STAMP_QUERY = """
MATCH ()-[r]->() WHERE r.ontology_version IS NOT NULL
RETURN max(r.ontology_version) AS max_version
"""

_AFFECTED_NODES_QUERY = """
MATCH (n:Entity) WHERE n.ontology_version IS NOT NULL AND n.ontology_version <> $version
RETURN count(n) AS affected
"""

_AFFECTED_EDGES_QUERY = """
MATCH ()-[r]->() WHERE r.ontology_version IS NOT NULL AND r.ontology_version <> $version
RETURN count(r) AS affected
"""


def migrate(
    ontology_version: str = typer.Option(
        ..., "--ontology-version", help="The ontology version to migrate the graph to"
    ),
) -> None:
    """Apply the numbered migration for a breaking ontology change, or
    report that none is needed (Doc 1 §9.6)."""
    settings = load_settings()
    configure_logging(settings)
    from limes.composition import build_run_context

    ctx = build_run_context(settings, needs_inference=False)
    try:
        _migrate(ctx.driver, ctx.settings.ontology_path, ctx.ontology.version, ontology_version)
    finally:
        ctx.driver.close()


def _migrate(
    driver: GraphDriver,
    ontology_path: Path,
    artifact_version: str,
    target_version: str,
) -> None:
    if artifact_version != target_version:
        raise LimesError(
            f"ontology artifact is version {artifact_version}, not the requested {target_version}"
        )

    stamped = _max_stamped_version(driver)
    if stamped is None:
        typer.echo("migrate: fresh database — nothing stamped, nothing to migrate")
        return
    if stamped == target_version:
        typer.echo(f"migrate: database already at {target_version}; nothing to migrate")
        return
    if _version_tuple(stamped) > _version_tuple(target_version):
        # The §4.3 guard at context build already refuses this; the check
        # here covers edge-only stamps the guard does not read.
        raise LimesError(f"downgrade refused: graph stamped {stamped}, artifact {target_version}")
    if _version_tuple(stamped)[0] == _version_tuple(target_version)[0]:
        typer.echo(
            f"migrate: additive change (same major) from {stamped} to {target_version}; "
            "existing data remains valid under its stamped version — no migration needed"
        )
        return

    script = _find_migration(ontology_path, target_version)
    nodes_before, edges_before = _count_affected(driver, target_version)
    script_upgrade(driver, script)
    nodes_after, edges_after = _count_affected(driver, target_version)
    typer.echo(
        f"migrate: ran {script} to {target_version}; affected nodes "
        f"{nodes_before} -> {nodes_after}, edges {edges_before} -> {edges_after}"
    )


def _max_stamped_version(driver: GraphDriver) -> str | None:
    """The maximum `ontology_version` stamped anywhere — nodes or edges —
    or None on a graph the loader never wrote to."""
    versions: list[str] = []
    for cypher in (_NODE_STAMP_QUERY, _EDGE_STAMP_QUERY):
        rows = driver.read(cypher, {}, timeout_s=30)
        if rows and rows[0].get("max_version") is not None:
            versions.append(str(rows[0]["max_version"]))
    if not versions:
        return None
    return max(versions, key=_version_tuple)


def _count_affected(driver: GraphDriver, target_version: str) -> tuple[int, int]:
    """The node and edge counts whose stamp differs from the target — the
    surface the migration must rewrite."""
    nodes = driver.read(_AFFECTED_NODES_QUERY, {"version": target_version}, timeout_s=60)[0][
        "affected"
    ]
    edges = driver.read(_AFFECTED_EDGES_QUERY, {"version": target_version}, timeout_s=60)[0][
        "affected"
    ]
    return int(nodes), int(edges)


def _find_migration(ontology_path: Path, target_version: str) -> Path:
    """The migration script whose `TO_VERSION` is the target, or a defect
    error — a breaking target without a migration is a broken release, not
    a runtime condition."""
    migrations_dir = ontology_path.parent / "migrations"
    if not migrations_dir.is_dir():
        raise LimesError(f"no migrations directory: {migrations_dir}")
    candidates: list[Path] = []
    for path in sorted(migrations_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        module = _load_migration_module(path)
        to_version = getattr(module, "TO_VERSION", None)
        if to_version == target_version:
            candidates.append(path)
    if not candidates:
        raise LimesError(
            f"no migration found for breaking target {target_version} in {migrations_dir}"
        )
    if len(candidates) > 1:
        raise LimesError(f"multiple migrations declare TO_VERSION {target_version}: {candidates}")
    return candidates[0]


def _load_migration_module(path: Path) -> Any:
    """Import one migration script by path under a unique module name."""
    module_name = f"limes_migration_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise LimesError(f"cannot import migration {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "upgrade", None)):
        raise LimesError(f"migration {path} has no upgrade(driver) function")
    return module


def script_upgrade(driver: GraphDriver, script: Path) -> None:
    """Run a migration's `upgrade(driver)` — the stamp rewrite. The
    upgrade itself is the script's contract; it is always run in its own
    transaction so a failing rewrite leaves the graph unchanged."""
    module = _load_migration_module(script)
    module.upgrade(driver)


def _version_tuple(version: str) -> tuple[int, int, int]:
    """'1.0.0' → (1, 0, 0) for comparisons; a malformed stamp is a defect
    and fails loudly."""
    parts = version.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise LimesError(f"malformed ontology version stamp: {version!r}")
    return (int(parts[0]), int(parts[1]), int(parts[2]))
