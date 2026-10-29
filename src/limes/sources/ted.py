# src/limes/sources/ted.py | v1.0.0 | introduced by WP-14
"""TED adapter per Technical Specification §8.5.2 (source: `ted`).

Loads public-procurement awards: `Contract` entities (deterministic key:
the notice id), their buying `PublicBody`, the awarded `Corporation` (LEI
where the notice carries one), the CPV subject `Topic`s, and the buyer's
address chain `HEADQUARTERED_IN` / `LOCATED_IN`.

Non-obvious choices, each load-bearing:

- TED assigns no buyer identifier, so the PublicBody rides a stable
  surrogate: a SHA-256 over `country|officialname` under the ontology's
  `ted_buyer_id` key. The digest is a pure function of the notice's own
  fields, so re-runs and backfills reproduce it and two notices whose
  buyer spells its name identically address one node; a buyer that changes
  its name is a different node, which is honest for a surrogate.
- TED notice XML exists in several schemas whose namespaces vary, so every
  element is reached by `local-name()` XPath and every attribute by its
  local name. A namespace change renames nothing the parser looks for.
- The notice's own `BUYER_NUTS` code is the buyer's region when present;
  the postal-code correspondence (`postal_lookup`) is consulted only
  otherwise. A miss or an absent lookup leaves the region unassigned —
  counted and summarized once, never guessed.
- The search API is POST-only and filters by date in the query text, so
  `fetch` compiles the window into an ISO publication-date range in the
  body; without a window the query is a match-all and the run is a full
  load. Iteration is bounded to 400 pages of `FETCH_LIMIT` notices;
  excessive requests fail without a checkpoint.
- A contractor's VAT, postal code, town, and country are read by no path:
  no ontology relation consumes them and the loader stamps no arbitrary
  properties. Only the name and, when present, the LEI drive identity.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Literal

import structlog
from lxml import etree  # type: ignore[import-untyped]

from limes.errors import SourceFetchError, SourceParseError
from limes.sources.base import (
    address_location,
    fetch_bytes,
    fetch_bytes_post,
    hash_entity_id,
    key_entity_id,
    make_assertion,
    now_utc,
    payload_hash,
    topic_endpoint,
)
from limes.types import (
    Assertion,
    EntityEndpoint,
    NormalizedRecord,
    RawRecord,
)

logger = structlog.get_logger(__name__)

SEARCH_URL = "https://api.ted.europa.eu/v3/notices/search"

# Per-page bound; iteration is additionally capped at 400 pages.
FETCH_LIMIT = 50

NOTICE_CONTENT_TYPE = "application/xml"


class TedAdapter:
    """TED — public procurement notices: contracts, buyers, awards."""

    source_id: str = "ted"
    name: str = "TED"
    kind: Literal["structured", "unstructured"] = "structured"
    trust_rank: float = 1.00
    supports_backfill: bool = True
    supports_incremental: bool = True

    def fetch(self, since: datetime | None, until: datetime | None) -> Iterator[RawRecord]:
        """Search for notices in the window, then GET each notice XML.

        The window is compiled into the search query text as an ISO
        publication-date range; without a window the query is a match-all
        and the run is a full load. The notices are fetched sequentially
        (politeness: zero concurrency against the source).
        """
        body: dict[str, object] = {
            "query": _build_query(since, until),
            "limit": FETCH_LIMIT,
            "fields": ["publication-number", "links"],
            "paginationMode": "ITERATION",
        }
        seen_tokens: set[str] = set()
        seen_notices: set[str] = set()
        expected: int | None = None
        for page in range(400):
            search_payload = fetch_bytes_post(SEARCH_URL, body)
            hits = _search_hits(search_payload)
            if not hits and page == 0:
                logger.info("ted: search returned no notices", source_id=self.source_id)
            document = json.loads(search_payload)
            if isinstance(document, dict):
                count = document.get("totalNoticeCount")
                if isinstance(count, int):
                    expected = count if expected is None else expected
                    if expected != count:
                        raise SourceFetchError(
                            "ted: search count changed during pagination; retry window"
                        )
            for notice_id, uri in hits:
                if notice_id in seen_notices:
                    raise SourceFetchError(
                        "ted: repeated notice during pagination; checkpoint unchanged"
                    )
                seen_notices.add(notice_id)
                payload = fetch_bytes(uri, max_bytes=16 * 1024 * 1024)
                yield RawRecord(
                    payload=payload,
                    content_type=NOTICE_CONTENT_TYPE,
                    source_url=uri,
                    fetched_at=now_utc(),
                    acquisition_context={
                        "requested_notice_id": notice_id,
                        "search_request": dict(body),
                        "search_response": search_payload.decode(),
                        "search_page": page + 1,
                    },
                )
            if expected is not None and len(seen_notices) == expected:
                return
            token = document.get("iterationNextToken") if isinstance(document, dict) else None
            if not token:
                if expected is not None and len(seen_notices) != expected:
                    raise SourceFetchError("ted: incomplete search; checkpoint unchanged")
                return
            if not isinstance(token, str) or token in seen_tokens or not hits:
                raise SourceFetchError(
                    "ted: invalid or repeated iteration token; checkpoint unchanged"
                )
            seen_tokens.add(token)
            body["iterationNextToken"] = token
        raise SourceFetchError("ted: page limit exceeded; submit a narrower window")

    def bound_ingest_window(self, since: datetime, until: datetime) -> datetime:
        """Catch up in daily checkpointed requests; explicit windows remain operator-selected."""
        return min(since + timedelta(days=1), until)

    def normalize(
        self,
        record: RawRecord,
        *,
        postal_lookup: Callable[[str, str], str | None] | None = None,
    ) -> NormalizedRecord:
        """One notice XML document -> contract, buyer, award, and topic
        assertions.

        `postal_lookup` resolves (country, postal code) to a NUTS code from
        graph-resident reference data (C-07); the notice's own `BUYER_NUTS`
        code wins over it when present. A notice without `NO_DOC_OJS` is
        skipped and counted; a notice without a buyer still normalizes the
        contract.
        """
        try:
            root = etree.fromstring(record.payload)
        except (etree.XMLSyntaxError, ValueError) as exc:
            raise SourceParseError(f"ted: payload is not parseable XML: {exc}") from exc

        namespace = etree.QName(root).namespace or ""
        if namespace.startswith("urn:oasis:names:specification:ubl:schema:xsd:"):
            from limes.sources.ted_ubl import normalize_ubl

            return normalize_ubl(self, root, record, postal_lookup=postal_lookup)
        notice_id = _first_text(root, "NO_DOC_OJS")
        if notice_id is None:
            logger.warning(
                "ted: notice without NO_DOC_OJS skipped",
                source_id=self.source_id,
            )
            return NormalizedRecord(
                content_hash=payload_hash(record.payload),
                kind="structured",
            )

        counts = {
            "cpv_codes": 0,
            "contractors": 0,
            "no_buyer": 0,
            "no_buyer_address": 0,
            "skipped_contractor_name": 0,
            "skipped_cpv_code": 0,
            "date_fallback": 0,
            "missing_regions": 0,
        }

        titles = _descendants(root, "TITLE")
        title = _first_text(titles[0], "VALUE") if titles else None
        contract = EntityEndpoint(
            entity_id=key_entity_id(("ted_notice_id", notice_id)),
            type="Contract",
            label=title or notice_id,
            deterministic_key=("ted_notice_id", notice_id),
        )

        pub_date = _parse_yyyymmdd(_first_text(root, "DT_PUBLISH"))
        if pub_date is None:
            pub_date = record.fetched_at
            counts["date_fallback"] += 1
            logger.warning(
                "ted: missing or unparseable DT_PUBLISH; valid_from is fetched_at",
                notice_id=notice_id,
            )

        assertions: list[Assertion] = []
        for code_el in _descendants(root, "CPV_CODE"):
            code = _attr(code_el, "CODE")
            if code is None:
                counts["skipped_cpv_code"] += 1
                logger.warning(
                    "ted: CPV_CODE without CODE attribute skipped",
                    notice_id=notice_id,
                )
                continue
            counts["cpv_codes"] += 1
            assertions.append(
                make_assertion(
                    self,
                    record,
                    contract,
                    "ABOUT_TOPIC",
                    topic_endpoint("CPV", code),
                    valid_from=pub_date,
                )
            )

        award_date = _award_date(root, pub_date, counts, notice_id)
        for award_el in _descendants(root, "AWARD_CONTRACT") + _descendants(
            root, "AWARDED_CONTRACT"
        ):
            for contractor_el in _descendants(award_el, "CONTRACTOR"):
                name = _first_text(contractor_el, "OFFICIALNAME")
                if name is None:
                    counts["skipped_contractor_name"] += 1
                    logger.warning(
                        "ted: contractor without OFFICIALNAME skipped",
                        notice_id=notice_id,
                    )
                    continue
                counts["contractors"] += 1
                lei = _first_text(contractor_el, "LEI")
                if lei is not None:
                    corporation = EntityEndpoint(
                        entity_id=key_entity_id(("lei", lei)),
                        type="Corporation",
                        label=name,
                        deterministic_key=("lei", lei),
                    )
                else:
                    corporation = EntityEndpoint(
                        entity_id=hash_entity_id("corporation", name),
                        type="Corporation",
                        label=name,
                    )
                assertions.append(
                    make_assertion(
                        self,
                        record,
                        contract,
                        "AWARDED_TO",
                        corporation,
                        valid_from=award_date,
                    )
                )

        buyer, buyer_address = _buyer(root)
        if buyer is None:
            counts["no_buyer"] += 1
            if buyer_address is not None:
                logger.warning(
                    "ted: buyer without OFFICIALNAME; buyer assertions skipped",
                    notice_id=notice_id,
                )
            else:
                logger.warning(
                    "ted: notice without CONTRACTING_BODY buyer",
                    notice_id=notice_id,
                )
        else:
            assertions.append(
                make_assertion(self, record, buyer, "BUYER_OF", contract, valid_from=pub_date)
            )
            if buyer_address is None:
                counts["no_buyer_address"] += 1
            else:
                country = _first_text(buyer_address, "COUNTRY") or ""
                postal = _first_text(buyer_address, "POSTAL_CODE") or ""
                town = _first_text(buyer_address, "TOWN") or ""
                if not country or not postal:
                    counts["no_buyer_address"] += 1
                    logger.warning(
                        "ted: buyer without postal address; region unassigned",
                        notice_id=notice_id,
                    )
                else:
                    location = address_location(country, postal, town)
                    assertions.append(
                        make_assertion(
                            self,
                            record,
                            buyer,
                            "HEADQUARTERED_IN",
                            location,
                            valid_from=pub_date,
                        )
                    )
                    nuts = _first_value_code(buyer_address, "BUYER_NUTS")
                    if nuts is None and postal_lookup is not None:
                        nuts = postal_lookup(country, postal)
                    if nuts is None:
                        counts["missing_regions"] += 1
                    else:
                        region = EntityEndpoint(
                            entity_id=key_entity_id(("nuts_code", nuts)),
                            type="AdministrativeRegion",
                            label=nuts,
                            deterministic_key=("nuts_code", nuts),
                        )
                        assertions.append(
                            make_assertion(
                                self,
                                record,
                                location,
                                "LOCATED_IN",
                                region,
                                valid_from=pub_date,
                            )
                        )

        if counts["missing_regions"]:
            logger.info(
                "gisco correspondence missing for N addresses; region unassigned",
                addresses=counts["missing_regions"],
                source_id=self.source_id,
            )

        # A contract that ended up in no assertion (no buyer, no CPV, no
        # award) still ships as a standalone entity so the loader
        # materializes the node.
        contract_involved = any(
            a.subject.entity_id == contract.entity_id or a.object.entity_id == contract.entity_id
            for a in assertions
        )
        logger.info(
            "ted: notice normalized",
            notice_id=notice_id,
            assertions=len(assertions),
            **counts,
            source_id=self.source_id,
        )
        return NormalizedRecord(
            content_hash=payload_hash(record.payload),
            kind="structured",
            assertions=assertions,
            entities=[] if contract_involved else [contract],
        )


def _build_query(since: datetime | None, until: datetime | None) -> str:
    """The search query text: an ISO publication-date range compiled from
    the window, or a match-all for a full load."""
    if since is None and until is None:
        return "*"
    clauses = []
    if since is not None:
        clauses.append(f"PD >= {since:%Y%m%d}")
    if until is not None:
        clauses.append(f"PD <= {until:%Y%m%d}")
    return " AND ".join(clauses)


def _search_hits(payload: bytes) -> list[tuple[str, str]]:
    """The (notice id, notice uri) pairs in a search response; hits missing
    either field are skipped and counted, never dropped."""
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceParseError(f"ted: search response is not valid JSON: {exc}") from exc
    if isinstance(data, dict) and data.get("timedOut"):
        raise SourceFetchError("ted: search timed out; retry a narrower window")
    results = data.get("notices", data.get("results")) if isinstance(data, dict) else data
    if not isinstance(results, list):
        raise SourceParseError("ted: search response has no results list")
    hits: list[tuple[str, str]] = []
    malformed = 0
    for item in results:
        if not isinstance(item, dict):
            malformed += 1
            continue
        notice_id = item.get("publication-number", item.get("id"))
        links = item.get("links", {})
        xml = links.get("xml", {}) if isinstance(links, dict) else {}
        uri = xml.get("MUL", item.get("uri")) if isinstance(xml, dict) else item.get("uri")
        if not isinstance(notice_id, str) or not notice_id.strip():
            malformed += 1
            continue
        if not isinstance(uri, str) or not uri.strip():
            malformed += 1
            continue
        hits.append((notice_id.strip(), uri.strip()))
    if malformed:
        if isinstance(data, dict) and "notices" in data:
            raise SourceFetchError("ted: malformed current search hit; checkpoint unchanged")
        logger.warning("ted: search hits without id or uri skipped", skipped=malformed)
    return hits


def _descendants(element: etree._Element, name: str) -> list[etree._Element]:
    """Descendant elements by local name, whatever the namespace."""
    matches: list[etree._Element] = element.xpath(f".//*[local-name()='{name}']")
    return matches


def _first_text(element: etree._Element, name: str) -> str | None:
    """The text of the first non-empty descendant with the given local
    name, or None."""
    for child in _descendants(element, name):
        text = (child.text or "").strip()
        if text:
            return text
    return None


def _attr(element: etree._Element, name: str) -> str | None:
    """An attribute by its local name, qualified or not."""
    value = element.get(name)
    if isinstance(value, str) and value.strip():
        return value.strip()
    for key, value in element.attrib.items():
        if isinstance(key, str) and isinstance(value, str):
            if key.split("}")[-1] == name and value.strip():
                return value.strip()
    return None


def _first_value_code(element: etree._Element, name: str) -> str | None:
    """The CODE attribute of the first VALUE descendant of the first
    non-empty holder element with the given local name (BUYER_NUTS)."""
    for holder in _descendants(element, name):
        for value_el in _descendants(holder, "VALUE"):
            code = _attr(value_el, "CODE")
            if code is not None:
                return code
    return None


def _buyer(root: etree._Element) -> tuple[EntityEndpoint | None, etree._Element | None]:
    """The buyer endpoint and its address element from the first
    `CONTRACTING_BODY`.

    A buyer without an official name has no identity (the surrogate needs
    the name), so it returns (None, address) and the caller counts it.
    """
    bodies = _descendants(root, "CONTRACTING_BODY")
    if not bodies:
        return None, None
    addresses = _descendants(bodies[0], "ADDRESS_CONTRACTING_BODY")
    if not addresses:
        return None, None
    address = addresses[0]
    name = _first_text(address, "OFFICIALNAME")
    if name is None:
        return None, address
    country = _first_text(address, "COUNTRY") or ""
    digest = hashlib.sha256(f"{country}|{name}".encode()).hexdigest()
    buyer = EntityEndpoint(
        entity_id=key_entity_id(("ted_buyer_id", digest)),
        type="PublicBody",
        label=name,
        deterministic_key=("ted_buyer_id", digest),
    )
    return buyer, address


def _award_date(
    root: etree._Element,
    fallback: datetime,
    counts: dict[str, int],
    notice_id: str,
) -> datetime:
    """The first `AWARD_DATE`/`VALUE` as an aware UTC instant, or the
    publication date when absent or unparseable (counted)."""
    award_dates = _descendants(root, "AWARD_DATE")
    if not award_dates:
        return fallback
    raw = _first_text(award_dates[0], "VALUE")
    parsed = _parse_yyyymmdd(raw)
    if parsed is not None:
        return parsed
    counts["date_fallback"] += 1
    logger.warning(
        "ted: unparseable AWARD_DATE; using publication date",
        notice_id=notice_id,
        raw=raw,
    )
    return fallback


def _parse_yyyymmdd(raw: str | None) -> datetime | None:
    """TED dates are `YYYYMMDD` digits; pinned to UTC midnight so assertion
    digests stay timezone-stable across re-runs."""
    if not raw:
        return None
    try:
        return datetime.strptime(raw.strip(), "%Y%m%d").replace(tzinfo=UTC)
    except ValueError:
        return None
