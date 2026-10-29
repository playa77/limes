# tests/integration/test_cli_migrate.py | v1.0.0 | introduced by WP-31
"""Migration CLI integration tests per Doc 2 §8.14, against the real
Neo4j container (G10).

`migrate --ontology-version 1.0.0` on a fresh database is a no-op that
reports nothing to migrate; after the production path has stamped the
graph (a gisco ingest), the same command reports the database is already
at the target. The version-routing branches (additive, breaking,
downgrade) are covered by the stub-driver unit tests in
tests/unit/test_migrate.py.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from limes.cli.main import app
from limes.types import RawRecord
from tests.integration.conftest import Neo4jInstance

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "gisco_nuts"

FETCHED_AT = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)

runner = CliRunner()


@pytest.fixture(autouse=True)
def _restore_structlog_defaults():
    """The CLI reconfigures the process-wide structlog (level and renderer)
    from the test env; the adapter unit tests assert on structlog's default
    KeyValueRenderer output via capfd. Restore the defaults after every
    in-process CLI invocation so the suite stays order-independent."""
    import structlog

    yield
    structlog.reset_defaults()


def _env(neo4j_instance: Neo4jInstance, tmp_path: Path) -> dict[str, str]:
    return {
        "LIMES_NEO4J_URI": neo4j_instance.uri,
        "LIMES_NEO4J_USER": neo4j_instance.user,
        "LIMES_NEO4J_PASSWORD": neo4j_instance.password,
        "LIMES_NEO4J_DATABASE": neo4j_instance.database,
        "LIMES_ONTOLOGY_PATH": str(ONTOLOGY_PATH),
        "LIMES_FEEDS_CONFIG_PATH": str(REPO_ROOT / "ontology" / "feeds.yaml"),
        "LIMES_GOLD_SET_PATH": str(tmp_path / "gold_set.jsonl"),
        "LIMES_BASELINE_PATH": str(tmp_path / "baseline.json"),
        "LIMES_ARCHIVE_PATH": str(tmp_path / "archive"),
        "LIMES_LOG_LEVEL": "WARNING",
    }


@pytest.fixture
def cli_env(neo4j_instance: Neo4jInstance, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    for key, value in _env(neo4j_instance, tmp_path).items():
        monkeypatch.setenv(key, value)


@pytest.fixture
def graph(neo4j_instance: Neo4jInstance):
    from limes.graph.driver import GraphDriver

    driver = GraphDriver(
        neo4j_instance.uri,
        neo4j_instance.user,
        neo4j_instance.password,
        neo4j_instance.database,
    )
    driver.write_batch([("MATCH (n) DETACH DELETE n", {})])
    yield driver
    driver.close()


def test_cli_migrate_fresh_database_is_a_no_op(graph, cli_env):
    # G10 — on a fresh database the command reports nothing to migrate and
    # exits zero; the migration pattern stays untouched.
    result = runner.invoke(app, ["migrate", "--ontology-version", "1.3.0"])
    assert result.exit_code == 0, result.output
    assert "nothing to migrate" in result.output


def test_cli_migrate_after_stamped_ingest_is_a_no_op(
    graph, cli_env, monkeypatch: pytest.MonkeyPatch
):
    # The production path stamps the graph at 1.0.0; the same migrate
    # command then reports the database is already at the target.
    from limes.sources.gisco_nuts import GiscoNutsAdapter

    records = [
        RawRecord(
            payload=(FIXTURES / "nuts_hierarchy.csv").read_bytes(),
            content_type="text/csv",
            source_url="https://example.test/nuts.csv",
            fetched_at=FETCHED_AT,
        )
    ]
    monkeypatch.setattr(GiscoNutsAdapter, "fetch", lambda self, since, until: iter(records))

    result = runner.invoke(app, ["ingest", "--source", "gisco_nuts"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(app, ["migrate", "--ontology-version", "1.3.0"])
    assert result.exit_code == 0, result.output
    assert "already at 1.3.0" in result.output

    rows = graph.read(
        "MATCH (n:Entity {ontology_version: '1.3.0'}) RETURN count(n) AS c",
        {},
        30,
    )
    assert rows[0]["c"] > 0


def test_cli_migrate_artifact_version_mismatch_fails(graph, cli_env):
    result = runner.invoke(app, ["migrate", "--ontology-version", "2.0.0"])
    assert result.exit_code == 1
    assert "not the requested 2.0.0" in result.output
