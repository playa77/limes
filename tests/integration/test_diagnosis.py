# tests/integration/test_diagnosis.py | v1.0.0 | introduced by WP-34
"""Empty-result diagnosis integration tests per Doc 2 §8.11 (AC-22): a
query returning zero rows produces a diagnosis naming the correct failing
clause, with graph-wide relation counts and a plain-language note."""

import pytest

from limes.coverage.diagnose import diagnose
from tests.fixtures.graph_data import (
    load_corporation_graph,
    load_ontology_artifact,
    make_driver,
)
from tests.integration.conftest import Neo4jInstance


@pytest.fixture(scope="module")
def seeded(neo4j_instance: Neo4jInstance) -> None:
    driver = make_driver(neo4j_instance)
    ontology = load_ontology_artifact()
    load_corporation_graph(driver, ontology)
    driver.close()


def test_ac22_first_empty_clause_is_named(neo4j_instance: Neo4jInstance, seeded: None):
    driver = make_driver(neo4j_instance)
    try:
        result = diagnose(
            driver,
            (
                "MATCH (a:Corporation {lei: 'LEI-ALPHA'}) "
                "MATCH (a)-[:SUBSIDIARY_OF]->(b:Corporation {lei: 'LEI-NOPE'}) "
                "RETURN b"
            ),
            {},
        )
        assert result.clause_index == 1
        assert "LEI-NOPE" in result.failing_clause
        assert result.relation_counts == {"SUBSIDIARY_OF": 1}
        assert "Corporation" in result.note
    finally:
        driver.close()


def test_ac22_first_clause_failure_is_named(neo4j_instance: Neo4jInstance, seeded: None):
    driver = make_driver(neo4j_instance)
    try:
        result = diagnose(
            driver,
            ("MATCH (a:Corporation {lei: 'LEI-UNKNOWN'}) MATCH (a)-[:SUBSIDIARY_OF]->(b) RETURN b"),
            {},
        )
        assert result.clause_index == 0
        assert "LEI-UNKNOWN" in result.failing_clause
        assert "No entities of type Corporation" in result.note
    finally:
        driver.close()


def test_diagnosis_of_matching_query_returns_no_failing_clause(
    neo4j_instance: Neo4jInstance, seeded: None
):
    driver = make_driver(neo4j_instance)
    try:
        result = diagnose(
            driver,
            ("MATCH (a:Corporation {lei: 'LEI-ALPHA'}) MATCH (a)-[:SUBSIDIARY_OF]->(b) RETURN b"),
            {},
        )
        assert result.clause_index == -1
        assert "matches individually" in result.note
    finally:
        driver.close()


def test_diagnosis_without_match_clauses(neo4j_instance: Neo4jInstance, seeded: None):
    driver = make_driver(neo4j_instance)
    try:
        result = diagnose(driver, "RETURN 1 AS one WHERE false", {})
        assert result.clause_index == -1
        assert "no MATCH clause" in result.note
    finally:
        driver.close()
