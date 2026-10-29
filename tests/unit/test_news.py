"""Distinct lifecycle, transport, qualification and relevance regressions for BE-43."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from limes.errors import SourceFetchError
from limes.extraction.schema import parse_extraction_response
from limes.news.models import TrackingRequest
from limes.news.store import TrackingStore
from limes.news.targets import queries_for
from limes.ontology.registry import load_ontology
from limes.sources.news import NewsAdapter
from limes.types import Passage

ROOT = Path(__file__).parents[2]


def test_lifecycle_schedules_fresh_cycles_and_requires_failed_replay(tmp_path):
    store = TrackingStore(tmp_path / "jobs.db")
    request = TrackingRequest(
        investigation_id="case", title="Supply investigation", entity_ids=["a"]
    )
    store.save(request)
    now = datetime.now(UTC)
    store.schedule(now)
    key = store.get_investigation("case").job_id
    store.schedule(now)
    assert store.get_investigation("case").job_id == key
    job = store.claim()
    assert job.request.argv() == ["limes", "news-refresh", "--investigation-id", "case"]
    store.recover()
    store.schedule(now + timedelta(days=2))
    assert store.get_investigation("case").status == "failed"
    assert store.claim() is None
    store.replay("case")
    store.schedule(now)
    assert store.get_investigation("case").job_id != key
    fresh = store.claim()
    store.finish(str(fresh.job_id), 0, "done")
    store.schedule(now)
    assert store.get_investigation("case").last_success
    store.schedule(now + timedelta(minutes=59))
    assert store.claim() is None
    store.save(request.model_copy(update={"active": False}))
    store.schedule(now + timedelta(days=5))
    assert store.claim() is None
    assert store.get_investigation("case").status == "paused"
    store.save(request)
    store.schedule(now + timedelta(days=6))
    assert store.claim() is not None


def test_relevance_refreshes_current_names_and_relation_endpoints():
    entities = [{"id": "a", "label": "Alpha", "aliases": ["New Alpha"]}]
    relations = [{"id": "edge", "subject": "Alpha", "object": "Beta", "relation": "SUPPLIES"}]
    driver = SimpleNamespace(
        read=lambda cypher, params, timeout: relations if "-[r]" in cypher else entities
    )
    request = TrackingRequest(
        investigation_id="case", title="Case", entity_ids=["a"], assertion_ids=["edge"]
    )
    first = queries_for(driver, request)
    assert "New Alpha" in first[0] and "Beta" in first[1]
    entities[0]["label"] = "Updated Alpha"
    assert "Updated Alpha" in queries_for(driver, request)[0]
    with pytest.raises(ValueError):
        queries_for(driver, request.model_copy(update={"entity_ids": ["missing"]}))


def test_upstream_discovery_retains_feed_and_per_report_identity(monkeypatch):
    payload = (ROOT / "tests/fixtures/news/discovery.xml").read_bytes()
    urls = []

    def fetch(url, **kwargs):
        urls.append(url)
        assert kwargs["max_bytes"] == 2097152
        assert kwargs["headers"]["Accept-Encoding"] == "identity"
        return payload

    monkeypatch.setattr("limes.sources.news.fetch_bytes", fetch)
    adapter = NewsAdapter()
    adapter.configure("case", 1, ['"Bundestag"'])
    records = list(adapter.fetch(None, None))
    assert len(urls) == 2 and "hl=de" in urls[0] and "hl=en" in urls[1]
    assert len(records) == 6  # One archived feed plus two unchanged reports per language.
    normalized = adapter.normalize(records[1])
    metadata = normalized.document.news_metadata
    assert metadata["dispatch_id"] and metadata["publisher"]
    assert metadata["feed_hash"] == adapter.normalize(records[0]).content_hash
    assert metadata["article_text_available"] is False
    assert metadata["publication_known"] is True
    assert metadata["modified"] is None
    assert normalized.document.body.startswith(normalized.document.title)
    assert records[0].payload == payload


def test_partial_feed_failure_yields_good_evidence_then_fails_closed(monkeypatch):
    payload = (ROOT / "tests/fixtures/news/discovery.xml").read_bytes()

    def fetch(url, **kwargs):
        if "hl=en" in url:
            raise SourceFetchError("outage")
        return payload

    monkeypatch.setattr("limes.sources.news.fetch_bytes", fetch)
    adapter = NewsAdapter()
    adapter.configure("case", 1, ["Alpha"])
    records = adapter.fetch(None, None)
    assert next(records).content_type == "application/rss+xml"
    assert next(records).content_type == next(records).content_type == "application/json"
    with pytest.raises(SourceFetchError, match="1 investigation feeds failed"):
        next(records)


@pytest.mark.parametrize(
    "case", json.loads((ROOT / "tests/fixtures/news/behavior.json").read_text())
)
def test_bilingual_qualified_schema_preserves_independent_labels(case):
    ontology = load_ontology(ROOT / "ontology/ontology.yaml")
    item = {
        "passage_index": 0,
        "subject": {"surface": "Alpha", "type": "Corporation"},
        "object": {"surface": "Beta", "type": "Corporation"},
        "relation": "SUPPLIES",
        "confidence": 0.8,
        "evidence_start": 0,
        "evidence_end": len(case["text"]),
        "qualifiers": {
            k: case[k] for k in ("modality", "event_status", "time_precision", "attribution")
        },
    }
    parsed, errors = parse_extraction_response(
        json.dumps([item]),
        [Passage(index=0, text=case["text"], doc_start=7, doc_end=len(case["text"]) + 7)],
        ontology,
        "2.0.0",
    )
    assert not errors
    assert parsed[0].qualifiers.modality == case["modality"]
    assert parsed[0].qualifiers.event_status == case["event_status"]
    assert parsed[0].qualifiers.time_precision == case["time_precision"]
    assert parsed[0].evidence_start == 7
    item["qualifiers"]["modality"] = "invented"
    assert parse_extraction_response(json.dumps([item]), [], ontology, "2.0.0")[1][0].startswith(
        "SCHEMA"
    )


def test_feed_change_does_not_change_unchanged_entry_identity(monkeypatch):
    payload = (ROOT / "tests/fixtures/news/discovery.xml").read_bytes()
    data = [payload]
    monkeypatch.setattr("limes.sources.news.fetch_bytes", lambda *a, **kw: data[0])
    adapter = NewsAdapter()
    adapter.configure("case", 1, ["Alpha"])
    first = list(adapter.fetch(None, None))[1]
    data[0] = payload.replace(
        b"</channel>", b"<lastBuildDate>Wed, 28 Oct 2026 21:00:00 GMT</lastBuildDate></channel>"
    )
    adapter.configure("case", 2, ["New Alpha"])
    second = list(adapter.fetch(None, None))[1]
    assert first.payload == second.payload
    assert first.acquisition_context["feed_hash"] != second.acquisition_context["feed_hash"]
    with pytest.raises(ValueError, match="four-target"):
        adapter.configure("case", 3, ["a", "b", "c", "d", "e"])


def test_scheduler_keeps_cycle_identity_when_queue_is_full(tmp_path, monkeypatch):
    store = TrackingStore(tmp_path / "queue.db")
    store.save(TrackingRequest(investigation_id="case", title="Case", entity_ids=["a"]))
    submit = store.submit

    def full(_):
        raise OverflowError("queue full")

    monkeypatch.setattr(store, "submit", full)
    with pytest.raises(OverflowError):
        store.schedule()
    key = store.get_investigation("case").job_id
    monkeypatch.setattr(store, "submit", submit)
    store.schedule()
    assert str(store.claim().job_id) == key


def test_news_operation_allowlist_is_bounded():
    from uuid import uuid4

    from pydantic import ValidationError

    from limes.operations.models import JobRequest

    request = JobRequest(
        request_id=uuid4(),
        command="news-reextract",
        investigation_id="case",
        version="2.0.0",
        after_document="a" * 64,
    )
    assert "--after-document" in request.argv() and "--prompt-version" in request.argv()
    with pytest.raises(ValidationError):
        JobRequest(request_id=uuid4(), command="backup", after_document="a" * 64)
    with pytest.raises(ValidationError):
        JobRequest(request_id=uuid4(), command="news-refresh", investigation_id="../../shell")


def test_updated_time_is_not_publication_and_oversized_text_is_retryable(monkeypatch):
    from limes.errors import SourceParseError
    from limes.types import RawRecord

    xml = b"""<feed xmlns="http://www.w3.org/2005/Atom"><title>Updates</title>
    <entry><id>wire:1</id><title>Alpha denies supplying Beta.</title>
    <updated>2026-10-28T20:00:00Z</updated></entry></feed>"""
    monkeypatch.setattr("limes.sources.news.fetch_bytes", lambda *a, **kw: xml)
    adapter = NewsAdapter()
    adapter.configure("case", 1, ["Alpha"])
    raw = list(adapter.fetch(None, None))[1]
    doc = adapter.normalize(raw).document
    assert doc.news_metadata["publication_known"] is False
    assert doc.news_metadata["modified"] == "2026-10-28T20:00:00+00:00"
    envelope = json.loads(raw.payload)
    envelope["summary"] = "x" * 24001
    with pytest.raises(SourceParseError, match="text work limit"):
        adapter.normalize(
            RawRecord(
                payload=json.dumps(envelope).encode(),
                content_type="application/json",
                fetched_at=datetime.now(UTC),
            )
        )


def test_job_reconnect_preserves_identity_across_optional_request_fields(tmp_path):
    from uuid import uuid4

    from limes.operations.models import JobRequest
    from limes.operations.store import JobStore

    store = JobStore(tmp_path / "old-queue.db")
    request = JobRequest(request_id=uuid4(), command="backup")
    original = store.submit(request)
    legacy = request.model_dump(mode="json")
    legacy.pop("investigation_id")
    legacy.pop("after_document")
    with store.connection() as db:
        db.execute(
            "UPDATE jobs SET request=? WHERE id=?", (json.dumps(legacy), str(request.request_id))
        )
    assert store.submit(request).job_id == original.job_id
    with pytest.raises(ValueError, match="different operation"):
        store.submit(JobRequest(request_id=request.request_id, command="ingest-all"))
