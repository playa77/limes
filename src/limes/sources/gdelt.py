# src/limes/sources/gdelt.py | v1.0.0 | introduced by WP-21
"""GDELT adapter per Technical Specification §8.5.2 (WP-21).

Loads events from the GDELT 2.0 event export (15-minute CSV files) into
`Event` nodes with `ACTOR_IN`, `TARGET_OF`, and `OCCURRED_IN` edges, plus one
`DocumentPayload` per file for passage extraction. Trust rank 0.50 (Doc 1
§5.8); the deterministic event facts carry confidence 1.0 (D-15 — they are
parsed data, not model output), and trust differentiation happens through the
source rank alone.

Non-obvious choices, each load-bearing:

- **One RawRecord per 15-minute file** (the roadmap's letter), and one
  `NormalizedRecord` per file: the event assertions for every row plus one
  document whose body is the joined per-row summaries. The window bounds the
  *file set*; within a file every row is normalized.
- **Actor typing is the ontology gap.** `ACTOR_IN`/`TARGET_OF` take an
  `Agent` domain and the ontology has no Agent type for a sovereign state
  (`Country` is a `Place`), so a bare-country actor code (e.g. "USA", "RUS")
  cannot be represented and the edge is skipped — with a count, never
  silently. What *is* representable: GDELT's own actor type codes (the
  `Actor1Type1Code` column): `GOV`/`MIL`/`COP`/`JUD` become `PublicBody`
  (state organs), `BUS` becomes `Corporation`. The type table is the refresh
  point if the CAMEO taxonomy evolves. Actor identity is the name digest —
  GDELT assigns no stable identifier to an actor.
- **Event identity** follows the multi-key convention (D-10): the stampable
  single declared key is `("source_event_id", GLOBALEVENTID)`, and the
  `entity_id` encodes the full identity (source event id + `occurred_at`).
- **The action geography** (where the event occurred) drives `OCCURRED_IN`:
  Geo_Type 1 (country) becomes a `Country` keyed on its ISO2 code; Geo_Type 2
  (ADM1) and 3 (city) become `Location` nodes whose identity is the rounded
  coordinate digest (the D-13 convention, as in the OSM adapter). A row
  without usable geography gets no `OCCURRED_IN` — counted.
- **`published_at` is the file's latest SQLDATE**, the events' vintage, never
  the fetch instant. The SQLDATE column is the event date at UTC midnight.
- **Window semantics:** `supports_incremental = True`, so window resolution
  anchors at `Source.last_success_at`; fetch iterates the 15-minute slots in
  the window, one GET per slot, sequentially and without concurrency (the
  GDELT service is not consulted more than once per slot). A 90-day backfill
  is ~8 640 files — that is the source's own granularity, and the run's
  explicit budget is what bounds it in practice.

The CSV column order follows the documented GDELT 2.0 event header, kept here
as the single refresh point (D-17: unverified endpoints and formats are
declared, never assumed).
"""

from __future__ import annotations

import csv
import hashlib
import io
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Literal

import structlog

from limes.errors import SourceParseError
from limes.pipeline.normalize import detect_language
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
    DocumentPayload,
    EntityEndpoint,
    NormalizedRecord,
    Provenance,
    RawRecord,
    Validity,
)

logger = structlog.get_logger(__name__)

# The GDELT 2.0 events export. The file name is the 15-minute slot's end
# instant as UTC YYYYMMDDHHMMSS (seconds always 00); the URL constant is the
# single refresh point (D-17).
GDELT_BASE_URL = "https://data.gdeltproject.org/gdelt2"
FILE_URL_TEMPLATE = f"{GDELT_BASE_URL}/{{slot:%Y%m%d%H%M%S}}00.events.csv"

EVENTS_CONTENT_TYPE = "text/csv"

# The GDELT 2.0 event CSV column order, from the documented header. The
# adapter reads positionally through these names; this list is the single
# refresh point if the export format changes.
_GDELT_FIELDS = [
    "GLOBALEVENTID",
    "SQLDATE",
    "MonthYear",
    "Year",
    "FractionDate",
    "Actor1Code",
    "Actor1Name",
    "Actor1CountryCode",
    "Actor1KnownGroupCode",
    "Actor1EthnicCode",
    "Actor1Religion1Code",
    "Actor1Religion2Code",
    "Actor1Type1Code",
    "Actor1Type2Code",
    "Actor1Type3Code",
    "Actor2Code",
    "Actor2Name",
    "Actor2CountryCode",
    "Actor2KnownGroupCode",
    "Actor2EthnicCode",
    "Actor2Religion1Code",
    "Actor2Religion2Code",
    "Actor2Type1Code",
    "Actor2Type2Code",
    "Actor2Type3Code",
    "IsRootEvent",
    "EventCode",
    "EventBaseCode",
    "EventRootCode",
    "QuadClass",
    "GoldsteinScale",
    "NumMentions",
    "NumSources",
    "NumArticles",
    "AvgTone",
    "Actor1Geo_Type",
    "Actor1Geo_FullName",
    "Actor1Geo_CountryCode",
    "Actor1Geo_ADM1Code",
    "Actor1Geo_Lat",
    "Actor1Geo_Long",
    "Actor2Geo_Type",
    "Actor2Geo_FullName",
    "Actor2Geo_CountryCode",
    "Actor2Geo_ADM1Code",
    "Actor2Geo_Lat",
    "Actor2Geo_Long",
    "ActionGeo_Type",
    "ActionGeo_FullName",
    "ActionGeo_CountryCode",
    "ActionGeo_ADM1Code",
    "ActionGeo_Lat",
    "ActionGeo_Long",
    "DATEADDED",
    "SOURCEURL",
]

# The 15-minute slot length. Files are published at each slot boundary.
_SLOT = timedelta(minutes=15)

# GDELT actor type codes (the CAMEO Actor1Type1Code column) and the ontology
# type they map to. Codes absent from this table are skipped with a count:
# state actors are the characteristic case (see the module docstring).
_ACTOR_TYPE_TO_ONTOLOGY = {
    "GOV": "PublicBody",  # government
    "MIL": "PublicBody",  # military
    "COP": "PublicBody",  # police
    "JUD": "PublicBody",  # judiciary
    "BUS": "Corporation",  # business
}

# GDELT action geography types: 1 = country, 2 = first-order division (ADM1),
# 3 = city. 1 becomes a Country (ISO2 key), 2/3 become coordinate-hash
# Locations; anything else gets no OCCURRED_IN edge.
_GEO_TYPE_COUNTRY = "1"


class GdeltAdapter:
    """GDELT 2.0 events — deterministic event facts plus per-file documents."""

    source_id: str = "gdelt"
    name: str = "GDELT"
    kind: Literal["structured", "unstructured"] = "unstructured"
    trust_rank: float = 0.50
    supports_backfill: bool = True
    supports_incremental: bool = True

    def fetch(self, since: datetime | None, until: datetime | None) -> Iterator[RawRecord]:
        """Fetch one 15-minute event file per slot in the window.

        The slot list is the 15-minute boundaries from `since` (rounded up to
        the next boundary) through `until` — or the current time when `until`
        is None. Each file is one GET, sequential, no concurrency. A missing
        slot surfaces as `SourceFetchError` (the shared retry policy applies
        to transient failures only); the run's budget is what bounds a long
        window in practice.
        """
        start = _first_slot(since, until)
        end = until if until is not None else now_utc()
        if end < start:
            return
        slot = start
        while slot <= end:
            url = FILE_URL_TEMPLATE.format(slot=slot)
            payload = fetch_bytes(url)
            fetched_at = now_utc()
            logger.info(
                "gdelt: event file fetched",
                url=url,
                bytes=len(payload),
                fetched_at=fetched_at.isoformat(),
            )
            yield RawRecord(
                payload=payload,
                content_type=EVENTS_CONTENT_TYPE,
                source_url=url,
                fetched_at=fetched_at,
            )
            slot += _SLOT

    def normalize(self, record: RawRecord) -> NormalizedRecord:
        """Parse one event CSV file into Event assertions plus a document.

        Pure — never touches the network. Every row becomes an Event; actor
        edges are emitted only where the actor type is representable in the
        ontology (see the module docstring), and every skip is counted in the
        summary log.
        """
        rows = _parse_csv(record.payload)
        assertions: list[Assertion] = []
        summaries: list[str] = []
        counts = {
            "rows": len(rows),
            "events": 0,
            "actor_in": 0,
            "target_of": 0,
            "occurred_in": 0,
            "untyped_actor_skipped": 0,
            "location_skipped": 0,
            "malformed_skipped": 0,
        }
        latest_date: datetime | None = None
        for row in rows:
            event_id = (row.get("GLOBALEVENTID") or "").strip()
            occurred_at = _parse_sqldate(row.get("SQLDATE"))
            if not event_id or occurred_at is None:
                counts["malformed_skipped"] += 1
                logger.warning("gdelt: row without event id or date skipped")
                continue
            counts["events"] += 1
            if latest_date is None or occurred_at > latest_date:
                latest_date = occurred_at

            event = _event(event_id, occurred_at)
            actor1 = _actor(row, "1")
            actor2 = _actor(row, "2")
            if actor1 is not None:
                assertions.append(
                    _actor_assertion(self, record, actor1, event, "ACTOR_IN", occurred_at)
                )
                counts["actor_in"] += 1
            else:
                counts["untyped_actor_skipped"] += 1
            if actor2 is not None:
                assertions.append(
                    _actor_assertion(self, record, actor2, event, "TARGET_OF", occurred_at)
                )
                counts["target_of"] += 1
            else:
                counts["untyped_actor_skipped"] += 1

            location = _action_location(row)
            if location is not None:
                assertions.append(
                    _actor_assertion(self, record, event, location, "OCCURRED_IN", occurred_at)
                )
                counts["occurred_in"] += 1
            else:
                counts["location_skipped"] += 1

            code = (row.get("EventCode") or "").strip()
            summary_parts = [row.get("Actor1Name")]
            if code:
                summary_parts.append(f"[{code}]")
            summary_parts.append(row.get("Actor2Name"))
            summaries.append(" — ".join(part for part in summary_parts if part))

        published_at = latest_date if latest_date is not None else record.fetched_at
        file_name = record.source_url.rsplit("/", 1)[-1] if record.source_url else "GDELT events"
        body = "\n".join(summaries).strip()
        document = DocumentPayload(
            content_hash=payload_hash(record.payload),
            title=f"GDELT events {file_name}",
            body=body,
            language=detect_language(body) if body else "en",
            published_at=published_at,
            url=record.source_url,
        )
        logger.info(
            "gdelt: event file normalized",
            source_id=self.source_id,
            **counts,
        )
        return NormalizedRecord(
            content_hash=payload_hash(record.payload),
            kind="document",
            assertions=assertions,
            document=document,
        )


def _parse_csv(payload: bytes) -> list[dict[str, str]]:
    """Decode a GDELT events CSV into row dicts.

    The files carry no header row; the documented column order is applied via
    `_GDELT_FIELDS`. A payload that is not decodable UTF-8 or not parseable as
    CSV is a `SourceParseError` — a counted record-level skip, never a silent
    empty.
    """
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SourceParseError(f"gdelt: payload is not UTF-8: {exc}") from exc
    reader = csv.DictReader(io.StringIO(text), fieldnames=_GDELT_FIELDS, restkey="_extra")
    try:
        rows = [row for row in reader if any(row.values())]
    except csv.Error as exc:
        raise SourceParseError(f"gdelt: unparseable CSV: {exc}") from exc
    return rows


def _first_slot(since: datetime | None, until: datetime | None) -> datetime:
    """The first 15-minute boundary at or after `since`, or the current time
    when `since` is None (a run without an explicit window fetches nothing
    until the next slot boundary — the window always has a start)."""
    anchor = since if since is not None else now_utc()
    anchor = anchor if anchor.tzinfo is not None else anchor.replace(tzinfo=UTC)
    slot = anchor.replace(second=0, microsecond=0)
    if slot.minute % 15:
        slot += timedelta(minutes=15 - slot.minute % 15)
    return slot


def _parse_sqldate(raw: object) -> datetime | None:
    """A GDELT SQLDATE (YYYYMMDD) as UTC midnight, or None when absent or
    malformed — such rows are counted and skipped."""
    if not isinstance(raw, str) or len(raw) != 8 or not raw.isdigit():
        return None
    try:
        return datetime.strptime(raw, "%Y%m%d").replace(tzinfo=UTC)
    except ValueError:
        return None


def _event(event_id: str, occurred_at: datetime) -> EntityEndpoint:
    """The Event endpoint: full identity in the hash, the stampable single
    declared key as the deterministic key (D-10)."""
    return EntityEndpoint(
        entity_id=hash_entity_id("event", event_id, occurred_at.isoformat()),
        type="Event",
        label=f"GDELT event {event_id}",
        deterministic_key=("source_event_id", event_id),
    )


def _actor(row: dict[str, str], which: str) -> EntityEndpoint | None:
    """The actor endpoint for Actor1/Actor2, typed by the GDELT type code, or
    None when the code names no representable Agent type (counted by the
    caller). The identity is the actor name digest — GDELT assigns no stable
    actor identifier."""
    code = (row.get(f"Actor{which}Type1Code") or "").strip()
    name = (row.get(f"Actor{which}Name") or "").strip()
    if not code or not name:
        return None
    ontology_type = _ACTOR_TYPE_TO_ONTOLOGY.get(code)
    if ontology_type is None:
        logger.warning(
            "gdelt: actor type not representable in the ontology",
            actor_type_code=code,
            actor_name=name,
        )
        return None
    return EntityEndpoint(
        entity_id=hash_entity_id(ontology_type.lower(), name),
        type=ontology_type,
        label=name,
    )


def _action_location(row: dict[str, str]) -> EntityEndpoint | None:
    """The action geography as a Country or Location endpoint, or None when
    the row carries no usable geography (counted by the caller)."""
    geo_type = (row.get("ActionGeo_Type") or "").strip()
    full_name = (row.get("ActionGeo_FullName") or "").strip()
    if geo_type == _GEO_TYPE_COUNTRY:
        country_code = (row.get("ActionGeo_CountryCode") or "").strip().upper()
        if _is_iso2(country_code):
            label = full_name or country_code
            return EntityEndpoint(
                entity_id=key_entity_id(("iso2", country_code)),
                type="Country",
                label=label,
                deterministic_key=("iso2", country_code),
            )
        return None
    if geo_type in ("2", "3"):
        lat = _parse_float(row.get("ActionGeo_Lat"))
        lon = _parse_float(row.get("ActionGeo_Long"))
        if lat is not None and lon is not None and full_name:
            return _coordinate_location(lat, lon, full_name)
        return None
    return None


def _is_iso2(code: str) -> bool:
    """A plausible ISO 3166-1 alpha-2 code: exactly two ASCII letters. GDELT's
    country codes are ISO2; the 2-letter shape is the sanity bound — the
    loader's unique constraint on `iso2` is the dedup."""
    return len(code) == 2 and code.isalpha()


def _parse_float(raw: object) -> float | None:
    if not isinstance(raw, str):
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _coordinate_location(lat: float, lon: float, label: str) -> EntityEndpoint:
    """A Location whose identity is the rounded-coordinate digest (D-13), the
    same convention as the OSM adapter: the hash is identity, never geometry."""
    coordinate_key = f"{lat:.5f},{lon:.5f}"
    digest = hashlib.sha256(coordinate_key.encode("utf-8")).hexdigest()
    return EntityEndpoint(
        entity_id=key_entity_id(("coordinate_hash", digest)),
        type="Location",
        label=label,
        deterministic_key=("coordinate_hash", digest),
    )


def _actor_assertion(
    adapter: GdeltAdapter,
    record: RawRecord,
    subject: EntityEndpoint,
    object_: EntityEndpoint,
    relation: str,
    occurred_at: datetime,
) -> Assertion:
    return Assertion(
        assertion_id=deterministic_assertion_id(
            adapter.source_id,
            relation,
            subject.entity_id,
            object_.entity_id,
            occurred_at,
        ),
        subject=subject,
        relation=relation,
        object=object_,
        validity=Validity(valid_from=occurred_at, recorded_at=record.fetched_at),
        provenance=Provenance(
            source_id=adapter.source_id,
            source_trust=adapter.trust_rank,
            confidence=1.0,
            ontology_version=ONTOLOGY_VERSION,
        ),
    )
