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
    env_file = tmp_path / "models.env"
    monkeypatch.setattr(select_models_module, "ENV_FILE", env_file)
    monkeypatch.setattr(select_models_module, "_confirm", lambda prompt: True)

    select_models_module._provisional(_ctx(settings), confirm=True)

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
    env_file = tmp_path / "models.env"
    monkeypatch.setattr(select_models_module, "ENV_FILE", env_file)
    # The operator declines everything: no pins, loud failure.
    monkeypatch.setattr(select_models_module, "_confirm", lambda prompt: False)
    with pytest.raises(LimesError, match="nothing written"):
        select_models_module._provisional(_ctx(settings), confirm=True)
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
    monkeypatch.setattr(select_models_module, "ENV_FILE", tmp_path / "models.env")
    with pytest.raises(LimesError, match="version >= 1.0.0"):
        select_models_module._measured(_ctx(settings))


def test_ac37_repin_reports_counts_without_reextracting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
):
    env_file = tmp_path / "models.env"
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
    report = json.loads(env_file.with_suffix(".evaluation.json").read_text())
    assert set(report["scores"]) == set(select_models_module.ROLE_ENV_KEYS)
    assert set(report["winners"]) == set(select_models_module.ROLE_ENV_KEYS)
    assert report["gold_set_version"] == "1.0.0"
    assert len(report["gold_set_sha256"]) == 64
    assert "measured_at" in report

    out = capsys.readouterr().out
    # The impact report measures and never performs (AC-37).
    assert "no re-extraction performed" in out
    assert "vector index rebuild is required and was NOT executed" in out
    assert "3 sources, 12 cached documents affected" in out


def test_write_pins_preserves_existing_env_content(tmp_path: Path):
    env_file = tmp_path / "models.env"
    env_file.write_text("LIMES_NL2CYPHER_MODEL=existing/model\n", encoding="utf-8")
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(select_models_module, "ENV_FILE", env_file)
    _write_pins({"extraction": "ext/cheap"}, "provisional")
    content = env_file.read_text(encoding="utf-8")
    assert "LIMES_NL2CYPHER_MODEL=existing/model" in content
    assert "LIMES_EXTRACTION_MODEL=ext/cheap" in content
    monkeypatch.undo()


# --------------------------------------------------------------------------
# Command wiring and refusal paths
# --------------------------------------------------------------------------


def test_select_models_requires_exactly_one_stage_flag():
    with pytest.raises(LimesError, match="exactly one of --provisional or --measured"):
        select_models_module.select_models(provisional=True, measured=True)
    with pytest.raises(LimesError, match="exactly one of --provisional or --measured"):
        select_models_module.select_models(provisional=False, measured=False)


def test_select_models_wires_the_provisional_stage(monkeypatch: pytest.MonkeyPatch):
    # The command body: settings, logging, context with the explicit
    # envelope, stage dispatch, driver close. The stages themselves are
    # covered by their own tests; this is the wiring between them.
    settings = _settings()
    ctx = SimpleNamespace(driver=SimpleNamespace(close=lambda: None))
    calls: list[str] = []
    monkeypatch.setattr("limes.config.load_settings", lambda: settings)
    monkeypatch.setattr("limes.logging_setup.configure_logging", lambda settings: None)
    monkeypatch.setattr(
        "limes.composition.build_run_context",
        lambda settings, needs_inference, budget_eur=None: ctx,
    )
    monkeypatch.setattr(
        select_models_module, "_provisional", lambda ctx, **kwargs: calls.append("provisional")
    )
    monkeypatch.setattr(select_models_module, "_measured", lambda ctx: calls.append("measured"))
    select_models_module.select_models(provisional=True, measured=False, budget=2.5)
    assert calls == ["provisional"]
    calls.clear()
    select_models_module.select_models(provisional=False, measured=True, budget=None)
    assert calls == ["measured"]


def test_select_models_gold_set_version_rejects_mixed_versions():
    with pytest.raises(LimesError, match="mixed versions"):
        select_models_module._gold_set_version(
            [{"gold_set_version": "1.0.0"}, {"gold_set_version": "1.1.0"}]
        )


def test_filter_candidates_skips_entries_with_unparseable_pricing():
    catalogue = [
        {"id": "broken-price", "pricing": {"prompt": "abc", "completion": "0.000000100"}},
        {"id": "fine", "pricing": {"prompt": "0.000000100", "completion": "0.000000100"}},
    ]
    # The unparseable entry is skipped, not fatal — the catalogue is
    # third-party input and one broken row must not kill the ranking.
    assert [c["id"] for c in filter_candidates(catalogue, "nl2cypher")] == ["fine"]


def test_filter_candidates_keeps_embeddings_with_unparseable_dimensions():
    catalogue = [
        {
            "id": "emb/odd-dims",
            "pricing": {"prompt": "0.000000050", "completion": "0"},
            "architecture": {"embedding_dimensions": "a lot"},
        }
    ]
    # A non-numeric dimension declaration is not a reason to exclude the
    # candidate — only a declared numeric dimension above the ceiling is.
    assert [c["id"] for c in filter_candidates(catalogue, "embedding")] == ["emb/odd-dims"]


def test_provisional_refuses_an_empty_catalogue(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    settings = _settings(gold_set_path=tmp_path / "does-not-exist.jsonl")
    with pytest.raises(LimesError, match="catalogue returned no models"):
        select_models_module._provisional(_ctx(settings, catalogue=[]))


def test_provisional_skips_roles_without_a_candidate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
):
    settings = _settings(gold_set_path=tmp_path / "does-not-exist.jsonl")
    monkeypatch.setattr(select_models_module, "ENV_FILE", tmp_path / "models.env")
    # Every catalogue entry exceeds every role ceiling: each role is
    # reported skipped, no pin is written, and the run refuses loudly.
    expensive = [
        {"id": "m/too-expensive", "pricing": {"prompt": "0.001000000", "completion": "0.001000000"}}
    ]
    with pytest.raises(LimesError, match="no role pinned"):
        select_models_module._provisional(_ctx(settings, catalogue=expensive))
    out = capsys.readouterr().out
    assert "no extraction candidate within the cost ceiling; skipped" in out


def _gold_set_version_2(tmp_path: Path) -> Path:
    """A valid gold set at version 2.0.0 plus its schema, beside the
    calibration set the measured stage also requires."""
    import shutil

    shutil.copy(REPO_ROOT / "gold_set" / "gold_set.schema.json", tmp_path / "gold_set.schema.json")
    gold = tmp_path / "gold_set.jsonl"
    gold.write_text(
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
                "gold_set_version": "2.0.0",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "calibration_set.jsonl").write_text(
        json.dumps(
            {
                "item_id": "1",
                "language": "de",
                "type": "Corporation",
                "mention_a": "A AG",
                "mention_b": "B AG",
                "is_match": False,
                "kind": "hard_negative",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return gold


def test_measured_refuses_an_empty_catalogue(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    gold = _gold_set_version_2(tmp_path)
    settings = _settings(gold_set_path=gold)
    monkeypatch.setattr(select_models_module, "ENV_FILE", tmp_path / "models.env")
    with pytest.raises(LimesError, match="catalogue returned no models"):
        select_models_module._measured(_ctx(settings, catalogue=[]))


def test_measured_skips_roles_without_a_candidate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
):
    gold = _gold_set_version_2(tmp_path)
    settings = _settings(gold_set_path=gold)
    monkeypatch.setattr(select_models_module, "ENV_FILE", tmp_path / "models.env")
    expensive = [
        {"id": "m/too-expensive", "pricing": {"prompt": "0.001000000", "completion": "0.001000000"}}
    ]
    with pytest.raises(LimesError, match="no role pinned"):
        select_models_module._measured(_ctx(settings, catalogue=expensive))
    out = capsys.readouterr().out
    assert "no extraction candidate within the cost ceiling; skipped" in out


# --------------------------------------------------------------------------
# The §8.7.2 selector metrics per role
# --------------------------------------------------------------------------


def test_score_role_routes_every_role_to_its_selector(monkeypatch: pytest.MonkeyPatch):
    ctx = _ctx(_settings())
    gold_items = [{"item_id": "x", "gold_set_version": "2.0.0", "expected_json": []}]
    calibration: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []

    # Extraction: per-candidate extractor from the composition root, then
    # the gold-set macro-F1.
    seen: dict[str, Any] = {}
    monkeypatch.setattr(
        "limes.composition.extractor_for",
        lambda settings, client: seen.setdefault("extractor", object()),
    )
    monkeypatch.setattr(
        select_models_module,
        "measure_extraction",
        lambda extractor, items, settings, ontology: {
            "SUPPLIES": {"precision": 1.0, "recall": 1.0, "f1": 0.9}
        },
    )
    monkeypatch.setattr(select_models_module, "macro_f1", lambda metrics, items: 0.9)
    assert (
        select_models_module._score_role(
            "extraction", "m1", ctx, gold_items, calibration, questions
        )
        == 0.9
    )

    # The other three roles pass the model id straight to their harness.
    monkeypatch.setattr(
        select_models_module, "adjudication_accuracy", lambda ctx, items, model_id=None: 0.8
    )
    assert (
        select_models_module._score_role(
            "adjudication", "m1", ctx, gold_items, calibration, questions
        )
        == 0.8
    )
    monkeypatch.setattr(
        select_models_module,
        "resolution_evaluation",
        lambda ctx, items, embedding_model=None: {"recall@10": 0.7},
    )
    assert (
        select_models_module._score_role("embedding", "m1", ctx, gold_items, calibration, questions)
        == 0.7
    )
    monkeypatch.setattr(
        select_models_module,
        "nl2cypher_evaluation",
        lambda ctx, questions, model_id=None: {"validation_pass_rate": 0.6},
    )
    assert (
        select_models_module._score_role("nl2cypher", "m1", ctx, gold_items, calibration, questions)
        == 0.6
    )

    with pytest.raises(LimesError, match="unknown role"):
        select_models_module._score_role("typo", "m1", ctx, gold_items, calibration, questions)


def test_blended_price_falls_back_on_unparseable_pricing():
    catalogue = [{"id": "m", "pricing": {"prompt": "abc", "completion": "0.000000100"}}]
    assert select_models_module._blended_price(catalogue, "m") == 0.50


def test_confirm_accepts_only_yes_answers(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    assert select_models_module._confirm("Pin? ") is True
    monkeypatch.setattr("builtins.input", lambda prompt: "no")
    assert select_models_module._confirm("Pin? ") is False


def test_pin_time_validation_rejects_unknown_models():
    with pytest.raises(LimesError, match="absent from current catalogue"):
        select_models_module.validate_pins({"extraction": "typo/model"}, CATALOGUE)


def test_provisional_default_does_not_prompt(monkeypatch, tmp_path):
    monkeypatch.setattr(select_models_module, "ENV_FILE", tmp_path / "models.env")

    def unexpected_prompt(*args):
        raise AssertionError("routine model selection must not prompt")

    monkeypatch.setattr(select_models_module, "_confirm", unexpected_prompt)
    select_models_module._provisional(_ctx(_settings()))
    assert (tmp_path / "models.env").exists()


def test_current_catalogue_supported_parameter_lists_are_accepted():
    catalogue = [
        {
            "id": "test/current",
            "supported_parameters": ["structured_outputs"],
            "pricing": {"prompt": "0", "completion": "0"},
        }
    ]
    assert filter_candidates(catalogue, "extraction")[0]["id"] == "test/current"


@pytest.mark.parametrize("pins", [{}, {"unknown": "test/model"}])
def test_invalid_pin_roles_leave_existing_file_unchanged(tmp_path, monkeypatch, pins):
    path = tmp_path / "models.env"
    original = "LIMES_EXTRACTION_MODEL=test/original\n"
    path.write_text(original)
    monkeypatch.setattr(select_models_module, "ENV_FILE", path)
    with pytest.raises(LimesError, match="no pins or unknown roles"):
        _write_pins(pins, "provisional")
    assert path.read_text() == original


def test_invalid_pin_stage_leaves_existing_file_unchanged(tmp_path, monkeypatch):
    path = tmp_path / "models.env"
    original = "LIMES_EXTRACTION_MODEL=test/original\n"
    path.write_text(original)
    monkeypatch.setattr(select_models_module, "ENV_FILE", path)
    with pytest.raises(LimesError, match="unknown model pin stage"):
        _write_pins({"extraction": "test/new"}, "typo")
    assert path.read_text() == original


def test_partial_measured_update_leaves_existing_file_unchanged(tmp_path, monkeypatch):
    path = tmp_path / "models.env"
    original = "LIMES_EXTRACTION_MODEL=test/original\n"
    path.write_text(original)
    monkeypatch.setattr(select_models_module, "ENV_FILE", path)
    with pytest.raises(LimesError, match="evaluation of all four roles"):
        _write_pins({"extraction": "test/new"}, "measured")
    assert path.read_text() == original
