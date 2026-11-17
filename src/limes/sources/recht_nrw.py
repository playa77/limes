# src/limes/sources/recht_nrw.py | v1.0.0 | introduced by BE-59
"""NRW state law (SGV.NRW / GV.NRW) from recht.nrw.de public pages (source: `recht_nrw`).

recht.nrw.de, the Land's official legal portal, publishes no API or bulk export.
This adapter is the machine interface built on its public, robots-permitted
surface only (never its internal search backend):

1. `sitemap.xml` → paged sitemaps list every published version (Fassung) of
   every law (`/lrgv/gesetz/…`) and ordinance (`/lrgv/rechtsverordnung/…`), as
   `<DDMMYYYY>-<slug>` paths. Sitemap documents are archived as acquisition
   evidence.
2. Versions are grouped by type and slug; only the newest version page of a group
   is fetched. Each version page lists all versions of its law (Fassungen), so a
   group whose slug is shared by two laws re-fetches the newest uncovered version
   until every listed URL is covered. ≈9.4k version URLs need ≈1 page per law.
3. Requests are serial with a minimum interval (unknown capacity; one in flight).

Each law page yields one `LegalAct` (current snapshot, original dates kept):
- Identity: the law's own promulgation citation when its change history links
  it (`GV. NRW. <year> S. <page>`, key `bgb_citation` — the ontology's gazette
  citation key), so references from amending laws converge on the same node;
  otherwise the portal's stable base-law id (`/taxonomy/term/<id>`), unkeyed.
- `ADOPTED` Landtag Nordrhein-Westfalen → Gesetz, valid from its Ausfertigungsdatum.
- `AMENDS` / `REPEALS` from amending/repealing acts linked in the change history,
  identified by their gazette citation. Unlinked mentions are counted, not guessed.

Recht.nrw.de covers only Nordrhein-Westfalen, so selection is inherent. The
window is ignored: each run observes the current portal.
"""

from __future__ import annotations

import contextlib
import re
import time
from collections import defaultdict
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import urljoin, urlsplit

import structlog
from lxml import etree, html  # type: ignore[import-untyped]

from limes.errors import SourceFetchError, SourceParseError
from limes.sources.base import (
    fetch_bytes,
    hash_entity_id,
    key_entity_id,
    make_assertion,
    now_utc,
    payload_hash,
)
from limes.types import Assertion, EntityEndpoint, NormalizedRecord, RawRecord

logger = structlog.get_logger(__name__)

ORIGIN = "https://recht.nrw.de"
SITEMAP_URL = ORIGIN + "/sitemap.xml"
ACT_KINDS = ("gesetz", "rechtsverordnung")
MIN_INTERVAL_SECONDS = 1.0
MAX_SITEMAPS = 200
MAX_LAWS = 20_000
MAX_PAGE_BYTES = 8 * 1024 * 1024
SITEMAP_CONTENT_TYPE = "application/xml"
PAGE_CONTENT_TYPE = "text/html"
LANDTAG = EntityEndpoint(
    entity_id=key_entity_id(("institution_id", "DE:nw")),
    type="PublicBody",
    label="Landtag Nordrhein-Westfalen",
    deterministic_key=("institution_id", "DE:nw"),
)

_SM = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
_VERSION = re.compile(r"^/lrgv/(gesetz|rechtsverordnung)/(\d{2})(\d{2})(\d{4})-([a-z0-9-]+)/?$")
_GAZETTE = re.compile(r"^/gvnrw/(\d{4})-")
_PAGE = re.compile(r"S\.\s*(\d+)")
_MONTHS = {m: i for i, m in enumerate(
    ("januar", "februar", "märz", "april", "mai", "juni", "juli", "august",
     "september", "oktober", "november", "dezember"), 1)}
_LONG_DATE = re.compile(r"(\d{1,2})\.\s*([A-Za-zäÄ]+)\s+(\d{4})")
_NUMERIC_DATE = re.compile(r"(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{4})")


def version_key(url: str) -> tuple[str, str, datetime] | None:
    """(kind, slug, version date) of a law version URL, or None."""
    match = _VERSION.match(urlsplit(url).path)
    if match is None:
        return None
    kind, day, month, year, slug = match.groups()
    try:
        return kind, slug, datetime(int(year), int(month), int(day), tzinfo=UTC)
    except ValueError:
        return None


def _canonical(url: str) -> str:
    return ORIGIN + urlsplit(url).path.rstrip("/") + "/"


class RechtNrwAdapter:
    """recht.nrw.de — current NRW laws and ordinances."""

    source_id: str = "recht_nrw"
    name: str = "recht.nrw.de (SGV.NRW)"
    kind: Literal["structured", "unstructured"] = "structured"
    trust_rank: float = 1.00
    supports_backfill: bool = False
    supports_incremental: bool = False

    def __init__(self) -> None:
        self._last_request = 0.0

    def _get(self, url: str) -> bytes:
        delay = MIN_INTERVAL_SECONDS - (time.monotonic() - self._last_request)
        if delay > 0:
            time.sleep(delay)
        try:
            return fetch_bytes(url, max_bytes=MAX_PAGE_BYTES)
        finally:
            self._last_request = time.monotonic()

    def _sitemaps(self) -> Iterator[tuple[RawRecord, list[str]]]:
        index = self._get(SITEMAP_URL)
        yield self._archive(index, SITEMAP_URL), []
        pages = [loc for loc in _locs(index) if loc.startswith(ORIGIN + "/sitemap/")]
        if not pages or len(pages) > MAX_SITEMAPS:
            raise SourceFetchError("recht_nrw: sitemap index empty or beyond its bound")
        for url in pages:
            payload = self._get(url)
            yield self._archive(payload, url), _locs(payload)

    def _archive(self, payload: bytes, url: str) -> RawRecord:
        return RawRecord(payload=payload, content_type=SITEMAP_CONTENT_TYPE, source_url=url,
                         fetched_at=now_utc(), acquisition_context={"archive_only": True})

    def fetch(self, since: datetime | None, until: datetime | None) -> Iterator[RawRecord]:
        groups: dict[tuple[str, str], list[tuple[datetime, str]]] = defaultdict(list)
        for record, locs in self._sitemaps():
            yield record
            for loc in locs:
                key = version_key(loc)
                if key is not None:
                    groups[(key[0], key[1])].append((key[2], _canonical(loc)))
        if not groups:
            raise SourceFetchError("recht_nrw: sitemap lists no law or ordinance versions")
        fetched = 0
        for group in sorted(groups):
            pending = dict(sorted(groups[group], reverse=True))  # newest first
            remaining = list(dict.fromkeys(pending.values()))
            while remaining:
                url = remaining[0]
                fetched += 1
                if fetched > MAX_LAWS:
                    raise SourceFetchError("recht_nrw: law page bound exceeded")
                payload = self._get(url)
                covered = {url} | set(_listed_versions(payload, url))
                remaining = [u for u in remaining if u not in covered]
                yield RawRecord(payload=payload, content_type=PAGE_CONTENT_TYPE,
                                source_url=url, fetched_at=now_utc())
        logger.info("recht_nrw acquired", groups=len(groups), pages=fetched)

    def normalize(self, record: RawRecord) -> NormalizedRecord:
        if (record.acquisition_context or {}).get("archive_only"):
            return NormalizedRecord(content_hash=payload_hash(record.payload), kind="structured")
        page = _parse(record.payload)
        key = version_key(record.source_url or "")
        if key is None:
            raise SourceParseError("recht_nrw: record is not a law version page")
        kind = key[0]
        counts = {"unlinked_changes": 0}
        own: str | None = None
        changes: list[tuple[str, str, datetime | None]] = []
        current: str | None = None
        for index, (text, links) in enumerate(page["history"]):
            relation = _relation(text)
            if index == 0 and relation is None:
                # Only an unchanged first clause states the law's own promulgation.
                cited = [_citation(link) for link in links]
                own = next((c for c in cited if c is not None), None)
                continue
            # Amendment lists continue across clauses: "geändert durch …, …; …".
            current = relation or current
            if current is None:
                continue
            found = False
            for link in links:
                citation = _citation(link)
                if citation is not None:
                    found = True
                    changes.append((current, citation, _date_before(text, link)))
            if not found and relation is not None:
                counts["unlinked_changes"] += 1
        act = _act(page, own)
        assertions: list[Assertion] = []
        enacted = page["enacted"]
        if kind == "gesetz":
            assertions.append(make_assertion(self, record, LANDTAG, "ADOPTED", act,
                                             valid_from=enacted or record.fetched_at))
        for relation, citation, dated in changes:
            other = _cited_act(citation)
            if other.entity_id == act.entity_id:
                continue
            assertions.append(make_assertion(self, record, other, relation, act,
                                             valid_from=dated or record.fetched_at))
        for assertion in assertions:
            assertion.provenance.source_url = record.source_url
        logger.info("recht_nrw law normalized", act=act.entity_id,
                    assertions=len(assertions), **counts)
        return NormalizedRecord(
            content_hash=payload_hash(record.payload),
            kind="structured",
            assertions=assertions,
            entities=[] if assertions else [act],
        )


def _locs(payload: bytes) -> list[str]:
    try:
        root = etree.fromstring(payload, etree.XMLParser(resolve_entities=False, no_network=True))
    except etree.XMLSyntaxError as exc:
        raise SourceFetchError(f"recht_nrw: malformed sitemap: {exc}") from exc
    return [str(loc.text).strip() for loc in root.iter(f"{_SM}loc") if loc.text]


def _listed_versions(payload: bytes, url: str) -> list[str]:
    try:
        root = html.fromstring(payload)
    except (etree.ParserError, ValueError):
        return []
    return [_canonical(urljoin(url, a.get("href")))
            for a in root.xpath('//*[contains(@class,"version")]//a[@href]')
            if version_key(urljoin(url, a.get("href"))) is not None]


def _text(node: html.HtmlElement) -> str:
    return " ".join(node.text_content().split())


def _parse(payload: bytes) -> dict[str, Any]:
    try:
        root = html.fromstring(payload)
    except (etree.ParserError, ValueError) as exc:
        raise SourceParseError(f"recht_nrw: unparseable page: {exc}") from exc
    titles = root.xpath("//main//h1") or root.xpath("//h1")
    terms = root.xpath('//a[contains(@href,"/taxonomy/term/")]/@href')
    term = re.search(r"/taxonomy/term/(\d+)", terms[0]) if terms else None
    if not titles or not _text(titles[0]) or term is None:
        raise SourceParseError("recht_nrw: law page lacks title or base-law id")
    fields: dict[str, str] = {}
    for label in root.xpath('//*[contains(@class,"field__label")]'):
        item = label.getnext()
        if item is not None:
            fields[_text(label)] = _text(item)
    history = [
        (_text(p), [a.get("href", "") + "|" + _text(a) for a in p.xpath(".//a")])
        for p in root.xpath('//*[contains(@class,"change-history-content")]//p')
    ]
    clauses: list[tuple[str, list[str]]] = []
    for text, links in history:
        # One paragraph can chain several events; links stay with their clause.
        parts = [part.strip() for part in text.split(";") if part.strip()]
        for part in parts:
            clauses.append((part, [link for link in links if link.split("|", 1)[1] in part]))
    return {
        "title": _text(titles[0]),
        "term": term[1],
        "enacted": _short_date(fields.get("Ausfertigungsdatum")),
        "history": clauses,
    }


def _short_date(raw: str | None) -> datetime | None:
    try:
        return datetime.strptime((raw or "").strip(), "%d.%m.%Y").replace(tzinfo=UTC)
    except ValueError:
        return None


def _relation(text: str) -> str | None:
    lowered = text.casefold()
    if "außer kraft" in lowered or "aufgehoben" in lowered:
        return "REPEALS"
    if "geändert" in lowered or "änderung" in lowered:
        return "AMENDS"
    return None


def _date_before(text: str, link: str) -> datetime | None:
    """The last long ("19. Dezember 2024") or numeric ("27.1.2004") date before the link."""
    label = link.split("|", 1)[1]
    head = text[: text.find(label)] if label in text else text
    found: list[tuple[int, datetime]] = []
    for match in _LONG_DATE.finditer(head):
        month = _MONTHS.get(match[2].casefold())
        if month:
            with contextlib.suppress(ValueError):
                found.append((match.start(), datetime(int(match[3]), month, int(match[1]),
                                                      tzinfo=UTC)))
    for match in _NUMERIC_DATE.finditer(head):
        with contextlib.suppress(ValueError):
            found.append((match.start(), datetime(int(match[3]), int(match[2]), int(match[1]),
                                                  tzinfo=UTC)))
    return max(found)[1] if found else None


def _citation(link: str) -> str | None:
    href, label = link.split("|", 1)
    year = _GAZETTE.match(urlsplit(href).path)
    page = _PAGE.search(label)
    return f"GV. NRW. {year[1]} S. {page[1]}" if year and page else None


def _act(page: dict[str, Any], citation: str | None) -> EntityEndpoint:
    if citation is not None:
        return _cited_act(citation, label=page["title"])
    return EntityEndpoint(
        entity_id=hash_entity_id("legal-act-recht-nrw", page["term"]),
        type="LegalAct",
        label=page["title"],
        aliases=[f"recht.nrw.de term {page['term']}"],
    )


def _cited_act(citation: str, *, label: str | None = None) -> EntityEndpoint:
    return EntityEndpoint(
        entity_id=key_entity_id(("bgb_citation", citation)),
        type="LegalAct",
        label=label or citation,
        deterministic_key=("bgb_citation", citation),
    )
