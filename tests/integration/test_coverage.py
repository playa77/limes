# tests/integration/test_coverage.py | v1.0.0 | introduced by WP-34
"""Coverage report integration tests per Doc 2 §8.11 and §12.2 (AC-23):
every result carries a coverage report with correct graph-wide relation
counts and source refresh timestamps. Graph state is produced by the
loader; the `:Source` refresh stamps by a real run (WP-34's production
path is the read; the stamps are the pipeline's)."""

from pathlib import Path

import pytest

from limes.coverage.report import report_for_relations
from limes.types import RawRecord
from tests.fixtures.graph_data import (
    load_corporation_graph,
    load_ontology_artifact,
    make_driver,
    wipe_graph,
)
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


@pytest.fixture(scope="module")
def seeded(neo4j_instance: Neo4jInstance) -> None:
    driver = make_driver(neo4j_instance)
    ontology = load_ontology_artifact()
    load_corporation_graph(driver, ontology)
    driver.close()


def test_ac23_coverage_counts_match_the_graph(neo4j_instance: Neo4jInstance, seeded: None):
    driver = make_driver(neo4j_instance)
    try:
        report = report_for_relations(driver, ["SUBSIDIARY_OF", "HEADQUARTERED_IN", "DIRECTOR_OF"])
        assert report.relation_counts == {
            "SUBSIDIARY_OF": 1,
            "HEADQUARTERED_IN": 1,
            "DIRECTOR_OF": 1,
        }
        assert report.contributing_sources == ["test-source"]
        # No :Source node exists, so no refresh stamps — the source is
        # still reported as contributing.
        assert report.source_refresh == {}
    finally:
        driver.close()


def test_coverage_source_refresh_stamps(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from limes.composition import build_run_context
    from limes.pipeline.run import RunSpec, execute_run
    from limes.sources.gisco_nuts import GiscoNutsAdapter
    from tests.fixtures.graph_data import api_settings

    fixture = RawRecord(
        payload=(FIXTURES / "nuts_hierarchy.csv").read_bytes(),
        content_type="text/csv",
        source_url="https://example.test/nuts.csv",
        fetched_at=__import__("datetime").datetime(
            2026, 8, 1, 10, 0, tzinfo=__import__("datetime").UTC
        ),
    )
    monkeypatch.setattr(GiscoNutsAdapter, "fetch", lambda self, since, until: iter([fixture]))

    ctx = build_run_context(api_settings(neo4j_instance, tmp_path), needs_inference=False)
    try:
        execute_run(RunSpec(source_id="gisco_nuts", mode="ingest"), ctx)
        report = report_for_relations(ctx.driver, ["PART_OF_REGION"])
    finally:
        ctx.driver.close()

    assert "gisco_nuts" in report.contributing_sources
    assert report.source_refresh.get("gisco_nuts") is not None


def test_coverage_empty_relation_set_returns_empty_report(
    neo4j_instance: Neo4jInstance, seeded: None
):
    driver = make_driver(neo4j_instance)
    try:
        report = report_for_relations(driver, [])
        assert report.relation_counts == {}
        assert report.contributing_sources == []
    finally:
        driver.close()
