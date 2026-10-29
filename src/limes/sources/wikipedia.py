"""Verified DE/EN MediaWiki revision context; names never choose an entity."""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from datetime import datetime
from typing import Any, Literal
from urllib.parse import quote, urlencode

from limes.enrichment.common import date, snapshot
from limes.enrichment.models import AcquisitionTarget, SectionStatus
from limes.errors import SourceFetchError, SourceParseError
from limes.sources.base import fetch_bytes, now_utc, payload_hash
from limes.types import DocumentPayload, NormalizedRecord, RawRecord

MAX_BYTES = 2 * 1024 * 1024
LICENSE = "https://creativecommons.org/licenses/by-sa/4.0/"


class WikipediaAdapter:
    source_id = "wikipedia"
    name = "Wikipedia"
    kind: Literal["structured", "unstructured"] = "unstructured"
    trust_rank = 0.65
    supports_backfill = False
    supports_incremental = False

    def __init__(self) -> None:
        self.targets: list[AcquisitionTarget] = []
        self.extract = False
        self._last_request = 0.0

    def configure(self, targets: list[AcquisitionTarget], *, extract: bool = False) -> None:
        if not 1 <= len(targets) <= 10 or any(not t.selection.qid for t in targets):
            raise SourceFetchError("Wikipedia requires one to ten reviewed QID selections")
        self.targets, self.extract = targets, extract

    def _get(self, url: str) -> bytes:
        delay = max(0.0, 0.5 - (time.monotonic() - self._last_request))
        if delay:
            time.sleep(delay)
        self._last_request = time.monotonic()
        return fetch_bytes(url, max_bytes=MAX_BYTES)

    def fetch(self, since: datetime | None, until: datetime | None) -> Iterator[RawRecord]:
        if not self.targets:
            raise SourceFetchError("Wikipedia requires reviewed enrichment selections")
        for target in self.targets:
            qid = target.selection.qid
            context: dict[str, Any] = {
                "target": target.model_dump(mode="json"),
                "section": "identity",
            }
            url = "https://www.wikidata.org/w/api.php?" + urlencode(
                {"action": "wbgetentities", "format": "json", "ids": qid, "props": "sitelinks"}
            )
            payload = b'{"error":"identity lookup failed"}'
            try:
                payload = self._get(url)
                item = json.loads(payload)["entities"][qid]
                if item.get("id") != qid or "missing" in item:
                    raise ValueError("QID missing or redirected")
                links = item.get("sitelinks", {})
                if not isinstance(links, dict):
                    raise ValueError("invalid sitelinks")
            except (SourceFetchError, ValueError, KeyError, TypeError, AttributeError):
                yield self._record(payload, url, {**context, "status": "failed"})
                continue
            yield self._record(payload, url, {**context, "status": "available"})
            for language in ("de", "en"):
                sitelink = links.get(language + "wiki", {})
                title = sitelink.get("title") if isinstance(sitelink, dict) else None
                context = {
                    "target": target.model_dump(mode="json"),
                    "language": language,
                    "section": language,
                    "sitelink": title,
                }
                if not isinstance(title, str):
                    yield self._record(
                        b'{"missing":"sitelink"}', url, {**context, "status": "missing"}
                    )
                    continue
                page_url = f"https://{language}.wikipedia.org/w/api.php?" + urlencode(
                    {
                        "action": "query",
                        "format": "json",
                        "prop": "revisions|pageprops",
                        "titles": title,
                        "redirects": 1,
                        "rvprop": "ids|timestamp|content",
                        "rvslots": "main",
                        "rvlimit": 1,
                    }
                )
                try:
                    payload = self._get(page_url)
                    state = "available"
                except SourceFetchError:
                    payload, state = b'{"error":"revision request failed"}', "failed"
                yield self._record(payload, page_url, {**context, "status": state})

    @staticmethod
    def _record(payload: bytes, url: str, context: dict[str, Any]) -> RawRecord:
        return RawRecord(
            payload=payload,
            content_type="application/json",
            source_url=url,
            fetched_at=now_utc(),
            acquisition_context=context,
        )

    def normalize(self, record: RawRecord) -> NormalizedRecord:
        try:
            return self._normalize(record)
        except (ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
            context = record.acquisition_context or {}
            if "target" in context and "section" in context:
                return snapshot(
                    self,
                    record,
                    SectionStatus(
                        section=str(context["section"]),
                        status="failed",
                        reason="malformed or oversized provider section",
                    ),
                    [],
                )
            raise SourceParseError(f"Wikipedia malformed revision: {exc}") from exc

    def _normalize(self, record: RawRecord) -> NormalizedRecord:
        if len(record.payload) > MAX_BYTES:
            raise ValueError("response exceeds limit")
        context = record.acquisition_context or {}
        target = AcquisitionTarget.model_validate(context["target"])
        section = str(context["section"])
        state = context.get("status", "available")
        if state != "available" or section == "identity":
            return snapshot(self, record, SectionStatus(section=section, status=state), [])  # type: ignore[arg-type]
        language = str(context["language"])
        if language not in ("de", "en"):
            raise ValueError("unsupported language")
        query = json.loads(record.payload)["query"]
        pages = query["pages"]
        if not isinstance(pages, dict) or len(pages) != 1:
            return snapshot(self, record, SectionStatus(section=section, status="ambiguous"), [])
        page = next(iter(pages.values()))
        if "missing" in page:
            return snapshot(self, record, SectionStatus(section=section, status="missing"), [])
        props = page.get("pageprops", {})
        if "disambiguation" in props or props.get("wikibase_item") != target.selection.qid:
            return snapshot(
                self,
                record,
                SectionStatus(
                    section=section, status="ambiguous", reason="page QID mismatch/disambiguation"
                ),
                [],
            )
        revisions = page["revisions"]
        if not isinstance(revisions, list) or len(revisions) != 1:
            raise ValueError("expected one revision")
        revision = revisions[0]
        body = revision["slots"]["main"]["*"]
        if not isinstance(body, str) or not body or len(body) > 500_000:
            raise ValueError("missing or oversized revision text")
        revision_id, page_id = revision["revid"], page["pageid"]
        if (
            not isinstance(revision_id, int)
            or not isinstance(page_id, int)
            or min(revision_id, page_id) <= 0
        ):
            raise ValueError("invalid page/revision identity")
        timestamp = date(revision["timestamp"])
        if timestamp is None:
            raise ValueError("revision timestamp missing")
        url = f"https://{language}.wikipedia.org/w/index.php?oldid={revision_id}"
        canonical = f"https://{language}.wikipedia.org/wiki/" + quote(
            page["title"].replace(" ", "_")
        )
        fields = {
            "kind": "encyclopedia_revision",
            "body": body,
            "text_format": "wikitext",
            "language": language,
            "revision_id": revision_id,
            "page_id": page_id,
            "revision_at": timestamp,
            "canonical_url": canonical,
            "revision_url": url,
            "license_url": LICENSE,
            "attribution": f"Wikipedia contributors, {page['title']}",
            "history_url": canonical + "?action=history",
            "wikidata_qid": target.selection.qid,
            "redirects": json.dumps(query.get("redirects", []), ensure_ascii=False),
        }
        normalized = snapshot(
            self,
            record,
            SectionStatus(section=section, status="available", source_as_of=timestamp),
            [fields],
            version_key=f"{language}:{page_id}:{revision_id}:{payload_hash(body.encode())}",
        )
        if self.extract:
            normalized.document = DocumentPayload(
                content_hash=payload_hash(record.payload),
                title=page["title"],
                body=body,
                language=language,
                published_at=timestamp,
                url=url,
                news_metadata={
                    "publisher": "Wikipedia",
                    "dispatch_id": f"{language}:{page_id}",
                    "publication_known": True,
                    "text_available": True,
                    "revision_id": revision_id,
                    "license_url": LICENSE,
                    "source_kind": "encyclopedia_context",
                },
            )
        return normalized
