"""Dynamic DE/EN search feeds for an investigation's current graph identities.

Google News RSS is a discovery/index surface: headlines and supplied snippets only.
No licensed agency full-text access, independent corroboration, or publisher rights
are inferred. We retain the index response, report link, publisher and missing-text
marker. No arbitrary discovered URL is fetched; all transport uses a fixed HTTPS
origin. Source outages are errors, never empty successful coverage.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlencode

import feedparser  # type: ignore[import-untyped]

from limes.errors import SourceFetchError, SourceParseError
from limes.pipeline.normalize import detect_language, extract_text_from_html
from limes.sources.base import fetch_bytes, payload_hash
from limes.sources.feeds import _entry_published
from limes.types import DocumentPayload, NormalizedRecord, RawRecord

MAX_FEEDS = 8
MAX_ENTRIES = 25
MAX_FEED_BYTES = 2 * 1024 * 1024
MAX_DOCUMENT_CHARS = 24000


class NewsAdapter:
    source_id = "news"
    name = "Investigation news discovery"
    kind: Literal["structured", "unstructured"] = "unstructured"
    trust_rank = 0.5  # Discovery index, not an agency's or publisher's trust.
    supports_backfill = False
    supports_incremental = True

    def __init__(self) -> None:
        self.targets: list[str] = []
        self.investigation_id = ""
        self.revision = 0
        self.failures = 0
        self.replay_records: list[RawRecord] | None = None

    def configure(self, key: str, revision: int, targets: list[str]) -> None:
        self.investigation_id, self.revision = key, revision
        self.targets = list(dict.fromkeys(targets))
        if len(self.targets) > MAX_FEEDS // 2:
            raise ValueError("news cycle exceeds four-target limit")
        self.failures = 0

    def fetch(self, since: datetime | None, until: datetime | None) -> Iterator[RawRecord]:
        if self.replay_records is not None:
            yield from self.replay_records
            return
        if not self.targets:
            raise SourceFetchError("news acquisition requires tracked investigation targets")
        # Replay latest bounded feed. Do not date-filter away corrections/undated reports.
        for query in self.targets:
            for language, country in (("de", "DE"), ("en", "GB")):
                url = "https://news.google.com/rss/search?" + urlencode(
                    {"q": query, "hl": language, "gl": country, "ceid": f"{country}:{language}"}
                )
                try:
                    payload = fetch_bytes(
                        url, max_bytes=MAX_FEED_BYTES, headers={"Accept-Encoding": "identity"}
                    )
                    parsed = feedparser.parse(payload)
                    if parsed.get("bozo") or not parsed.get("version"):
                        raise SourceParseError("news discovery returned an invalid feed")
                except (SourceFetchError, SourceParseError):
                    self.failures += 1
                    continue
                now = datetime.now(UTC)
                # Archive the actual upstream feed once; entry envelopes retain its hash.
                yield RawRecord(
                    payload=payload,
                    content_type="application/rss+xml",
                    source_url=url,
                    fetched_at=now,
                )
                for index, entry in enumerate(parsed.entries[:MAX_ENTRIES]):
                    # Feed update time is not publication time.
                    published = _entry_published(
                        {"published_parsed": entry.get("published_parsed")}
                    )
                    modified = _entry_published(
                        {"updated_parsed": dict(entry).get("updated_parsed")}
                    )
                    publisher = entry.get("source") or {}
                    envelope = {
                        "title": str(entry.get("title") or ""),
                        "summary": str(entry.get("summary") or ""),
                        "link": str(entry.get("link") or ""),
                        "dispatch_id": str(entry.get("id") or entry.get("link") or ""),
                        "publisher": str(publisher.get("title") or "unknown"),
                        "publisher_url": str(publisher.get("href") or ""),
                        "published": published.isoformat() if published else None,
                        "modified": modified.isoformat() if modified else None,
                        "language": language,
                        "investigation_id": self.investigation_id,
                    }
                    yield RawRecord(
                        payload=json.dumps(envelope, sort_keys=True).encode(),
                        content_type="application/json",
                        acquisition_context={
                            "query": query,
                            "feed_url": url,
                            "feed_hash": payload_hash(payload),
                            "entry_index": index,
                            "revision": self.revision,
                            "feed_entries": len(parsed.entries),
                            "entries_limited": len(parsed.entries) > MAX_ENTRIES,
                        },
                        source_url=url,
                        fetched_at=now,
                    )
        if self.failures:
            raise SourceFetchError(f"{self.failures} investigation feeds failed; replay required")

    def normalize(self, record: RawRecord) -> NormalizedRecord:
        digest = payload_hash(record.payload)
        if record.content_type == "application/rss+xml":
            return NormalizedRecord(content_hash=digest, kind="structured")
        try:
            entry = {**json.loads(record.payload), **(record.acquisition_context or {})}
            title = entry["title"]
            # Verbatim normalized supplied text, never generated article prose.
            body = title + "\n" + extract_text_from_html(entry["summary"])
            if len(body) > MAX_DOCUMENT_CHARS:
                raise SourceParseError("news report exceeds text work limit")
            publication = datetime.fromisoformat(entry["published"]) if entry["published"] else None
            document = DocumentPayload(
                content_hash=digest,
                title=title,
                body=body,
                language=detect_language(body),
                published_at=publication or record.fetched_at,
                url=entry["link"],
                news_metadata={
                    **entry,
                    "article_text_available": False,
                    "publication_known": publication is not None,
                },
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SourceParseError("invalid news entry envelope") from exc
        return NormalizedRecord(content_hash=digest, kind="document", document=document)
