# tests/acceptance/test_ac38_40_41_registry_composition.py | v1.0.0 | introduced by WP-39
"""AC-38, AC-40, AC-41.

AC-38: `build_default_registry()` returns every delivered adapter; an
unknown source fails naming both the unknown and the registered ones; no
production module constructs an empty `SourceRegistry`.
AC-40: `composition.py` is the only constructor of driver, registry,
archive, governor, client, extractor, and gate — grep-verified.
AC-41: a structured-only run loads no spaCy model and constructs no
extractor.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from limes.errors import SourceFetchError
from limes.sources.registry import build_default_registry
from tests.acceptance.test_ac04_adapters import EXPECTED_SOURCE_IDS
from tests.fixtures.graph_data import wipe_graph
from tests.integration.conftest import Neo4jInstance

REPO_ROOT = Path(__file__).resolve().parents[2]

CONSTRUCTOR_PATTERNS = [
    (r"GraphDriver\(", "driver"),
    (r"OpenRouterClient\(", "client"),
    (r"ArchiveStore\(", "archive"),
    (r"CostRecorder\(", "cost recorder"),
    (r"OpenRouterExtractor\(", "extractor"),
    (r"GateContext\(", "gate"),
]

# §15.2's FastAPI row and the roadmap WP-32 task 1 sanction the API
# startup handler's driver construction; the registry's own factory is the
# population seam.
API_MAIN_DRIVER_EXEMPTION = "src/limes/api/main.py"


def test_ac38_registry_returns_every_delivered_adapter():
    registry = build_default_registry()
    assert registry.source_ids() == EXPECTED_SOURCE_IDS


def test_ac38_unknown_source_fails_naming_both():
    registry = build_default_registry()
    with pytest.raises(SourceFetchError) as excinfo:
        registry.get("no-such-source")
    message = str(excinfo.value)
    assert "no-such-source" in message
    for source_id in EXPECTED_SOURCE_IDS[:3]:
        assert source_id in message, message


def test_ac38_no_production_module_constructs_an_empty_registry():
    offenders: list[str] = []
    for path in sorted((REPO_ROOT / "src" / "limes").rglob("*.py")):
        for line_number, line in enumerate(path.read_text().splitlines(), start=1):
            if re.search(r"SourceRegistry\(", line):
                relative = path.relative_to(REPO_ROOT)
                if str(relative) != "src/limes/sources/registry.py":
                    offenders.append(f"{relative}:{line_number}: {line.strip()}")
    assert not offenders, "SourceRegistry constructed outside its factory:\n" + "\n".join(offenders)


def test_ac40_composition_is_the_only_constructor():
    """Every infrastructure constructor appears only in composition.py (or
    the sanctioned API startup driver site, or the registry's own factory).
    A new module constructing infrastructure fails here before it ships."""
    offenders: list[str] = []
    for pattern, _name in CONSTRUCTOR_PATTERNS:
        for path in sorted((REPO_ROOT / "src" / "limes").rglob("*.py")):
            if "composition.py" in str(path):
                continue
            relative = path.relative_to(REPO_ROOT)
            if pattern == r"GraphDriver\(" and str(relative) == API_MAIN_DRIVER_EXEMPTION:
                continue
            for line_number, line in enumerate(path.read_text().splitlines(), start=1):
                if re.search(pattern, line):
                    offenders.append(f"{relative}:{line_number}: {line.strip()}")
    assert not offenders, "infrastructure constructed outside the composition root:\n" + "\n".join(
        offenders
    )


def test_ac41_structured_only_build_loads_no_spacy_and_constructs_no_extractor(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """The resource contract: a structured-only context never calls
    spacy.load (proven by making it explode) and leaves every inference
    slot None."""
    from limes import composition as composition_module
    from limes.resolution.resolve import RunContext

    def _explode(*_args, **_kwargs):
        raise AssertionError("spacy.load called on a structured-only build")

    monkeypatch.setattr(composition_module.spacy, "load", _explode)
    wipe_graph(neo4j_instance)

    from tests.acceptance.conftest import acceptance_settings

    ctx = composition_module.build_run_context(
        acceptance_settings(neo4j_instance, tmp_path), needs_inference=False
    )
    try:
        assert isinstance(ctx, RunContext)
        assert ctx.governor is None
        assert ctx.client is None
        assert ctx.extractor is None
        assert ctx.gate is None
    finally:
        ctx.driver.close()
