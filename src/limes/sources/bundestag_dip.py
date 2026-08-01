# src/limes/sources/bundestag_dip.py | v1.0.0 | introduced by WP-16
"""Bundestag DIP adapter per Technical Specification §8.5.2 (WP-16).

Loads members of the Bundestag from the DIP person endpoint into `Person`,
`PoliticalParty`, and reified `Office` nodes: `MEMBER_OF` (Person →
PoliticalParty), `HOLDS_OFFICE` (Person → Office), and `OFFICE_AT` (Office →
PoliticalParty), all temporal (Doc 1 §5.4).

Non-obvious choices, each load-bearing:

- The DIP API requires an operator API key; without one the endpoint answers
  HTTP 401. Wiring an operator key is a deployment decision (WP-28/38) and
  deliberately adds no configuration key here; the adapter merely appends
  `apikey=` when one is passed to the constructor. Without a key, `fetch`
  surfaces the 401 as `SourceFetchError` — honestly, without retries: 401 is
  a non-retryable 4xx (§11 retries only 429 and 5xx).
- Office is reified (DD-13): its identity is body + title + interval, so
  "who held this position when" is joinable. The deterministic key carries
  only `("body_id", "BT")`; the interval lives in the hashed `entity_id`, so
  one person's offices in two Wahlperioden are distinct nodes that share a
  deterministic key.
- The person endpoint carries no per-person dates and no mandate end dates:
  `MEMBER_OF` and the fallback `valid_from` use the fetch instant, and
  `HOLDS_OFFICE` / `OFFICE_AT` are open-ended (`valid_to` None). A deceased
  person (`verstorben`) is still processed: death does not end an edge
  without a date, and inventing one is worse than the absence.
- `WAHLPERIODE_STARTS` is the single refresh point when a new Wahlperiode
  begins. An unknown period number skips that period's office assertions and
  is counted — never invented.
- The `f.aktualisiert` wire format cannot be verified from this host (the
  OpenAPI spec answers 401 without an operator key). It is isolated in
  `_aktualisiert_value` so exactly one place changes when the first live
  fetch proves the format.
- This WP fetches persons only. DIP documents arrive in later DIP queries;
  the source table lists them, the roadmap's WP-16 scope does not.
- A person with neither fraktion nor Wahlperiode appears in no relationship
  and still lands in `NormalizedRecord.entities`: nothing is dropped
  silently (C-07).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import structlog

from limes.errors import SourceParseError
from limes.sources.base import (
    ONTOLOGY_VERSION,
    deterministic_assertion_id,
    fetch_bytes,
    hash_entity_id,
    key_entity_id,
    now_utc,
    payload_hash,
)
from limes.types import (
    Assertion,
    EntityEndpoint,
    NormalizedRecord,
    Provenance,
    RawRecord,
    Validity,
)

logger = structlog.get_logger(__name__)

# The DIP person search endpoint. The f.known=true filter keeps only persons
# whose record is marked as confirmed.
PERSON_URL = "https://search.dip.bundestag.de/api/v1/person"

# Wahlperiode start dates, the refresh point when a new Wahlperiode begins
# (see the module docstring). Values are ISO dates of the constituent sitting.
WAHLPERIODE_STARTS: dict[int, str] = {
    19: "2017-10-24",
    20: "2021-10-26",
    21: "2025-04-25",
}

JSON_CONTENT_TYPE = "application/json"

# The Office body key: the Bundestag itself. The interval (Wahlperiode) is
# part of the entity identity, not of the deterministic key (DD-13).
OFFICE_BODY_ID = "BT"

_OFFICE_TITLE_PREFIX = "Mitglied des Deutschen Bundestages"


class BundestagDipAdapter:
    """Bundestag DIP — members, parties, and reified offices."""

    source_id = "bundestag_dip"
    name = "Bundestag DIP"
    kind = "structured"
    trust_rank = 1.00
    supports_backfill = True
    supports_incremental = True

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    def fetch(self, since: datetime | None, until: datetime | None) -> Iterator[RawRecord]:
        """One person search response per call, filtered by the window and the
        optional operator API key (see the module docstring on the key)."""
        params: list[tuple[str, str]] = [("f.known", "true")]
        if since is not None or until is not None:
            params.append(("f.aktualisiert", _aktualisiert_value(since, until)))
        if self._api_key:
            params.append(("apikey", self._api_key))
        url = f"{PERSON_URL}?{urlencode(params)}"
        payload = fetch_bytes(url)
        fetched_at = now_utc()
        logger.info(
            "bundestag_dip payload fetched",
            url=url,
            bytes=len(payload),
            fetched_at=fetched_at.isoformat(),
        )
        yield RawRecord(
            payload=payload,
            content_type=JSON_CONTENT_TYPE,
            source_url=url,
            fetched_at=fetched_at,
        )

    def normalize(self, record: RawRecord) -> NormalizedRecord:
        """One person search response to Person / PoliticalParty / Office
        assertions; the pure half of the adapter, no network."""
        document = _parse_document(record.payload)
        rows = document.get("rows")
        if not isinstance(rows, list):
            raise SourceParseError("bundestag_dip: response has no 'rows' list")
        assertions: list[Assertion] = []
        entities: list[EntityEndpoint] = []
        counts = {
            "rows": len(rows),
            "persons": 0,
            "memberships": 0,
            "holds_office": 0,
            "office_at": 0,
            "no_fraktion": 0,
            "no_wahlperioden": 0,
            "unknown_period": 0,
            "standalone_persons": 0,
            "no_name_skipped": 0,
            "malformed_skipped": 0,
        }
        for row in rows:
            if not isinstance(row, dict):
                counts["malformed_skipped"] += 1
                logger.warning("bundestag_dip: person row is not an object; skipped", row=row)
                continue
            person = _person_from_row(row)
            if person is None:
                counts["no_name_skipped"] += 1
                logger.warning(
                    "bundestag_dip: person row without a name skipped",
                    row_id=row.get("id"),
                )
                continue
            counts["persons"] += 1
            assert person.deterministic_key is not None
            bundestag_id = person.deterministic_key[1]
            person_assertions = 0
            fraktion = (row.get("fraktion") or "").strip()
            party = None
            if fraktion:
                party = _party(fraktion)
                assertions.append(
                    _assertion(self, record, person, "MEMBER_OF", party, record.fetched_at)
                )
                counts["memberships"] += 1
                person_assertions += 1
            else:
                counts["no_fraktion"] += 1
                logger.warning(
                    "bundestag_dip: person without fraktion; no MEMBER_OF",
                    bundestag_id=bundestag_id,
                )
            wahlperioden = row.get("wahlperioden") or []
            if not wahlperioden:
                counts["no_wahlperioden"] += 1
                logger.warning(
                    "bundestag_dip: person without wahlperioden; no office assertions",
                    bundestag_id=bundestag_id,
                )
            for period in wahlperioden:
                period_start = _period_start(period)
                if period_start is None:
                    counts["unknown_period"] += 1
                    logger.warning(
                        "bundestag_dip: Wahlperiode without a known start skipped",
                        period=period,
                        bundestag_id=bundestag_id,
                    )
                    continue
                office = _office(period, period_start)
                assertions.append(
                    _assertion(self, record, person, "HOLDS_OFFICE", office, period_start)
                )
                counts["holds_office"] += 1
                person_assertions += 1
                if party is not None:
                    assertions.append(
                        _assertion(self, record, office, "OFFICE_AT", party, period_start)
                    )
                    counts["office_at"] += 1
                    person_assertions += 1
            if person_assertions == 0:
                entities.append(person)
                counts["standalone_persons"] += 1
        logger.info(
            "bundestag_dip: person file normalized",
            source_id=self.source_id,
            **counts,
        )
        return NormalizedRecord(
            content_hash=payload_hash(record.payload),
            kind="structured",
            assertions=assertions,
            entities=entities,
        )


def _parse_document(payload: bytes) -> dict[str, Any]:
    """A DIP response is a JSON object with numFound/start/rows/facets; any
    other payload is a parse error, counted by the caller and skipped."""
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceParseError(f"bundestag_dip: payload is not valid JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise SourceParseError("bundestag_dip: JSON payload is not an object")
    return document


def _person_from_row(row: dict[str, Any]) -> EntityEndpoint | None:
    """The deterministic Person endpoint, or None when the row carries no
    name — the only rows a person search cannot represent as a Person."""
    raw_id = row.get("id")
    if raw_id is None:
        return None
    vorname = (row.get("vorname") or "").strip()
    nachname = (row.get("nachname") or "").strip()
    if not vorname or not nachname:
        return None
    return EntityEndpoint(
        entity_id=key_entity_id(("bundestag_id", str(raw_id))),
        type="Person",
        label=f"{vorname} {nachname}",
        deterministic_key=("bundestag_id", str(raw_id)),
    )


def _party(fraktion: str) -> EntityEndpoint:
    """A party from its DIP label. DIP returns no Wikidata QID, so the name
    is the identity: hashed, not keyed (the loader can still merge a later
    Wikidata-adapter QID onto the same label)."""
    return EntityEndpoint(
        entity_id=hash_entity_id("politicalparty", fraktion),
        type="PoliticalParty",
        label=fraktion,
    )


def _office(period: int, period_start: datetime) -> EntityEndpoint:
    """The reified office of one Wahlperiode: body + title + interval make
    the identity, per the multi-key convention (Doc 1 §5.2, DD-13)."""
    title = f"{_OFFICE_TITLE_PREFIX} (Wahlperiode {period})"
    return EntityEndpoint(
        entity_id=hash_entity_id("office", OFFICE_BODY_ID, title, period_start.isoformat()),
        type="Office",
        label=title,
        deterministic_key=("body_id", OFFICE_BODY_ID),
        aliases=[title],
    )


def _period_start(period: int) -> datetime | None:
    """The constituent sitting of a Wahlperiode as UTC midnight; unknown
    periods return None and are skipped, never invented."""
    raw = WAHLPERIODE_STARTS.get(period)
    if raw is None:
        return None
    return datetime.fromisoformat(raw).replace(tzinfo=UTC)


def _aktualisiert_value(since: datetime | None, until: datetime | None) -> str:
    """The DIP `f.aktualisiert` range value. The wire format is unverified
    from this host (see the module docstring); the open-ended halves express
    a one-sided window."""
    start = since.strftime("%Y-%m-%d") if since is not None else ""
    end = until.strftime("%Y-%m-%d") if until is not None else ""
    return f"{start}..{end}"


def _assertion(
    adapter: BundestagDipAdapter,
    record: RawRecord,
    subject: EntityEndpoint,
    relation: str,
    object_: EntityEndpoint,
    valid_from: datetime,
) -> Assertion:
    return Assertion(
        assertion_id=deterministic_assertion_id(
            adapter.source_id,
            relation,
            subject.entity_id,
            object_.entity_id,
            valid_from,
        ),
        subject=subject,
        relation=relation,
        object=object_,
        validity=Validity(valid_from=valid_from, recorded_at=record.fetched_at),
        provenance=_provenance(adapter, record),
    )


def _provenance(adapter: BundestagDipAdapter, record: RawRecord) -> Provenance:
    return Provenance(
        source_id=adapter.source_id,
        source_trust=adapter.trust_rank,
        confidence=1.0,
        ontology_version=ONTOLOGY_VERSION,
    )
