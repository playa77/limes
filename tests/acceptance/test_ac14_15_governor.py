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

from limes.cost.governor import Governor
from limes.errors import BudgetExhausted
from limes.pipeline.run import RunSpec, execute_run
from limes.types import CostLedgerEntry, RawRecord
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
                    budget_eur=envelope or Decimal("3.00"),
                )
                record = execute_run(spec, ctx)
            return record
        finally:
            ctx.driver.close()
    finally:
        feeds_module._load_feed_config = real_load
        FeedsAdapter.fetch = real_fetch
        composition_module.spacy.load = real_spacy_load


def test_ac14_run_terminates_cleanly_on_budget_exhaustion(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """A backfill under an envelope so small that the first paid call would
    breach it: `BudgetExhausted` propagates, the run record is closed, and
    the source's `last_success_at` stays untouched (the run did not
    succeed)."""
    from limes.graph.driver import GraphDriver

    wipe_graph(neo4j_instance)
    driver = GraphDriver(
        neo4j_instance.uri,
        neo4j_instance.user,
        neo4j_instance.password,
        neo4j_instance.database,
    )
    try:
        with pytest.raises(BudgetExhausted):
            _inference_run(
                neo4j_instance, tmp_path, envelope=Decimal("0.0000001"), monkeypatch=monkeypatch
            )

        rows = driver.read("MATCH (r:IngestionRun {source_id: 'feeds'}) RETURN r", {}, 30)
        assert rows, "the aborted run must still leave a durable record"
        closed = rows[0]["r"]
        assert closed["finished_at"] is not None, "the run must close cleanly"
        assert closed["mode"] == "backfill"

        rows = driver.read(
            "MATCH (s:Source {source_id: 'feeds'}) RETURN s.last_success_at AS last", {}, 30
        )
        assert rows[0]["last"] is None, "last_success_at must not advance on a terminated run"
    finally:
        driver.close()


def test_ac15_envelope_meters_against_envelope_not_monthly_ceiling(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
):
    """The distinguishing property: a spend the monthly ceiling would
    accept is refused by the envelope."""
    from limes.graph.driver import GraphDriver

    driver = GraphDriver(
        neo4j_instance.uri,
        neo4j_instance.user,
        neo4j_instance.password,
        neo4j_instance.database,
    )
    try:
        wipe_graph(neo4j_instance)
        monthly = Governor(driver, Decimal("10.00"), 0.95, 0.92)
        envelope = Governor(driver, Decimal("10.00"), 0.95, 0.92, envelope_eur=Decimal("1.00"))

        entry = CostLedgerEntry(
            ledger_id="ac15-entry-1",
            period="2099-01",
            purpose="extraction",
            model_id="m",
            input_tokens=1000,
            output_tokens=0,
            cost_usd=Decimal("0.80"),
            cost_eur=Decimal("0.80"),
            created_at=datetime.now(UTC),
        )
        monthly.commit(entry)
        envelope.commit(entry)

        # Monthly ceiling (soft stop at 9.50): 0.80 + 0.30 < 9.50 — accepted.
        monthly.check(Decimal("0.30"))
        # Envelope (1.00): 0.80 + 0.30 > 1.00 — refused.
        with pytest.raises(BudgetExhausted, match="envelope"):
            envelope.check(Decimal("0.30"))
    finally:
        driver.close()


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
