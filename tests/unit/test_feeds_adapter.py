# tests/unit/test_feeds_adapter.py | v1.0.0 | introduced by WP-21
"""Curated feeds adapter tests per Doc 2 §8.5.2, §12.3 (WP-21).

The acceptance: `fetch` yields one raw record per feed entry from the feeds
listed in `feeds.yaml` (respx-mocked), `normalize` turns the entry envelope
into a `DocumentPayload` with the HTML body stripped, the language declared or
detected, and the published date normalized. The per-feed trust override is
the produced seam for WP-27.
"""

import json
from datetime import UTC, datetime

import respx
import structlog
from httpx import Response

from limes.errors import ConfigurationError, SourceParseError
from limes.sources.feeds import DEFAULT_TRUST_RANK, FeedsAdapter, _entry_published
from limes.types import RawRecord

FIXTURES = __import__("pathlib").Path(__file__).parents[1] / "fixtures" / "feeds"
FETCHED_AT = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)
FEED_URL = "https://example.com/feed.xml"

_MINIMAL_CONFIG = f"""
version: "1.0.0"
feeds:
  - url: {FEED_URL}
    name: Fixture feed
"""

_OVERRIDE_CONFIG = f"""
version: "1.0.0"
feeds:
  - url: {FEED_URL}
    name: Fixture feed
    language: de
    trust_rank: 0.70
"""


def _adapter(tmp_path, config: str = _MINIMAL_CONFIG) -> FeedsAdapter:
    path = tmp_path / "feeds.yaml"
    path.write_text(config, encoding="utf-8")
    return FeedsAdapter(path)


def _feed_records(adapter: FeedsAdapter) -> list[RawRecord]:
    payload = (FIXTURES / "feed.xml").read_bytes()
    with respx.mock:
        respx.get(FEED_URL).mock(return_value=Response(200, content=payload))
        return list(adapter.fetch(None, None))


def test_config_loads_and_exposes_per_feed_trust(tmp_path):
    adapter = _adapter(tmp_path, _OVERRIDE_CONFIG)
    assert adapter.trust_rank == DEFAULT_TRUST_RANK
    assert adapter.trust_rank_for(FEED_URL) == 0.70
    assert adapter.trust_rank_for("https://unknown.example/x") == DEFAULT_TRUST_RANK


def test_missing_config_is_configuration_error(tmp_path):
    try:
        FeedsAdapter(tmp_path / "missing.yaml")
    except ConfigurationError:
        pass
    else:
        raise AssertionError("expected ConfigurationError for a missing feeds.yaml")


def test_config_without_urls_is_configuration_error(tmp_path):
    path = tmp_path / "feeds.yaml"
    path.write_text("version: '1.0.0'\nfeeds:\n  - name: no url\n", encoding="utf-8")
    try:
        FeedsAdapter(path)
    except ConfigurationError:
        pass
    else:
        raise AssertionError("expected ConfigurationError for a feed without a url")


def test_config_rejects_unsupported_language(tmp_path):
    path = tmp_path / "feeds.yaml"
    path.write_text(
        f"version: '1.0.0'\nfeeds:\n  - url: {FEED_URL}\n    language: fr\n", encoding="utf-8"
    )
    try:
        FeedsAdapter(path)
    except ConfigurationError:
        pass
    else:
        raise AssertionError("expected ConfigurationError for an unsupported language")


def test_fetch_yields_one_record_per_entry(tmp_path):
    records = _feed_records(_adapter(tmp_path))
    assert len(records) == 3
    assert all(r.content_type == "application/json" for r in records)
    assert all(r.source_url == FEED_URL for r in records)


def test_fetch_envelope_is_deterministic_and_carries_entry_fields(tmp_path):
    records = _feed_records(_adapter(tmp_path))
    envelope = json.loads(records[0].payload.decode("utf-8"))
    assert envelope["title"] == "EU-Kommission legt neues Sanktionspaket vor"
    assert envelope["entry_id"] == "fixture-1"
    assert envelope["link"] == "https://example.com/de/1"
    assert envelope["published"] == "2026-07-31T07:30:00+00:00"
    assert "<b>" in envelope["content"]

    # The envelope is byte-deterministic: re-serialization reproduces the hash.
    first = records[0].payload
    second = json.dumps(envelope, sort_keys=True).encode("utf-8")
    assert first == second


def test_normalize_builds_document_payload(tmp_path):
    adapter = _adapter(tmp_path)
    records = _feed_records(adapter)
    normalized = adapter.normalize(records[0])
    assert normalized.kind == "document"
    document = normalized.document
    assert document is not None
    assert document.title == "EU-Kommission legt neues Sanktionspaket vor"
    assert "<b>" not in document.body
    assert "neues Sanktionspaket" in document.body
    assert document.language == "de"  # no declared language; detection runs
    assert document.published_at == datetime(2026, 7, 31, 7, 30, tzinfo=UTC)
    assert document.url == "https://example.com/de/1"
    assert document.content_hash == __import__("hashlib").sha256(records[0].payload).hexdigest()


def test_normalize_declared_language_wins(tmp_path):
    adapter = _adapter(tmp_path, _OVERRIDE_CONFIG)
    normalized = adapter.normalize(_feed_records(adapter)[0])
    assert normalized.document is not None
    assert normalized.document.language == "de"


def test_undated_entry_falls_back_to_fetch_instant(tmp_path):
    adapter = _adapter(tmp_path)
    records = _feed_records(adapter)
    undated = next(
        r
        for r in records
        if "undated" in r.source_url + json.dumps(json.loads(r.payload.decode("utf-8")))
    )
    normalized = adapter.normalize(undated)
    assert normalized.document is not None
    assert normalized.document.published_at == undated.fetched_at


def test_language_detected_when_not_declared(tmp_path):
    adapter = _adapter(tmp_path)
    records = _feed_records(adapter)
    english = next(
        r for r in records if json.loads(r.payload.decode("utf-8"))["entry_id"] == "fixture-2"
    )
    document = adapter.normalize(english).document
    assert document is not None
    assert document.language == "en"


def test_unparseable_feed_yields_no_entries_and_warns(tmp_path):
    adapter = _adapter(tmp_path)
    with respx.mock:
        respx.get(FEED_URL).mock(return_value=Response(200, content=b"this is not a feed"))
        with structlog.testing.capture_logs() as captured:
            records = list(adapter.fetch(None, None))
    assert records == []
    warnings = [
        e for e in captured if e.get("event") == "feeds: feed unparseable or empty; no entries"
    ]
    assert len(warnings) == 1
    assert warnings[0]["url"] == FEED_URL


_ATOM_WITH_CONTENT = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Inline Atom Feed</title>
  <id>urn:inline:feed</id>
  <updated>2026-08-01T10:00:00Z</updated>
  <entry>
    <title>Eintrag mit content</title>
    <id>inline-1</id>
    <link href="https://example.com/inline/1"/>
    <published>2026-08-01T09:00:00Z</published>
    <content type="html"><![CDATA[<p>Erster <b>Absatz</b>.</p>]]></content>
    <summary>wird vom content verdrängt</summary>
  </entry>
</feed>
"""


def test_entry_content_wins_over_summary_in_envelope(tmp_path):
    adapter = _adapter(tmp_path)
    with respx.mock:
        respx.get(FEED_URL).mock(return_value=Response(200, content=_ATOM_WITH_CONTENT.encode()))
        records = list(adapter.fetch(None, None))
    assert len(records) == 1
    envelope = json.loads(records[0].payload.decode("utf-8"))
    assert envelope["content"] == "<p>Erster <b>Absatz</b>.</p>"


def test_normalize_rejects_malformed_envelope(tmp_path):
    adapter = _adapter(tmp_path)
    record = RawRecord(
        payload=b"not an envelope",
        content_type="application/json",
        source_url=FEED_URL,
        fetched_at=FETCHED_AT,
    )
    try:
        adapter.normalize(record)
    except SourceParseError:
        pass
    else:
        raise AssertionError("expected SourceParseError")


def test_config_with_unparsable_yaml_is_configuration_error(tmp_path):
    path = tmp_path / "feeds.yaml"
    path.write_text("feeds: [unclosed\n  - url: x\n", encoding="utf-8")
    try:
        FeedsAdapter(path)
    except ConfigurationError:
        pass
    else:
        raise AssertionError("expected ConfigurationError for unparsable YAML")


def test_config_without_feeds_list_is_configuration_error(tmp_path):
    path = tmp_path / "feeds.yaml"
    path.write_text("version: '1.0.0'\n", encoding="utf-8")
    try:
        FeedsAdapter(path)
    except ConfigurationError:
        pass
    else:
        raise AssertionError("expected ConfigurationError for a config without a feeds list")


def test_config_with_non_numeric_trust_rank_is_configuration_error(tmp_path):
    path = tmp_path / "feeds.yaml"
    path.write_text(
        f"version: '1.0.0'\nfeeds:\n  - url: {FEED_URL}\n    trust_rank: high\n",
        encoding="utf-8",
    )
    try:
        FeedsAdapter(path)
    except ConfigurationError:
        pass
    else:
        raise AssertionError("expected ConfigurationError for a non-numeric trust_rank")


def test_config_with_empty_feeds_list_is_configuration_error(tmp_path):
    path = tmp_path / "feeds.yaml"
    path.write_text("version: '1.0.0'\nfeeds: []\n", encoding="utf-8")
    try:
        FeedsAdapter(path)
    except ConfigurationError:
        pass
    else:
        raise AssertionError("expected ConfigurationError for an empty feeds list")


def test_entry_published_tolerates_malformed_time_struct():
    # A dict without the struct_time attributes cannot be built by feedparser
    # (which only produces real struct_times), so the helper is called
    # directly with the malformed value.
    assert _entry_published({"published_parsed": {"tm_year": 2026}}) is None


def test_normalize_unparseable_published_timestamp_falls_back(tmp_path):
    adapter = _adapter(tmp_path)
    envelope = json.dumps(
        {
            "feed": {"url": FEED_URL, "name": "x", "language": None},
            "entry_id": "x",
            "title": "Titel",
            "link": None,
            "summary": "",
            "content": "Body",
            "published": "not-a-timestamp",
        },
        sort_keys=True,
    ).encode()
    record = RawRecord(
        payload=envelope,
        content_type="application/json",
        source_url=FEED_URL,
        fetched_at=FETCHED_AT,
    )
    with structlog.testing.capture_logs() as captured:
        document = adapter.normalize(record).document
    assert document is not None
    assert document.published_at == FETCHED_AT
    warnings = [e for e in captured if e.get("event") == "feeds: unparseable published timestamp"]
    assert len(warnings) == 1
