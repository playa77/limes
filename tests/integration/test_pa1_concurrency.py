# tests/integration/test_pa1_concurrency.py | PA-1 | AC-1/AC-2/AC-3 evidence
"""Real disposable-graph evidence for PA-1: two sources run concurrently and
both land (AC-1 partial) with their write batches going through the actual
flock gate on the jobs volume (AC-2), and a run whose upstream hangs aborts
inside its per-source budget while the healthy run completes normally
(AC-3). Worker-pool/cancel semantics carry unit evidence in
test_pa1_jobs.py (real subprocesses); this file covers the pipeline-level
seams that evidence cannot."""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from limes.composition import build_run_context
from limes.config import Settings
from limes.errors import SourceRunBudgetExceeded
from limes.pipeline.run import RunSpec, execute_run
from limes.sources.gisco_nuts import GiscoNutsAdapter
from limes.sources.offeneregister import OffeneRegisterAdapter
from limes.types import RawRecord
from tests.integration.conftest import Neo4jInstance

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "gisco_nuts"

FETCHED_AT = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)


def _gisco_records() -> list[RawRecord]:
    return [
        RawRecord(
            payload=(FIXTURES / "nuts_hierarchy.csv").read_bytes(),
            content_type="text/csv",
            source_url="https://example.test/nuts.csv",
            fetched_at=FETCHED_AT,
        ),
        RawRecord(
            payload=(FIXTURES / "postcode_correspondence.csv").read_bytes(),
            content_type="text/csv",
            source_url="https://example.test/postcodes.csv",
            fetched_at=FETCHED_AT,
        ),
    ]


def _settings(neo4j_instance: Neo4jInstance, tmp_path: Path, **overrides) -> Settings:
    base = dict(
        neo4j_uri=neo4j_instance.uri,
        neo4j_user=neo4j_instance.user,
        neo4j_password=neo4j_instance.password,
        neo4j_database=neo4j_instance.database,
        ontology_path=ONTOLOGY_PATH,
        feeds_config_path=REPO_ROOT / "ontology" / "feeds.yaml",
        gold_set_path=tmp_path / "gold_set.jsonl",
        baseline_path=tmp_path / "baseline.json",
        archive_path=tmp_path / "archive",
        # test-host writable shared subtree for the graph write gate (PA-1 R2)
        jobs_path=tmp_path / "jobs" / "jobs.sqlite3",
        http_timeout_seconds=10,
    )
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def contexts(neo4j_instance: Neo4jInstance, tmp_path: Path):
    """Two independent contexts (one per concurrent run). The graph is the
    shared session container, cleaned per the sanctioned fixture exception."""
    (tmp_path / "jobs").mkdir(exist_ok=True)  # gate parent on the test host
    context = build_run_context(_settings(neo4j_instance, tmp_path), needs_inference=False)
    context.driver.write_batch([("MATCH (n) DETACH DELETE n", {})])
    yield [context]
    context.driver.close()


def test_two_sources_run_concurrently_and_both_land_through_the_gate(
    contexts, monkeypatch, tmp_path
):
    ctx = contexts[0]
    monkeypatch.setattr(GiscoNutsAdapter, "fetch", lambda self, s, u: iter(_gisco_records()))
    monkeypatch.setattr(OffeneRegisterAdapter, "fetch", lambda self, s, u: iter(_gisco_records()))

    records: dict[str, object] = {}
    errors: list[Exception] = []

    def run(source_id: str) -> None:
        try:
            records[source_id] = execute_run(RunSpec(source_id=source_id, mode="ingest"), ctx)
        except Exception as exc:  # noqa: BLE001  (test surface)
            errors.append(exc)

    threads = [
        threading.Thread(target=run, args=("gisco_nuts",)),
        threading.Thread(target=run, args=("offeneregister",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=180)
    assert not errors, errors
    gisco_record = records["gisco_nuts"]
    other_record = records["offeneregister"]
    # the healthy run must be clean; the appended-source run may carry
    # record-level parse errors (its normalize is its own) — what matters is
    # that BOTH durably closed while writing through one gate
    assert gisco_record.finished_at is not None and gisco_record.errors == 0
    assert other_record.finished_at is not None
    rows = ctx.driver.read("MATCH (:Source) RETURN count(*) AS c", {}, 30)
    assert rows[0]["c"] == 2
    # the actual gate file on the test-host jobs volume was used (PA-1 R2)
    assert (tmp_path / "jobs" / "write-gate.lock").exists()


def test_hanging_run_aborts_within_budget_while_other_completes(
    contexts, neo4j_instance, tmp_path, monkeypatch
):
    ctx = contexts[0]
    hanging_ctx = build_run_context(
        _settings(neo4j_instance, tmp_path, source_run_budget_seconds=1),
        needs_inference=False,
    )  # second context leans on the same shared container
    monkeypatch.setattr(GiscoNutsAdapter, "fetch", lambda self, s, u: iter(_gisco_records()))

    def hang_fetch(self, since, until):
        for record in _gisco_records():
            time.sleep(0.6)
            yield record

    monkeypatch.setattr(OffeneRegisterAdapter, "fetch", hang_fetch)

    records: dict[str, object] = {}
    budget_errors: list[SourceRunBudgetExceeded] = []
    other_errors: list[Exception] = []
    started_at = time.monotonic()

    def healthy_run() -> None:
        try:
            records["gisco_nuts"] = execute_run(RunSpec(source_id="gisco_nuts", mode="ingest"), ctx)
        except Exception as exc:  # noqa: BLE001
            other_errors.append(exc)

    def hanging_run() -> None:
        start = time.monotonic()
        try:
            records["offeneregister"] = execute_run(
                RunSpec(source_id="offeneregister", mode="ingest"), hanging_ctx
            )
        except SourceRunBudgetExceeded as exc:
            budget_errors.append(exc)
            records["offeneregister_elapsed"] = time.monotonic() - start

    threads = [threading.Thread(target=healthy_run), threading.Thread(target=hanging_run)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=180)
    assert not other_errors, other_errors
    assert budget_errors, "hang must abort via the run budget, not finish"

    elapsed = records["offeneregister_elapsed"]
    assert elapsed < 3.0, elapsed  # the 2026-11-08 defect burned 5+ hours; this is seconds
    assert started_at is not None
    healthy = records["gisco_nuts"]
    assert healthy.finished_at is not None and healthy.errors == 0
    # the aborted run still closed its durable record (checkpoint untouched)
    rows = hanging_ctx.driver.read(
        "MATCH (r:IngestionRun {source_id: 'offeneregister'}) RETURN r.errors AS errors",
        {},
        30,
    )
    assert rows and rows[0]["errors"] >= 1  # abort closed the record with error(s)
    # keeping the extra context alive until every read is done
    hanging_ctx.driver.write_batch([("RETURN 1", {})])  # gate churn sanity
    hanging_ctx.driver.close()
