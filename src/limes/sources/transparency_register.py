# src/limes/sources/transparency_register.py | v1.0.0 | introduced by WP-15
"""EU Transparency Register adapter per Technical Specification §8.5.

Loads the register's interest-group backbone: `InterestGroup` nodes keyed by
the register id, `MEMBER_OF` edges from each group's head person, `LOBBIES_FOR`
edges to the group's declared interests as `Topic` nodes, and `MET_WITH` edges
to the Commission officials each declared meeting names (Doc 1 §5.4).

The export XML is the full current register: `fetch` ignores the window and
yields one `RawRecord`; `supports_incremental` is True per the source table,
but a full snapshot always supersedes any window.

Non-obvious choices, each load-bearing:

- The current daily XML endpoint is linked by the official transparency-register
  dataset catalog. ListOfIRPublicDetail export date/count are required. Current
  exports supply interests but no head-person or meetings: neither is inferred.
  Archived Templates payloads retain their legacy parser.
- Declared interests are `Topic` nodes under the register's own "EU_TR"
  vocabulary, never EuroVoc: the register's interest classification has no
  EuroVoc equivalent, and a source-namespaced vocabulary keeps the two
  classifications addressable separately instead of merging them.
- The register publishes no separate membership list; the head person named
  in <Head> is the person the group answers for, so the head's `MEMBER_OF`
  edge is the adapter's membership reading, documented here.
- The register id is not among `Person`'s identifying keys
  (ontology/ontology.yaml: [wikidata_qid, bundestag_id]), so keying a person
  by it would not be stamped and would log warnings. Persons are therefore
  hashed from name alone (`person:<sha256>`), the shared convention for
  endpoints without a deterministic key.
- Meeting targets are names of Commission officials, always persons in this
  data — never public bodies — so the `MET_WITH` object is a `Person`.
- Dates arrive in two formats: `EntryDate` is ISO (`2021-06-11`), meeting
  dates are `DD/MM/YYYY` (`13/06/2023`). Both parse to UTC midnight so
  assertion digests stay stable across re-runs; an unparseable date falls
  back to the fetch instant, counted, never silent.
- `OrganisationType` and `Status` gate nothing in this pipeline and are not
  mapped to the ontology; parsed organisations and skips by reason are
  counted in the normalize summary instead.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Literal

import structlog
from lxml import etree  # type: ignore[import-untyped]

from limes.errors import SourceParseError
from limes.sources.base import (
    fetch_bytes,
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

# The single place to refresh when the download URL moves (see the module
# docstring: the data.europa.eu URL is not stable).
EXPORT_URL = "https://transparency-register.europa.eu/odplastorganisationxml_en"

XML_CONTENT_TYPE = "application/xml"

# The register's own interest-classification vocabulary (see the module
# docstring: never EuroVoc).
INTEREST_VOCABULARY = "EU_TR"

# EntryDate is ISO; meeting dates are DD/MM/YYYY. Both are pinned to UTC
# midnight so assertion digests are stable across re-runs.
_ISO_DATE = "%Y-%m-%d"
_MEETING_DATE = "%d/%m/%Y"


class TransparencyRegisterAdapter:
    """EU Transparency Register — interest groups, declared interests, head
    persons, and declared Commission meetings."""

    source_id: str = "transparency_register"
    name: str = "EU Transparency Register"
    kind: Literal["structured", "unstructured"] = "structured"
    trust_rank: float = 1.00
    supports_backfill: bool = True
    supports_incremental: bool = True

    def fetch(self, since: datetime | None, until: datetime | None) -> Iterator[RawRecord]:
        """GET the full export. The window is ignored: the export is the
        whole current register and there is no delta endpoint, so every run
        is a full load."""
        payload = fetch_bytes(EXPORT_URL, max_bytes=256 * 1024 * 1024)
        fetched_at = now_utc()
        logger.info(
            "transparency_register: export fetched",
            bytes=len(payload),
            fetched_at=fetched_at.isoformat(),
        )
        yield RawRecord(
            payload=payload,
            content_type=XML_CONTENT_TYPE,
            source_url=EXPORT_URL,
            fetched_at=fetched_at,
        )

    def normalize(self, record: RawRecord) -> NormalizedRecord:
        """Convert one export payload into the interest-group assertion set.
        Pure: never touches the network."""
        try:
            payload = _repair_xml_controls(record.payload)
            root = etree.fromstring(
                payload, etree.XMLParser(resolve_entities=False, no_network=True, recover=False)
            )
            if root.getroottree().docinfo.doctype:
                raise SourceParseError("transparency_register: DTD declarations are not supported")
        except (etree.XMLSyntaxError, ValueError) as exc:
            raise SourceParseError(
                f"transparency_register: payload is not parseable XML: {exc}"
            ) from exc
        if etree.QName(root).localname == "ListOfIRPublicDetail":
            return self._normalize_current(root, record)
        if etree.QName(root).localname != "Templates":
            raise SourceParseError(
                "transparency_register: payload root is not <Templates>; not the register export"
            )

        counts: dict[str, int] = {
            "organisations": 0,
            "organisations_skipped_no_id": 0,
            "organisations_skipped_no_name": 0,
            "persons_indexed": 0,
            "persons_skipped_no_id": 0,
            "persons_skipped_no_name": 0,
            "head_persons": 0,
            "head_refs_unmatched": 0,
            "member_of_assertions": 0,
            "interests": 0,
            "interests_skipped_no_code": 0,
            "interest_labels_fallback": 0,
            "lobbies_for_assertions": 0,
            "meetings": 0,
            "meetings_skipped_no_target": 0,
            "met_with_assertions": 0,
            "date_fallbacks": 0,
        }

        # The head reference matches Person elements by register id. The
        # index is lookup-only: the emitted person identity is the name hash,
        # never this id (see the module docstring).
        persons: dict[str, tuple[str, str]] = {}
        for person in root.findall("Person"):
            person_id = (person.get("id") or "").strip()
            if not person_id:
                counts["persons_skipped_no_id"] += 1
                continue
            first = _text(person, "PersonName/FirstName")
            family = _text(person, "PersonName/FamilyName")
            if not (first and family):
                counts["persons_skipped_no_name"] += 1
                logger.warning(
                    "transparency_register: person without full name skipped",
                    person_id=person_id,
                )
                continue
            persons[person_id] = (first, family)
        counts["persons_indexed"] = len(persons)

        assertions: list[Assertion] = []
        for organisation in root.findall("Organisation"):
            counts["organisations"] += 1
            assertions.extend(_normalize_organisation(self, organisation, persons, record, counts))

        logger.info(
            "transparency_register: export normalized",
            **counts,
            assertions=len(assertions),
            source_id=self.source_id,
        )
        return NormalizedRecord(
            content_hash=payload_hash(record.payload),
            kind="structured",
            assertions=assertions,
        )

    def _normalize_current(self, root: etree._Element, record: RawRecord) -> NormalizedRecord:
        def text(node: etree._Element, name: str) -> str | None:
            values = node.xpath(f".//*[local-name()='{name}']/text()")
            return str(values[0]).strip() if values else None

        def date(raw: str | None) -> datetime | None:
            try:
                parsed = datetime.fromisoformat(raw.replace("Z", "+00:00")) if raw else None
                if parsed is None:
                    return None
                return (
                    parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
                )
            except ValueError:
                return None

        rows = root.xpath(".//*[local-name()='interestRepresentative']")
        try:
            expected = int(text(root, "numberOfIR") or "-1")
        except ValueError as exc:
            raise SourceParseError("transparency_register: invalid export count") from exc
        as_of = date(text(root, "exportDate"))
        if as_of is None or expected != len(rows):
            raise SourceParseError(
                "transparency_register: incomplete export or missing export date"
            )
        assertions: list[Assertion] = []
        entities: list[EntityEndpoint] = []
        errors = 0
        for ordinal, row in enumerate(rows, 1):
            identifier, name = text(row, "identificationCode"), text(row, "originalName")
            if not identifier or not name:
                errors += 1
                continue
            group = EntityEndpoint(
                entity_id=key_entity_id(("transparency_register_id", identifier)),
                type="InterestGroup",
                label=name,
                deterministic_key=("transparency_register_id", identifier),
            )
            entities.append(group)
            for interest in row.xpath("./*[local-name()='interests']/*[local-name()='interest']"):
                label = text(interest, "name")
                if not label:
                    errors += 1
                    continue
                # Export supplies labels, not classification codes: namespaced label digest.
                code = hash_entity_id("interest", label).split(":", 1)[1]
                assertion = make_assertion(
                    self,
                    record,
                    group,
                    "LOBBIES_FOR",
                    topic_endpoint(INTEREST_VOCABULARY, code, label=label),
                    valid_from=as_of,
                )
                assertion.provenance.source_recorded_at = date(text(row, "lastUpdateDate"))
                assertion.provenance.source_url = record.source_url
                assertion.provenance.evidence_row = ordinal
                assertions.append(assertion)
        return NormalizedRecord(
            content_hash=payload_hash(record.payload),
            kind="structured",
            entities=entities,
            assertions=assertions,
            errors=errors,
        )


def _normalize_organisation(
    adapter: TransparencyRegisterAdapter,
    organisation: etree._Element,
    persons: dict[str, tuple[str, str]],
    record: RawRecord,
    counts: dict[str, int],
) -> list[Assertion]:
    """One <Organisation> element → MEMBER_OF, LOBBIES_FOR, and MET_WITH
    assertions. Skipped facets are counted by reason, never dropped."""
    organisation_id = (organisation.get("id") or "").strip()
    if not organisation_id:
        counts["organisations_skipped_no_id"] += 1
        logger.warning(
            "transparency_register: organisation without id skipped",
            organisation_id=organisation.get("id"),
        )
        return []
    name = _text(organisation, "OrganisationName/TransliteratedName")
    if not name:
        counts["organisations_skipped_no_name"] += 1
        logger.warning(
            "transparency_register: organisation without name skipped",
            organisation_id=organisation_id,
        )
        return []

    group = EntityEndpoint(
        entity_id=key_entity_id(("transparency_register_id", organisation_id)),
        type="InterestGroup",
        label=name,
        deterministic_key=("transparency_register_id", organisation_id),
    )

    entry_date = _text(organisation, "EntryDate")
    member_since, date_fell_back = _parse_date(entry_date, record.fetched_at)
    if date_fell_back:
        counts["date_fallbacks"] += 1

    assertions: list[Assertion] = []

    head = organisation.find("Head/PersonRef")
    if head is not None:
        counts["head_persons"] += 1
        head_id = head.get("id") or ""
        match = persons.get(head_id)
        if match is None:
            counts["head_refs_unmatched"] += 1
            logger.warning(
                "transparency_register: head person reference not in export; MEMBER_OF skipped",
                organisation_id=organisation_id,
                person_ref=head_id,
            )
        else:
            first, family = match
            head_person = _person(first, family)
            assertions.append(
                make_assertion(
                    adapter,
                    record,
                    head_person,
                    "MEMBER_OF",
                    group,
                    valid_from=member_since,
                )
            )
            counts["member_of_assertions"] += 1

    # No declared interests means no LOBBIES_FOR edges; the organisation is
    # still parsed and counted. The interest element carries no date, so the
    # assertion is valid from the fetch instant.
    for interest in organisation.findall("Interests/Interest"):
        counts["interests"] += 1
        code = _text(interest, "Code")
        if not code:
            counts["interests_skipped_no_code"] += 1
            logger.warning(
                "transparency_register: interest without code skipped",
                organisation_id=organisation_id,
            )
            continue
        label = _text(interest, "Label")
        if not label:
            label = code
            counts["interest_labels_fallback"] += 1
            logger.warning(
                "transparency_register: interest without label; code used as label",
                organisation_id=organisation_id,
                code=code,
            )
        topic = topic_endpoint(INTEREST_VOCABULARY, code, label=label)
        assertions.append(
            make_assertion(
                adapter,
                record,
                group,
                "LOBBIES_FOR",
                topic,
                valid_from=record.fetched_at,
            )
        )
        counts["lobbies_for_assertions"] += 1

    for meeting in organisation.findall("Meetings/Meeting"):
        counts["meetings"] += 1
        target = _text(meeting, "Target")
        if not target:
            counts["meetings_skipped_no_target"] += 1
            logger.warning(
                "transparency_register: meeting without target skipped",
                organisation_id=organisation_id,
            )
            continue
        meeting_date = _text(meeting, "Date")
        met_on, date_fell_back = _parse_date(meeting_date, record.fetched_at)
        if date_fell_back:
            counts["date_fallbacks"] += 1
        official = EntityEndpoint(
            entity_id=hash_entity_id("person", target),
            type="Person",
            label=target,
        )
        assertions.append(
            make_assertion(adapter, record, group, "MET_WITH", official, valid_from=met_on)
        )
        counts["met_with_assertions"] += 1

    return assertions


def _person(first: str, family: str) -> EntityEndpoint:
    """A Person endpoint hashed from name alone — no deterministic key: the
    register id is not a Person identifying key, and stamping an undeclared
    key would warn (see the module docstring)."""
    return EntityEndpoint(
        entity_id=hash_entity_id("person", first, family),
        type="Person",
        label=f"{first} {family}",
    )


def _text(element: etree._Element, path: str) -> str | None:
    """Trimmed text of the first child matching `path`, or None when absent."""
    node = element.find(path)
    if node is None or node.text is None:
        return None
    # lxml is untyped (import-untyped): node.text is Any here, but an XML
    # element's text is always str once the None check passed.
    return str(node.text).strip()


def _parse_date(raw: str | None, fallback: datetime) -> tuple[datetime, bool]:
    """An entry or meeting date as UTC midnight, or (fallback, True) when the
    string is unparseable. UTC midnight keeps assertion digests stable across
    re-runs."""
    if not raw:
        return fallback, True
    for fmt in (_ISO_DATE, _MEETING_DATE):
        try:
            parsed = datetime.strptime(raw, fmt)
        except ValueError:
            continue
        return parsed.replace(tzinfo=UTC), False
    logger.warning(
        "transparency_register: unparseable date; falling back to fetch time",
        raw=raw,
    )
    return fallback, True


_INVALID_XML_CONTROLS = re.compile(
    rb"<!--[\s\S]*?-->|<!\[CDATA\[[\s\S]*?\]\]>|<\?[\s\S]*?\?>|"
    rb"[\x00-\x08\x0b\x0c\x0e-\x1f]|&#(?:[0-9]+|x[0-9a-fA-F]+);"
)


def _repair_xml_controls(payload: bytes) -> bytes:
    """Replace XML 1.0 forbidden C0 controls with spaces; never repair structure.

    Original bytes remain the archived evidence and content-hash identity.
    Spaces prevent joining words across damaged source text.
    """
    # Repair only the UTF-8 export contract; byte replacement would corrupt UTF-16.
    if payload.startswith((b"\xff\xfe", b"\xfe\xff", b"\x00<", b"<\x00")):
        return payload
    repairs = 0

    def replace(match: re.Match[bytes]) -> bytes:
        nonlocal repairs
        value = match.group()
        if value.startswith(b"<"):
            return value
        if value.startswith(b"&#"):
            # Huge/unrelated numeric references remain strict parser errors.
            if len(value) > 16:
                return value
            number = int(value[3:-1], 16) if value.startswith(b"&#x") else int(value[2:-1])
            if number > 31 or number in (9, 10, 13):
                return value
        repairs += 1
        return b" "

    repaired = _INVALID_XML_CONTROLS.sub(replace, payload)
    if repairs:
        logger.warning("transparency_register: XML controls replaced", replacements=repairs)
    return repaired
