# src/limes/sources/bundestag_dip.py | v1.0.0 | introduced by WP-16
"""DIP historical person/term evidence with stable legacy identity (BE-56).

DIP is not a serving-member directory. Official roster adapters own current
observations; parliamentary groups never imply party membership. The 1.4.0
migration retains and source-scopingly supersedes the old interpretation.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import urlencode

import structlog

from limes.errors import SourceFetchError, SourceParseError
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

# The DIP person search endpoint; date-time filters and cursor are query parameters.
PERSON_URL = "https://search.dip.bundestag.de/api/v1/person"

# Frozen legacy hash inputs, not person service dates or current-term selection.
# New periods use their scoped key without inventing an unknown start date.
WAHLPERIODE_STARTS: dict[int, str] = {
    19: "2017-10-24",
    20: "2021-10-26",
    21: "2025-03-25",
}

JSON_CONTENT_TYPE = "application/json"

# Frozen legacy Office hash namespace; the new compound key includes the term.
OFFICE_BODY_ID = "BT"

_OFFICE_TITLE_PREFIX = "Mitglied des Deutschen Bundestages"


class BundestagDipAdapter:
    """Bundestag DIP — historical persons, term references and group evidence."""

    source_id: str = "bundestag_dip"
    name: str = "Bundestag DIP"
    kind: Literal["structured", "unstructured"] = "structured"
    trust_rank: float = 1.00
    supports_backfill: bool = True
    supports_incremental: bool = True
    full_initial_load: bool = True

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    def fetch(self, since: datetime | None, until: datetime | None) -> Iterator[RawRecord]:
        """Person search pages, filtered by the updated-time window.
        Authentication stays in headers, outside archived source URLs."""
        params: list[tuple[str, str]] = []
        if since is not None:
            params.append(("f.aktualisiert.start", since.astimezone(UTC).isoformat()))
        if until is not None:
            params.append(("f.aktualisiert.end", until.astimezone(UTC).isoformat()))
        headers = {"Authorization": f"ApiKey {self._api_key}"} if self._api_key else {}
        cursor = None
        seen_cursors: set[str] = set()
        seen_pages: set[str] = set()
        # Bounded acquisition, never mark a truncated response covered.
        while True:
            page_params = params + ([("cursor", cursor)] if cursor else [])
            url = f"{PERSON_URL}?{urlencode(page_params)}" if page_params else PERSON_URL
            payload = fetch_bytes(url, headers=headers)
            document = _parse_document(payload)
            rows = document.get("documents", document.get("rows"))
            if not isinstance(rows, list):
                raise SourceParseError("bundestag_dip: response has no documents list")
            if not rows:
                return
            next_cursor = document.get("cursor")
            page_key = json.dumps(rows, sort_keys=True)
            if page_key in seen_pages:
                if next_cursor == cursor:
                    return
                raise SourceFetchError("bundestag_dip: repeated page; checkpoint unchanged")
            seen_pages.add(page_key)
            yield RawRecord(
                payload=payload,
                content_type=JSON_CONTENT_TYPE,
                source_url=url,
                fetched_at=now_utc(),
            )
            if not next_cursor or next_cursor == cursor:
                return
            if not isinstance(next_cursor, str):
                raise SourceParseError("bundestag_dip: invalid cursor")
            if next_cursor in seen_cursors:
                raise SourceFetchError("bundestag_dip: cursor cycle; checkpoint unchanged")
            seen_cursors.add(next_cursor)
            cursor = next_cursor

    def normalize(self, record: RawRecord) -> NormalizedRecord:
        """Historical DIP participation evidence, never an authoritative current roster.

        Fraktion is group evidence only when its period is unambiguous. DIP
        person records do not supply individual mandate intervals; no term start
        is promoted to a person's service date. BE-56's official roster sources
        own current membership observations.
        """
        document = _parse_document(record.payload)
        rows = document.get("documents", document.get("rows"))
        if not isinstance(rows, list):
            raise SourceParseError("bundestag_dip: response has no documents list")
        assertions: list[Assertion] = []
        entities: list[EntityEndpoint] = []
        errors = 0
        body = EntityEndpoint(
            entity_id="institution_id:DE:bt",
            type="PublicBody",
            label="Deutscher Bundestag",
            deterministic_key=("institution_id", "DE:bt"),
        )
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                errors += 1
                continue
            person = _person_from_row(row)
            if person is None:
                errors += 1
                continue
            entities.append(person)
            periods = row.get("wahlperiode", row.get("wahlperioden")) or []
            if not isinstance(periods, list) or any(type(p) is not int or p < 1 for p in periods):
                errors += 1
                continue
            raw_group = row.get("fraktion")
            if isinstance(raw_group, list):
                raw_group = raw_group[0] if len(raw_group) == 1 else None
            group_label = raw_group.strip() if isinstance(raw_group, str) else ""
            for period in dict.fromkeys(periods):
                office = _office(period, _period_start(period))
                relations = [(person, "PARTICIPATED_IN_TERM", office), (office, "OFFICE_AT", body)]
                if group_label and len(periods) == 1 and group_label.lower() != "fraktionslos":
                    group_key = json.dumps(["bt", str(period), group_label], ensure_ascii=False)
                    group = EntityEndpoint(
                        entity_id=key_entity_id(("group_id", group_key)),
                        type="ParliamentaryGroup",
                        label=group_label,
                        deterministic_key=("group_id", group_key),
                        properties={"scope": "bt", "term": str(period)},
                    )
                    relations.extend([(person, "GROUP_EVIDENCE", group), (group, "GROUP_AT", body)])
                for subject, relation, object_ in relations:
                    assertion = make_assertion(self, record, subject, relation, object_)
                    assertion.provenance.evidence_channel = "dip_term_evidence"
                    assertion.provenance.validity_basis = "historical_term_reference"
                    assertion.provenance.evidence_member = f"/documents/{index}"
                    assertion.provenance.source_url = record.source_url
                    updated = row.get("aktualisiert")
                    if isinstance(updated, str):
                        try:
                            stamp = datetime.fromisoformat(updated)
                            if stamp.tzinfo is not None:
                                assertion.provenance.source_recorded_at = stamp
                        except ValueError:
                            pass
                    assertions.append(assertion)
        return NormalizedRecord(
            content_hash=payload_hash(record.payload),
            kind="structured",
            assertions=assertions,
            entities=entities,
            errors=errors,
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
    if not isinstance(row.get("vorname"), str) or not isinstance(row.get("nachname"), str):
        return None
    vorname = row["vorname"].strip()
    nachname = row["nachname"].strip()
    if not vorname or not nachname:
        return None
    addition = row.get("namenszusatz")
    label = (
        f"{vorname} {addition.strip()} {nachname}"
        if isinstance(addition, str) and addition.strip()
        else f"{vorname} {nachname}"
    )
    aliases = [label]
    for role in row.get("person_roles") or []:
        if isinstance(role, dict) and role.get("vorname") and role.get("nachname"):
            aliases.append(f"{role['vorname']} {role['nachname']}")
    return EntityEndpoint(
        entity_id=key_entity_id(("bundestag_id", str(raw_id))),
        type="Person",
        label=label,
        aliases=list(dict.fromkeys(aliases)),
        deterministic_key=("bundestag_id", str(raw_id)),
    )


def _office(period: int, period_start: datetime | None) -> EntityEndpoint:
    """Keep legacy office IDs while replacing the incomplete body-only key."""
    title = f"{_OFFICE_TITLE_PREFIX} (Wahlperiode {period})"
    office_key = json.dumps(["bt", "member", str(period), None], ensure_ascii=False)
    identity = (
        hash_entity_id("office", OFFICE_BODY_ID, title, period_start.isoformat())
        if period_start is not None
        else key_entity_id(("office_key", office_key))
    )
    return EntityEndpoint(
        entity_id=identity,
        type="Office",
        label=title,
        deterministic_key=("office_key", office_key),
        aliases=[title],
        properties={"scope": "bt", "term": str(period), "role": "member"},
    )


def _period_start(period: int) -> datetime | None:
    """Frozen legacy Office identity input; never a personal service date."""
    raw = WAHLPERIODE_STARTS.get(period)
    if raw is None:
        return None
    return datetime.fromisoformat(raw).replace(tzinfo=UTC)
