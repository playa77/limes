# tests/acceptance/test_ac11_gate_status.py | v1.0.0 | introduced by WP-39
"""AC-11: the gate rejects documents below the mention threshold and
records the reason; counts appear in `/ingest/status`.

The document runs through the production document path (`execute_run`,
Trace 2) with an injected spaCy model that finds no entity spans — the
gate's below-threshold path — and the run's `documents_gated_out` counter
is then read through the API's `/ingest/status` endpoint, the durable
surface the criterion names.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from limes.pipeline.gate import GateDecision
from limes.pipeline.run import RunSpec, execute_run
from limes.types import DocumentPayload, NerSpan, RawRecord
from tests.acceptance.conftest import FakeNer, acceptance_settings
from tests.fixtures.graph_data import make_api_client, wipe_graph
from tests.integration.conftest import Neo4jInstance

REPO_ROOT = Path(__file__).resolve().parents[2]

FETCHED_AT = datetime(2026, 8, 1, 9, 30, tzinfo=UTC)

# A document whose text carries exactly one entity mention — below the
# configured threshold of two — so the gate must reject it.
BODY = "Die Bundesregierung berät ein neues Gesetz. Das Wetter bleibt wechselhaft."


@pytest.fixture(scope="module")
def graph(neo4j_instance: Neo4jInstance, tmp_path_factory: pytest.TempPathFactory):
    from limes.graph.driver import GraphDriver

    tmp = tmp_path_factory.mktemp("ac11")
    driver = GraphDriver(
        neo4j_instance.uri,
        neo4j_instance.user,
        neo4j_instance.password,
        neo4j_instance.database,
    )
    wipe_graph(neo4j_instance)
    from limes.graph.schema import provision
    from limes.ontology.registry import load_ontology

    provision(driver, load_ontology(REPO_ROOT / "ontology" / "ontology.yaml"), 1024)
    yield driver, tmp
    driver.close()


def _record() -> RawRecord:
    envelope = {
        "feed": {"url": "https://example.com/rss", "name": "Test", "language": "de"},
        "entry_id": "gated-entry",
        "title": "Bericht",
        "link": "https://example.com/1",
        "summary": "",
        "content": f"<p>{BODY}</p>",
        "published": "2026-07-31T09:30:00+00:00",
    }
    import json

    return RawRecord(
        payload=json.dumps(envelope, sort_keys=True).encode("utf-8"),
        content_type="application/vnd.limes.feed-entry+json",
        source_url="https://example.com/rss",
        fetched_at=FETCHED_AT,
    )


def test_ac11_gate_rejects_below_threshold_with_reason(
    neo4j_instance: Neo4jInstance, graph, monkeypatch: pytest.MonkeyPatch
):
    """The gate decision itself: one entity mention against a threshold of
    two produces `below_mention_threshold` with no passages."""
    driver, tmp = graph
    from limes.pipeline.gate import GateContext, gate_document

    settings = acceptance_settings(neo4j_instance, tmp)
    doc = DocumentPayload(
        content_hash="a" * 64,
        title="Bericht",
        body=BODY,
        language="de",
        published_at=FETCHED_AT,
    )
    ctx = GateContext(
        settings=settings,
        driver=driver,
        nlp_de=FakeNer(enabled=False),
        nlp_en=FakeNer(enabled=False),
    )
    decision = gate_document(doc, ctx)
    assert isinstance(decision, GateDecision)
    assert not decision.passed
    assert decision.reason == "below_mention_threshold"
    assert decision.passages == []

    # The direct counterpart: a document with two mentions passes and
    # yields passages (the gate is not rejecting everything).
    from limes.pipeline.gate import select_passages

    spans = [
        NerSpan(text="Bundesregierung", label="ORG", start=4, end=19),
        NerSpan(text="Gesetz", label="LAW", start=31, end=37),
    ]
    passages = select_passages(
        f"Bericht\n\n{BODY}",
        "de",
        spans,
        settings.extraction_passage_window_sentences,
        settings.gate_min_entity_mentions,
    )
    assert passages


def test_ac11_gate_out_count_appears_in_ingest_status(
    neo4j_instance: Neo4jInstance,
    graph,
    monkeypatch: pytest.MonkeyPatch,
):
    """The count the criterion names: a gated-out document lands in the run
    record as `documents_gated_out` and is served by `/ingest/status`."""
    driver, tmp = graph

    from limes import composition as composition_module
    from limes.sources import feeds as feeds_module
    from limes.sources.feeds import FeedsAdapter

    wipe_graph(neo4j_instance)

    real_load = feeds_module._load_feed_config
    feeds_config_path = tmp / "feeds.yaml"
    feeds_config_path.write_text(
        'version: "1.0.0"\nfeeds:\n'
        "  - url: https://example.com/rss\n"
        "    name: Test\n"
        "    language: de\n"
    )
    real_fetch = FeedsAdapter.fetch
    real_spacy_load = composition_module.spacy.load
    fake_de = FakeNer(enabled=False)
    fake_en = FakeNer(enabled=False)
    try:
        feeds_module._load_feed_config = lambda _path: real_load(feeds_config_path)
        FeedsAdapter.fetch = lambda self, since, until: iter([_record()])
        composition_module.spacy.load = lambda name: fake_de if name.endswith("de") else fake_en

        from limes.composition import build_run_context

        settings = acceptance_settings(neo4j_instance, tmp)
        ctx = build_run_context(settings, needs_inference=True, budget_eur=None)
        try:
            record = execute_run(RunSpec(source_id="feeds", mode="ingest"), ctx)
            assert record.documents_gated_out == 1
            assert record.assertions_written == 0
        finally:
            ctx.driver.close()

        with make_api_client(neo4j_instance, tmp) as client:
            response = client.get("/ingest/status")
            assert response.status_code == 200, response.text
            statuses = response.json()
            feeds_status = next(
                (status for status in statuses if status["source_id"] == "feeds"), None
            )
            assert feeds_status is not None, statuses
            assert feeds_status["documents_gated_out"] == 1
    finally:
        feeds_module._load_feed_config = real_load
        FeedsAdapter.fetch = real_fetch
        composition_module.spacy.load = real_spacy_load
