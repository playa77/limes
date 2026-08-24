# src/limes/sources/gleif.py | v1.0.0 | introduced by WP-11
"""GLEIF golden-copy adapter per Technical Specification §8.5.2.

Loads the legal-entity backbone: `Corporation` nodes keyed by `lei`,
`HEADQUARTERED_IN` edges to address-identity `Location` nodes, `LOCATED_IN`
edges to the NUTS region the postal-code correspondence resolves, and
`SUBSIDIARY_OF` / `OWNS_STAKE_IN` edges between corporations (Doc 1 §5.4).

The golden copy is a full snapshot: `fetch` downloads both zips, ignores the
window, and yields one `RawRecord` per zip. `supports_incremental` is True
per the source table, but the snapshot always supersedes any window, so
window resolution never changes what is fetched.

Non-obvious choices, each load-bearing:

- The URL constants are the single place to refresh when the golden-copy
  endpoints move. They follow the documented GLEIF pattern; the exact live
  URL could not be verified from this host, so treat them as unverified
  until the first fetch succeeds.
- An address without geonames identity gets its `entity_id` from a SHA-256
  over `country|postal|city` (the `coordinate_hash` key). The hash is
  identity, not location: region membership is a lookup, never geometry
  (Doc 2 §8.5.2), so the hash must be stable across runs, not spatial.
- The direct percentage is not stamped as a property (the loader stamps no
  arbitrary properties); it selects *whether* an `OWNS_STAKE_IN` assertion
  is emitted. A positive direct percentage emits ownership; 0 or empty does
  not — a deliberately coarse reading, documented here so nobody looks for
  the value in the graph.
- A relationship endpoint carries no legal name (the relationship file has
  no name columns), so its Corporation label is the LEI itself. The loader
  never overwrites a label on merge, so whichever record loads first
  establishes it; the legal name wins when the entity file loads first.
- The relationship file cannot be cross-checked against the entity file:
  the two zips are separate records, `normalize` is pure and per-record,
  and cross-record module state is forbidden (C-07). The adapter enforces
  the endpoint-materializability check it can run per record — the LEI's
  form — and emits every endpoint under the deterministic `lei:<LEI>`
  identity the entity file would produce, so a relationship to an LEI
  absent from the entity file still merges onto the same node identity.
- A corporation with no HQ address and no relationship is a real and common
  row (Doc 2 §5.6) and goes to `NormalizedRecord.entities`. The
  no-relationship half is unknowable per record; the loader's idempotent
  merge on `entity_id` absorbs the overlap if the relationship record later
  names the same LEI.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Literal

import structlog

from limes.errors import SourceParseError
from limes.sources.base import (
    address_location,
    fetch_bytes,
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

# The single place to refresh when the golden-copy endpoints move (see the
# module docstring: the exact live URL is unverified from this host).
ENTITY_ZIP_URL = "https://goldencopy.gleif.org/api/v2/golden-copies/latest/lei2-goldencopy.csv.zip"
RELATIONSHIP_ZIP_URL = (
    "https://goldencopy.gleif.org/api/v2/golden-copies/latest/lei2-relationships-goldencopy.csv.zip"
)

ZIP_CONTENT_TYPE = "application/zip"

_ENTITY_CSV_MARKERS = ("LEI", "Entity.EntityStatus")
_RELATIONSHIP_CSV_MARKER = "Relationship.RelationshipType"
_RELATIONSHIP_MEMBER_HINT = "relationships"
_SUBSIDIARY_TYPE = "IS_SUBSIDIARY_OF"
_ACTIVE_STATUS = "ACTIVE"

# GLEIF LEIs are exactly 20 uppercase letters and digits. A relationship
# endpoint that does not match cannot be addressed as a Corporation node.
_LEI_PATTERN = re.compile(r"[A-Z0-9]{20}")


class GleifAdapter:
    """GLEIF — legal-entity backbone: corporations, addresses, ownership."""

    source_id: str = "gleif"
    name: str = "GLEIF"
    kind: Literal["structured", "unstructured"] = "structured"
    trust_rank: float = 1.00
    supports_backfill: bool = True
    supports_incremental: bool = True

    def fetch(self, since: datetime | None, until: datetime | None) -> Iterator[RawRecord]:
        """Download both golden-copy zips. The window is ignored: the golden
        copy is a full snapshot and always supersedes any window."""
        fetched_at = now_utc()
        for url in (ENTITY_ZIP_URL, RELATIONSHIP_ZIP_URL):
            payload = fetch_bytes(url)
            logger.info(
                "gleif payload fetched",
                url=url,
                bytes=len(payload),
                fetched_at=fetched_at.isoformat(),
            )
            yield RawRecord(
                payload=payload,
                content_type=ZIP_CONTENT_TYPE,
                source_url=url,
                fetched_at=fetched_at,
            )

    def normalize(
        self,
        record: RawRecord,
        *,
        postal_lookup: Callable[[str, str], str | None] | None = None,
    ) -> NormalizedRecord:
        """One zip to entity or relationship records, routed on the inner CSV
        member name.

        `postal_lookup` resolves (country, postal code) to a NUTS code from
        graph-resident reference data (C-07); the caller passes it when the
        correspondence is available. A missing lookup or miss means no
        `LOCATED_IN` — never guessed — counted and summarized once.
        """
        member, text = _read_zip(record)
        if _RELATIONSHIP_MEMBER_HINT in member.lower():
            return self._normalize_relationships(text, record)
        return self._normalize_entities(text, record, postal_lookup)

    def _normalize_entities(
        self,
        text: str,
        record: RawRecord,
        postal_lookup: Callable[[str, str], str | None] | None,
    ) -> NormalizedRecord:
        rows = _csv_rows(text, *_ENTITY_CSV_MARKERS)
        assertions: list[Assertion] = []
        entities: list[EntityEndpoint] = []
        inactive = 0
        malformed = 0
        no_hq = 0
        missing_regions = 0
        for row in rows:
            lei = (row.get("LEI") or "").strip()
            if not lei:
                malformed += 1
                logger.warning("gleif: entity row without LEI skipped", row=row)
                continue
            status = (row.get("Entity.EntityStatus") or "").strip()
            if status != _ACTIVE_STATUS:
                inactive += 1
                logger.warning("gleif: non-ACTIVE entity skipped", lei=lei, status=status)
                continue
            legal_name = (row.get("Entity.LegalName") or "").strip() or lei
            corporation = _corporation(lei, legal_name)
            country = (row.get("Entity.HeadquartersAddress.Country") or "").strip()
            postal = (row.get("Entity.HeadquartersAddress.PostalCode") or "").strip()
            city = (row.get("Entity.HeadquartersAddress.City") or "").strip()
            if not country or not postal:
                no_hq += 1
                entities.append(corporation)
                continue
            location = address_location(country, postal, city)
            assertions.append(
                make_assertion(
                    self,
                    record,
                    corporation,
                    "HEADQUARTERED_IN",
                    location,
                    valid_from=record.fetched_at,
                )
            )
            if postal_lookup is None:
                missing_regions += 1
                continue
            nuts = postal_lookup(country, postal)
            if not nuts:
                missing_regions += 1
                continue
            region = EntityEndpoint(
                entity_id=key_entity_id(("nuts_code", nuts)),
                type="AdministrativeRegion",
                label=nuts,
                deterministic_key=("nuts_code", nuts),
            )
            assertions.append(
                make_assertion(
                    self, record, location, "LOCATED_IN", region, valid_from=record.fetched_at
                )
            )
        if missing_regions:
            logger.info(
                "gisco correspondence missing for N addresses; region unassigned",
                addresses=missing_regions,
                source_id=self.source_id,
            )
        logger.info(
            "gleif: entity file normalized",
            rows=len(rows),
            corporations=len(rows) - malformed - inactive,
            inactive_skipped=inactive,
            malformed_skipped=malformed,
            standalone_entities=len(entities),
            missing_regions=missing_regions,
            source_id=self.source_id,
        )
        return NormalizedRecord(
            content_hash=payload_hash(record.payload),
            kind="structured",
            assertions=assertions,
            entities=entities,
        )

    def _normalize_relationships(self, text: str, record: RawRecord) -> NormalizedRecord:
        rows = _csv_rows(text, _RELATIONSHIP_CSV_MARKER)
        assertions: list[Assertion] = []
        subsidiary = 0
        ownership = 0
        other_types = 0
        unmaterializable = 0
        date_fallback = 0
        unparseable_pct = 0
        for row in rows:
            record_id = row.get("Relationship.RecordID") or ""
            rel_type = (row.get("Relationship.RelationshipType") or "").strip()
            if rel_type != _SUBSIDIARY_TYPE:
                other_types += 1
                logger.warning(
                    "gleif: non-subsidiary relationship skipped",
                    record_id=record_id,
                    relationship_type=rel_type,
                )
                continue
            start_lei = (row.get("Relationship.StartNodeID") or "").strip()
            end_lei = (row.get("Relationship.EndNodeID") or "").strip()
            if not (_LEI_PATTERN.fullmatch(start_lei) and _LEI_PATTERN.fullmatch(end_lei)):
                unmaterializable += 1
                logger.warning(
                    "gleif: relationship endpoint LEI cannot be materialized; skipped",
                    record_id=record_id,
                    start_node=start_lei,
                    end_node=end_lei,
                )
                continue
            raw_start = (row.get("Relationship.Periods.StartDate") or "").strip()
            valid_from = _parse_period_start(raw_start) if raw_start else None
            if raw_start and valid_from is None:
                date_fallback += 1
                logger.warning(
                    "gleif: unparseable period start date; falling back to fetch time",
                    record_id=record_id,
                    raw=raw_start,
                )
            valid_from = valid_from or record.fetched_at
            subsidiary_corp = _corporation(start_lei, start_lei)
            parent_corp = _corporation(end_lei, end_lei)
            assertions.append(
                make_assertion(
                    self,
                    record,
                    subsidiary_corp,
                    "SUBSIDIARY_OF",
                    parent_corp,
                    valid_from=valid_from,
                )
            )
            subsidiary += 1
            raw_pct = (row.get("Relationship.Ownership.DirectPercentage") or "").strip()
            if raw_pct:
                try:
                    pct = float(raw_pct)
                except ValueError:
                    unparseable_pct += 1
                    logger.warning(
                        "gleif: unparseable direct percentage; no ownership assertion",
                        record_id=record_id,
                        raw=raw_pct,
                    )
                else:
                    if pct > 0:
                        assertions.append(
                            make_assertion(
                                self,
                                record,
                                parent_corp,
                                "OWNS_STAKE_IN",
                                subsidiary_corp,
                                valid_from=valid_from,
                            )
                        )
                        ownership += 1
        logger.info(
            "gleif: relationship file normalized",
            rows=len(rows),
            subsidiary_assertions=subsidiary,
            ownership_assertions=ownership,
            other_types_skipped=other_types,
            unmaterializable_skipped=unmaterializable,
            date_fallback=date_fallback,
            unparseable_percentages=unparseable_pct,
            source_id=self.source_id,
        )
        return NormalizedRecord(
            content_hash=payload_hash(record.payload),
            kind="structured",
            assertions=assertions,
        )


def _read_zip(record: RawRecord) -> tuple[str, str]:
    """The inner CSV member name and its decoded text; non-CSV members
    (README, LICENSE) are ignored."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(record.payload))
    except zipfile.BadZipFile as exc:
        raise SourceParseError(f"gleif: payload is not a zip archive: {exc}") from exc
    members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
    if not members:
        raise SourceParseError("gleif: zip contains no CSV member")
    member = members[0]
    if len(members) > 1:
        logger.warning(
            "gleif: zip has multiple CSV members; using the first",
            member=member,
        )
    return member, archive.read(member).decode("utf-8-sig", errors="replace")


def _csv_rows(text: str, *markers: str) -> list[dict[str, str]]:
    """All non-empty rows of a GLEIF CSV, with the header validated against
    the given column markers. A file whose header lacks the markers is not a
    GLEIF file and is rejected whole."""
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or not all(marker in reader.fieldnames for marker in markers):
        first = text.splitlines()[0] if text else ""
        raise SourceParseError(f"gleif: unrecognized CSV header ({first[:80]!r})")
    rows = [row for row in reader if any((row.get(k) or "").strip() for k in row)]
    if not rows:
        raise SourceParseError("gleif: CSV file has no data rows")
    return rows


def _parse_period_start(raw: str) -> datetime | None:
    """GLEIF period dates are `YYYY-MM-DD`; a bare date is treated as UTC
    midnight so assertion ids stay timezone-stable."""
    try:
        return datetime.fromisoformat(raw).replace(tzinfo=UTC)
    except ValueError:
        return None


def _corporation(lei: str, label: str) -> EntityEndpoint:
    return EntityEndpoint(
        entity_id=key_entity_id(("lei", lei)),
        type="Corporation",
        label=label,
        deterministic_key=("lei", lei),
    )
