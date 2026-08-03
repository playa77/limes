# tests/acceptance/test_ac12_13_cache_evidence.py | v1.0.0 | introduced by WP-39
"""AC-12 and AC-13: the extraction cache and the evidence-span check.

AC-12: a cache hit on the current version triple issues no paid call and
is recorded as cached. The document path runs twice over the identical
record inside one mocked transport: the first run extracts (the transport
counts the call), the second run's gate short-circuits on the cache entry
the first run wrote — zero additional paid calls, zero new writes, and
the run records the cache-hit document as gated out.

AC-13: an assertion whose evidence span does not contain its subject or
object surface is rejected as `EVIDENCE_SPAN_MISMATCH` — the extractor's
deterministic rejection, exercised through the production extractor with
a canned model response.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import respx
from httpx import Response

from limes.composition import build_run_context
from limes.pipeline.run import RunSpec, execute_run
from limes.types import RawRecord
from tests.acceptance.conftest import (
    CATALOGUE,
    CATALOGUE_URL,
    COMPLETIONS_URL,
    EMBEDDINGS_URL,
    FakeNer,
    acceptance_settings,
    fake_embedder_vectors,
)
from tests.fixtures.graph_data import wipe_graph
from tests.integration.conftest import Neo4jInstance

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"

FETCHED_AT = datetime(2026, 8, 1, 9, 30, tzinfo=UTC)

SUBJECT_LEI = "529900T8BM49AURSDO55"
OBJECT_LEI = "549300BEQ1B5L7Z2WE72"
FEED_URL = "https://example.com/rss"

USAGE = {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70}

# The gate text the passage window covers: title, blank line, body.
GATE_TEXT = f"Holding announcement\n\n{SUBJECT_LEI} holds {OBJECT_LEI}."


def _record() -> RawRecord:
    envelope = {
        "feed": {"url": FEED_URL, "name": "Test feed", "language": "en"},
        "entry_id": "entry-1",
        "title": "Holding announcement",
        "link": "https://example.com/entries/1",
        "summary": "",
        "content": f"<p>{SUBJECT_LEI} holds {OBJECT_LEI}.</p>",
        "published": "2026-07-31T09:30:00+00:00",
    }
    return RawRecord(
        payload=json.dumps(envelope, sort_keys=True).encode("utf-8"),
        content_type="application/vnd.limes.feed-entry+json",
        source_url=FEED_URL,
        fetched_at=FETCHED_AT,
    )


def _completions_calls(router) -> int:
    """The number of chat-completion requests the transport saw."""
    return sum(1 for call in router.calls if str(call.request.url) == COMPLETIONS_URL)


def test_ac12_cache_hit_issues_no_paid_call(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """The same document, same version triple, twice inside one mocked
    transport: the second run's gate short-circuits on the cache entry —
    the paid endpoint is not hit again and nothing new is written."""
    from limes import composition as composition_module
    from limes.sources import feeds as feeds_module
    from limes.sources.feeds import FeedsAdapter

    wipe_graph(neo4j_instance)
    tmp_feeds = tmp_path / "feeds.yaml"
    tmp_feeds.write_text(
        f'version: "1.0.0"\nfeeds:\n  - url: {FEED_URL}\n    name: Test feed\n    language: en\n'
    )
    real_load = feeds_module._load_feed_config
    real_fetch = FeedsAdapter.fetch
    real_spacy_load = composition_module.spacy.load
    try:
        feeds_module._load_feed_config = lambda _path: real_load(tmp_feeds)
        FeedsAdapter.fetch = lambda self, s, u: iter([_record()])
        composition_module.spacy.load = lambda name: FakeNer(True)

        settings = acceptance_settings(neo4j_instance, tmp_path)
        ctx = build_run_context(settings, needs_inference=True, budget_eur=None)
        try:
            with respx.mock as router:
                respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=CATALOGUE))
                respx.post(COMPLETIONS_URL).mock(
                    return_value=Response(
                        200,
                        json={
                            "choices": [
                                {
                                    "message": {
                                        "content": json.dumps(
                                            [
                                                {
                                                    "passage_index": 0,
                                                    "subject": {
                                                        "surface": SUBJECT_LEI,
                                                        "type": "Corporation",
                                                    },
                                                    "relation": "SUBSIDIARY_OF",
                                                    "object": {
                                                        "surface": OBJECT_LEI,
                                                        "type": "Corporation",
                                                    },
                                                    "valid_from": "2026-07-01",
                                                    "confidence": 0.95,
                                                    "evidence_start": GATE_TEXT.index(SUBJECT_LEI),
                                                    "evidence_end": GATE_TEXT.index(SUBJECT_LEI)
                                                    + len(SUBJECT_LEI),
                                                }
                                            ]
                                        )
                                    }
                                }
                            ],
                            "usage": USAGE,
                        },
                    )
                )
                respx.post(EMBEDDINGS_URL).mock(side_effect=fake_embedder_vectors)

                first = execute_run(RunSpec(source_id="feeds", mode="ingest"), ctx)
                assert first.assertions_written == 1
                calls_after_first = _completions_calls(router)

                second = execute_run(RunSpec(source_id="feeds", mode="ingest"), ctx)

                assert _completions_calls(router) == calls_after_first, (
                    "a cache hit must not issue another paid call"
                )
            assert second.documents_gated_out == 1  # the cache-hit doc is counted
            assert second.assertions_written == 0
            assert second.nodes_created == 0
        finally:
            ctx.driver.close()
    finally:
        feeds_module._load_feed_config = real_load
        FeedsAdapter.fetch = real_fetch
        composition_module.spacy.load = real_spacy_load


def test_ac13_evidence_span_mismatch_is_rejected(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
):
    """AC-13: a canned model response whose evidence span does not contain
    the subject or object surface is rejected with `EVIDENCE_SPAN_MISMATCH`
    by the production extractor's deterministic half; the well-formed span
    passes the same half."""
    from limes.extraction.openrouter import OpenRouterExtractor
    from limes.ontology.registry import load_ontology
    from limes.types import Passage

    class _FakeClient:
        def __init__(self, content: str) -> None:
            self.content = content
            self.calls = 0

        def complete(self, messages, model_id, purpose, json_schema=None):
            self.calls += 1
            return self.content, 10, 5

    text = f"{SUBJECT_LEI} holds {OBJECT_LEI}."
    passages = [Passage(index=0, text=text, doc_start=0, doc_end=len(text))]

    # The span sits on the space between the two surfaces — it contains
    # neither, so the assertion must be rejected.
    bad_item = {
        "passage_index": 0,
        "subject": {"surface": SUBJECT_LEI, "type": "Corporation"},
        "relation": "SUBSIDIARY_OF",
        "object": {"surface": OBJECT_LEI, "type": "Corporation"},
        "confidence": 0.95,
        "evidence_start": len(SUBJECT_LEI),
        "evidence_end": len(SUBJECT_LEI) + 1,
        "valid_from": None,
        "valid_to": None,
    }
    settings = acceptance_settings(neo4j_instance, tmp_path)
    ontology = load_ontology(ONTOLOGY_PATH)

    bad_client = _FakeClient(json.dumps([bad_item]))
    extractor = OpenRouterExtractor(settings, bad_client)  # type: ignore[arg-type]
    result = extractor.extract(
        passages,
        ontology,
        settings.extraction_prompt_version,
        settings.extraction_schema_version,
    )
    assert result.assertions == []
    assert any("EVIDENCE_SPAN_MISMATCH" in error for error in result.parse_errors), (
        result.parse_errors
    )
    assert bad_client.calls == 1  # the rejection is deterministic, after the call

    # The well-formed counterpart — the span is exactly the subject surface
    # — passes the same deterministic half.
    good_item = dict(bad_item, evidence_start=0, evidence_end=len(SUBJECT_LEI))
    good_client = _FakeClient(json.dumps([good_item]))
    good_extractor = OpenRouterExtractor(settings, good_client)  # type: ignore[arg-type]
    good_result = good_extractor.extract(
        passages,
        ontology,
        settings.extraction_prompt_version,
        settings.extraction_schema_version,
    )
    assert len(good_result.assertions) == 1
    assert good_result.parse_errors == []
