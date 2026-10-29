# src/limes/sources/offeneregister.py | v1.0.0 | introduced by WP-20
"""OffeneRegister adapter per Technical Specification §8.5.2.

Loads German company directorships from the OffeneRegister dataset (German
Handelsregister data, published by OpenCorporates under CC-BY 4.0). The
dataset is deliberately stale and sits at trust rank 0.30 — the lowest in the
system (Doc 1 §5.8) — and that rank is only safe because the vintage is
honest.

Current unwrapped bzip2 JSONL records include a historical `retrieved_at`
on each company. That source observation time is the assertion's recorded_at,
never the ingestion timestamp or HTTP Last-Modified. Wrapped gzip archives
remain readable with an explicitly provided legacy publication metadata record.
Missing both historical dates is a parse failure; no current-time fallback.

Fetch archives the original compressed snapshot, then bounded chunks whose
manifests retain the original hash and row offset. Normalize never does I/O.

Identity and mapping choices:

- `Corporation` keys on `("german_register_number", company_number)` — the
  OpenCorporates company number is the register identifier (court + register
  type + number).
- Officers carry no deterministic key: persons are name digests
  (`person:...`). German officer names arrive as "Nachname, Vorname"; the
  hash covers the raw trimmed name and the label keeps the source spelling
  verbatim (German source data is stored, never translated).
- The ontology's only Person → Corporation edge is `DIRECTOR_OF`, so every
  officer position (Geschäftsführer, Vorstand, Prokurist, ...) is emitted as
  `DIRECTOR_OF`; the position string has no property slot the loader could
  stamp and is retained in the archived payload. Ownership percentages are
  not part of this dataset, so `OWNS_STAKE_IN` is emitted for none of the
  records; the source table lists it as available where the data provides
  it, and this data does not.
- Officer start/end dates become the assertion's `valid_from`/`valid_to`
  (the `DIRECTOR_OF` interval is exactly what makes "who directed this
  company in March 2025" answerable).
"""

from __future__ import annotations

import bz2
import gzip
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Literal

import structlog
from dateutil import parser as dateutil_parser  # type: ignore[import-untyped]

from limes.errors import SourceParseError
from limes.sources.base import (
    fetch_bytes,
    hash_entity_id,
    key_entity_id,
    make_assertion,
    now_utc,
    payload_hash,
)
from limes.types import (
    Assertion,
    EntityEndpoint,
    NormalizedRecord,
    RawRecord,
)

logger = structlog.get_logger(__name__)

# Advertised on offeneregister.de. Legacy metadata is explicit, never guessed.
DATA_URL = "https://daten.offeneregister.de/de_companies_ocdata.jsonl.bz2"

METADATA_CONTENT_TYPE = "application/json"
DATA_CONTENT_TYPE = "application/gzip"

# Officer positions that are directorships. The ontology has no finer edge
# than DIRECTOR_OF for Person → Corporation; this list is the refresh point
# if the dataset introduces positions that should not be directorships.
# Matching is by stem so gendered forms (Geschäftsführerin, Prokuristin)
# and compounds (Vorstandsvorsitzender) stay directorships.
_DIRECTOR_POSITION_STEMS = ("geschäftsführer", "vorstand", "prokurist", "direktor")

# OpenCorporates wraps every company line in a "company" object.
_COMPANY_KEY = "company"


class OffeneRegisterAdapter:
    """OffeneRegister — German company directorships with honest vintage."""

    source_id: str = "offeneregister"
    name: str = "OffeneRegister"
    kind: Literal["structured", "unstructured"] = "structured"
    trust_rank: float = 0.30
    supports_backfill: bool = False
    supports_incremental: bool = False

    def __init__(self, metadata_url: str | None = None) -> None:
        self._metadata_url = metadata_url
        # The dataset's publication date, set by the metadata record's
        # normalize and consumed by every data record's normalize. In-process
        # state within one run; never a cross-process value (C-07). Refusing
        # to emit without it is the vintage guarantee.
        self._published_at: datetime | None = None

    def fetch(self, since: datetime | None, until: datetime | None) -> Iterator[RawRecord]:
        """Archive original bzip2 JSONL, then yield bounded normalization chunks.

        The window is ignored: the dataset is a snapshot with no delta API
        (`supports_incremental` is False). The data file is large (a
        compressed JSONL of the whole German register); a full load is the
        only load.
        """
        fetched_at = now_utc()
        self._published_at = None
        if self._metadata_url:
            yield RawRecord(
                payload=fetch_bytes(self._metadata_url),
                content_type=METADATA_CONTENT_TYPE,
                source_url=self._metadata_url,
                fetched_at=fetched_at,
            )
        data_payload = fetch_bytes(DATA_URL, max_bytes=512 * 1024 * 1024)
        logger.info(
            "offeneregister: dataset fetched",
            bytes=len(data_payload),
            fetched_at=fetched_at.isoformat(),
        )
        from limes.sources.bulk import bz2_jsonl_records

        yield from bz2_jsonl_records(data_payload, DATA_URL, fetched_at)

    def normalize(self, record: RawRecord) -> NormalizedRecord:
        """Route on the record's content type: metadata or data. Pure —
        never touches the network."""
        if (record.acquisition_context or {}).get("archive_only"):
            return NormalizedRecord(content_hash=payload_hash(record.payload), kind="structured")
        if record.content_type == METADATA_CONTENT_TYPE:
            return self._normalize_metadata(record)
        if record.content_type in (DATA_CONTENT_TYPE, "application/x-bzip2"):
            return self._normalize_data(record)
        raise SourceParseError(f"offeneregister: unknown content type {record.content_type!r}")

    def _normalize_metadata(self, record: RawRecord) -> NormalizedRecord:
        """The dataset's publication date, remembered for every data record
        that follows. Produces no assertions."""
        try:
            data = json.loads(record.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SourceParseError(f"offeneregister: metadata is not valid JSON: {exc}") from exc
        raw_date = data.get("published_at") if isinstance(data, dict) else None
        if not isinstance(raw_date, str) or not raw_date.strip():
            raise SourceParseError("offeneregister: metadata has no published_at date")
        try:
            parsed = dateutil_parser.parse(raw_date, dayfirst=True)
        except (ValueError, TypeError) as exc:
            raise SourceParseError(
                f"offeneregister: unparseable published_at {raw_date!r}"
            ) from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        self._published_at = parsed.astimezone(UTC)
        logger.info(
            "offeneregister: dataset publication date",
            published_at=self._published_at.isoformat(),
            source_id=self.source_id,
        )
        return NormalizedRecord(
            content_hash=payload_hash(record.payload),
            kind="structured",
        )

    def _normalize_data(self, record: RawRecord) -> NormalizedRecord:
        """One JSONL (gzip) of companies → directorships."""
        published_at = self._published_at
        try:
            unpack = (
                bz2.decompress if record.content_type == "application/x-bzip2" else gzip.decompress
            )
            text = unpack(record.payload).decode("utf-8")
        except (ValueError, EOFError, OSError, UnicodeDecodeError) as exc:
            raise SourceParseError("offeneregister: invalid compressed UTF-8 JSONL") from exc

        assertions: list[Assertion] = []
        entities: list[EntityEndpoint] = []
        companies = 0
        malformed_lines = 0
        skipped_no_number = 0
        skipped_no_officers = 0
        officer_count = 0
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                malformed_lines += 1
                logger.warning("offeneregister: unparseable JSONL line; skipped")
                continue
            company_obj = obj.get(_COMPANY_KEY, obj) if isinstance(obj, dict) else None
            if not isinstance(company_obj, dict):
                malformed_lines += 1
                continue
            companies += 1
            vintage = _parse_officer_date(company_obj.get("retrieved_at")) or published_at
            if vintage is None:
                raise SourceParseError(
                    "offeneregister: no source retrieved_at or publication date; "
                    "refusing a wall-clock vintage"
                )
            number = (company_obj.get("company_number") or "").strip()
            name = (company_obj.get("name") or "").strip()
            if not number or not name:
                skipped_no_number += 1
                logger.warning(
                    "offeneregister: company without register number or name; skipped",
                    company_number=number,
                )
                continue
            corporation = EntityEndpoint(
                entity_id=key_entity_id(("german_register_number", number)),
                type="Corporation",
                label=name,
                deterministic_key=("german_register_number", number),
            )
            entities.append(corporation)
            officers = company_obj.get("officers") or []
            if not officers:
                skipped_no_officers += 1
                continue
            for officer in officers:
                if not isinstance(officer, dict):
                    malformed_lines += 1
                    continue
                officer_name = (officer.get("name") or "").strip()
                position = (officer.get("position") or "").strip()
                if not officer_name:
                    continue
                if not any(stem in position.lower() for stem in _DIRECTOR_POSITION_STEMS):
                    logger.warning(
                        "offeneregister: non-director position skipped",
                        company_number=number,
                        position=position,
                    )
                    continue
                person = EntityEndpoint(
                    entity_id=hash_entity_id("person", officer_name),
                    type="Person",
                    label=officer_name,
                )
                valid_from = _parse_officer_date(officer.get("start_date")) or vintage
                valid_to = _parse_officer_date(officer.get("end_date"))
                assertions.append(
                    make_assertion(
                        self,
                        record,
                        person,
                        "DIRECTOR_OF",
                        corporation,
                        valid_from=valid_from,
                        valid_to=valid_to,
                        recorded_at=vintage,
                    )
                )
                officer_count += 1
        logger.info(
            "offeneregister: dataset normalized",
            companies=companies,
            director_assertions=officer_count,
            malformed_lines=malformed_lines,
            companies_without_number_or_name=skipped_no_number,
            companies_without_officers=skipped_no_officers,
            recorded_at_basis="per-company retrieved_at or explicit legacy publication metadata",
            source_id=self.source_id,
        )
        return NormalizedRecord(
            content_hash=payload_hash(record.payload),
            kind="structured",
            assertions=assertions,
            entities=entities,
            errors=malformed_lines + skipped_no_number,
        )


def _parse_officer_date(raw: object) -> datetime | None:
    """An officer date (ISO) as an aware UTC instant, or None when absent or
    unparseable. A bad date is not a reason to drop a directorship: the start
    falls back to the publication date at the call site, the end to an open
    interval, and the raw value stays in the archived payload. The wall clock
    never enters: the fallback for a missing end is "no end known", not now."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw.strip())
    except ValueError:
        logger.warning("offeneregister: unparseable officer date", raw=raw)
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
