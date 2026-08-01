# tests/integration/test_pipeline_run_structured.py | v1.0.0 | introduced by WP-27
"""Structured pipeline run tests per Doc 2 §8.6.1, AC-05, and §15.3
Trace 1, against the real Neo4j container.

Trace 1 runs through the production composition root and the real GISCO
adapter; only the network boundary (fetch) is stubbed with the recorded
fixture payloads — no live service is hit. The second run over the same
records is AC-05: identical content, zero new nodes, zero new
relationships, and the skip count reported.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from limes.composition import build_run_context
from limes.config import Settings
from limes.pipeline.run import RunSpec, execute_run
from limes.sources.gisco_nuts import GiscoNutsAdapter
from limes.types import RawRecord
from tests.integration.conftest import Neo4jInstance

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "gisco_nuts"

FETCHED_AT = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)


def _settings(neo4j_instance: Neo4jInstance, tmp_path: Path) -> Settings:
    return Settings(
        neo4j_uri=neo4j_instance.uri,
        neo4j_user=neo4j_instance.user,
        neo4j_password=neo4j_instance.password,
        neo4j_database=neo4j_instance.database,
        ontology_path=ONTOLOGY_PATH,
        feeds_config_path=REPO_ROOT / "ontology" / "feeds.yaml",
        gold_set_path=tmp_path / "gold_set.jsonl",
        baseline_path=tmp_path / "baseline.json",
        archive_path=tmp_path / "archive",
        openrouter_api_key="sk-test",
        openrouter_base_url="https://openrouter.test/api/v1",
        http_timeout_seconds=10,
    )


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
def fixture_fetch(monkeypatch: pytest.MonkeyPatch):
    records = _fixture_records()
    monkeypatch.setattr(
        GiscoNutsAdapter,
        "fetch",
        lambda self, since, until: iter(records),
    )
    return records


@pytest.fixture
def ctx(neo4j_instance: Neo4jInstance, tmp_path: Path):
    context = build_run_context(
        _settings(neo4j_instance, tmp_path),
        needs_inference=False,
    )
    yield context
    context.driver.close()


@pytest.fixture(autouse=True)
def _isolated_graph(ctx):
    # Each test asserts absolute counts over its own run; the session
    # container is shared, so the graph is emptied before every test (the
    # sanctioned fixture-teardown exception to the delete ban).
    ctx.driver.write_batch([("MATCH (n) DETACH DELETE n", {})])
    yield


def test_trace1_structured_run_end_to_end(ctx, fixture_fetch):
    # Trace 1: fetch → archive → normalize → stamp → validate → load →
    # close. gisco_nuts is non-incremental, so the window is a full load.
    record = execute_run(RunSpec(source_id="gisco_nuts", mode="ingest"), ctx)

    assert record.records_fetched == 2
    assert record.errors == 0
    assert record.assertions_rejected == 0
    assert record.cost_eur == 0
    assert record.finished_at is not None

    # The NUTS fixture: 9 region→parent assertions over 10 entity nodes,
    # plus 3 :PostalCode lookup nodes — nodes_created counts every merged
    # node, lookup rows included.
    assert record.assertions_written == 9
    assert record.assertions_skipped == 0
    assert record.nodes_created == 13
    assert record.nodes_matched == 0

    rows = ctx.driver.read(
        "MATCH ()-[r:PART_OF_REGION]->() RETURN count(r) AS c",
        {},
        30,
    )
    assert rows[0]["c"] == 9
    rows = ctx.driver.read("MATCH (n:PostalCode) RETURN count(n) AS c", {}, 30)
    assert rows[0]["c"] == 3
    rows = ctx.driver.read(
        "MATCH (e:Entity {entity_id: 'nuts_code:DE111'}) RETURN e.label AS label",
        {},
        30,
    )
    assert rows[0]["label"] == "Stuttgart, Stadtkreis"

    # Provenance is stamped from the registry (§15.2).
    rows = ctx.driver.read(
        "MATCH (:Entity)-[r:PART_OF_REGION]->(:Entity) RETURN DISTINCT r.source_id AS sid, "
        "r.source_trust AS trust LIMIT 1",
        {},
        30,
    )
    assert rows[0]["sid"] == "gisco_nuts"
    assert rows[0]["trust"] == pytest.approx(GiscoNutsAdapter().trust_rank)

    # The archive holds both payloads (content-addressed gzip files).
    root = ctx.archive.path_for("x").parents[2]
    stored = [p for p in root.glob("**/*") if p.is_file()]
    assert len(stored) == 2


def test_ac05_reingest_writes_nothing_new(ctx, fixture_fetch):
    first = execute_run(RunSpec(source_id="gisco_nuts", mode="ingest"), ctx)
    assert first.assertions_written == 9

    second = execute_run(RunSpec(source_id="gisco_nuts", mode="ingest"), ctx)
    # AC-05: identical re-ingest — zero new nodes, zero new relationships,
    # every assertion reported as skipped. nodes_matched counts entity
    # merges (10); lookup nodes are not part of the entity-match derivation.
    assert second.assertions_written == 0
    assert second.assertions_skipped == 9
    assert second.nodes_created == 0
    assert second.nodes_matched == 10
    assert second.errors == 0

    rows = ctx.driver.read(
        "MATCH ()-[r:PART_OF_REGION]->() RETURN count(r) AS c",
        {},
        30,
    )
    assert rows[0]["c"] == 9


def test_record_level_parse_error_is_counted_and_skipped(ctx, fixture_fetch, monkeypatch):
    # A record whose payload the adapter cannot parse counts one error and
    # does not abort the run; the good records still load.
    records = _fixture_records()
    records.append(
        RawRecord(
            payload=b"NOT A GISCO FILE",
            content_type="text/csv",
            source_url="https://example.test/broken.csv",
            fetched_at=FETCHED_AT,
        )
    )
    monkeypatch.setattr(GiscoNutsAdapter, "fetch", lambda self, since, until: iter(records))

    record = execute_run(RunSpec(source_id="gisco_nuts", mode="ingest"), ctx)
    assert record.records_fetched == 3
    assert record.errors == 1
    assert record.assertions_written == 9
    assert record.finished_at is not None


def test_fetch_failure_aborts_run_and_closes_record(ctx, fixture_fetch, monkeypatch):
    from limes.errors import SourceFetchError

    def _boom(self, since, until):
        yield _fixture_records()[0]
        raise SourceFetchError("test: upstream 503")

    monkeypatch.setattr(GiscoNutsAdapter, "fetch", _boom)

    with pytest.raises(SourceFetchError):
        execute_run(RunSpec(source_id="gisco_nuts", mode="ingest"), ctx)

    rows = ctx.driver.read(
        "MATCH (r:IngestionRun) RETURN r.finished_at IS NOT NULL AS closed, r.errors AS errors",
        {},
        30,
    )
    assert rows[0]["closed"] is True
    assert rows[0]["errors"] == 1
    # The aborted run must not advance the source's last-success mark.
    rows = ctx.driver.read(
        "MATCH (s:Source {source_id: 'gisco_nuts'}) RETURN s.last_success_at AS at",
        {},
        30,
    )
    assert rows[0]["at"] is None


def test_source_and_run_nodes_are_durable(ctx, fixture_fetch):
    record = execute_run(RunSpec(source_id="gisco_nuts", mode="ingest"), ctx)

    rows = ctx.driver.read(
        "MATCH (s:Source {source_id: 'gisco_nuts'}) RETURN s.name AS name, s.kind AS kind, "
        "s.last_run_id AS run_id, s.last_success_at AS at",
        {},
        30,
    )
    assert rows[0]["name"] == "GISCO/NUTS"
    assert rows[0]["kind"] == "structured"
    assert rows[0]["run_id"] == record.run_id
    assert rows[0]["at"] == record.finished_at

    rows = ctx.driver.read(
        "MATCH (r:IngestionRun {run_id: $run_id}) "
        "RETURN r.mode AS mode, r.window_from IS NULL AS full_load, "
        "r.records_fetched AS fetched, r.assertions_written AS written",
        {"run_id": record.run_id},
        30,
    )
    assert rows[0]["mode"] == "ingest"
    assert rows[0]["full_load"] is True
    assert rows[0]["fetched"] == 2
    assert rows[0]["written"] == 9
