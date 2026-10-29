# tests/integration/test_cli_ingest.py | v1.0.0 | introduced by WP-28
"""CLI ingest tests per Doc 2 §8.14 and §15.3 Trace 1.

`limes ingest --source gisco_nuts` runs the full CLI stack — typer parsing,
`load_settings` from the environment, the composition root, the advisory
lock, `execute_run` — against the real Neo4j container. Only the network
boundary is stubbed (the adapter's `fetch`, the same seam Trace 1's own
test uses); no live service is hit. The CliRunner invocation is in-process
by design: the CLI layer's process boundary (env → settings → context) is
exactly what is under test, and the lock refusal itself is additionally
proven across a real subprocess in test_cli_lock.py.
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


def _fixture_records() -> list[RawRecord]:
    def record(name: str, content_type: str, url: str) -> RawRecord:
        return RawRecord(
            payload=(FIXTURES / name).read_bytes(),
            content_type=content_type,
            source_url=url,
            fetched_at=FETCHED_AT,
        )

    return [
        record("nuts_hierarchy.csv", "text/csv", "https://example.test/nuts.csv"),
        record(
            "postcode_correspondence.csv",
            "text/csv",
            "https://example.test/postcodes.csv",
        ),
    ]


@pytest.fixture
def cli_env(neo4j_instance: Neo4jInstance, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    env = _env(neo4j_instance, tmp_path)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return env


@pytest.fixture
def fixture_fetch(monkeypatch: pytest.MonkeyPatch):
    from limes.sources.gisco_nuts import GiscoNutsAdapter

    records = _fixture_records()
    monkeypatch.setattr(GiscoNutsAdapter, "fetch", lambda self, since, until: iter(records))
    return records


@pytest.fixture
def graph(neo4j_instance: Neo4jInstance):
    """A scratch driver for graph assertions, emptied before each test (the
    sanctioned fixture-teardown exception to the delete ban)."""
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


def test_cli_ingest_gisco_nuts_end_to_end(graph, cli_env, fixture_fetch):
    # G1 — Trace 1 through the CLI: parse, settings, context, lock,
    # execute_run, release. The run record is durable and the lock is gone.
    result = runner.invoke(app, ["ingest", "--source", "gisco_nuts"])
    assert result.exit_code == 0, result.output

    rows = graph.read(
        "MATCH ()-[r:PART_OF_REGION]->() RETURN count(r) AS c",
        {},
        30,
    )
    assert rows[0]["c"] == 9

    rows = graph.read(
        "MATCH (r:IngestionRun) RETURN r.mode AS mode, r.assertions_written AS written",
        {},
        30,
    )
    assert rows[0]["mode"] == "ingest"
    assert rows[0]["written"] == 9

    # The lock was released: no :AdvisoryLock node remains.
    rows = graph.read("MATCH (l:AdvisoryLock) RETURN count(l) AS c", {}, 30)
    assert rows[0]["c"] == 0


def test_cli_ingest_since_window_is_honored(graph, cli_env, fixture_fetch):
    # An explicit --since lands in the run record's window (explicit-since
    # wins, §8.6.2); gisco is non-incremental, so without one it is a full
    # load — the two windows differ.
    result = runner.invoke(
        app,
        ["ingest", "--source", "gisco_nuts", "--since", "2026-07-15T00:00:00+00:00"],
    )
    assert result.exit_code == 0, result.output
    rows = graph.read("MATCH (r:IngestionRun) RETURN r.window_from AS since", {}, 30)
    assert rows[0]["since"].to_native() == datetime(2026, 7, 15, tzinfo=UTC)


def test_cli_ingest_unknown_source_fails_naming_registered(graph, cli_env, fixture_fetch):
    # AC-38 through the CLI: an unknown source id fails with the registered
    # menu and a non-zero exit, before any fetch happens.
    result = runner.invoke(app, ["ingest", "--source", "not-a-source"])
    assert result.exit_code == 1
    assert "unknown source 'not-a-source'" in result.output
    assert "gisco_nuts" in result.output


def test_ingest_all_skips_enrichment_only_sources(graph, cli_env, fixture_fetch):
    # G11 — the ingestable list excludes enrichment-only sources (wikidata)
    # and investigation-driven news; selection happens before any
    # run (wikidata's fetch raises NotImplementedError and must never reach
    # the run loop).
    from limes.cli.ingest import _ingestable_source_ids
    from limes.sources.registry import build_default_registry

    registered = set(build_default_registry().source_ids())
    ingestable = _ingestable_source_ids()
    assert "wikidata" not in ingestable
    assert "news" not in ingestable  # Requires tracked investigation context.
    assert set(ingestable) == registered - {"wikidata", "news"}
