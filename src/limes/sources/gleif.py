# src/limes/sources/gleif.py | v2.0.0 | introduced by WP-11, NRW API rewrite BE-59
"""GLEIF LEI API adapter, selected to Nordrhein-Westfalen at the source.

Loads the legal-entity backbone for NRW: `Corporation` nodes keyed by `lei`,
`HEADQUARTERED_IN` edges to address-identity `Location` nodes, `LOCATED_IN` edges
to the NUTS-3 region of an NRW headquarters postcode, and direct/ultimate
accounting-consolidation edges (ontology 1.3.0).

BE-59 replaces the global golden copy (millions of records) with the public LEI
API filtered server-side: `filter[entity.addresses.region]=DE-NW` returns every
LEI record with a legal or headquarters address in NRW (≈44k on 2026-11-17).
Deep page numbers are capped by the API at 10,000 results, so acquisition uses
cursor pagination (`page[cursor]=*`, then each page's `links.next`). Each page
is archived as one record.

Non-obvious choices, each load-bearing:
- Only `ACTIVE` entities are loaded, as before; inactive rows are counted.
- Region assignment uses the pinned NRW postcode reference (`limes.geo_scope`),
  a lookup and never geometry. A headquarters outside NRW (the record matched
  on its legal address) gets its Location but no NRW region.
- The API exposes each record's direct/ultimate parent as an LEI reference, or
  a reporting exception (no parent). A parent is an observed current fact of
  this snapshot: valid from the fetch instant, without the golden copy's
  relationship periods. The parent node's label is its LEI until its own
  record loads; the loader never overwrites an established label.
- `next` URLs are accepted only on the API host with the same filter, so a
  response can never redirect acquisition elsewhere.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from datetime import datetime
from typing import Any, Literal
from urllib.parse import parse_qs, urlencode, urlsplit

import structlog

from limes.errors import SourceFetchError, SourceParseError
from limes.geo_scope import ISO_3166_2, postcode_table
from limes.sources.base import (
    address_location,
    fetch_bytes,
    key_entity_id,
    make_assertion,
    now_utc,
    payload_hash,
)
from limes.types import Assertion, EntityEndpoint, NormalizedRecord, RawRecord

logger = structlog.get_logger(__name__)

API_URL = "https://api.gleif.org/api/v1/lei-records"
REGION_FILTER = "filter[entity.addresses.region]"
PAGE_SIZE = 200
MAX_PAGES = 1_000  # ≈200k records; the NRW slice is ≈44k.
MAX_PAGE_BYTES = 16 * 1024 * 1024
CONTENT_TYPE = "application/vnd.api+json"

_ACTIVE_STATUS = "ACTIVE"
_LEI_PATTERN = re.compile(r"[A-Z0-9]{20}")
_PARENTS = {
    "direct-parent": "DIRECTLY_CONSOLIDATED_BY",
    "ultimate-parent": "ULTIMATELY_CONSOLIDATED_BY",
}


def first_page_url() -> str:
    return API_URL + "?" + urlencode(
        {REGION_FILTER: ISO_3166_2, "page[size]": PAGE_SIZE, "page[cursor]": "*"}
    )


def _checked_next(url: str | None) -> str | None:
    if not url:
        return None
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    if (
        parts.scheme != "https"
        or f"{parts.netloc}{parts.path}" != "api.gleif.org/api/v1/lei-records"
        or query.get(REGION_FILTER) != [ISO_3166_2]
        or not query.get("page[cursor]")
    ):
        raise SourceFetchError("gleif: unexpected pagination link; acquisition stopped")
    return url


class GleifAdapter:
    """GLEIF — NRW legal entities, addresses and consolidation parents."""

    source_id: str = "gleif"
    name: str = "GLEIF"
    kind: Literal["structured", "unstructured"] = "structured"
    trust_rank: float = 1.00
    supports_backfill: bool = False
    supports_incremental: bool = False

    def fetch(self, since: datetime | None, until: datetime | None) -> Iterator[RawRecord]:
        """Every NRW LEI page. The window is ignored: each run is a snapshot."""
        url: str | None = first_page_url()
        seen: set[str] = set()
        while url is not None:
            if url in seen or len(seen) >= MAX_PAGES:
                raise SourceFetchError("gleif: pagination cycle or page bound exceeded")
            seen.add(url)
            payload = fetch_bytes(url, max_bytes=MAX_PAGE_BYTES)
            try:
                links = json.loads(payload).get("links", {})
            except ValueError as exc:
                raise SourceFetchError(f"gleif: malformed API page: {exc}") from exc
            yield RawRecord(
                payload=payload, content_type=CONTENT_TYPE, source_url=url, fetched_at=now_utc()
            )
            url = _checked_next(links.get("next"))

    def normalize(self, record: RawRecord) -> NormalizedRecord:
        try:
            document = json.loads(record.payload)
            rows: list[dict[str, Any]] = document["data"]
        except (ValueError, KeyError, TypeError) as exc:
            raise SourceParseError(f"gleif: malformed API page: {exc}") from exc
        assertions: list[Assertion] = []
        entities: list[EntityEndpoint] = []
        inactive = malformed = 0
        postcodes = postcode_table()
        for row in rows:
            lei = str(row.get("id") or "")
            entity = (row.get("attributes") or {}).get("entity") or {}
            if not _LEI_PATTERN.fullmatch(lei) or not entity:
                malformed += 1
                continue
            if entity.get("status") != _ACTIVE_STATUS:
                inactive += 1
                continue
            name = ((entity.get("legalName") or {}).get("name") or "").strip() or lei
            corporation = _corporation(lei, name)
            emitted = False
            hq = entity.get("headquartersAddress") or {}
            country = (hq.get("country") or "").strip()
            postal = (hq.get("postalCode") or "").strip()
            city = (hq.get("city") or "").strip()
            if country and postal:
                location = address_location(country, postal, city)
                assertions.append(make_assertion(self, record, corporation,
                                                 "HEADQUARTERED_IN", location))
                emitted = True
                nuts = postcodes.get(postal) if country == "DE" else None
                if nuts:
                    region = EntityEndpoint(
                        entity_id=key_entity_id(("nuts_code", nuts)),
                        type="AdministrativeRegion",
                        label=nuts,
                        deterministic_key=("nuts_code", nuts),
                    )
                    assertions.append(make_assertion(self, record, location, "LOCATED_IN", region))
            for name_, relation in _PARENTS.items():
                ref = ((row.get("relationships") or {}).get(name_) or {}).get("data") or {}
                parent = str(ref.get("id") or "")
                if ref.get("type") != "lei-records":
                    continue  # Reporting exception: the entity reports no such parent.
                if not _LEI_PATTERN.fullmatch(parent):
                    malformed += 1
                    continue
                assertions.append(make_assertion(
                    self, record, corporation, relation, _corporation(parent, parent)))
                emitted = True
            if not emitted:
                entities.append(corporation)
        for assertion in assertions:
            assertion.provenance.source_url = record.source_url
        logger.info(
            "gleif: API page normalized",
            records=len(rows),
            assertions=len(assertions),
            standalone=len(entities),
            inactive_skipped=inactive,
            malformed=malformed,
        )
        return NormalizedRecord(
            content_hash=payload_hash(record.payload),
            kind="structured",
            assertions=assertions,
            entities=entities,
            errors=malformed,
        )


def _corporation(lei: str, label: str) -> EntityEndpoint:
    return EntityEndpoint(
        entity_id=key_entity_id(("lei", lei)),
        type="Corporation",
        label=label,
        deterministic_key=("lei", lei),
    )
