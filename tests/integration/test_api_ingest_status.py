# tests/integration/test_api_ingest_status.py | v1.0.0 | introduced by WP-32
"""`GET /ingest/status` per Doc 2 §6: the latest `:IngestionRun` per source
with all its counters, produced by a real `execute_run` through the
composition root (network boundary stubbed at the adapter's fetch)."""

from pathlib import Path

import pytest

from limes.types import RawRecord
from tests.fixtures.graph_data import make_api_client, wipe_graph
from tests.integration.conftest import Neo4jInstance

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "gisco_nuts"


@pytest.fixture(scope="module", autouse=True)
def _restore_clean_graph(neo4j_instance: Neo4jInstance):
    """This module ingests GISCO fixture data, which leaves a `:Country`
    with `iso2 = 'DE'` behind; the loader tests assume a fresh graph, so
    the graph is reset when this module ends (the sanctioned fixture
    teardown)."""
    yield
    wipe_graph(neo4j_instance)


def test_ingest_status_reports_last_run_per_source(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from limes.composition import build_run_context
    from limes.pipeline.run import RunSpec, execute_run
    from limes.sources.gisco_nuts import GiscoNutsAdapter
    from tests.fixtures.graph_data import api_settings

    def records():
        for name in ("nuts_hierarchy.csv", "postcode_correspondence.csv"):
            yield RawRecord(
                payload=(FIXTURES / name).read_bytes(),
                content_type="text/csv",
                source_url="https://example.test/fixture.csv",
                fetched_at=__import__("datetime").datetime(
                    2026, 8, 1, 10, 0, tzinfo=__import__("datetime").UTC
                ),
            )

    monkeypatch.setattr(GiscoNutsAdapter, "fetch", lambda self, since, until: records())

    ctx = build_run_context(api_settings(neo4j_instance, tmp_path), needs_inference=False)
    try:
        run = execute_run(RunSpec(source_id="gisco_nuts", mode="ingest"), ctx)
    finally:
        ctx.driver.close()

    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.get("/ingest/status")
        assert response.status_code == 200
        statuses = {entry["source_id"]: entry for entry in response.json()}
        assert "gisco_nuts" in statuses
        status = statuses["gisco_nuts"]
        assert status["run_id"] == run.run_id
        assert status["mode"] == "ingest"
        assert status["errors"] == 0
        assert status["records_fetched"] == 2
        assert status["assertions_written"] >= 0
        assert status["last_success_at"] is not None
