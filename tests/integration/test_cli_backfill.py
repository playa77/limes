# tests/integration/test_cli_backfill.py | v1.0.0 | introduced by WP-28
"""CLI backfill tests per Doc 2 §8.14 and §15.3 Trace 2.

The `--budget` refusal is exercised across a real process boundary (a
typer usage error at parse time, before any context is built — no network
and no graph involved). The end-to-end backfill runs the full CLI stack
with the feeds adapter: the network boundary is stubbed (adapter fetch,
respx transport for the paid calls, fake spaCy models) — the same seams
Trace 2's own test uses; no live service is hit.
"""

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
import respx
from httpx import Response
from typer.testing import CliRunner

from limes.cli.main import app
from tests.fixtures.embeddings import TEST_EMBEDDING_DIMENSIONS, fake_embedder
from tests.integration.conftest import Neo4jInstance

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"

BASE_URL = "https://openrouter.test/api/v1"
CATALOGUE_URL = f"{BASE_URL}/models"
COMPLETIONS_URL = f"{BASE_URL}/chat/completions"
EMBEDDINGS_URL = f"{BASE_URL}/embeddings"

EXTRACTION_MODEL = "test/extractor"
EMBED_MODEL = "test/embed"
ADJUDICATE_MODEL = "test/adjudicator"
FEED_URL = "https://example.com/rss"
FEED_TRUST = 0.70

SUBJECT_LEI = "529900T8BM49AURSDO55"
OBJECT_LEI = "549300BEQ1B5L7Z2WE72"

TITLE = "Holding announcement"
BODY = f"{SUBJECT_LEI} holds {OBJECT_LEI}."
FETCHED_AT = datetime(2026, 8, 1, 9, 30, tzinfo=UTC)

USAGE = {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70}

CATALOGUE = {
    "data": [
        {
            "id": EXTRACTION_MODEL,
            "pricing": {"prompt": "0.000000500", "completion": "0.000001500", "request": "0"},
        },
        {
            "id": EMBED_MODEL,
            "pricing": {"prompt": "0.000000100", "completion": "0", "request": "0"},
        },
        {
            "id": ADJUDICATE_MODEL,
            "pricing": {"prompt": "0.000000500", "completion": "0.000001500", "request": "0"},
        },
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
    """The injected spaCy model: finds the LEIs anywhere in the text."""

    def __call__(self, text: str) -> SimpleNamespace:
        spans = []
        for surface in (SUBJECT_LEI, OBJECT_LEI):
            start = text.find(surface)
            if start >= 0:
                spans.append(_FakeEnt(surface, "ORG", start, start + len(surface)))
        return SimpleNamespace(ents=spans)


def _env(neo4j_instance: Neo4jInstance, tmp_path: Path) -> dict[str, str]:
    return {
        "LIMES_NEO4J_URI": neo4j_instance.uri,
        "LIMES_NEO4J_USER": neo4j_instance.user,
        "LIMES_NEO4J_PASSWORD": neo4j_instance.password,
        "LIMES_NEO4J_DATABASE": neo4j_instance.database,
        "LIMES_ONTOLOGY_PATH": str(ONTOLOGY_PATH),
        "LIMES_FEEDS_CONFIG_PATH": str(tmp_path / "feeds.yaml"),
        "LIMES_GOLD_SET_PATH": str(tmp_path / "gold_set.jsonl"),
        "LIMES_BASELINE_PATH": str(tmp_path / "baseline.json"),
        "LIMES_ARCHIVE_PATH": str(tmp_path / "archive"),
        "LIMES_OPENROUTER_API_KEY": "sk-test",
        "LIMES_OPENROUTER_BASE_URL": BASE_URL,
        "LIMES_EXTRACTION_MODEL": EXTRACTION_MODEL,
        "LIMES_EMBEDDING_MODEL": EMBED_MODEL,
        "LIMES_ADJUDICATION_MODEL": ADJUDICATE_MODEL,
        "LIMES_EMBEDDING_DIMENSIONS": str(TEST_EMBEDDING_DIMENSIONS),
        "LIMES_HTTP_TIMEOUT_SECONDS": "10",
        "LIMES_LOG_LEVEL": "WARNING",
    }


def test_backfill_refuses_without_budget():
    # G2 (subprocess) — the refusal is a typer usage error at parse time:
    # non-zero exit, the missing option named, no context built, no network.
    result = subprocess.run(
        [sys.executable, "-m", "limes.cli.main", "backfill", "--source", "feeds", "--days", "90"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode != 0
    assert "--budget" in result.stderr


@pytest.fixture
def cli_env(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    env = _env(neo4j_instance, tmp_path)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    feeds_config = tmp_path / "feeds.yaml"
    feeds_config.write_text(
        f'version: "1.0.0"\nfeeds:\n'
        f"  - url: {FEED_URL}\n"
        f"    name: Test feed\n"
        f"    language: en\n"
        f"    trust_rank: {FEED_TRUST}\n"
    )

    from limes.sources import feeds as feeds_module

    real_load = feeds_module._load_feed_config
    monkeypatch.setattr(
        feeds_module,
        "_load_feed_config",
        lambda _path: real_load(feeds_config),
    )
    fake_de = _FakeNer()
    fake_en = _FakeNer()
    monkeypatch.setattr(
        "limes.composition.spacy.load",
        lambda name: fake_de if name.endswith("de") else fake_en,
    )

    from limes.sources.feeds import FeedsAdapter
    from limes.types import RawRecord

    envelope = json.dumps(
        {
            "feed": {"url": FEED_URL, "name": "Test feed", "language": "en"},
            "entry_id": "entry-1",
            "title": TITLE,
            "link": "https://example.com/entries/1",
            "summary": "",
            "content": f"<p>{BODY}</p>",
            "published": "2026-07-31T09:30:00+00:00",
        },
        sort_keys=True,
    ).encode("utf-8")
    records = [
        RawRecord(
            payload=envelope,
            content_type="application/json",
            source_url=FEED_URL,
            fetched_at=FETCHED_AT,
        )
    ]
    monkeypatch.setattr(FeedsAdapter, "fetch", lambda self, since, until: iter(records))
    return env


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


def _mock_transport() -> None:
    gate_text = f"{TITLE}\n\n{BODY}"
    extraction_items = [
        {
            "passage_index": 0,
            "subject": {"surface": SUBJECT_LEI, "type": "Corporation"},
            "relation": "SUBSIDIARY_OF",
            "object": {"surface": OBJECT_LEI, "type": "Corporation"},
            "valid_from": "2026-07-01",
            "confidence": 0.95,
            "evidence_start": 0,
            "evidence_end": len(gate_text),
        }
    ]
    respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=CATALOGUE))
    respx.post(COMPLETIONS_URL).mock(
        return_value=Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(extraction_items)}}],
                "usage": USAGE,
            },
        )
    )

    def _embeddings(request) -> Response:
        payload = json.loads(request.content.decode("utf-8"))
        texts = [str(item) for item in (payload or {}).get("input", [])]
        return Response(
            200,
            json={
                "data": [{"embedding": vector} for vector in fake_embedder()(texts)],
                "usage": {"prompt_tokens": 40, "total_tokens": 40},
            },
        )

    respx.post(EMBEDDINGS_URL).mock(side_effect=_embeddings)


def test_cli_backfill_feeds_end_to_end(graph, cli_env):
    # Trace 2 through the CLI: backfill with an explicit envelope runs the
    # document path and reports honest counts; the envelope (AC-15) is the
    # governor's, so the run's cost lands in the record.
    with respx.mock:
        _mock_transport()
        result = runner.invoke(
            app,
            ["backfill", "--source", "feeds", "--days", "90", "--budget", "3.00"],
        )
    assert result.exit_code == 0, result.output

    rows = graph.read("MATCH ()-[r:SUBSIDIARY_OF]->() RETURN count(r) AS c", {}, 30)
    assert rows[0]["c"] == 1

    rows = graph.read(
        "MATCH (r:IngestionRun) RETURN r.mode AS mode, r.window_from AS since, "
        "r.cost_eur AS cost, r.assertions_written AS written",
        {},
        30,
    )
    assert rows[0]["mode"] == "backfill"
    assert rows[0]["written"] == 1
    assert rows[0]["cost"] > 0
    # --days 90 became the explicit window: now − 90 days (D-44).
    expected_since = datetime.now(UTC) - timedelta(days=90)
    actual_since = rows[0]["since"].to_native()
    assert abs((actual_since - expected_since).total_seconds()) < 300

    rows = graph.read(
        "MATCH (s:Source {source_id: 'feeds'}) RETURN s.last_run_id AS run_id",
        {},
        30,
    )
    assert rows[0]["run_id"] is not None

    rows = graph.read("MATCH (l:AdvisoryLock) RETURN count(l) AS c", {}, 30)
    assert rows[0]["c"] == 0
