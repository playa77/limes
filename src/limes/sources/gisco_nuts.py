# src/limes/sources/gisco_nuts.py | v1.0.0 | introduced by WP-10
"""GISCO/NUTS adapter per Technical Specification §8.5.2.

Loads the administrative backbone: `AdministrativeRegion` entities, the NUTS
hierarchy as `PART_OF_REGION`, and the postal-code-to-NUTS correspondence as
`LookupRow(kind="postal_code")` — the first cross-process reference data in
the system (C-07, DD-20). The correspondence is produced here, consumed by
GLEIF, TED, and OSM in separate processes via `graph/lookups.py`, and never
stored in module state or a derived file.

The NUTS hierarchy file carries no level column (verified against the live
file, Doc 2 §8.5.2): level derives from `NUTS_ID` length — 2 chars is the
country itself, 3 NUTS1, 4 NUTS2, 5 NUTS3 — and the parent region is the
`NUTS_ID` minus its last character. The postcode file uses mixed single and
double quoting; `_parse_rows` normalizes single-quoted fields to the
double-quoted form the CSV module understands, so a quoted field containing a
comma parses as one field, not two.

Both files are static snapshots: the adapter is non-incremental, `fetch`
ignores the window and yields one `RawRecord` per file, and every assertion's
`valid_from` is the fetch instant.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterator
from datetime import datetime
from typing import Literal

import structlog

from limes.errors import SourceParseError
from limes.sources.base import (
    ONTOLOGY_VERSION,
    deterministic_assertion_id,
    fetch_bytes,
    key_entity_id,
    now_utc,
    payload_hash,
)
from limes.types import (
    Assertion,
    EntityEndpoint,
    LookupRow,
    NormalizedRecord,
    Provenance,
    RawRecord,
    Validity,
)

logger = structlog.get_logger(__name__)

# Verified live (2026-08): the 2024 hierarchy CSV is a whole-EU flat table
# (`NUTS_AT_2024.csv` is the file's official name), and the postcode
# correspondence lives at /v2/pcode/csv/, not /postalcodes/.
NUTS_URL = "https://gisco-services.ec.europa.eu/distribution/v2/nuts/csv/NUTS_AT_2024.csv"
POSTCODE_URL = (
    "https://gisco-services.ec.europa.eu/distribution/v2/pcode/csv/PCODE_PT_2024_4326.csv"
)

NUTS_CONTENT_TYPE = "text/csv; charset=utf-8"

_SINGLE_QUOTED = re.compile(r"'([^']*)'")


class GiscoNutsAdapter:
    """GISCO/NUTS — administrative regions, hierarchy, postal correspondence."""

    source_id: str = "gisco_nuts"
    name: str = "GISCO/NUTS"
    kind: Literal["structured", "unstructured"] = "structured"
    trust_rank: float = 1.00
    supports_backfill: bool = False
    supports_incremental: bool = False

    def fetch(self, since: datetime | None, until: datetime | None) -> Iterator[RawRecord]:
        """Fetch both CSV files. The window is ignored: static snapshots are
        always full loads (§8.6.2 — `supports_incremental` is False)."""
        fetched_at = now_utc()
        for url in (NUTS_URL, POSTCODE_URL):
            payload = fetch_bytes(url)
            logger.info(
                "gisco payload fetched",
                url=url,
                bytes=len(payload),
                fetched_at=fetched_at.isoformat(),
            )
            yield RawRecord(
                payload=payload,
                content_type=NUTS_CONTENT_TYPE,
                source_url=url,
                fetched_at=fetched_at,
            )

    def normalize(self, record: RawRecord) -> NormalizedRecord:
        """One file → assertions (hierarchy) or lookup rows (postcodes)."""
        text = record.payload.decode("utf-8-sig", errors="replace")
        header = text.splitlines()[0] if text.splitlines() else ""

        if "CNTR_CODE" in header:
            return self._normalize_hierarchy(text, record)
        if "POSTCODE" in header:
            return self._normalize_postcodes(text, record)
        raise SourceParseError(f"gisco_nuts: unrecognized payload (first line: {header[:80]!r})")

    def _normalize_hierarchy(self, text: str, record: RawRecord) -> NormalizedRecord:
        rows = _parse_rows(text)
        if len(rows) < 2:
            raise SourceParseError("gisco_nuts: NUTS hierarchy file has no data rows")

        names: dict[str, str] = {row[1]: row[2] for row in rows}
        assertions: list[Assertion] = []
        for row in rows:
            nuts_id = row[1]
            name = row[2]
            if len(nuts_id) == 2:
                continue  # the country row itself; regions reference it below
            parent_id = nuts_id[:-1]
            if parent_id not in names:
                logger.warning(
                    "gisco_nuts: parent region missing from file; skipped",
                    nuts_id=nuts_id,
                    parent=parent_id,
                )
                continue
            region = EntityEndpoint(
                entity_id=key_entity_id(("nuts_code", nuts_id)),
                type="AdministrativeRegion",
                label=name,
                deterministic_key=("nuts_code", nuts_id),
            )
            parent_is_country = len(parent_id) == 2
            parent = EntityEndpoint(
                entity_id=key_entity_id(
                    ("iso2", parent_id) if parent_is_country else ("nuts_code", parent_id)
                ),
                type="Country" if parent_is_country else "AdministrativeRegion",
                label=names[parent_id],
                deterministic_key=(
                    ("iso2", parent_id) if parent_is_country else ("nuts_code", parent_id)
                ),
            )
            validity = Validity(valid_from=record.fetched_at, recorded_at=record.fetched_at)
            assertions.append(
                Assertion(
                    assertion_id=deterministic_assertion_id(
                        self.source_id,
                        "PART_OF_REGION",
                        region.entity_id,
                        parent.entity_id,
                        record.fetched_at,
                    ),
                    subject=region,
                    relation="PART_OF_REGION",
                    object=parent,
                    validity=validity,
                    provenance=_provenance(self, record),
                )
            )
        logger.info(
            "gisco_nuts: hierarchy normalized",
            records=len(rows),
            assertions=len(assertions),
            source_id=self.source_id,
        )
        return NormalizedRecord(
            content_hash=payload_hash(record.payload),
            kind="structured",
            assertions=assertions,
        )

    def _normalize_postcodes(self, text: str, record: RawRecord) -> NormalizedRecord:
        rows = _parse_rows(text)
        if len(rows) < 2:
            raise SourceParseError("gisco_nuts: postcode file has no data rows")

        lookup_rows: list[LookupRow] = []
        skipped = 0
        for row in rows[1:]:
            if len(row) < 7:
                skipped += 1
                continue
            postal_code, country_code, nuts3 = row[0], row[1], row[6]
            if not postal_code or not country_code or not nuts3:
                skipped += 1
                continue
            lookup_rows.append(
                LookupRow(
                    kind="postal_code",
                    key={"country_code": country_code, "postal_code": postal_code},
                    value={"nuts_code": nuts3},
                )
            )
        logger.info(
            "gisco_nuts: postcodes normalized",
            records=len(rows) - 1,
            lookup_rows=len(lookup_rows),
            skipped=skipped,
            source_id=self.source_id,
        )
        return NormalizedRecord(
            content_hash=payload_hash(record.payload),
            kind="structured",
            lookup_rows=lookup_rows,
        )


def _parse_rows(text: str) -> list[list[str]]:
    """Parse a GISCO CSV line by line, normalizing single-quoted fields.

    `csv.reader` understands double quotes only; the postcode file wraps some
    fields in single quotes, so those are rewritten to double quotes first.
    This keeps a quoted field containing a comma intact — the failure mode a
    quote-aware parser must not have.
    """
    rows: list[list[str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        normalized = _SINGLE_QUOTED.sub(r'"\1"', line)
        try:
            rows.append(next(csv.reader([normalized])))
        except csv.Error as exc:
            raise SourceParseError(f"gisco_nuts: unparseable CSV line: {exc}") from exc
    return rows


def _provenance(adapter: GiscoNutsAdapter, record: RawRecord) -> Provenance:
    return Provenance(
        source_id=adapter.source_id,
        source_trust=adapter.trust_rank,
        confidence=1.0,
        ontology_version=ONTOLOGY_VERSION,
    )
