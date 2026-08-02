# tests/integration/test_cli_evaluate.py | v1.0.0 | introduced by WP-30
"""End-to-end evaluate tests per Doc 2 §15.3 Trace 4 and AC-31, against
the real Neo4j container.

The model boundary is stubbed with respx (canned extraction responses per
gold item); the rest is the production path: the CLI, the composition
root with injected fake spaCy models, the real extractor and its parsing,
the baseline gate, the `:GoldSetItem` write, and the changelog record.
"""

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import respx
from httpx import Response
from typer.testing import CliRunner

from limes.cli.main import app
from tests.integration.conftest import Neo4jInstance

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"
GOLD_SOURCE = REPO_ROOT / "gold_set" / "gold_set.jsonl"
GOLD_SCHEMA_SOURCE = REPO_ROOT / "gold_set" / "gold_set.schema.json"

BASE_URL = "https://openrouter.test/api/v1"
CATALOGUE_URL = f"{BASE_URL}/models"
COMPLETIONS_URL = f"{BASE_URL}/chat/completions"

EXTRACTION_MODEL = "test/extractor"

USAGE = {"prompt_tokens": 40, "completion_tokens": 15, "total_tokens": 55}

CATALOGUE = {
    "data": [
        {
            "id": EXTRACTION_MODEL,
            "pricing": {"prompt": "0.000000500", "completion": "0.000001500", "request": "0"},
        }
    ]
}

runner = CliRunner()


@pytest.fixture(autouse=True)
def _restore_structlog_defaults():
    """The CLI reconfigures the process-wide structlog (level and renderer)
    from the test env; the adapter unit tests assert on structlog's default
    KeyValueRenderer output via capfd. Restore the defaults after every
    in-process CLI invocation so the suite stays order-independent."""
    import structlog

    yield
    structlog.reset_defaults()


class _FakeEnt:
    def __init__(self, text: str, label: str, start: int, end: int) -> None:
        self.text = text
        self.label_ = label
        self.start_char = start
        self.end_char = end


class _FakeNer:
    """The injected spaCy model: no spans — the gate is not under test."""

    def __call__(self, text: str) -> SimpleNamespace:
        return SimpleNamespace(ents=[])


PASSAGES = {
    "amends": (
        "Die Europäische Kommission hat am 3. April 2026 die "
        "Durchführungsverordnung (EU) 2026/999 erlassen, die die "
        "Verordnung (EU) 2015/2447 ändert."
    ),
    "subsidiary": (
        "Volkswagen AG announced that its subsidiary Audi AG will supply "
        "battery cells to BMW AG under a new long-term contract."
    ),
}

PERFECT_ITEMS = {
    "amends": [
        {
            "passage_index": 0,
            "subject": {"surface": "Durchführungsverordnung (EU) 2026/999", "type": "LegalAct"},
            "relation": "AMENDS",
            "object": {"surface": "Verordnung (EU) 2015/2447", "type": "LegalAct"},
            "valid_from": "2026-04-03",
            "confidence": 0.95,
            "evidence_start": 0,
            "evidence_end": len(PASSAGES["amends"]),
        }
    ],
    "subsidiary": [
        {
            "passage_index": 0,
            "subject": {"surface": "Audi AG", "type": "Corporation"},
            "relation": "SUBSIDIARY_OF",
            "object": {"surface": "Volkswagen AG", "type": "Corporation"},
            "valid_from": "2026-07-01",
            "confidence": 0.95,
            "evidence_start": 0,
            "evidence_end": len(PASSAGES["subsidiary"]),
        },
        {
            "passage_index": 0,
            "subject": {"surface": "Audi AG", "type": "Corporation"},
            "relation": "SUPPLIES",
            "object": {"surface": "BMW AG", "type": "Corporation"},
            "valid_from": "2026-07-01",
            "confidence": 0.95,
            "evidence_start": 0,
            "evidence_end": len(PASSAGES["subsidiary"]),
        },
    ],
}


def _items_for(content: str, degraded: bool) -> list[dict[str, Any]]:
    # The extraction message carries the passage inside the delimiters; the
    # marker selects which gold item this call serves. The evidence span
    # stays inside the passage — the AC-13 check rejects spans outside it.
    is_subsidiary = "Volkswagen AG announced" in content
    if is_subsidiary:
        return [] if degraded else PERFECT_ITEMS["subsidiary"]
    return PERFECT_ITEMS["amends"]


def _mock_transport(degraded: bool = False) -> None:
    respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=CATALOGUE))

    def _completions(request) -> Response:
        payload = json.loads(request.content.decode("utf-8"))
        content = str(payload["messages"][0]["content"])
        items = _items_for(content, degraded)
        return Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(items)}}],
                "usage": USAGE,
            },
        )

    respx.post(COMPLETIONS_URL).mock(side_effect=_completions)


@pytest.fixture
def cli_env(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    # The gold set and its schema are copied into the tmp dir so the run's
    # changelog record lands there, never in the committed artifact.
    shutil.copy(GOLD_SOURCE, tmp_path / "gold_set.jsonl")
    shutil.copy(GOLD_SCHEMA_SOURCE, tmp_path / "gold_set.schema.json")
    env = {
        "LIMES_NEO4J_URI": neo4j_instance.uri,
        "LIMES_NEO4J_USER": neo4j_instance.user,
        "LIMES_NEO4J_PASSWORD": neo4j_instance.password,
        "LIMES_NEO4J_DATABASE": neo4j_instance.database,
        "LIMES_ONTOLOGY_PATH": str(ONTOLOGY_PATH),
        "LIMES_FEEDS_CONFIG_PATH": str(REPO_ROOT / "ontology" / "feeds.yaml"),
        "LIMES_GOLD_SET_PATH": str(tmp_path / "gold_set.jsonl"),
        "LIMES_BASELINE_PATH": str(tmp_path / "baseline.json"),
        "LIMES_ARCHIVE_PATH": str(tmp_path / "archive"),
        "LIMES_OPENROUTER_API_KEY": "sk-test",
        "LIMES_OPENROUTER_BASE_URL": BASE_URL,
        "LIMES_EXTRACTION_MODEL": EXTRACTION_MODEL,
        "LIMES_HTTP_TIMEOUT_SECONDS": "10",
        "LIMES_LOG_LEVEL": "WARNING",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    fake_de = _FakeNer()
    fake_en = _FakeNer()
    monkeypatch.setattr(
        "limes.composition.spacy.load",
        lambda name: fake_de if name.endswith("de") else fake_en,
    )
    return tmp_path


@pytest.fixture
def graph(neo4j_instance: Neo4jInstance):
    from limes.graph.driver import GraphDriver

    driver = GraphDriver(
        neo4j_instance.uri,
        neo4j_instance.user,
        neo4j_instance.password,
        neo4j_instance.database,
    )
    driver.write_batch([("MATCH (n) DETACH DELETE n", {})])
    yield driver
    driver.close()


def test_ac31_evaluate_records_baseline_and_writes_gold_set_nodes(graph, cli_env):
    # Trace 4: perfect extraction over the placeholder set — three
    # relations at F1 1.0 — the baseline is written, the changelog
    # appended, and the corpus materialized as :GoldSetItem nodes.
    with respx.mock:
        _mock_transport()
        result = runner.invoke(app, ["evaluate"])
    assert result.exit_code == 0, result.output
    assert "baseline recorded" in result.output

    baseline = json.loads((cli_env / "baseline.json").read_text(encoding="utf-8"))
    assert baseline["gold_set_version"] == "1.0.0"
    for relation in ("AMENDS", "SUBSIDIARY_OF", "SUPPLIES"):
        assert baseline["per_relation"][relation]["f1"] == 1.0

    rows = graph.read("MATCH (g:GoldSetItem) RETURN count(g) AS c", {}, 30)
    assert rows[0]["c"] == 2
    rows = graph.read(
        "MATCH (g:GoldSetItem {item_id: 'gold-002'}) RETURN g.expected_json AS expected",
        {},
        30,
    )
    assert "SUPPLIES" in rows[0]["expected"]

    changelog = (cli_env / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "evaluation run" in changelog


def test_ac31_regression_beyond_0_05_fails(graph, cli_env):
    # Run 1 records the perfect baseline. Run 2 extracts only the AMENDS
    # fact — SUBSIDIARY_OF and SUPPLIES drop to F1 0.0, a regression of
    # 1.0 (> 0.05) — the gate exits non-zero naming the relations.
    with respx.mock:
        _mock_transport(degraded=False)
        first = runner.invoke(app, ["evaluate"])
        assert first.exit_code == 0, first.output

        _mock_transport(degraded=True)
        second = runner.invoke(app, ["evaluate"])
    assert second.exit_code == 1
    assert "REGRESSION" in second.output
    assert "SUBSIDIARY_OF" in second.output
    assert "SUPPLIES" in second.output

    baseline = json.loads((cli_env / "baseline.json").read_text(encoding="utf-8"))
    assert baseline["per_relation"]["SUBSIDIARY_OF"]["f1"] == 0.0
