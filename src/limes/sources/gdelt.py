# src/limes/sources/gdelt.py | v1.0.0 | introduced by WP-21
"""GDELT 2.0 coded observations, not article text.

Official 15-minute exports are single-member ZIPs of 61-column UTF-8 TSV.
SQLDATE is event validity; DATEADDED is the coding timestamp, not publication.
Each row retains archive/member/row/report identity. Missing article text and
export-only report coverage are explicit; Mentions acquisition belongs to BE-43.
Actor typing remains bounded by the ontology; unsupported actors are counted.
"""

from __future__ import annotations

import csv
import io
import math
import re
import zipfile
import zlib
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Literal

import structlog

from limes.errors import SourceParseError
from limes.sources.base import (
    coordinate_location,
    fetch_bytes,
    hash_entity_id,
    key_entity_id,
    make_assertion,
    now_utc,
    payload_hash,
)
from limes.sources.gdelt_countries import FIPS_TO_ISO2
from limes.types import (
    Assertion,
    EntityEndpoint,
    NormalizedRecord,
    RawRecord,
)

logger = structlog.get_logger(__name__)

# The GDELT 2.0 events export. The file name is the 15-minute slot's end
# instant as UTC YYYYMMDDHHMMSS (seconds always 00); the URL constant is the
# single refresh point (D-17).
GDELT_BASE_URL = "https://data.gdeltproject.org/gdeltv2"
FILE_URL_TEMPLATE = f"{GDELT_BASE_URL}/{{slot:%Y%m%d%H%M%S}}.export.CSV.zip"

EVENTS_CONTENT_TYPE = "application/zip"
MAX_COMPRESSED_BYTES = 16 * 1024 * 1024
MAX_EXPANDED_BYTES = 128 * 1024 * 1024
MAX_ROWS = 250_000
MAX_SLOTS = 96

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
    "Actor1Geo_ADM2Code",
    "Actor1Geo_Lat",
    "Actor1Geo_Long",
    "Actor1Geo_FeatureID",
    "Actor2Geo_Type",
    "Actor2Geo_FullName",
    "Actor2Geo_CountryCode",
    "Actor2Geo_ADM1Code",
    "Actor2Geo_ADM2Code",
    "Actor2Geo_Lat",
    "Actor2Geo_Long",
    "Actor2Geo_FeatureID",
    "ActionGeo_Type",
    "ActionGeo_FullName",
    "ActionGeo_CountryCode",
    "ActionGeo_ADM1Code",
    "ActionGeo_ADM2Code",
    "ActionGeo_Lat",
    "ActionGeo_Long",
    "ActionGeo_FeatureID",
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
# 3 = US city, 4 = world city, 5 = world ADM1. Country FIPS codes are
# explicitly converted; coordinate types become coordinate-hash Locations.
_GEO_TYPE_COUNTRY = "1"


class GdeltAdapter:
    """GDELT 2.0 deterministic coded observations with row-scoped provenance."""

    source_id: str = "gdelt"
    name: str = "GDELT"
    kind: Literal["structured", "unstructured"] = "structured"
    trust_rank: float = 0.50
    supports_backfill: bool = True
    supports_incremental: bool = True

    def fetch(self, since: datetime | None, until: datetime | None) -> Iterator[RawRecord]:
        """Fetch at most one day (96 slots); larger windows fail before I/O.

        Callers can submit consecutive bounded windows. Legacy budgets do not
        limit work. Missing slots abort without advancing the checkpoint.
        """
        start = _first_slot(since, until)
        end = until if until is not None else now_utc()
        end = end.replace(tzinfo=UTC) if end.tzinfo is None else end.astimezone(UTC)
        if end < start:
            return
        if (end - start) // _SLOT + 1 > MAX_SLOTS:
            from limes.errors import SourceFetchError

            raise SourceFetchError("gdelt: window exceeds 96 slots; submit bounded windows")
        slot = start
        while slot <= end:
            url = FILE_URL_TEMPLATE.format(slot=slot)
            payload = fetch_bytes(url, max_bytes=MAX_COMPRESSED_BYTES)
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
        """Parse an official export; retain original row locators and report links.

        Pure: no graph/network access and no fabricated article/extraction input.
        Malformed event identities are counted and block checkpoint advancement.
        """
        member, rows = _parse_export(record.payload)
        assertions: list[Assertion] = []
        entities: list[EntityEndpoint] = []
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
        for row_number, row in enumerate(rows, 1):
            event_id = (row.get("GLOBALEVENTID") or "").strip()
            occurred_at = _parse_sqldate(row.get("SQLDATE"))
            if not event_id or occurred_at is None:
                counts["malformed_skipped"] += 1
                logger.warning("gdelt: row without event id or date skipped")
                continue
            counts["events"] += 1

            event = _event(event_id, occurred_at)
            entities.append(event)
            first_assertion = len(assertions)
            actor1 = _actor(row, "1")
            actor2 = _actor(row, "2")
            if actor1 is not None:
                assertions.append(
                    make_assertion(
                        self,
                        record,
                        actor1,
                        "ACTOR_IN",
                        event,
                        valid_from=occurred_at,
                    )
                )
                counts["actor_in"] += 1
            else:
                counts["untyped_actor_skipped"] += 1
            if actor2 is not None:
                assertions.append(
                    make_assertion(
                        self,
                        record,
                        actor2,
                        "TARGET_OF",
                        event,
                        valid_from=occurred_at,
                    )
                )
                counts["target_of"] += 1
            else:
                counts["untyped_actor_skipped"] += 1

            location = _action_location(row)
            if location is not None:
                assertions.append(
                    make_assertion(
                        self,
                        record,
                        event,
                        "OCCURRED_IN",
                        location,
                        valid_from=occurred_at,
                    )
                )
                counts["occurred_in"] += 1
            else:
                counts["location_skipped"] += 1

            for assertion in assertions[first_assertion:]:
                provenance = assertion.provenance
                provenance.evidence_document_id = payload_hash(record.payload)
                provenance.evidence_channel = "coded"
                provenance.evidence_member = member
                provenance.evidence_row = row_number
                provenance.source_event_id = event_id
                provenance.source_url = record.source_url
                provenance.report_url = row.get("SOURCEURL") or None
                provenance.source_recorded_at = _parse_dateadded(row.get("DATEADDED"))
                provenance.article_text_available = False
                # Preserve separate observations even when facts match across exports.
                assertion.assertion_id = hash_entity_id(
                    "coded", assertion.assertion_id, payload_hash(record.payload), str(row_number)
                )

        logger.info(
            "gdelt: event file normalized",
            source_id=self.source_id,
            **counts,
        )
        return NormalizedRecord(
            content_hash=payload_hash(record.payload),
            kind="structured",
            assertions=assertions,
            entities=entities,
            errors=counts["malformed_skipped"],
        )


def _parse_export(payload: bytes) -> tuple[str, list[dict[str, str]]]:
    """Bound compressed input, member count/name, expansion, fields and rows.

    No filesystem extraction. Reject schema drift rather than shifting columns.
    """
    if len(payload) > MAX_COMPRESSED_BYTES:
        raise SourceParseError("gdelt: compressed export exceeds limit")
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            members = archive.infolist()
            if len(members) != 1:
                raise SourceParseError("gdelt: expected exactly one ZIP member")
            info = members[0]
            if not re.fullmatch(r"[0-9]{14}\.export\.CSV", info.filename):
                raise SourceParseError("gdelt: invalid export member name")
            if info.file_size > MAX_EXPANDED_BYTES:
                raise SourceParseError("gdelt: expanded export exceeds limit")
            with archive.open(info) as stream:
                data = stream.read(MAX_EXPANDED_BYTES + 1)
            if len(data) > MAX_EXPANDED_BYTES:
                raise SourceParseError("gdelt: expanded export exceeds limit")
        reader = csv.reader(io.StringIO(data.decode("utf-8")), delimiter="\t", strict=True)
        rows = []
        for number, fields in enumerate(reader, 1):
            if number > MAX_ROWS or len(fields) != 61:
                raise SourceParseError(f"gdelt: invalid row {number}: expected 61 fields")
            rows.append(dict(zip(_GDELT_FIELDS, fields, strict=True)))
        return info.filename, rows
    except (
        zipfile.BadZipFile,
        UnicodeError,
        csv.Error,
        RuntimeError,
        OSError,
        EOFError,
        NotImplementedError,
        zlib.error,
    ) as exc:
        raise SourceParseError("gdelt: invalid ZIP/TSV export") from exc


def _parse_dateadded(raw: str | None) -> datetime | None:
    try:
        return datetime.strptime(raw or "", "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return None


def _first_slot(since: datetime | None, until: datetime | None) -> datetime:
    """The first 15-minute boundary at or after `since`, or the current time
    when `since` is None (a run without an explicit window fetches nothing
    until the next slot boundary — the window always has a start)."""
    anchor = since if since is not None else now_utc()
    anchor = anchor.replace(tzinfo=UTC) if anchor.tzinfo is None else anchor.astimezone(UTC)
    slot = anchor.replace(second=0, microsecond=0)
    slot -= timedelta(minutes=slot.minute % 15)
    if slot < anchor:
        slot += _SLOT
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
        country_code = FIPS_TO_ISO2.get(country_code, "")
        if country_code:
            label = full_name or country_code
            return EntityEndpoint(
                entity_id=key_entity_id(("iso2", country_code)),
                type="Country",
                label=label,
                deterministic_key=("iso2", country_code),
            )
        return None
    if geo_type in ("2", "3", "4", "5"):
        lat = _parse_float(row.get("ActionGeo_Lat"))
        lon = _parse_float(row.get("ActionGeo_Long"))
        if (
            lat is not None
            and lon is not None
            and full_name
            and -90 <= lat <= 90
            and -180 <= lon <= 180
        ):
            return coordinate_location(lat, lon, label=full_name)
        return None
    return None


def _parse_float(raw: object) -> float | None:
    if not isinstance(raw, str):
        return None
    try:
        value = float(raw)
        return value if math.isfinite(value) else None
    except ValueError:
        return None
