# tests/unit/test_evaluate.py | v1.0.0 | introduced by WP-30
"""Evaluation harness unit tests per Doc 2 §12.5–12.6 and §8.14.

Covers the metric mathematics (per-relation precision/recall/F1 with
multiset semantics, macro-F1, the 0.05 regression gate), the artifact
loaders and their structural contracts (gold set schema, calibration
counts, reference questions — G8/G9), and the resolution-evaluation metric
with stubbed blocking (the vector search itself is WP-25's test surface).
The end-to-end AC-31 CLI gate lives in tests/integration/test_cli_evaluate.py.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from limes.cli import evaluate as evaluate_module
from limes.cli.evaluate import (
    adjudication_accuracy,
    load_calibration_set,
    load_gold_set,
    load_reference_questions,
    macro_f1,
    measure_extraction,
    regressed_relations,
    resolution_evaluation,
    structural_problems,
    write_baseline,
)
from limes.config import Settings
from limes.errors import ConfigurationError
from limes.extraction.base import ExtractionResult
from limes.ontology.registry import load_ontology
from limes.types import ExtractedAssertion, Mention

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY = load_ontology(REPO_ROOT / "ontology" / "ontology.yaml")
GOLD_SET_PATH = REPO_ROOT / "gold_set" / "gold_set.jsonl"
CALIBRATION_PATH = REPO_ROOT / "gold_set" / "calibration_set.jsonl"
QUESTIONS_PATH = REPO_ROOT / "reference_questions" / "questions.yaml"


def _settings(**overrides: Any) -> Settings:
    base = dict(
        neo4j_uri="bolt://test:7687",
        neo4j_user="u",
        neo4j_password="p",
        ontology_path=REPO_ROOT / "ontology" / "ontology.yaml",
        feeds_config_path=REPO_ROOT / "ontology" / "feeds.yaml",
        gold_set_path=GOLD_SET_PATH,
        baseline_path=REPO_ROOT / "gold_set" / "baseline.json",
        archive_path=Path("/tmp/archive"),
        extraction_prompt_version="1.0.0",
        extraction_schema_version="1.0.0",
    )
    base.update(overrides)
    return Settings(**base)


class FakeExtractor:
    """An extractor whose output is the test's canned assertions — the
    model boundary, stubbed exactly as respx stubs the transport."""

    model_id = "test/extractor"

    def __init__(self, assertions: list[ExtractedAssertion]) -> None:
        self._assertions = assertions

    def extract(self, passages, ontology, prompt_version, schema_version) -> ExtractionResult:
        return ExtractionResult(
            assertions=self._assertions,
            input_tokens=10,
            output_tokens=5,
            raw_response="{}",
            parse_errors=[],
        )


def _assertion(relation: str, subject: str, object_: str) -> ExtractedAssertion:
    return ExtractedAssertion(
        passage_index=0,
        subject=Mention(surface=subject, type="Corporation"),
        relation=relation,
        object=Mention(surface=object_, type="Corporation"),
        confidence=0.9,
        evidence_start=0,
        evidence_end=50,
    )


# --------------------------------------------------------------------------
# Artifacts (G9)
# --------------------------------------------------------------------------


def test_gold_set_validates_against_its_schema():
    items = load_gold_set(GOLD_SET_PATH)
    assert len(items) == 2
    assert {item["language"] for item in items} == {"de", "en"}
    # Every expected assertion names subject/object/relation (schema-enforced).
    for item in items:
        assert item["expected_json"]


def test_gold_set_rejects_a_schema_violating_item(tmp_path):
    import shutil

    shutil.copy(REPO_ROOT / "gold_set" / "gold_set.schema.json", tmp_path / "gold_set.schema.json")
    bad = tmp_path / "gold_set.jsonl"
    bad.write_text(
        json.dumps(
            {
                "item_id": "x",
                "language": "de",
                "passage": "text",
                "expected_json": [{"subject": {"surface": "a"}, "relation": "R"}],
                "gold_set_version": "1.0.0",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="fails schema"):
        load_gold_set(bad)


def test_calibration_set_counts_exactly_per_spec():
    items = load_calibration_set(CALIBRATION_PATH)
    assert len(items) == 100
    languages = Counter(item["language"] for item in items)
    kinds = Counter(item["kind"] for item in items)
    assert languages == {"de": 50, "en": 50}
    assert kinds == {"true_match": 40, "hard_negative": 40, "cross_language": 20}


# --------------------------------------------------------------------------
# Reference questions (G8 / AC-25)
# --------------------------------------------------------------------------


def test_ac25_reference_questions_load_and_pass_the_structural_check():
    questions = load_reference_questions(QUESTIONS_PATH)
    assert len(questions) == 5
    for question in questions:
        assert question["question"]
        problems = structural_problems(question["reference_cypher"], ONTOLOGY)
        assert problems == [], f"{question['id']}: {problems}"


def test_structural_problems_detects_writes_and_unknown_names():
    cypher = (
        "MATCH (a:Corporation)-[:SUPPLIES]->(b:Corporation) "
        "CREATE (c:NotAType) SET a.lei = 'x' RETURN a OFFSET 5 LIMIT 1"
    )
    problems = structural_problems(cypher, ONTOLOGY)
    assert "WRITE_CLAUSE:CREATE" in problems
    assert "WRITE_CLAUSE:SET" in problems
    assert "UNKNOWN_NAME:NotAType" in problems
    # OFFSET must not be caught as SET — the check is token-based.
    assert problems.count("WRITE_CLAUSE:SET") == 1


def test_structural_problems_allows_apoc_free_read_queries():
    cypher = (
        "MATCH (p:Person)-[:HOLDS_OFFICE]->(o:Office)-[:OFFICE_AT]->(b:PublicBody) "
        "RETURN p.label LIMIT 10"
    )
    assert structural_problems(cypher, ONTOLOGY) == []


# --------------------------------------------------------------------------
# Metric mathematics
# --------------------------------------------------------------------------


def test_measure_extraction_computes_per_relation_metrics():
    items = [
        {
            "item_id": "a",
            "language": "en",
            "passage": "x",
            "expected_json": [
                {
                    "subject": {"surface": "Acme AG"},
                    "relation": "SUPPLIES",
                    "object": {"surface": "BMW AG"},
                },
                {
                    "subject": {"surface": "Acme AG"},
                    "relation": "SUPPLIES",
                    "object": {"surface": "VW AG"},
                },
            ],
            "gold_set_version": "1.0.0",
        }
    ]
    # Extracted: one exact hit (with different whitespace/case — normalized
    # matching), one duplicate of that hit, one correct other-assertion.
    extractor = FakeExtractor(
        [
            _assertion("SUPPLIES", "acme ag", "BMW AG"),
            _assertion("SUPPLIES", "Acme AG", "BMW AG"),
            _assertion("SUPPLIES", "Acme AG", "VW AG"),
        ]
    )
    metrics = measure_extraction(extractor, items, _settings(), ONTOLOGY)
    # Multiset semantics: TP = 2 (both expected tuples extracted once); the
    # duplicate of (Acme, BMW) is one false positive; nothing is missing
    # (FN = 0). Precision 2/3, recall 1.0, F1 0.8.
    assert metrics["SUPPLIES"]["precision"] == pytest.approx(2 / 3, abs=0.0005)
    assert metrics["SUPPLIES"]["recall"] == pytest.approx(1.0)
    assert metrics["SUPPLIES"]["f1"] == pytest.approx(0.8, abs=0.0005)


def test_macro_f1_covers_only_relations_the_gold_set_asks_about():
    metrics = {
        "SUPPLIES": {"precision": 1.0, "recall": 1.0, "f1": 1.0},
        "AMENDS": {"precision": 0.0, "recall": 0.0, "f1": 0.0},
    }
    items = [
        {
            "item_id": "a",
            "language": "en",
            "passage": "x",
            "expected_json": [
                {"subject": {"surface": "a"}, "relation": "SUPPLIES", "object": {"surface": "b"}}
            ],
            "gold_set_version": "1.0.0",
        }
    ]
    assert macro_f1(metrics, items) == 1.0


def test_regression_gate_compares_against_the_baseline(tmp_path):
    baseline_path = tmp_path / "baseline.json"
    metrics = {"SUPPLIES": {"precision": 1.0, "recall": 1.0, "f1": 1.0}}
    write_baseline(baseline_path, metrics, "1.0.0")
    baseline = evaluate_module.read_baseline(baseline_path)

    assert regressed_relations(baseline, metrics) == []
    # Exactly at the threshold is not a regression; below it is.
    at_threshold = {"SUPPLIES": {"precision": 0.0, "recall": 0.0, "f1": 1.0 - 0.05}}
    assert regressed_relations(baseline, at_threshold) == []
    regressed = {"SUPPLIES": {"precision": 0.0, "recall": 0.0, "f1": 1.0 - 0.051}}
    assert regressed_relations(baseline, regressed) == ["SUPPLIES"]
    # Relations absent from the baseline never regress.
    assert regressed_relations({}, regressed) == []


def test_baseline_round_trip(tmp_path):
    baseline_path = tmp_path / "baseline.json"
    metrics = {"AMENDS": {"precision": 0.8, "recall": 0.7, "f1": 0.7467}}
    write_baseline(baseline_path, metrics, "1.0.0")
    stored = evaluate_module.read_baseline(baseline_path)
    assert stored["gold_set_version"] == "1.0.0"
    assert stored["per_relation"]["AMENDS"]["f1"] == pytest.approx(0.7467)


# --------------------------------------------------------------------------
# Resolution measurement (stubbed vector search)
# --------------------------------------------------------------------------


def test_resolution_evaluation_metrics(monkeypatch):
    items = [
        {
            "item_id": "1",
            "language": "de",
            "type": "Corporation",
            "mention_a": "Volkswagen AG",
            "mention_b": "VW AG",
            "is_match": True,
            "kind": "true_match",
        },
        {
            "item_id": "2",
            "language": "de",
            "type": "Corporation",
            "mention_a": "Volkswagen AG",
            "mention_b": "Audi AG",
            "is_match": False,
            "kind": "hard_negative",
        },
    ]
    # The stub vector search is deterministic per surface: the embedder
    # emits a distinguishable vector, the candidate list follows from it.
    vectors = {
        "Volkswagen AG": [0.1, 0.0, 0.0, 0.0],
        "VW AG": [0.2, 0.0, 0.0, 0.0],
        "Audi AG": [0.3, 0.0, 0.0, 0.0],
    }
    candidates_by_vector = {
        (0.1, 0.0, 0.0, 0.0): ["Volkswagen AG", "VW AG"],
        (0.2, 0.0, 0.0, 0.0): ["Volkswagen AG"],
        (0.3, 0.0, 0.0, 0.0): ["Audi AG"],
    }

    def fake_embed(texts, client, model_id, dimensions=None):
        return [vectors[text] for text in texts]

    def fake_candidates(driver, embedding, entity_type, limit):
        labels = candidates_by_vector[tuple(embedding)]
        return [
            {"entity_id": f"id:{label}", "label": label, "score": 0.9} for label in labels[:limit]
        ]

    monkeypatch.setattr("limes.resolution.blocking.embed", fake_embed)
    monkeypatch.setattr("limes.resolution.blocking.candidates", fake_candidates)

    ctx = SimpleNamespace(
        settings=_settings(embedding_model="test/embed", embedding_dimensions=4),
        client=object(),
        driver=object(),
    )
    scores = resolution_evaluation(ctx, items)
    # Pair 1: "VW AG" appears in the top-10 of "Volkswagen AG" -> recall hit;
    # predicts match (top-1 of b is "Volkswagen AG" == a) -> correct.
    # Pair 2: predicts non-match (neither top-1 equals the other surface) -> correct.
    assert scores["recall@10"] == 1.0
    assert scores["accuracy"] == 1.0


def test_adjudication_accuracy_uses_the_pairwise_verdict(monkeypatch):
    items = [
        {
            "item_id": "1",
            "language": "de",
            "type": "Corporation",
            "mention_a": "Volkswagen AG",
            "mention_b": "VW AG",
            "is_match": True,
            "kind": "true_match",
        },
        {
            "item_id": "2",
            "language": "de",
            "type": "Corporation",
            "mention_a": "Volkswagen AG",
            "mention_b": "Audi AG",
            "is_match": False,
            "kind": "hard_negative",
        },
    ]

    def fake_adjudicate(mention, candidates, client, prompt_version, model_id):
        # Same verdict as a perfect adjudicator: same when the candidate
        # carries the other surface of a match pair, different otherwise.
        label = str(candidates[0]["label"])
        return ("id:match", 0.9) if label == "VW AG" else (None, 0.0)

    # The adjudicator is imported inside the function; patch the module
    # it imports from.
    monkeypatch.setattr("limes.resolution.adjudicate.adjudicate", fake_adjudicate)
    ctx = SimpleNamespace(
        settings=_settings(adjudication_prompt_version="1.0.0"),
        client=object(),
    )
    assert adjudication_accuracy(ctx, items, model_id="test/adjudicator") == 1.0
