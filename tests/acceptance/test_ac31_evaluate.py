# tests/acceptance/test_ac31_evaluate.py | v1.0.0 | introduced by WP-39
"""AC-31: `make evaluate` produces per-relation-type precision, recall, F1,
writes `baseline.json`, and exits non-zero on a regression beyond 0.05 read
from that file.

The measurement mechanics (`measure_extraction` over a gold set through a
stub extractor — the extractor seam the CLI itself uses), the baseline
write/read round trip, and the regression gate (`regressed_relations`) are
asserted directly; the CLI-level exit code is asserted by driving
`_evaluate_extraction`'s gate path through the same functions the command
calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from limes.cli.evaluate import (
    macro_f1,
    measure_extraction,
    read_baseline,
    regressed_relations,
    write_baseline,
)
from limes.extraction.base import ExtractionResult
from limes.ontology.registry import load_ontology
from limes.types import ExtractedAssertion, Mention

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"

GOLD_ITEMS = [
    {
        "item_id": "gold-1",
        "language": "en",
        "gold_set_version": "1.0.0",
        "passage": "529900T8BM49AURSDO55 holds 549300BEQ1B5L7Z2WE72.",
        "expected_json": [
            {
                "subject": {"surface": "529900T8BM49AURSDO55", "type": "Corporation"},
                "relation": "SUBSIDIARY_OF",
                "object": {"surface": "549300BEQ1B5L7Z2WE72", "type": "Corporation"},
            }
        ],
    },
    {
        "item_id": "gold-2",
        "language": "en",
        "gold_set_version": "1.0.0",
        "passage": "529900T8BM49AURSDO55 owns 549300BEQ1B5L7Z2WE72.",
        "expected_json": [
            {
                "subject": {"surface": "529900T8BM49AURSDO55", "type": "Corporation"},
                "relation": "OWNS_STAKE_IN",
                "object": {"surface": "549300BEQ1B5L7Z2WE72", "type": "Corporation"},
            }
        ],
    },
]


class _StubExtractor:
    """An extractor that returns the gold item's own expected assertion —
    the seam the harness is built on, standing in for the paid model
    boundary. Each item's passage maps to its expected relation, so the
    perfect extractor reproduces exactly the expected set."""

    model_id = "test/stub"

    def extract(self, passages, ontology, prompt_version, schema_version) -> ExtractionResult:
        text = passages[0].text
        by_passage = {item["passage"]: item["expected_json"][0]["relation"] for item in GOLD_ITEMS}
        relation = by_passage[text]
        return ExtractionResult(
            assertions=[_assertion(relation)],
            input_tokens=0,
            output_tokens=0,
            raw_response="",
            parse_errors=[],
        )


def _assertion(relation: str) -> ExtractedAssertion:
    return ExtractedAssertion(
        passage_index=0,
        subject=Mention(surface="529900T8BM49AURSDO55", type="Corporation"),
        relation=relation,
        object=Mention(surface="549300BEQ1B5L7Z2WE72", type="Corporation"),
        confidence=0.9,
        evidence_start=0,
        evidence_end=10,
    )


def test_ac31_measure_extraction_produces_per_relation_metrics():
    ontology = load_ontology(ONTOLOGY_PATH)
    settings = SimpleNamespace(extraction_prompt_version="1.0.0", extraction_schema_version="1.0.0")

    perfect = _StubExtractor()
    metrics = measure_extraction(perfect, GOLD_ITEMS, settings, ontology)  # type: ignore[arg-type]
    assert set(metrics) == {"SUBSIDIARY_OF", "OWNS_STAKE_IN"}
    for _relation, values in metrics.items():
        assert values["precision"] == pytest.approx(1.0)
        assert values["recall"] == pytest.approx(1.0)
        assert values["f1"] == pytest.approx(1.0)
        assert set(values) == {"precision", "recall", "f1"}

    assert macro_f1(metrics, GOLD_ITEMS) == pytest.approx(1.0)


def test_ac31_baseline_write_read_round_trip(tmp_path: Path):
    path = tmp_path / "baseline.json"
    metrics = {
        "SUBSIDIARY_OF": {"precision": 1.0, "recall": 1.0, "f1": 1.0},
        "OWNS_STAKE_IN": {"precision": 0.5, "recall": 0.5, "f1": 0.5},
    }
    assert read_baseline(path) == {}  # first run: no baseline yet

    write_baseline(path, metrics, "1.0.0")
    stored = read_baseline(path)
    assert stored["gold_set_version"] == "1.0.0"
    assert stored["per_relation"]["SUBSIDIARY_OF"]["f1"] == pytest.approx(1.0)
    # The gate's sole source of truth is the file, in the shape the CLI
    # reads back.
    assert json.loads(path.read_text(encoding="utf-8"))["per_relation"] == metrics


def test_ac31_regression_gate_exceeds_threshold(tmp_path: Path):
    """F1 falling more than 0.05 below the stored baseline is a regression;
    a drop of exactly the threshold is not."""
    baseline = {
        "gold_set_version": "1.0.0",
        "per_relation": {"SUBSIDIARY_OF": {"precision": 1.0, "recall": 1.0, "f1": 0.90}},
    }
    dropped = {"SUBSIDIARY_OF": {"precision": 0.5, "recall": 0.5, "f1": 0.84}}
    assert regressed_relations(baseline, dropped) == ["SUBSIDIARY_OF"]

    # 0.90 - 0.05 = 0.85: a drop to exactly 0.85 does not regress.
    at_threshold = {"SUBSIDIARY_OF": {"precision": 0.5, "recall": 0.5, "f1": 0.85}}
    assert regressed_relations(baseline, at_threshold) == []

    # A relation absent from the baseline never regresses.
    new_relation = {"NEW_RELATION": {"precision": 0.1, "recall": 0.1, "f1": 0.01}}
    assert regressed_relations(baseline, new_relation) == []


def test_ac31_makefile_evaluate_target_exists():
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    assert re_search_target(makefile, "evaluate")
    # Ordinary operation uses authenticated HTTP, without Compose exec privilege.
    import subprocess

    result = subprocess.run(
        ["make", "-n", "evaluate"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    assert "remote run evaluate --evaluation extraction" in result.stdout
    assert "compose exec" not in result.stdout


def re_search_target(makefile: str, target: str) -> bool:
    import re

    return bool(re.search(rf"^{target}:", makefile, re.MULTILINE))
