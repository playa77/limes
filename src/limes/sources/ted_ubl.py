"""Current eForms UBL normalization, with explicit buyer and winner references.

A tenderer is an awardee only through a winning LotResult -> LotTender ->
TenderingParty -> organization chain. Unsuccessful or merely participating
organizations never become awardees. Lot identities isolate multi-lot awards.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from lxml import etree  # type: ignore[import-untyped]

from limes.errors import SourceParseError
from limes.sources.base import (
    address_location,
    hash_entity_id,
    key_entity_id,
    make_assertion,
    payload_hash,
    topic_endpoint,
)
from limes.sources.country_codes import ISO3_TO_ISO2
from limes.types import Assertion, EntityEndpoint, NormalizedRecord, RawRecord


def children(node: etree._Element, name: str) -> list[etree._Element]:
    return [
        child
        for child in node
        if isinstance(child.tag, str) and etree.QName(child).localname == name
    ]


def descendants(node: etree._Element, name: str) -> list[etree._Element]:
    return list(node.xpath(f".//*[local-name()='{name}']"))


def value(node: etree._Element, name: str) -> str | None:
    values = children(node, name)
    return (values[0].text or "").strip() or None if values else None


def date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    # XML Schema dates may include a timezone suffix, unlike Python date literals.
    try:
        if len(raw) >= 10 and raw[10:11] in ("+", "-", "Z"):
            raw = raw[:10] + "T00:00:00" + raw[10:]
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    except ValueError:
        return None


def normalize_ubl(
    adapter: Any,
    root: etree._Element,
    record: RawRecord,
    *,
    postal_lookup: Callable[[str, str], str | None] | None = None,
) -> NormalizedRecord:
    if etree.QName(root).localname not in (
        "ContractNotice",
        "ContractAwardNotice",
        "PriorInformationNotice",
    ):
        raise SourceParseError("ted: unsupported UBL notice kind")
    publications = descendants(root, "Publication")
    publication = publications[0] if publications else None
    identifier = value(publication, "NoticePublicationID") if publication is not None else None
    published = date(value(publication, "PublicationDate")) if publication is not None else None
    if not identifier or published is None:
        raise SourceParseError("ted: UBL notice lacks publication identity/date")
    # Official IDs are zero-padded in XML and unpadded in the search API.
    identifier = identifier.lstrip("0")
    requested = (record.acquisition_context or {}).get("requested_notice_id")
    if requested is not None and str(requested).lstrip("0") != identifier:
        raise SourceParseError("ted: returned XML publication does not match search notice")
    orgs = {}
    for company in descendants(root, "Company"):
        ids = children(company, "PartyIdentification")
        if ids and value(ids[0], "ID"):
            orgs[value(ids[0], "ID")] = company
    if not orgs:
        raise SourceParseError("ted: UBL organization table missing")

    def company_name(company: etree._Element) -> str | None:
        names = children(company, "PartyName")
        return value(names[0], "Name") if names else None

    def reference(node: etree._Element, holder: str) -> list[str]:
        return [ref for part in children(node, holder) if (ref := value(part, "ID"))]

    buyer_refs = []
    for contracting in children(root, "ContractingParty"):
        for party in children(contracting, "Party"):
            buyer_refs.extend(reference(party, "PartyIdentification"))
    if not buyer_refs or any(ref not in orgs for ref in buyer_refs):
        raise SourceParseError("ted: unresolved UBL buyer reference")
    lots = children(root, "ProcurementProjectLot")
    if not lots:
        lots = [root]
    projects = children(root, "ProcurementProject")
    entities: list[EntityEndpoint] = []
    assertions: list[Assertion] = []
    errors = 0
    contracts = {}

    def link(
        subject: EntityEndpoint, relation: str, target: EntityEndpoint, when: datetime = published
    ) -> None:
        assertion = make_assertion(adapter, record, subject, relation, target, valid_from=when)
        assertion.provenance.source_url = record.source_url
        assertions.append(assertion)

    for lot in lots:
        lot_id = value(lot, "ID") if lot is not root else "notice"
        if not lot_id:
            errors += 1
            continue
        project = children(lot, "ProcurementProject") or projects
        title = value(project[0], "Name") if project else None
        key = f"{identifier}#{lot_id}"
        contract = EntityEndpoint(
            entity_id=key_entity_id(("ted_notice_id", key)),
            type="Contract",
            label=title or key,
            deterministic_key=("ted_notice_id", key),
        )
        contracts[lot_id] = contract
        entities.append(contract)
        cpvs = []
        for project_node in project:
            cpvs.extend(descendants(project_node, "ItemClassificationCode"))
        for cpv in cpvs:
            code = (cpv.text or "").strip()
            if cpv.get("listName") == "cpv" and code:
                link(contract, "ABOUT_TOPIC", topic_endpoint("CPV", code))
        for buyer_ref in buyer_refs:
            company = orgs[buyer_ref]
            name = company_name(company)
            if not name:
                errors += 1
                continue
            addresses = children(company, "PostalAddress")
            address = addresses[0] if addresses else None
            countries = children(address, "Country") if address is not None else []
            country = value(countries[0], "IdentificationCode") if countries else ""
            country = ISO3_TO_ISO2.get(country or "", country)
            buyer_key = hashlib.sha256(f"{country or ''}|{name}".encode()).hexdigest()
            buyer = EntityEndpoint(
                entity_id=key_entity_id(("ted_buyer_id", buyer_key)),
                type="PublicBody",
                label=name,
                deterministic_key=("ted_buyer_id", buyer_key),
            )
            link(buyer, "BUYER_OF", contract)
            if address is not None:
                postal = value(address, "PostalZone")
                city = value(address, "CityName") or ""
                if country and postal:
                    location = address_location(country, postal, city)
                    link(buyer, "HEADQUARTERED_IN", location)
                    nuts = value(address, "CountrySubentityCode")
                    if nuts is None and postal_lookup is not None:
                        # Only reference-mapped ISO2 codes can join the correspondence.
                        if len(country) == 2:
                            nuts = postal_lookup(country, postal)
                    if nuts:
                        region = EntityEndpoint(
                            entity_id=key_entity_id(("nuts_code", nuts)),
                            type="AdministrativeRegion",
                            label=nuts,
                            deterministic_key=("nuts_code", nuts),
                        )
                        link(location, "LOCATED_IN", region)

    # Definitions are distinguished from their nested ID-only references.
    tenders = {
        value(t, "ID"): t for t in descendants(root, "LotTender") if children(t, "TenderingParty")
    }
    parties = {
        value(t, "ID"): t for t in descendants(root, "TenderingParty") if children(t, "Tenderer")
    }
    award_dates: dict[str, set[datetime]] = {}
    for settled in descendants(root, "SettledContract"):
        when = date(value(settled, "AwardDate"))
        if when is not None:
            for ref in reference(settled, "LotTender"):
                award_dates.setdefault(ref, set()).add(when)
    for result in descendants(root, "LotResult"):
        if value(result, "TenderResultCode") != "selec-w":
            continue
        lot_refs = reference(result, "TenderLot")
        tender_refs = reference(result, "LotTender")
        if len(lot_refs) != 1 or lot_refs[0] not in contracts or not tender_refs:
            errors += 1
            continue
        contract = contracts[lot_refs[0]]
        for tender_ref in tender_refs:
            tender = tenders.get(tender_ref)
            if tender is None:
                errors += 1
                continue
            party_refs = reference(tender, "TenderingParty")
            if not party_refs:
                errors += 1
            for party_ref in party_refs:
                party = parties.get(party_ref)
                if party is None:
                    errors += 1
                    continue
                org_refs = reference(party, "Tenderer")
                if not org_refs:
                    errors += 1
                for org_ref in org_refs:
                    company = orgs.get(org_ref)
                    if company is None:
                        errors += 1
                        continue
                    name = company_name(company)
                    if not name:
                        errors += 1
                        continue
                    lei = None
                    for legal in children(company, "PartyLegalEntity"):
                        for code in children(legal, "CompanyID"):
                            scheme = (code.get("schemeName") or code.get("schemeID") or "").lower()
                            if scheme == "lei":
                                lei = (code.text or "").strip()
                    winner = EntityEndpoint(
                        entity_id=key_entity_id(("lei", lei))
                        if lei
                        else hash_entity_id("corporation", name),
                        type="Corporation",
                        label=name,
                        deterministic_key=("lei", lei) if lei else None,
                    )
                    for when in award_dates.get(tender_ref, {published}):
                        link(contract, "AWARDED_TO", winner, when)
    return NormalizedRecord(
        content_hash=payload_hash(record.payload),
        kind="structured",
        entities=entities,
        assertions=assertions,
        errors=errors,
    )
