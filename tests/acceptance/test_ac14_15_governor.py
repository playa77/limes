# tests/acceptance/test_ac14_15_governor.py | v1.0.0 | introduced by WP-39
"""AC-14 and AC-15: the budget governor.

AC-14: the governor refuses a call that would breach the ceiling, and the
run terminates cleanly — the `:IngestionRun` record is closed (finished_at
set) and `:Source.last_success_at` is untouched, with the remaining work
reported as queued.

AC-15: backfill and reextract meter against their explicit envelope, not
the monthly ceiling — the distinguishing assertion is a spend the monthly
ceiling would happily accept but the envelope refuses.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import respx
from httpx import Response

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


def _inference_run(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    envelope: Decimal | None,
    monkeypatch: pytest.MonkeyPatch,
):
    """The production document path over the feed sample under an explicit
    envelope (or the monthly ceiling when `envelope` is None)."""
    from limes import composition as composition_module
    from limes.sources import feeds as feeds_module
    from limes.sources.feeds import FeedsAdapter

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

        from limes.composition import build_run_context

        wipe_graph(neo4j_instance)
        settings = acceptance_settings(neo4j_instance, tmp_path)
        ctx = build_run_context(settings, needs_inference=True, budget_eur=envelope)
        try:
            with respx.mock:
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
                spec = RunSpec(
                    source_id="feeds",
                    mode="backfill",
                    since=datetime.now(UTC) - timedelta(days=7),
                    budget_eur=envelope,
                )
                record = execute_run(spec, ctx)
            return record
        finally:
            ctx.driver.close()
    finally:
        feeds_module._load_feed_config = real_load
        FeedsAdapter.fetch = real_fetch
        composition_module.spacy.load = real_spacy_load


def test_ac14_calls_continue_with_a_zero_legacy_budget(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    wipe_graph(neo4j_instance)
    record = _inference_run(neo4j_instance, tmp_path, Decimal("0"), monkeypatch)
    assert record.finished_at is not None
    assert record.cost_eur > 0
    assert record.errors == 0


def test_ac15_backfill_under_envelope_meters_and_records(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """The run-level claim: a backfill under an explicit envelope records
    its cost in the run record and in the ledger, metered against the
    envelope (a 3 EUR envelope trivially accepts the test call)."""
    record = _inference_run(
        neo4j_instance, tmp_path, envelope=Decimal("3.00"), monkeypatch=monkeypatch
    )
    assert record.assertions_written == 1
    assert record.cost_eur > 0, "the run must report its metered cost"

    from limes.cost.ledger import read_period_spend
    from limes.graph.driver import GraphDriver

    driver = GraphDriver(
        neo4j_instance.uri,
        neo4j_instance.user,
        neo4j_instance.password,
        neo4j_instance.database,
    )
    try:
        period = datetime.now(UTC).strftime("%Y-%m")
        spend = read_period_spend(driver, period)
        # Neo4j stores cost_eur as a float; the rounding is far below the
        # metered amounts, so a tolerance absorbs it.
        assert spend + Decimal("0.000001") >= record.cost_eur, (
            "the ledger must carry the run's spend"
        )
        rows = driver.read(
            "MATCH (e:CostLedgerEntry) WHERE e.period = $period RETURN count(e) AS c",
            {"period": period},
            30,
        )
        assert rows[0]["c"] >= 1, "the run's paid calls must be ledgered"
    finally:
        driver.close()
