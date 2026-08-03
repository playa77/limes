# tests/acceptance/test_ac33_rebuild.py | v1.0.0 | introduced by WP-39
"""AC-33: a full rebuild from the archive with an unchanged version triple
issues zero paid calls.

The mechanical core of the criterion is the extraction cache: identical
content (same content hash) under the same prompt/schema/model triple must
never be paid for twice. The document path runs twice over the identical
archived record inside one mocked transport: the first run extracts once;
the second run — a rebuild of the same content — issues zero additional
paid calls and writes nothing new, because the gate's zero-cost cache
check short-circuits before any extraction.
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

FETCHED_AT = datetime(2026, 8, 1, 9, 30, tzinfo=UTC)

SUBJECT_LEI = "529900T8BM49AURSDO55"
OBJECT_LEI = "549300BEQ1B5L7Z2WE72"
FEED_URL = "https://example.com/rss"

USAGE = {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70}

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


def _extraction_item() -> list[dict]:
    return [
        {
            "passage_index": 0,
            "subject": {"surface": SUBJECT_LEI, "type": "Corporation"},
            "relation": "SUBSIDIARY_OF",
            "object": {"surface": OBJECT_LEI, "type": "Corporation"},
            "valid_from": "2026-07-01",
            "confidence": 0.95,
            "evidence_start": GATE_TEXT.index(SUBJECT_LEI),
            "evidence_end": GATE_TEXT.index(SUBJECT_LEI) + len(SUBJECT_LEI),
        }
    ]


def test_ac33_rebuild_with_unchanged_triple_issues_zero_paid_calls(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
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
        record = _record()
        FeedsAdapter.fetch = lambda self, s, u: iter([record])
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
                            "choices": [{"message": {"content": json.dumps(_extraction_item())}}],
                            "usage": USAGE,
                        },
                    )
                )
                respx.post(EMBEDDINGS_URL).mock(side_effect=fake_embedder_vectors)

                first = execute_run(RunSpec(source_id="feeds", mode="ingest"), ctx)
                assert first.assertions_written == 1

                completions_before = sum(
                    1 for call in router.calls if str(call.request.url) == COMPLETIONS_URL
                )
                # The rebuild: the identical record, same triple.
                rebuilt = execute_run(RunSpec(source_id="feeds", mode="ingest"), ctx)
                completions_after = sum(
                    1 for call in router.calls if str(call.request.url) == COMPLETIONS_URL
                )

            assert completions_after == completions_before, (
                "the rebuild issued paid calls despite an unchanged version triple"
            )
            assert rebuilt.assertions_written == 0
            assert rebuilt.nodes_created == 0
        finally:
            ctx.driver.close()
    finally:
        feeds_module._load_feed_config = real_load
        FeedsAdapter.fetch = real_fetch
        composition_module.spacy.load = real_spacy_load
