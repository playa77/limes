# tests/unit/test_select_models.py | v1.0.0 | introduced by WP-29
"""Model selection tests per Doc 2 §8.7.2 (AC-36, AC-37).

Stage 1 (provisional): catalogue filtering by role criteria and ranking,
the operator-confirmation flow, and the pin write — with the gold set
never read. Stage 2 (measured): the gold-set version refusal, the
per-role evaluation and pin write, and the impact report that measures
and never performs (AC-37). The catalogue is stubbed; no network.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from limes.cli import select_models as select_models_module
from limes.cli.select_models import _write_pins, filter_candidates
from limes.config import Settings
from limes.errors import LimesError
from limes.ontology.registry import load_ontology

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"

# Catalogue entries with one candidate per role, priced inside the §8.7.2
# ceilings; plus an over-ceiling and a non-structured-output entry that
# must be filtered out.
CATALOGUE = [
    {
        "id": "ext/cheap",
        "pricing": {"prompt": "0.000000200", "completion": "0.000000400", "request": "0"},
        "supported_parameters": {"structured_outputs": True},
    },
    {
        "id": "adj/cheap",
        "pricing": {"prompt": "0.000000100", "completion": "0.000000200", "request": "0"},
        "supported_parameters": {"structured_outputs": True},
    },
    {
        "id": "emb/cheap",
        "pricing": {"prompt": "0.000000050", "completion": "0", "request": "0"},
        "supported_parameters": {"structured_outputs": False},
        "architecture": {"embedding_dimensions": 1024},
    },
    {
        "id": "nlq/cheap",
        "pricing": {"prompt": "0.000000400", "completion": "0.000000400", "request": "0"},
        "supported_parameters": {"structured_outputs": False},
    },
    {
        "id": "ext/too-expensive",
        "pricing": {"prompt": "0.000001000", "completion": "0.000001000", "request": "0"},
        "supported_parameters": {"structured_outputs": True},
    },
    {
        "id": "ext/no-structured",
        "pricing": {"prompt": "0.000000100", "completion": "0.000000200", "request": "0"},
        "supported_parameters": {"structured_outputs": False},
    },
    {
        "id": "emb/too-wide",
        "pricing": {"prompt": "0.000000050", "completion": "0", "request": "0"},
        "supported_parameters": {"structured_outputs": False},
        "architecture": {"embedding_dimensions": 3072},
    },
]


def _settings(**overrides: Any) -> Settings:
    base = dict(
        neo4j_uri="bolt://test:7687",
        neo4j_user="u",
        neo4j_password="p",
        ontology_path=ONTOLOGY_PATH,
        feeds_config_path=REPO_ROOT / "ontology" / "feeds.yaml",
        gold_set_path=REPO_ROOT / "gold_set" / "gold_set.jsonl",
        baseline_path=REPO_ROOT / "gold_set" / "baseline.json",
        archive_path=Path("/tmp/archive"),
        extraction_model="old/extraction",
        embedding_model="old/embedding",
    )
    base.update(overrides)
    return Settings(**base)


class _CountDriver:
    """Answers the impact-report count queries."""

    def read(self, cypher: str, params: dict, timeout_s: int) -> list[dict]:
        if "ExtractionCacheEntry" in cypher:
            return [{"c": 12}]
        if "extractor_model" in cypher:
            return [{"c": 3}]
        if "count(e) AS c" in cypher:
            return [{"c": 40}]
        return []


def _ctx(settings: Settings, catalogue: list[dict[str, Any]] = CATALOGUE) -> SimpleNamespace:
    return SimpleNamespace(
        settings=settings,
        client=SimpleNamespace(catalogue=lambda: catalogue),
        driver=_CountDriver(),
        ontology=load_ontology(ONTOLOGY_PATH),
    )


# --------------------------------------------------------------------------
# Filtering and ranking
# --------------------------------------------------------------------------


def test_filter_candidates_applies_role_criteria():
    extraction = filter_candidates(CATALOGUE, "extraction")
    extraction_ids = [c["id"] for c in extraction]
    # A cheap model qualifies for several roles (the ceilings overlap by
    # design); the role-specific exclusions are what matter.
    assert "ext/cheap" in extraction_ids
    assert "adj/cheap" in extraction_ids
    assert "ext/too-expensive" not in extraction_ids
    assert "ext/no-structured" not in extraction_ids

    embedding = filter_candidates(CATALOGUE, "embedding")
    embedding_ids = [c["id"] for c in embedding]
    assert embedding_ids[0] == "emb/cheap"  # cheapest within the 0.20 ceiling
    assert "emb/too-wide" not in embedding_ids
    assert "ext/cheap" not in embedding_ids  # 0.30/M blended exceeds the ceiling

    assert "adj/cheap" in [c["id"] for c in filter_candidates(CATALOGUE, "adjudication")]
    assert "nlq/cheap" in [c["id"] for c in filter_candidates(CATALOGUE, "nl2cypher")]


def test_filter_candidates_ranks_by_blended_cost_then_structured_output():
    catalogue = [
        {
            "id": "dear-structured",
            "pricing": {"prompt": "0.000000300", "completion": "0.000000300", "request": "0"},
            "supported_parameters": {"structured_outputs": True},
        },
        {
            "id": "cheap-plain",
            "pricing": {"prompt": "0.000000100", "completion": "0.000000100", "request": "0"},
            "supported_parameters": {"structured_outputs": False},
        },
        {
            "id": "cheap-structured",
            "pricing": {"prompt": "0.000000100", "completion": "0.000000100", "request": "0"},
            "supported_parameters": {"structured_outputs": True},
        },
    ]
    # The extraction role requires declared structured output: the plain
    # entry is excluded; the two structured entries rank by blended cost.
    ranked = filter_candidates(catalogue, "extraction")
    assert [c["id"] for c in ranked] == ["cheap-structured", "dear-structured"]
    # The nl2cypher role does not require structured output: the cheapest
    # candidate wins, structured or not.
    ranked_nlq = filter_candidates(catalogue, "nl2cypher")
    # Equal cost breaks toward the declared structured output (the sort
    # key's second term); the plain entry follows.
    assert [c["id"] for c in ranked_nlq] == ["cheap-structured", "cheap-plain", "dear-structured"]


# --------------------------------------------------------------------------
# Stage 1 — provisional (AC-36)
# --------------------------------------------------------------------------


def test_ac36_provisional_writes_pin_set_without_gold_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
):
    # The gold set path points at a nonexistent file: the provisional stage
    # must never read it (AC-36).
    settings = _settings(gold_set_path=tmp_path / "does-not-exist.jsonl")
    env_file = tmp_path / ".env"
    monkeypatch.setattr(select_models_module, "ENV_FILE", env_file)
    monkeypatch.setattr(select_models_module, "_confirm", lambda prompt: True)

    select_models_module._provisional(_ctx(settings))

    content = env_file.read_text(encoding="utf-8")
    # The winners are the ranked top candidate per role — derived, not
    # asserted by name (the ranking is the code under test).
    for role, key in select_models_module.ROLE_ENV_KEYS.items():
        winner = filter_candidates(CATALOGUE, role)[0]["id"]
        assert f"{key}={winner}" in content, f"{role} pin missing"
    assert "LIMES_MODEL_PIN_STAGE=provisional" in content
    out = capsys.readouterr().out
    assert "written" in out


def test_provisional_skips_unconfirmed_roles(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    settings = _settings(gold_set_path=tmp_path / "does-not-exist.jsonl")
    env_file = tmp_path / ".env"
    monkeypatch.setattr(select_models_module, "ENV_FILE", env_file)
    # The operator declines everything: no pins, loud failure.
    monkeypatch.setattr(select_models_module, "_confirm", lambda prompt: False)
    with pytest.raises(LimesError, match="nothing written"):
        select_models_module._provisional(_ctx(settings))
    assert not env_file.exists()


# --------------------------------------------------------------------------
# Stage 2 — measured (AC-37)
# --------------------------------------------------------------------------


def test_ac37_measured_refuses_without_gold_set(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    # A gold set below 1.0.0 is a refusal, not a measurement (AC-37).
    import shutil

    shutil.copy(REPO_ROOT / "gold_set" / "gold_set.schema.json", tmp_path / "gold_set.schema.json")
    old_gold = tmp_path / "gold_set.jsonl"
    old_gold.write_text(
        json.dumps(
            {
                "item_id": "x",
                "language": "en",
                "passage": "text",
                "expected_json": [
                    {
                        "subject": {"surface": "a"},
                        "relation": "SUPPLIES",
                        "object": {"surface": "b"},
                    }
                ],
                "gold_set_version": "0.9.0",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    settings = _settings(gold_set_path=old_gold)
    monkeypatch.setattr(select_models_module, "ENV_FILE", tmp_path / ".env")
    with pytest.raises(LimesError, match="version >= 1.0.0"):
        select_models_module._measured(_ctx(settings))


def test_ac37_repin_reports_counts_without_reextracting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
):
    env_file = tmp_path / ".env"
    monkeypatch.setattr(select_models_module, "ENV_FILE", env_file)
    # The per-role scoring is the harness's (WP-30); the selection logic
    # under test consumes the scores and reports the impact.
    monkeypatch.setattr(
        select_models_module,
        "_score_role",
        lambda role, model, ctx, gold, calib, questions: {
            "extraction": 0.9,
            "adjudication": 0.8,
            "embedding": 0.7,
            "nl2cypher": 0.6,
        }[role],
    )
    settings = _settings(
        extraction_model="old/extraction",
        embedding_model="old/embedding",
        usd_eur_rate=0.92,
    )
    select_models_module._measured(_ctx(settings))

    content = env_file.read_text(encoding="utf-8")
    # The winners are the evaluated top candidate per role (the score is
    # stubbed; the selection consumes the scores and pins the winner).
    for role, key in select_models_module.ROLE_ENV_KEYS.items():
        winner = filter_candidates(CATALOGUE, role)[0]["id"]
        assert f"{key}={winner}" in content, f"{role} pin missing"
    assert "LIMES_MODEL_PIN_STAGE=measured" in content

    out = capsys.readouterr().out
    # The impact report measures and never performs (AC-37).
    assert "no re-extraction performed" in out
    assert "vector index rebuild is required and was NOT executed" in out
    assert "3 sources, 12 cached documents affected" in out


def test_write_pins_preserves_existing_env_content(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("LIMES_OTHER_KEY=value\n", encoding="utf-8")
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(select_models_module, "ENV_FILE", env_file)
    _write_pins({"extraction": "ext/cheap"}, "provisional")
    content = env_file.read_text(encoding="utf-8")
    assert "LIMES_OTHER_KEY=value" in content
    assert "LIMES_EXTRACTION_MODEL=ext/cheap" in content
    monkeypatch.undo()
