# tests/integration/test_api_sources.py | v1.0.0 | introduced by WP-32
"""`GET /sources` per Doc 2 §6: the registry with trust ranks and the
graph's last-refresh stamps. A source that has never run is visible with
null refresh. The refresh stamps are produced by a real `execute_run`
through the composition root — only the adapter's network boundary is
stubbed, the same seam the CLI tests use."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from limes.types import RawRecord
from tests.fixtures.graph_data import make_api_client, wipe_graph
from tests.integration.conftest import Neo4jInstance

REGISTERED_SOURCES = {
    "gisco_nuts",
    "gleif",
    "eurlex",
    "fsd",
    "ted",
    "transparency_register",
    "bundestag_dip",
    "gesetze_im_internet",
    "wikidata",
    "osm",
    "offeneregister",
    "gdelt",
    "feeds",
    "news",
    "wikipedia",
    "yahoo_finance",
}

FETCHED_AT = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)


@pytest.fixture(scope="module", autouse=True)
def _restore_clean_graph(neo4j_instance: Neo4jInstance):
    """This module ingests GISCO fixture data, which leaves a `:Country`
    with `iso2 = 'DE'` behind; the loader tests assume a fresh graph, so
    the graph is reset when this module ends (the sanctioned fixture
    teardown)."""
    yield
    wipe_graph(neo4j_instance)


def test_sources_returns_registry_with_trust_ranks(neo4j_instance: Neo4jInstance, tmp_path: Path):
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.get("/sources")
        assert response.status_code == 200
        sources = {entry["source_id"]: entry for entry in response.json()}
        assert set(sources) == REGISTERED_SOURCES
        assert sources["gleif"]["trust_rank"] == 1.0
        assert sources["offeneregister"]["trust_rank"] == 0.3
        assert sources["feeds"]["kind"] == "unstructured"
        assert sources["gisco_nuts"]["supports_incremental"] is False
        assert sources["gleif"]["supports_incremental"] is True
        # No source has ever run in this database.
        assert sources["gleif"]["last_success_at"] is None


def test_sources_reports_last_refresh_from_graph(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from limes.composition import build_run_context
    from limes.pipeline.run import RunSpec, execute_run
    from limes.sources.gisco_nuts import GiscoNutsAdapter
    from tests.fixtures.graph_data import api_settings

    fixture = RawRecord(
        payload=(Path(__file__).parents[1] / "fixtures/gisco_nuts/nuts_hierarchy.csv").read_bytes(),
        content_type="text/csv",
        source_url=None,
        fetched_at=datetime(2026, 8, 1, 10, 0, tzinfo=UTC),
    )
    monkeypatch.setattr(GiscoNutsAdapter, "fetch", lambda self, since, until: iter([fixture]))

    # A full run through the composition root stamps :Source.last_success_at
    # — the production path the /sources endpoint reads.
    ctx = build_run_context(api_settings(neo4j_instance, tmp_path), needs_inference=False)
    try:
        execute_run(RunSpec(source_id="gisco_nuts", mode="ingest"), ctx)
    finally:
        ctx.driver.close()

    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.get("/sources")
        sources = {entry["source_id"]: entry for entry in response.json()}
        assert sources["gisco_nuts"]["last_success_at"] is not None
        assert sources["gisco_nuts"]["last_run_id"] is not None
