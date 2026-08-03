# tests/acceptance/test_ac22_23_coverage.py | v1.0.0 | introduced by WP-39
"""AC-22 and AC-23: empty-result diagnosis and coverage reports.

AC-22: a query returning zero rows automatically produces a diagnosis
naming the correct failing clause — a two-clause query whose first clause
matches and whose second clause matches nothing.

AC-23: every result carries a coverage report with correct graph-wide
relation counts and source refresh timestamps, from a graph populated
through the production ingestion path.
"""

from __future__ import annotations

from limes.coverage.diagnose import diagnose
from limes.coverage.report import report_for_relations
from tests.fixtures.graph_data import make_driver
from tests.integration.conftest import Neo4jInstance


def test_ac22_diagnosis_names_the_correct_failing_clause(
    populated_graph, neo4j_instance: Neo4jInstance
):
    """The populated graph has corporations but no `Person -[DIRECTOR_OF]->
    Corporation` edges: a two-clause query fails at the second clause, and
    the diagnosis must name that clause."""
    driver = make_driver(neo4j_instance)
    try:
        cypher = (
            "MATCH (c:Corporation) "
            "MATCH (p:Person)-[:DIRECTOR_OF]->(o:Corporation) "
            "RETURN p.label AS person"
        )
        result = diagnose(driver, cypher, {})
        assert result.clause_index == 1
        assert "Person" in result.failing_clause
        assert "DIRECTOR_OF" in result.failing_clause
        assert result.note  # a plain-language note, never empty

        # The control: the first clause alone matches, so the diagnosis
        # cannot blame it.
        first_only = diagnose(driver, "MATCH (c:Corporation) RETURN c", {})
        assert first_only.failing_clause == ""  # it matches — no failure
    finally:
        driver.close()


def test_ac23_coverage_report_counts_and_refresh(populated_graph, neo4j_instance: Neo4jInstance):
    """The coverage report over the populated graph: correct graph-wide
    relation counts and per-source refresh timestamps for the relations
    the query involves."""
    driver = make_driver(neo4j_instance)
    try:
        report = report_for_relations(driver, ["SUBSIDIARY_OF", "PART_OF_REGION"])

        # Every edge in the graph of these types must be counted.
        counts = {
            str(row["relation"]): int(row["count"])
            for row in driver.read(
                "MATCH ()-[r:SUBSIDIARY_OF|PART_OF_REGION]->() "
                "RETURN type(r) AS relation, count(*) AS count",
                {},
                30,
            )
        }
        for relation, count in counts.items():
            assert report.relation_counts.get(relation) == count, report.relation_counts

        assert set(report.relation_counts) >= {"SUBSIDIARY_OF", "PART_OF_REGION"}

        # The contributing sources are the ones that wrote the edges, and
        # each carries a refresh timestamp (the runs succeeded).
        assert set(report.contributing_sources) <= {"gisco_nuts", "gleif", "feeds"}
        assert report.contributing_sources
        for source_id in report.contributing_sources:
            assert source_id in report.source_refresh, report.source_refresh
            assert report.source_refresh[source_id] is not None, (
                f"source {source_id} ran successfully but carries no refresh stamp"
            )
    finally:
        driver.close()


def test_ac23_empty_relation_set_yields_empty_report(
    neo4j_instance: Neo4jInstance,
):
    driver = make_driver(neo4j_instance)
    try:
        report = report_for_relations(driver, [])
        assert report.relation_counts == {}
        assert report.contributing_sources == []
        assert report.source_refresh == {}
    finally:
        driver.close()
