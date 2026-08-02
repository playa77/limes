# tests/integration/test_pipeline_run_unstructured.py | v1.0.0 | introduced by WP-27
"""Unstructured pipeline run tests per Doc 2 §8.6.1 and §15.3 Trace 2,
against the real Neo4j container.

Trace 2 runs through the production composition root (real FeedsAdapter,
real gate with injected fake spaCy models, real OpenRouterExtractor and
resolver) with respx-mocked transport — no live service is hit. The
mentions carry LEIs, so resolution is deterministic (AC-16): no
adjudication, no embedding of mentions; the only paid call beyond the
extraction is the loader's label-embedding stamp on the two new entity
nodes. The per-feed trust override (D-20) is exercised: the fixture
envelope's feed URL matches the tmp `feeds.yaml`, so assertions carry the
feed's 0.70 trust, not the adapter default.
"""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import respx
from httpx import Response

from limes.composition import build_run_context
from limes.config import Settings
from limes.errors import BudgetExhausted
from limes.pipeline.run import RunSpec, execute_run
from limes.sources import feeds as feeds_module
from limes.types import RawRecord
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
ENTRY_URL = "https://example.com/entries/1"
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


class _FakeEnt:
    def __init__(self, text: str, label: str, start: int, end: int) -> None:
        self.text = text
        self.label_ = label
        self.start_char = start
        self.end_char = end


class _FakeNer:
    """The injected spaCy model: finds the LEIs anywhere in the text. The
    gate feeds it `title + body`; the spans carry the label the gate's
    non-entity filter must keep."""

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled

    def __call__(self, text: str) -> SimpleNamespace:
        if not self._enabled:
            return SimpleNamespace(ents=[])
        spans = []
        for surface in (SUBJECT_LEI, OBJECT_LEI):
            start = text.find(surface)
            if start >= 0:
                spans.append(_FakeEnt(surface, "ORG", start, start + len(surface)))
        return SimpleNamespace(ents=spans)


def _settings(neo4j_instance: Neo4jInstance, tmp_path: Path, **overrides) -> Settings:
    base = dict(
        neo4j_uri=neo4j_instance.uri,
        neo4j_user=neo4j_instance.user,
        neo4j_password=neo4j_instance.password,
        neo4j_database=neo4j_instance.database,
        ontology_path=ONTOLOGY_PATH,
        feeds_config_path=tmp_path / "feeds.yaml",
        gold_set_path=tmp_path / "gold_set.jsonl",
        baseline_path=tmp_path / "baseline.json",
        archive_path=tmp_path / "archive",
        openrouter_api_key="sk-test",
        openrouter_base_url=BASE_URL,
        extraction_model=EXTRACTION_MODEL,
        embedding_model=EMBED_MODEL,
        adjudication_model=ADJUDICATE_MODEL,
        embedding_dimensions=TEST_EMBEDDING_DIMENSIONS,
        http_timeout_seconds=10,
    )
    base.update(overrides)
    return Settings(**base)


def _feeds_config(tmp_path: Path) -> Path:
    path = tmp_path / "feeds.yaml"
    path.write_text(
        f'version: "1.0.0"\nfeeds:\n'
        f"  - url: {FEED_URL}\n"
        f"    name: Test feed\n"
        f"    language: en\n"
        f"    trust_rank: {FEED_TRUST}\n"
    )
    return path


def _envelope_record() -> RawRecord:
    envelope = {
        "feed": {"url": FEED_URL, "name": "Test feed", "language": "en"},
        "entry_id": "entry-1",
        "title": TITLE,
        "link": ENTRY_URL,
        "summary": "",
        "content": f"<p>{BODY}</p>",
        "published": "2026-07-31T09:30:00+00:00",
    }
    return RawRecord(
        payload=json.dumps(envelope, sort_keys=True).encode("utf-8"),
        content_type="application/vnd.limes.feed-entry+json",
        source_url=FEED_URL,
        fetched_at=FETCHED_AT,
    )


@pytest.fixture
def ctx(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    feeds_config_path = _feeds_config(tmp_path)
    # The class-level default path is bound at definition time, so the
    # registry's `FeedsAdapter()` picks up the tmp config through the loader
    # seam instead.
    real_load = feeds_module._load_feed_config
    monkeypatch.setattr(
        feeds_module,
        "_load_feed_config",
        lambda _path: real_load(feeds_config_path),
    )
    fake_de = _FakeNer()
    fake_en = _FakeNer()
    monkeypatch.setattr(
        "limes.composition.spacy.load",
        lambda name: fake_de if name.endswith("de") else fake_en,
    )
    context = build_run_context(
        _settings(neo4j_instance, tmp_path),
        needs_inference=True,
        budget_eur=Decimal("3.00"),
    )
    yield context
    context.driver.close()


@pytest.fixture(autouse=True)
def _isolated_graph(ctx):
    # Each test asserts absolute counts over its own runs; the session
    # container is shared, so the graph is emptied before every test (the
    # sanctioned fixture-teardown exception to the delete ban).
    ctx.driver.write_batch([("MATCH (n) DETACH DELETE n", {})])
    yield


def _mock_transport(
    *,
    extraction_items: list[dict[str, Any]] | None = None,
) -> None:
    """respx routes for the catalogue, chat completions, and embeddings.
    The chat response carries `extraction_items` (or the default single
    LEI-carrying assertion); embeddings return deterministic vectors via
    the test embedder."""
    if extraction_items is None:
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


@pytest.fixture
def fixture_fetch(monkeypatch: pytest.MonkeyPatch):
    records = [_envelope_record()]

    def _fetch(self, since, until):
        return iter(records)

    monkeypatch.setattr(feeds_module.FeedsAdapter, "fetch", _fetch)
    return records


def test_trace2_document_run_end_to_end(ctx, fixture_fetch):
    with respx.mock:
        _mock_transport()
        record = execute_run(
            RunSpec(
                source_id="feeds",
                mode="backfill",
                since=datetime(2026, 7, 1, tzinfo=UTC),
                budget_eur=__import__("decimal").Decimal("3.00"),
            ),
            ctx,
        )

    assert record.records_fetched == 1
    assert record.documents_gated_out == 0
    assert record.errors == 0
    assert record.assertions_rejected == 0
    assert record.assertions_written == 1
    assert record.assertions_skipped == 0
    assert record.nodes_created == 2
    assert record.cost_eur > 0
    assert record.finished_at is not None

    # One SUBSIDIARY_OF between the two LEI entities.
    rows = ctx.driver.read(
        "MATCH (:Entity)-[r:SUBSIDIARY_OF]->(:Entity) RETURN "
        "r.source_id AS sid, r.source_trust AS trust, "
        "r.extractor_model AS model, r.prompt_version AS prompt, "
        "r.schema_version AS schema, r.confidence AS confidence, "
        "r.evidence_document_id AS doc_id",
        {},
        30,
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["sid"] == "feeds"
    assert row["trust"] == pytest.approx(FEED_TRUST)
    assert row["model"] == EXTRACTION_MODEL
    assert row["prompt"] == "1.0.0"
    assert row["schema"] == "1.0.0"
    assert row["confidence"] == pytest.approx(0.95)
    assert row["doc_id"] == hashlib.sha256(_envelope_record().payload).hexdigest()

    # The resolver's intermediates never reached the graph (D-29): the
    # assertion_id is the real D-10 digest over the real source id.
    from limes.sources.base import deterministic_assertion_id

    rows = ctx.driver.read(
        "MATCH ()-[r:SUBSIDIARY_OF]->() RETURN r.assertion_id AS aid",
        {},
        30,
    )
    assert rows[0]["aid"] == deterministic_assertion_id(
        "feeds",
        "SUBSIDIARY_OF",
        f"lei:{SUBJECT_LEI}",
        f"lei:{OBJECT_LEI}",
        datetime(2026, 7, 1, tzinfo=UTC),
    )

    # Mentions exist for every endpoint; SAME_AS is created only for
    # entities present at resolution time (D-42): the backbone loads before
    # extraction, so a first ingest of a never-seen LEI carries no link —
    # the loader materializes the entity after resolution. The reextract
    # test proves the links materialize on the second pass.
    rows = ctx.driver.read("MATCH (m:Mention) RETURN count(m) AS c", {}, 30)
    assert rows[0]["c"] == 2
    rows = ctx.driver.read("MATCH (:Mention)-[l:SAME_AS]->(:Entity) RETURN count(l) AS c", {}, 30)
    assert rows[0]["c"] == 0

    # The extraction cache holds the document's result (D-38: written only
    # after the load succeeded).
    rows = ctx.driver.read(
        "MATCH (e:ExtractionCacheEntry) RETURN count(e) AS c",
        {},
        30,
    )
    assert rows[0]["c"] == 1

    # The embeddings the loader stamped are index-ready (normalized, dims
    # declared) — the merge-stamp contract (WP-25a).
    rows = ctx.driver.read(
        "MATCH (e:Entity {entity_id: 'lei:" + SUBJECT_LEI + "'}) RETURN "
        "size(e.label_embedding) AS dims",
        {},
        30,
    )
    assert rows[0]["dims"] == TEST_EMBEDDING_DIMENSIONS

    # The run closed and the source advanced.
    rows = ctx.driver.read(
        "MATCH (s:Source {source_id: 'feeds'}) RETURN s.last_run_id AS run_id, "
        "s.last_success_at AS at",
        {},
        30,
    )
    assert rows[0]["run_id"] == record.run_id
    assert rows[0]["at"] == record.finished_at


def test_documents_gated_out_are_counted(ctx, fixture_fetch):
    # A document with no recognized entities is gated out with its reason —
    # counted, never silent — and no paid call is made (respx has no routes:
    # any HTTP attempt fails loudly).
    assert ctx.gate is not None
    ctx.gate.nlp_de._enabled = False
    ctx.gate.nlp_en._enabled = False
    with respx.mock:
        record = execute_run(
            RunSpec(
                source_id="feeds",
                mode="ingest",
                since=datetime(2026, 7, 1, tzinfo=UTC),
            ),
            ctx,
        )
    assert record.documents_gated_out == 1
    assert record.records_fetched == 1
    assert record.assertions_written == 0
    assert record.errors == 0
    rows = ctx.driver.read(
        "MATCH (e:ExtractionCacheEntry) RETURN count(e) AS c",
        {},
        30,
    )
    assert rows[0]["c"] == 0


def test_budget_exhausted_closes_run_cleanly(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    ctx,
    fixture_fetch,
):
    # The envelope governs the run (AC-15); the first paid call is refused,
    # the run record closes with finished_at set, the source's last-success
    # mark stays untouched, and the exception surfaces for the CLI.
    hungry = build_run_context(
        _settings(neo4j_instance, tmp_path),
        needs_inference=True,
        budget_eur=Decimal("0.00"),
    )
    try:
        with respx.mock:
            _mock_transport()
            with pytest.raises(BudgetExhausted):
                execute_run(
                    RunSpec(
                        source_id="feeds",
                        mode="backfill",
                        since=datetime(2026, 7, 1, tzinfo=UTC),
                        budget_eur=Decimal("0.00"),
                    ),
                    hungry,
                )
        rows = hungry.driver.read(
            "MATCH (r:IngestionRun) RETURN r.finished_at IS NOT NULL AS closed "
            "ORDER BY r.started_at DESC LIMIT 1",
            {},
            30,
        )
        assert rows[0]["closed"] is True
        rows = hungry.driver.read(
            "MATCH (s:Source {source_id: 'feeds'}) RETURN s.last_success_at AS at",
            {},
            30,
        )
        assert rows[0]["at"] is None
    finally:
        hungry.driver.close()


def test_reextract_retracts_superseded_and_relinks(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    ctx,
    fixture_fetch,
    monkeypatch: pytest.MonkeyPatch,
):
    # Run 1 with prompt 1.0.0 writes assertion A (valid_from 2026-07-01).
    # Reextract with prompt 1.0.1: cache miss, extraction yields the same
    # fact with a later validity — a NEW assertion_id. A is superseded and
    # retracted (D-39), B is written, and the now-existing entities receive
    # their SAME_AS links (D-42). The prompt artifact itself is not touched:
    # the loader seam serves the 1.0.0 text for the bumped version.
    from limes.extraction.openrouter import _load_prompt

    real_load = _load_prompt
    monkeypatch.setattr(
        "limes.extraction.openrouter._load_prompt",
        lambda version: real_load("1.0.0"),
    )

    first_items = [
        {
            "passage_index": 0,
            "subject": {"surface": SUBJECT_LEI, "type": "Corporation"},
            "relation": "SUBSIDIARY_OF",
            "object": {"surface": OBJECT_LEI, "type": "Corporation"},
            "valid_from": "2026-07-01",
            "confidence": 0.95,
            "evidence_start": 0,
            "evidence_end": len(f"{TITLE}\n\n{BODY}"),
        }
    ]
    second_items = [
        dict(first_items[0], valid_from="2026-08-01"),
    ]
    call_count = {"n": 0}

    def _completions(request) -> Response:
        call_count["n"] += 1
        items = first_items if call_count["n"] == 1 else second_items
        return Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(items)}}],
                "usage": USAGE,
            },
        )

    with respx.mock:
        respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=CATALOGUE))
        respx.post(COMPLETIONS_URL).mock(side_effect=_completions)
        respx.post(EMBEDDINGS_URL).mock(
            side_effect=lambda request: Response(
                200,
                json={
                    "data": [
                        {"embedding": vector}
                        for vector in fake_embedder()(
                            [str(item) for item in json.loads(request.content)["input"]]
                        )
                    ],
                    "usage": {"prompt_tokens": 40, "total_tokens": 40},
                },
            )
        )
        first = execute_run(
            RunSpec(
                source_id="feeds",
                mode="ingest",
                since=datetime(2026, 7, 1, tzinfo=UTC),
            ),
            ctx,
        )
        assert first.assertions_written == 1
        assert first.nodes_created == 2

        second = build_run_context(
            _settings(neo4j_instance, tmp_path, extraction_prompt_version="1.0.1"),
            needs_inference=True,
            budget_eur=Decimal("3.00"),
        )
        try:
            reextracted = execute_run(
                RunSpec(
                    source_id="feeds",
                    mode="reextract",
                    since=datetime(2026, 7, 1, tzinfo=UTC),
                    budget_eur=Decimal("3.00"),
                ),
                second,
            )
            assert reextracted.assertions_written == 1
            assert reextracted.errors == 0
            assert reextracted.documents_gated_out == 0

            rows = ctx.driver.read(
                "MATCH ()-[r:SUBSIDIARY_OF]->() RETURN r.valid_from AS vf, "
                "r.retracted_at AS retracted ORDER BY r.valid_from",
                {},
                30,
            )
            assert len(rows) == 2
            assert rows[0]["retracted"] is not None  # the 2026-07-01 fact
            assert rows[1]["retracted"] is None  # the 2026-08-01 fact

            # The second pass resolves against the materialized backbone:
            # both mentions now carry their SAME_AS links (D-42).
            rows = ctx.driver.read(
                "MATCH (:Mention)-[l:SAME_AS]->(:Entity) RETURN count(l) AS c",
                {},
                30,
            )
            assert rows[0]["c"] == 2
        finally:
            second.driver.close()


def test_reingest_hits_cache_and_writes_nothing_new(ctx, fixture_fetch):
    # AC-05 for the document path: the second run's gate short-circuits on
    # the cache entry — the document is counted as gated out (cache_hit),
    # zero paid calls, zero new graph content.
    with respx.mock:
        _mock_transport()
        first = execute_run(
            RunSpec(
                source_id="feeds",
                mode="ingest",
                since=datetime(2026, 7, 1, tzinfo=UTC),
            ),
            ctx,
        )
        assert first.assertions_written == 1

        second = execute_run(
            RunSpec(
                source_id="feeds",
                mode="ingest",
                since=datetime(2026, 7, 1, tzinfo=UTC),
            ),
            ctx,
        )
    assert second.documents_gated_out == 1
    assert second.assertions_written == 0
    assert second.records_fetched == 1
    rows = ctx.driver.read(
        "MATCH ()-[r:SUBSIDIARY_OF]->() RETURN count(r) AS c",
        {},
        30,
    )
    assert rows[0]["c"] == 1
