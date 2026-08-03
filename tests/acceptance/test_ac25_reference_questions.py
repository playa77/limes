# tests/acceptance/test_ac25_reference_questions.py | v1.0.0 | introduced by WP-39
"""AC-25: all five reference questions have hand-written Cypher passing
validation and planning against an empty graph.

The questions are expressibility fixtures (Doc 2 §12.6): each must pass
the deterministic validator and the EXPLAIN plan gate regardless of
ingested data — against an empty graph here, exactly as specified. The
plan gate never executes the queries.
"""

from __future__ import annotations

import yaml  # type: ignore[import-untyped]

from limes.config import Settings
from limes.nlq.plan import explain_gate
from limes.nlq.validate import validate
from limes.ontology.registry import load_ontology
from tests.fixtures.graph_data import make_driver, wipe_graph
from tests.integration.conftest import Neo4jInstance

REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
QUESTIONS_PATH = REPO_ROOT / "reference_questions" / "questions.yaml"
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"


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


def _questions() -> list[dict]:
    data = yaml.safe_load(QUESTIONS_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, list) and len(data) == 5, "exactly five reference questions"
    return data


def test_ac25_all_five_questions_pass_validation_and_planning(
    neo4j_instance: Neo4jInstance,
):
    """Against an empty graph: every reference Cypher validates against the
    ontology and passes the plan gate."""
    ontology = load_ontology(ONTOLOGY_PATH)
    settings = _settings()
    driver = make_driver(neo4j_instance)
    try:
        wipe_graph(neo4j_instance)
        for entry in _questions():
            cypher = entry["reference_cypher"]
            assert entry["question"], entry
            result = validate(cypher, ontology, settings)
            assert result.valid, (entry["id"], result.errors)
            # The plan gate runs EXPLAIN — never the query — against the
            # empty graph.
            explain_gate(driver, result.cypher, {}, settings)
    finally:
        driver.close()


def test_ac25_reference_cypher_uses_only_ontology_surface():
    """The questions must not name labels or relations outside the
    ontology — they are ontology-expressibility fixtures."""
    ontology = load_ontology(ONTOLOGY_PATH)
    settings = _settings()
    for entry in _questions():
        result = validate(entry["reference_cypher"], ontology, settings)
        assert not result.errors, (entry["id"], result.errors)
