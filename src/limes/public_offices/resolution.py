"""Shared deterministic person resolution for official roster observations."""

from __future__ import annotations

import json

from limes.errors import SourceParseError
from limes.graph.driver import GraphDriver
from limes.resolution.resolve import observation_identity_candidates
from limes.types import EntityEndpoint, NormalizedRecord


def resolve_identities(driver: GraphDriver, normalized: NormalizedRecord) -> None:
    replacements: dict[str, EntityEndpoint] = {}
    for membership in normalized.entities:
        if membership.type != "RosterMembership":
            continue
        external_id = str(membership.properties["external_id"])
        person_id = str(membership.properties["person_id"])
        person = next(
            e for e in normalized.entities if e.type == "Person" and e.entity_id == person_id
        )
        dip_id = person.deterministic_key[1] if person.deterministic_key else None
        matches = driver.read(
            "MATCH (p:Person) WHERE "
            "($dip IS NOT NULL AND p.bundestag_id=$dip) OR EXISTS { "
            "MATCH (i:PersonIdentifier {external_id:$external}) "
            "WHERE i.canonical_person_id=p.entity_id OR "
            "(i.canonical_person_id IS NULL AND EXISTS { "
            "MATCH (i)-[binding:IDENTIFIES]->(p) WHERE binding.retracted_at IS NULL }) } "
            "RETURN DISTINCT p.entity_id AS id, p.label AS label ORDER BY id LIMIT 3",
            {"dip": dip_id, "external": external_id},
            30,
        )
        if len(matches) > 1:
            raise SourceParseError("conflicting verified person identifiers; review required")
        if matches:
            canonical = EntityEndpoint(
                entity_id=str(matches[0]["id"]),
                type="Person",
                label=str(matches[0]["label"]),
                aliases=[person.label],
            )
            replacements[person_id] = canonical
            membership.properties["person_id"] = canonical.entity_id
            membership.properties["identity_status"] = "verified_identifier_reuse"
        else:
            candidates = observation_identity_candidates(
                driver, person.label, "Person", matching_aliases(person.label)
            )
            candidates = [c for c in candidates if c != person_id]
            membership.properties["identity_candidates"] = json.dumps(candidates)
            if candidates and not dip_id:
                membership.properties["identity_status"] = "candidate_review_required"
    if not replacements:
        return
    normalized.entities = [replacements.get(e.entity_id, e) for e in normalized.entities]
    for assertion in normalized.assertions:
        old_subject, old_object = assertion.subject.entity_id, assertion.object.entity_id
        assertion.subject = replacements.get(assertion.subject.entity_id, assertion.subject)
        assertion.object = replacements.get(assertion.object.entity_id, assertion.object)
        if (old_subject, old_object) != (assertion.subject.entity_id, assertion.object.entity_id):
            from limes.sources.base import hash_entity_id

            assertion.assertion_id = hash_entity_id(
                "canonical-roster",
                assertion.assertion_id,
                assertion.subject.entity_id,
                assertion.object.entity_id,
            )


def matching_aliases(label: str) -> list[str]:
    """Candidate spellings only; official labels and identifiers remain intact."""
    import re

    clean = re.sub(r",\s*(?:LL\.M\.|Ph\.?D\.?|M\.A\.).*$", "", label)
    clean = re.sub(r"^(?:(?:Prof\.|Dr\.|h\.c\.)\s*)+", "", clean).strip()
    aliases = [label, clean]
    if clean.count(",") == 1:
        last, first = clean.split(",", 1)
        aliases.append(f"{first.strip()} {last.strip()}")
    translation: dict[str, str | int | None] = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "Ä": "Ae",
        "Ö": "Oe",
        "Ü": "Ue",
        "ß": "ss",
    }
    for value in list(aliases):
        variant = value.translate(str.maketrans(translation))
        aliases.append(variant)
    return list(dict.fromkeys(aliases))
