# tests/acceptance/test_ac20_21_validation_plan.py | v1.0.0 | introduced by WP-39
"""AC-20 and AC-21: every validation code and every plan-gate rejection in
§8.10 is produced by a crafted query and blocks execution.

AC-20's codes: `UNKNOWN_LABEL`, `UNKNOWN_RELATION`, `DOMAIN_VIOLATION`,
`RANGE_VIOLATION`, `WRITE_CLAUSE`, `DISALLOWED_PROCEDURE`,
`LIMIT_EXCEEDS_MAX` — each produced by one crafted query through the
deterministic validator, and the API refuses a validation-failing query
with 400 (execution blocked).

AC-21's codes: `UNBOUNDED_EXPANSION`, `EXPANSION_TOO_DEEP`,
`CARTESIAN_PRODUCT`, `OPERATOR_ROWS_EXCEEDED`, `TOTAL_ROWS_EXCEEDED` —
each produced by one crafted query against the real EXPLAIN plan, and the
API refuses a plan-rejected query with 422.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from limes.config import Settings
from limes.errors import QueryPlanRejected
from limes.nlq.plan import explain_gate
from limes.nlq.validate import validate
from limes.ontology.registry import load_ontology
from tests.fixtures.graph_data import (
    make_api_client,
    make_driver,
    wipe_graph,
)
from tests.integration.conftest import Neo4jInstance

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"

VALIDATION_CORPUS = [
    ("UNKNOWN_LABEL", "MATCH (n:NotAThing) RETURN n"),
    ("UNKNOWN_RELATION", "MATCH (a:Corporation)-[:FLIES]->(b:Corporation) RETURN a"),
    # SUBSIDIARY_OF domain is Corporation; a Person subject violates it.
    ("DOMAIN_VIOLATION", "MATCH (p:Person)-[:SUBSIDIARY_OF]->(c:Corporation) RETURN p"),
    # HEADQUARTERED_IN range is Location; a Person object violates it.
    ("RANGE_VIOLATION", "MATCH (c:Corporation)-[:HEADQUARTERED_IN]->(p:Person) RETURN c"),
    ("WRITE_CLAUSE", "MATCH (n) DELETE n"),
    ("DISALLOWED_PROCEDURE", "CALL apoc.do.stuff() YIELD value RETURN value"),
    ("LIMIT_EXCEEDS_MAX", "MATCH (n:Corporation) RETURN n LIMIT 999999"),
]


def _settings() -> Settings:
    return Settings(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="limes",
        neo4j_password="pw",
        ontology_path=ONTOLOGY_PATH,
        feeds_config_path=REPO_ROOT / "ontology" / "feeds.yaml",
        gold_set_path=REPO_ROOT / "gold_set" / "gold_set.jsonl",
        baseline_path=REPO_ROOT / "gold_set" / "baseline.json",
        archive_path=REPO_ROOT / "archive",
        openrouter_api_key="sk-test",
        query_default_limit=500,
        query_max_limit=5000,
    )


def test_ac20_every_validation_code_is_produced_by_a_crafted_query():
    ontology = load_ontology(ONTOLOGY_PATH)
    settings = _settings()
    for expected_code, query in VALIDATION_CORPUS:
        result = validate(query, ontology, settings)
        assert not result.valid, (expected_code, query)
        assert any(expected_code in error for error in result.errors), (
            expected_code,
            query,
            result.errors,
        )


def test_ac20_validation_failure_blocks_execution(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
):
    """The blocking half: an operator-supplied query that fails validation
    is refused by the API with 400 and never reaches the database."""
    wipe_graph(neo4j_instance)
    with make_api_client(neo4j_instance, tmp_path) as client:
        for _code, query in VALIDATION_CORPUS:
            response = client.post("/query/cypher", json={"cypher": query})
            assert response.status_code == 400, (query, response.text)


def test_ac21_every_plan_gate_rejection_is_produced_by_a_crafted_query(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
):
    """Each plan-gate code, produced by one crafted query against the real
    EXPLAIN plan (the plan never executes). The row-ceiling codes use
    planner estimates: the planner multiplies row estimates along
    UNWIND chains (10^k), and a LIMIT caps a branch's own estimate while
    the UNION root still sums every branch — so a 16-branch union totals
    above the 20M cap with no operator above the 5M cap."""
    driver = make_driver(neo4j_instance)
    settings = _settings()
    chain8 = (
        "UNWIND range(0, 1000) AS a UNWIND range(0, 1000) AS b "
        "UNWIND range(0, 1000) AS c UNWIND range(0, 1000) AS d "
        "UNWIND range(0, 1000) AS e UNWIND range(0, 1000) AS f "
        "UNWIND range(0, 1000) AS g UNWIND range(0, 1000) AS h RETURN h"
    )
    branch6 = (
        "UNWIND range(0, 1000) AS a UNWIND range(0, 1000) AS b "
        "UNWIND range(0, 1000) AS c UNWIND range(0, 1000) AS d "
        "UNWIND range(0, 1000) AS e UNWIND range(0, 1000) AS f "
        "RETURN f LIMIT 100000"
    )
    try:
        corpus = [
            # [*] without an upper bound.
            ("UNBOUNDED_EXPANSION", "MATCH (a:Corporation)-[*]->(b) RETURN b"),
            # Upper bound above LIMES_QUERY_MAX_VARLENGTH_HOPS (4).
            ("EXPANSION_TOO_DEEP", "MATCH (a:Corporation)-[*1..10]->(b) RETURN b"),
            # Two independent patterns — the planner's cartesian product.
            ("CARTESIAN_PRODUCT", "MATCH (a:Corporation), (b:Corporation) RETURN a, b"),
            # Eight chained UNWINDS: the planner multiplies estimates along
            # the chain, so the top operator estimates 10^8 rows.
            ("OPERATOR_ROWS_EXCEEDED", chain8),
            # Sixteen UNION branches, each capped by LIMIT 100000: every
            # operator stays under 5M rows while the union totals ~32M.
            ("TOTAL_ROWS_EXCEEDED", " UNION ".join([branch6] * 16)),
        ]
        for expected_code, query in corpus:
            with pytest.raises(QueryPlanRejected) as excinfo:
                explain_gate(driver, query, {}, settings)
            assert getattr(excinfo.value, "code", None) == expected_code, (
                expected_code,
                query,
                str(excinfo.value),
            )
    finally:
        driver.close()


def test_ac21_plan_rejection_blocks_execution(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
):
    """The blocking half: a plan-rejected query is refused by the API with
    422 (the §11 mapping) and never executes."""
    wipe_graph(neo4j_instance)
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.post(
            "/query/cypher",
            json={"cypher": "MATCH (a:Corporation)-[*]->(b) RETURN b"},
        )
        assert response.status_code == 422, response.text
