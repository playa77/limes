# tests/integration/test_composition_root.py | v1.0.0 | introduced by WP-26
"""Composition root integration tests per Doc 2 §8.15 (AC-40, AC-41,
AC-44), against the real Neo4j container.

AC-40's grep is a test here: no module below the composition root
constructs a driver, registry, archive, governor, client, extractor, or
gate — the registry's own factory in `sources/registry.py` is the single
exception, because `build_default_registry` *is* the population seam.
AC-41's resource contract is behavior: a structured-only build must not
load a spaCy model (monkeypatched here — the models are not installed in
the test venv, which is itself why the contract matters).
"""

import dataclasses
import re
from pathlib import Path

import pytest

from limes.composition import (
    NlqContext,
    build_nlq_context,
    build_run_context,
    embedder_for,
)
from limes.config import Settings
from limes.pipeline.gate import GateContext
from limes.resolution.resolve import RunContext
from tests.integration.conftest import Neo4jInstance

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"

CONSTRUCTOR_PATTERNS = [
    (r"GraphDriver\(", "driver"),
    (r"OpenRouterClient\(", "client"),
    (r"ArchiveStore\(", "archive"),
    (r"CostRecorder\(", "cost recorder"),
    (r"OpenRouterExtractor\(", "extractor"),
    (r"GateContext\(", "gate"),
    (r"RunContext\(", "run context"),
]


def _settings(neo4j_instance: Neo4jInstance, tmp_path: Path, **overrides) -> Settings:
    base = dict(
        neo4j_uri=neo4j_instance.uri,
        neo4j_user=neo4j_instance.user,
        neo4j_password=neo4j_instance.password,
        neo4j_database=neo4j_instance.database,
        ontology_path=ONTOLOGY_PATH,
        feeds_config_path=REPO_ROOT / "ontology" / "feeds.yaml",
        gold_set_path=tmp_path / "gold_set.jsonl",
        baseline_path=tmp_path / "baseline.json",
        archive_path=tmp_path / "archive",
        openrouter_api_key="sk-test",
        openrouter_base_url="https://openrouter.test/api/v1",
        embedding_model="test/embed",
        adjudication_model="test/adjudicator",
        extraction_model="test/extractor",
        gate_spacy_model_de="de_core_news_md",
        gate_spacy_model_en="en_core_web_md",
        http_timeout_seconds=10,
    )
    base.update(overrides)
    return Settings(**base)


# src/limes/api/main.py — the API startup handler is the second sanctioned
# driver construction site: Doc 2 §15.2's FastAPI row ("constructs settings,
# ontology, driver") and the roadmap's WP-32 task 1 both name it, and §8.15
# exempts "the API startup handler" from the construction ban explicitly.
# The exemption is for the driver pattern only; everything else must still
# route through composition.py.
API_MAIN_DRIVER_EXEMPTION = "src/limes/api/main.py"


def test_ac40_composition_is_the_only_constructor(neo4j_instance: Neo4jInstance):
    # The roadmap's grep verification as a test: every infra constructor
    # appears in exactly one place — composition.py (or the registry's own
    # factory, or the API startup handler's driver per §15.2). A new module
    # constructing infrastructure fails here before it can ship (AC-40).
    offenders: list[str] = []
    for pattern, _name in CONSTRUCTOR_PATTERNS:
        for path in sorted((REPO_ROOT / "src" / "limes").rglob("*.py")):
            text = path.read_text()
            if "composition.py" in str(path):
                continue
            relative = path.relative_to(REPO_ROOT)
            if pattern == r"GraphDriver\(" and str(relative) == API_MAIN_DRIVER_EXEMPTION:
                # §15.2's FastAPI row and the roadmap WP-32 task 1 sanction
                # the API startup handler's driver construction.
                continue
            for line_number, line in enumerate(text.splitlines(), start=1):
                if re.search(pattern, line):
                    offenders.append(f"{relative}:{line_number}: {line.strip()}")
    assert not offenders, "infrastructure constructed outside the composition root:\n" + "\n".join(
        offenders
    )


def test_ac41_structured_build_loads_no_models_and_constructs_no_extractor(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    # AC-41: the resource contract. A structured-only run must not load a
    # spaCy model — here proven by making spacy.load fail loudly — and must
    # leave every inference slot None.
    def _explode(*_args, **_kwargs):
        raise AssertionError("spacy.load called on a structured-only build")

    monkeypatch.setattr("limes.composition.spacy.load", _explode)
    ctx = build_run_context(_settings(neo4j_instance, tmp_path), needs_inference=False)
    try:
        assert isinstance(ctx, RunContext)
        assert ctx.governor is None
        assert ctx.client is None
        assert ctx.extractor is None
        assert ctx.gate is None
    finally:
        ctx.driver.close()


def test_inference_build_loads_models_and_constructs_inference_slots(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    loaded: list[str] = []

    def _fake_load(name: str):
        loaded.append(name)
        return object()

    monkeypatch.setattr("limes.composition.spacy.load", _fake_load)
    ctx = build_run_context(
        _settings(
            neo4j_instance,
            tmp_path,
            gate_spacy_model_de="de/test",
            gate_spacy_model_en="en/test",
        ),
        needs_inference=True,
    )
    try:
        assert loaded == ["de/test", "en/test"]
        assert ctx.governor is not None
        assert ctx.client is not None
        assert ctx.extractor is not None
        assert ctx.extractor.model_id == "test/extractor"
        assert isinstance(ctx.gate, GateContext)
        assert ctx.gate.nlp_de is not None
        assert ctx.gate.nlp_en is not None
    finally:
        ctx.driver.close()


def test_provision_called_on_every_build(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import limes.composition as composition

    calls = 0
    real_provision = composition.provision

    def _counting_provision(driver, ontology, embedding_dimensions):
        nonlocal calls
        calls += 1
        return real_provision(driver, ontology, embedding_dimensions)

    monkeypatch.setattr(composition, "provision", _counting_provision)
    ctx = build_run_context(_settings(neo4j_instance, tmp_path), needs_inference=False)
    try:
        assert calls == 1
    finally:
        ctx.driver.close()
    ctx = build_run_context(_settings(neo4j_instance, tmp_path), needs_inference=False)
    try:
        assert calls == 2
    finally:
        ctx.driver.close()


def test_contexts_are_frozen(neo4j_instance: Neo4jInstance, tmp_path: Path):
    ctx = build_run_context(_settings(neo4j_instance, tmp_path), needs_inference=False)
    try:
        with pytest.raises(dataclasses.FrozenInstanceError):
            ctx.settings = _settings(neo4j_instance, tmp_path)
    finally:
        ctx.driver.close()

    from limes.graph.driver import GraphDriver

    driver = GraphDriver(
        neo4j_instance.uri,
        neo4j_instance.user,
        neo4j_instance.password,
        neo4j_instance.database,
    )
    try:
        nlq = build_nlq_context(_settings(neo4j_instance, tmp_path), ctx.ontology, driver)
        assert isinstance(nlq, NlqContext)
        with pytest.raises(dataclasses.FrozenInstanceError):
            nlq.driver = driver
    finally:
        driver.close()


def test_envelope_governor_created_for_budget(neo4j_instance: Neo4jInstance, tmp_path: Path):
    from decimal import Decimal

    ctx = build_run_context(
        _settings(neo4j_instance, tmp_path),
        needs_inference=True,
        budget_eur=Decimal("3.00"),
    )
    try:
        assert ctx.governor is not None
        assert ctx.governor.total_spend == Decimal("0")
    finally:
        ctx.driver.close()


def test_embedder_for_none_client_returns_none(neo4j_instance: Neo4jInstance, tmp_path: Path):
    settings = _settings(neo4j_instance, tmp_path)
    assert embedder_for(settings, None) is None


def test_provision_runs_the_downgrade_guard(neo4j_instance: Neo4jInstance, tmp_path: Path):
    # The downgrade guard is part of provision() (WP-04); building a context
    # against an empty database must succeed, proving the guard passes on a
    # fresh graph (Doc 2 §4.3). The guard's rejection side is covered by the
    # WP-04 schema tests.
    ctx = build_run_context(_settings(neo4j_instance, tmp_path), needs_inference=False)
    try:
        rows = ctx.driver.read(
            "MATCH (n:Source) RETURN count(n) AS c",
            {},
            timeout_s=30,
        )
        assert rows[0]["c"] == 0
    finally:
        ctx.driver.close()


def test_import_from_limes_is_clean():
    # AC-44: the context types resolve from the modules §8.15 names —
    # importing composition must not fail on the circularity between
    # resolve.py (RunContext) and pipeline/gate.py (GateContext).
    import limes.composition  # noqa: F401
    from limes.pipeline.gate import GateContext as G
    from limes.resolution.resolve import RunContext as R

    assert R.__name__ == "RunContext"
    assert G.__name__ == "GateContext"
