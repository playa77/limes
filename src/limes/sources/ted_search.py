# src/limes/sources/ted_search.py | v1.0.0 | introduced by BE-59
"""TED Search API acquisition of NRW result notices, normalized from fields.

BE-59 replaces the EU-wide monthly/daily XML packages (≈32k notices a month)
with the official Search API, filtered server-side to result notices performed
in Nordrhein-Westfalen (`place-of-performance IN (DEA)`, ≈1k a month). The
per-notice XML rendering on ted.europa.eu answers automated clients with an
empty WAF challenge (HTTP 202), so notices are read from the API's structured
fields instead; one archived record per search page.

Mapping follows the XML path in `ted.py` so identities converge:
- `Contract` keyed by the normalized notice id (`<number>-<year>`).
- `PublicBody` keyed by `ted_buyer_id` = SHA-256 of `country|name`, with the
  ISO3 country converted to the ISO2 code the XML path digests.
- CPV `Topic`s via `topic_endpoint("CPV", code)`; buyer `HEADQUARTERED_IN`
  address `Location`; `LOCATED_IN` its NUTS-3 region from the pinned NRW
  postcode reference.
- Winners (`AWARDED_TO`) by name digest, or LEI when the identifier is one.
  The index exposes winners for eForms notices; legacy-schema notices (before
  the 2023 eForms switch) carry no winner fields there, so their awards are not
  asserted. That gap is counted, never filled from other notices.

Months are acquisition units: a closed calendar month completes a durable
receipt, so an interrupted initial load resumes at the first unfinished month.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import structlog

from limes.data_scope import DATA_START
from limes.errors import SourceFetchError, SourceParseError
from limes.geo_scope import NUTS1, postcode_table
from limes.sources.base import (
    SourceAdapter,
    address_location,
    fetch_bytes_post,
    hash_entity_id,
    key_entity_id,
    make_assertion,
    now_utc,
    payload_hash,
    topic_endpoint,
)
from limes.sources.country_codes import ISO3_TO_ISO2
from limes.types import Assertion, EntityEndpoint, NormalizedRecord, RawRecord

logger = structlog.get_logger(__name__)

SEARCH_URL = "https://api.ted.europa.eu/v3/notices/search"
CONTENT_TYPE = "application/json"
PAGE_LIMIT = 250
MAX_PAGES_PER_WINDOW = 400
RESULT_NOTICE_TYPES = ("can-standard", "can-social", "can-desg", "can-tran", "can-modif")
FIELDS = [
    "publication-number", "notice-type", "publication-date", "place-of-performance",
    "title-proc", "classification-cpv", "buyer-name", "buyer-country", "buyer-city",
    "buyer-post-code", "winner-name", "winner-identifier", "winner-decision-date",
]
_NOTICE = re.compile(r"^0*(\d+)-(\d{4})$")
_LEI = re.compile(r"^[A-Z0-9]{18}[0-9]{2}$")
_LANGS = ("deu", "eng")


def nrw_query(since: date, until: date) -> str:
    types = " ".join(RESULT_NOTICE_TYPES)
    return (
        f"place-of-performance IN ({NUTS1}) AND notice-type IN ({types}) "
        f"AND PD >= {since:%Y%m%d} AND PD <= {until:%Y%m%d}"
    )


def month_windows(since: date, until: date) -> Iterator[tuple[date, date]]:
    start = since
    while start <= until:
        following = date(start.year + start.month // 12, start.month % 12 + 1, 1)
        yield start, min(until, following - timedelta(days=1))
        start = following


def fetch_nrw(adapter: SourceAdapter, since: datetime, until: datetime) -> Iterator[RawRecord]:
    from limes.sources.acquisition import active_acquisition

    acquisition = active_acquisition.get()
    today = now_utc().date()
    for start, end in month_windows(since.date(), until.date()):
        closed = start.day == 1 and end + timedelta(days=1) <= today and (
            end.month != (end + timedelta(days=1)).month)
        unit = f"ted-search:{start.isoformat()}:{end.isoformat()}"
        if closed and acquisition is not None and acquisition.unit_loaded(unit):
            continue
        record_keys: list[str] = []
        for raw in _search_window(start, end, unit):
            if acquisition is not None:
                record_keys.append(acquisition.record_key(raw))
            yield raw
        if closed and acquisition is not None:
            acquisition.finish_unit(unit, record_keys)


def _search_window(start: date, end: date, unit: str) -> Iterator[RawRecord]:
    body: dict[str, object] = {
        "query": nrw_query(start, end), "fields": FIELDS, "limit": PAGE_LIMIT,
        "paginationMode": "ITERATION", "scope": "ALL", "onlyLatestVersions": False,
    }
    expected: int | None = None
    seen: set[str] = set()
    tokens: set[str] = set()
    for page in range(1, MAX_PAGES_PER_WINDOW + 1):
        payload = fetch_bytes_post(SEARCH_URL, body)
        document = _document(payload)
        count = document.get("totalNoticeCount")
        if isinstance(count, int):
            if expected is not None and count != expected:
                raise SourceFetchError("ted: search count changed during pagination; retry")
            expected = count
        notices = document["notices"]
        for notice in notices:
            ident = str(notice.get("publication-number") or "")
            match = _NOTICE.match(ident)
            if match is not None and int(match[2]) < DATA_START.year:
                raise SourceFetchError("ted: search returned a pre-2020 publication")
            if ident in seen:
                raise SourceFetchError("ted: repeated notice during pagination")
            seen.add(ident)
        if notices:
            yield RawRecord(
                payload=payload, content_type=CONTENT_TYPE, source_url=SEARCH_URL,
                fetched_at=now_utc(),
                acquisition_context={"unit": unit, "search_query": body["query"],
                                     "search_page": page},
            )
        token = document.get("iterationNextToken")
        if expected is not None and len(seen) >= expected or not token or not notices:
            if expected is not None and len(seen) != expected:
                raise SourceFetchError("ted: incomplete search window; checkpoint unchanged")
            return
        if not isinstance(token, str) or token in tokens:
            raise SourceFetchError("ted: invalid or repeated iteration token")
        tokens.add(token)
        body["iterationNextToken"] = token
    raise SourceFetchError("ted: search page bound exceeded for one month")


def _document(payload: bytes) -> dict[str, Any]:
    try:
        document = json.loads(payload)
    except ValueError as exc:
        raise SourceParseError(f"ted: search response is not valid JSON: {exc}") from exc
    if not isinstance(document, dict) or not isinstance(document.get("notices"), list):
        raise SourceParseError("ted: search response has no notices list")
    if document.get("timedOut"):
        raise SourceFetchError("ted: search timed out; retry a narrower window")
    return document


def _text(value: Any) -> str | None:
    """First non-empty value of a language map or list, German then English."""
    if isinstance(value, dict):
        for lang in (*_LANGS, *sorted(value)):
            found = _text(value.get(lang))
            if found:
                return found
        return None
    if isinstance(value, list):
        return next((str(v).strip() for v in value if str(v).strip()), None)
    return str(value).strip() if value not in (None, "") else None


def _values(value: Any) -> list[str]:
    if isinstance(value, dict):
        for lang in (*_LANGS, *sorted(value)):
            if value.get(lang):
                return _values(value[lang])
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value).strip()] if value not in (None, "") else []


def _day(raw: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat((raw or "")[:10]).replace(tzinfo=UTC)
    except ValueError:
        return None


def normalize_page(adapter: SourceAdapter, record: RawRecord) -> NormalizedRecord:
    notices = _document(record.payload)["notices"]
    assertions: list[Assertion] = []
    entities: list[EntityEndpoint] = []
    counts = {"notices": 0, "malformed": 0, "no_buyer": 0, "legacy_without_winners": 0,
              "winners": 0, "date_fallback": 0}
    postcodes = postcode_table()
    for notice in notices:
        match = _NOTICE.match(str(notice.get("publication-number") or ""))
        if match is None:
            counts["malformed"] += 1
            continue
        counts["notices"] += 1
        notice_id = f"{int(match[1])}-{match[2]}"
        published = _day(notice.get("publication-date"))
        if published is None:
            published = record.fetched_at
            counts["date_fallback"] += 1
        contract = EntityEndpoint(
            entity_id=key_entity_id(("ted_notice_id", notice_id)),
            type="Contract",
            label=_text(notice.get("title-proc")) or notice_id,
            deterministic_key=("ted_notice_id", notice_id),
        )
        mine: list[Assertion] = []
        for code in dict.fromkeys(_values(notice.get("classification-cpv"))):
            mine.append(make_assertion(adapter, record, contract, "ABOUT_TOPIC",
                                       topic_endpoint("CPV", code), valid_from=published))
        winners = _values(notice.get("winner-name"))
        if not winners:
            counts["legacy_without_winners"] += 1
        identifiers = _values(notice.get("winner-identifier"))
        decided = _day(_text(notice.get("winner-decision-date"))) or published
        for index, winner in enumerate(dict.fromkeys(winners)):
            ident = identifiers[index] if len(identifiers) == len(winners) else ""
            corporation = (
                EntityEndpoint(entity_id=key_entity_id(("lei", ident)), type="Corporation",
                               label=winner, deterministic_key=("lei", ident))
                if _LEI.match(ident)
                else EntityEndpoint(entity_id=hash_entity_id("corporation", winner),
                                    type="Corporation", label=winner)
            )
            counts["winners"] += 1
            mine.append(make_assertion(adapter, record, contract, "AWARDED_TO", corporation,
                                       valid_from=decided))
        buyer_name = _text(notice.get("buyer-name"))
        if buyer_name is None:
            counts["no_buyer"] += 1
        else:
            name = buyer_name
            iso3 = _text(notice.get("buyer-country")) or ""
            country = ISO3_TO_ISO2.get(iso3, iso3)
            digest = hashlib.sha256(f"{country}|{name}".encode()).hexdigest()
            buyer = EntityEndpoint(
                entity_id=key_entity_id(("ted_buyer_id", digest)), type="PublicBody",
                label=name, deterministic_key=("ted_buyer_id", digest),
            )
            mine.append(make_assertion(adapter, record, buyer, "BUYER_OF", contract,
                                       valid_from=published))
            postal = _text(notice.get("buyer-post-code")) or ""
            city = _text(notice.get("buyer-city")) or ""
            if country and postal:
                location = address_location(country, postal, city)
                mine.append(make_assertion(adapter, record, buyer, "HEADQUARTERED_IN",
                                           location, valid_from=published))
                nuts = postcodes.get(postal) if country == "DE" else None
                if nuts:
                    region = EntityEndpoint(
                        entity_id=key_entity_id(("nuts_code", nuts)),
                        type="AdministrativeRegion", label=nuts,
                        deterministic_key=("nuts_code", nuts),
                    )
                    mine.append(make_assertion(adapter, record, location, "LOCATED_IN",
                                               region, valid_from=published))
        for assertion in mine:
            assertion.provenance.source_url = record.source_url
            assertion.provenance.evidence_member = notice_id
        assertions.extend(mine)
        if not mine:
            entities.append(contract)
    logger.info("ted: search page normalized", assertions=len(assertions), **counts)
    return NormalizedRecord(
        content_hash=payload_hash(record.payload),
        kind="structured",
        assertions=assertions,
        entities=entities,
        errors=counts["malformed"],
    )
