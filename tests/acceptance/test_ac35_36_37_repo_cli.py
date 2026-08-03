# tests/acceptance/test_ac35_36_37_repo_cli.py | v1.0.0 | introduced by WP-39
"""AC-35, AC-36, AC-37.

AC-35: the repository contains the personal-artifact disclaimer required
by Design Document §7.5.
AC-36: `--provisional` writes a complete pin set without reading the gold
set, requiring operator confirmation.
AC-37: `--measured` refuses without a gold set, and on re-pinning reports
affected counts and cost without re-extracting.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import respx
from httpx import Response

from limes.cli import select_models
from limes.cli.select_models import _measured, _provisional, _report_affected
from limes.errors import LimesError
from tests.acceptance.conftest import CATALOGUE_URL, FakeNer
from tests.fixtures.graph_data import wipe_graph
from tests.integration.conftest import Neo4jInstance

REPO_ROOT = Path(__file__).resolve().parents[2]

# A catalogue whose entries satisfy every role's §8.7.2 criteria (cost
# ceiling and declared structured output), so the complete pin set is
# reachable: extraction ≤ $0.50/M, adjudication ≤ $0.30/M, embedding
# ≤ $0.20/M, nl2cypher ≤ $1.00/M blended, structured output where the
# role requires it.
SELECT_CATALOGUE = {
    "data": [
        {
            "id": "test/extractor",
            "pricing": {"prompt": "0.000000100", "completion": "0.000000100", "request": "0"},
            "supported_parameters": {"structured_outputs": True},
        },
        {
            "id": "test/adjudicator",
            "pricing": {"prompt": "0.000000100", "completion": "0.000000100", "request": "0"},
            "supported_parameters": {"structured_outputs": True},
        },
        {
            "id": "test/embed",
            "pricing": {"prompt": "0.000000100", "completion": "0", "request": "0"},
            "supported_parameters": {"structured_outputs": False},
        },
        {
            "id": "test/nl2cypher",
            "pricing": {"prompt": "0.000000100", "completion": "0.000000100", "request": "0"},
            "supported_parameters": {"structured_outputs": False},
        },
    ]
}


def test_ac35_repository_contains_the_personal_artifact_disclaimer():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "personal research artifact" in readme
    assert "personal" in readme.lower()


def _provisional_env(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """The provisional-stage environment: a context whose gold set path
    points at a file that does not exist (a gold-set read would fail
    loudly), and fake spaCy models for the inference context."""
    from limes import composition as composition_module

    env = dict(
        neo4j_uri=neo4j_instance.uri,
        neo4j_user=neo4j_instance.user,
        neo4j_password=neo4j_instance.password,
        neo4j_database=neo4j_instance.database,
        ontology_path=str(REPO_ROOT / "ontology" / "ontology.yaml"),
        feeds_config_path=str(REPO_ROOT / "ontology" / "feeds.yaml"),
        gold_set_path=str(tmp_path / "does-not-exist.jsonl"),  # never read
        baseline_path=str(tmp_path / "baseline.json"),
        archive_path=str(tmp_path / "archive"),
        openrouter_api_key="sk-test",
        openrouter_base_url="https://openrouter.test/api/v1",
        http_timeout_seconds=10,
    )
    for key, value in env.items():
        monkeypatch.setenv(f"LIMES_{key.upper()}", str(value))

    fake_de, fake_en = FakeNer(True), FakeNer(True)
    monkeypatch.setattr(
        composition_module.spacy,
        "load",
        lambda name: fake_de if name.endswith("de") else fake_en,
    )


def _build_ctx(tmp_path: Path):
    from limes.composition import build_run_context
    from limes.config import load_settings

    return build_run_context(load_settings(), needs_inference=True)


def test_ac36_provisional_writes_complete_pin_set_without_reading_gold_set(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """The gold set path points at a nonexistent file — a gold-set read
    would fail loudly — and every role is pinned after confirmation."""
    _provisional_env(neo4j_instance, tmp_path, monkeypatch)
    wipe_graph(neo4j_instance)

    ctx = _build_ctx(tmp_path)
    written: list[tuple[str, str, str]] = []

    def fake_write_pins(pins: dict[str, str], stage: str) -> None:
        for key, value in pins.items():
            written.append((key, value, stage))

    monkeypatch.setattr(select_models, "_write_pins", fake_write_pins)
    monkeypatch.setattr(select_models, "_confirm", lambda prompt: True)
    try:
        with respx.mock:
            respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=SELECT_CATALOGUE))
            _provisional(ctx)

        assert written, "the provisional stage must pin at least one role"
        roles = {role for role, _value, _stage in written}
        assert roles == {"extraction", "adjudication", "embedding", "nl2cypher"}, (
            "the complete pin set must cover all four roles"
        )
        for _role, _value, stage in written:
            assert stage == "provisional"
    finally:
        ctx.driver.close()


def test_ac36_provisional_requires_operator_confirmation(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Declined confirmation skips the pin — the operator's confirmation is
    load-bearing, not decorative."""
    _provisional_env(neo4j_instance, tmp_path, monkeypatch)
    wipe_graph(neo4j_instance)

    ctx = _build_ctx(tmp_path)
    written: list[tuple[str, str, str]] = []

    monkeypatch.setattr(
        select_models,
        "_write_pins",
        lambda pins, stage: written.extend((role, value, stage) for role, value in pins.items()),
    )
    monkeypatch.setattr(select_models, "_confirm", lambda prompt: False)
    try:
        with respx.mock:
            respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=SELECT_CATALOGUE))
            with pytest.raises(LimesError, match="no role pinned"):
                _provisional(ctx)
        assert written == []
    finally:
        ctx.driver.close()


def test_ac37_measured_refuses_without_gold_set(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """`--measured` without a gold set fails before any evaluation runs."""
    _provisional_env(neo4j_instance, tmp_path, monkeypatch)
    wipe_graph(neo4j_instance)

    from limes.errors import ConfigurationError

    ctx = _build_ctx(tmp_path)
    try:
        with pytest.raises(ConfigurationError, match="gold set missing"):
            _measured(ctx)
    finally:
        ctx.driver.close()


def test_ac37_repinning_reports_affected_counts_and_cost_without_reextracting(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """The impact report reads the graph (cached documents, extraction
    sources, entity nodes) and the catalogue for the cost estimate — never
    an extraction call."""
    from limes.extraction.base import ExtractionResult
    from limes.extraction.cache import put
    from limes.graph.driver import GraphDriver

    wipe_graph(neo4j_instance)
    driver = GraphDriver(
        neo4j_instance.uri,
        neo4j_instance.user,
        neo4j_instance.password,
        neo4j_instance.database,
    )
    try:
        put(
            driver,
            "c" * 64,
            "1.0.0",
            "1.0.0",
            "test/extractor",
            ExtractionResult(
                assertions=[], input_tokens=1, output_tokens=1, raw_response="", parse_errors=[]
            ),
        )

        ctx = SimpleNamespace(
            driver=driver,
            settings=SimpleNamespace(
                extraction_model="test/extractor",
                embedding_model="test/embed",
                usd_eur_rate=0.92,
            ),
            client=SimpleNamespace(catalogue=lambda: SELECT_CATALOGUE["data"]),
        )
        calls: list[str] = []
        monkeypatch.setattr(
            select_models, "typer", SimpleNamespace(echo=lambda message: calls.append(str(message)))
        )
        _report_affected(ctx, {"extraction": "test/winner", "embedding": "test/embed"})

        text = "\n".join(calls)
        assert "1 cached documents affected" in text
        assert "no re-extraction performed" in text
        # The embedding model is unchanged, so no re-embedding is reported.
        assert "must be re-embedded" not in text
    finally:
        driver.close()
