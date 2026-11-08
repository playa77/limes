"""Ontology-typed roster observations; current observation is distinct from service dates."""

from __future__ import annotations

import json

from limes.public_offices.models import Snapshot
from limes.sources.base import (
    SourceAdapter,
    hash_entity_id,
    key_entity_id,
    make_assertion,
    payload_hash,
)
from limes.types import Assertion, EntityEndpoint, NormalizedRecord, RawRecord


def normalize_snapshot(
    adapter: SourceAdapter, raw: RawRecord, snapshot: Snapshot
) -> NormalizedRecord:
    scope = snapshot.scope
    snapshot_id = hash_entity_id("roster", scope, payload_hash(raw.payload))
    snapshot_node = EntityEndpoint(
        entity_id=snapshot_id,
        type="RosterSnapshot",
        label=f"{scope}: {snapshot.observed_at.isoformat()}",
        deterministic_key=("snapshot_id", snapshot_id),
        properties={
            "scope": scope,
            "term": snapshot.term,
            "observed_at": snapshot.observed_at,
            "source_id": adapter.source_id,
            "expected_ids": json.dumps(snapshot.expected_ids),
            "expected_count": snapshot.expected_count,
            "check_basis": snapshot.check_basis,
            "consistent": snapshot.consistent,
            "manifest_hash": payload_hash(raw.payload),
            "source_updates": json.dumps(snapshot.source_updates),
        },
    )
    body_key = "DE:" + scope
    body = EntityEndpoint(
        entity_id=key_entity_id(("institution_id", body_key)),
        type="PublicBody",
        label=adapter.name.removesuffix(" — official serving roster"),
        deterministic_key=("institution_id", body_key),
        properties={
            "jurisdiction": "DE"
            if scope in ("bt", "br", "bp") or scope.startswith("bverfg")
            else "DE-" + scope.upper()
        },
    )
    assertions: list[Assertion] = []
    entities = [snapshot_node, body]
    court = body
    if scope.startswith("bverfg"):
        court = EntityEndpoint(
            entity_id="institution_id:DE:BVerfG",
            type="PublicBody",
            label="Bundesverfassungsgericht",
            deterministic_key=("institution_id", "DE:BVerfG"),
        )
        entities.append(court)
        structure = make_assertion(adapter, raw, body, "PART_OF_BODY", court)
        structure.provenance.validity_basis = "roster_observation"
        structure.provenance.roster_snapshot_id = snapshot_id
        structure.provenance.evidence_document_id = (
            snapshot.pages[0]["sha256"] if snapshot.pages else None
        )
        structure.provenance.source_url = raw.source_url
        assertions.append(structure)
    rows = [(row, True) for row in snapshot.members] + [
        (row, False) for row in snapshot.historical_members
    ]
    for row, is_current in rows:
        episode_key = (
            "current"
            if is_current
            else "historical:"
            + (
                row.service_end.isoformat()
                if row.service_end is not None
                else row.evidence_hash + row.locator
            )
        )
        # The identity resolver may later replace this endpoint with an exact
        # verified external-identifier/DIP match. Names never mint identity.
        scoped = f"official:{scope}:{row.external_id}"
        person_id = (
            key_entity_id(("bundestag_id", row.bundestag_id))
            if row.bundestag_id
            else hash_entity_id("person", scoped)
        )
        person = EntityEndpoint(
            entity_id=person_id,
            type="Person",
            label=row.name,
            aliases=list(dict.fromkeys([row.name, *row.aliases])),
            deterministic_key=("bundestag_id", row.bundestag_id) if row.bundestag_id else None,
        )
        identifier = EntityEndpoint(
            entity_id=hash_entity_id("person-identifier", scoped),
            type="PersonIdentifier",
            label=scoped,
            deterministic_key=("external_id", scoped),
        )
        # Unknown parliamentary term never collapses offices across turnover.
        term_key = snapshot.term or (snapshot_id if row.role == "member" else "service")
        office_key = json.dumps([scope, row.role, term_key, row.land], ensure_ascii=False)
        office = EntityEndpoint(
            entity_id=hash_entity_id("office", office_key),
            type="Office",
            label=f"{body.label}: {row.role}" + (f" ({snapshot.term})" if snapshot.term else ""),
            deterministic_key=("office_key", office_key),
            properties={
                "scope": scope,
                "term": snapshot.term,
                "role": row.role,
                "represented_land": row.land,
            },
        )
        if scope == "bt" and snapshot.term is not None and snapshot.term.isdigit():
            from limes.sources.bundestag_dip import _office, _period_start

            office = _office(int(snapshot.term), _period_start(int(snapshot.term)))
        member_id = hash_entity_id("roster-member", snapshot_id, row.external_id, episode_key)
        membership = EntityEndpoint(
            entity_id=member_id,
            type="RosterMembership",
            label=row.name,
            deterministic_key=("membership_id", member_id),
            properties={
                "scope": scope,
                "is_current": is_current,
                "snapshot_id": snapshot_id,
                "person_id": person_id,
                "office_id": office.entity_id,
                "external_id": scoped,
                "profile_url": row.profile_url,
                "term": snapshot.term,
                "role": row.role,
                "represented_land": row.land,
                "group_label": row.group,
                "party_label": row.party,
                "constituency": row.constituency,
                "mandate_kind": row.mandate_kind,
                "service_start": row.service_start,
                "service_end": row.service_end,
                "source_updated_text": row.source_updated_text,
                "service_precision": row.service_precision,
                "time_basis": "source_service_date" if row.service_start else "observed_current",
                "observed_at": snapshot.observed_at,
                "source_id": adapter.source_id,
                "evidence_hash": row.evidence_hash,
                "evidence_url": row.evidence_url,
                "evidence_locator": row.locator,
                "identity_status": "source_identified",
                "identity_candidates": "[]",
                "profile_member_class": row.profile_member_class,
                "conflicts": json.dumps(row.conflicts),
                "profile_evidence_hash": row.profile_evidence_hash,
                "leadership": json.dumps(row.leadership, ensure_ascii=False),
                "service_evidence": json.dumps(row.service_evidence, ensure_ascii=False),
            },
        )
        entities.extend([person, identifier, office, membership])
        relations = [
            (identifier, "IDENTIFIES", person),
            (snapshot_node, "HAS_ROSTER_MEMBER", membership),
            (membership, "ROSTER_PERSON", person),
            (membership, "ROSTER_OFFICE", office),
            (person, "HOLDS_OFFICE" if is_current else "PARTICIPATED_IN_TERM", office),
            (office, "OFFICE_AT", body),
        ]
        for leadership in row.leadership:
            leadership_body = court if leadership in ("Präsident", "Vizepräsident") else body
            leadership_key = json.dumps([leadership_body.entity_id, leadership], ensure_ascii=False)
            leadership_office = EntityEndpoint(
                entity_id=key_entity_id(("office_key", leadership_key)),
                type="Office",
                label=leadership,
                deterministic_key=("office_key", leadership_key),
                properties={"scope": scope, "role": leadership},
            )
            entities.append(leadership_office)
            relations.extend(
                [
                    (person, "HOLDS_OFFICE", leadership_office),
                    (leadership_office, "OFFICE_AT", leadership_body),
                ]
            )
        if row.group and row.group.casefold() not in ("fraktionslos", "parteilos", "unabhängig"):
            group_key = json.dumps([scope, term_key, row.group], ensure_ascii=False)
            group = EntityEndpoint(
                entity_id=key_entity_id(("group_id", group_key)),
                type="ParliamentaryGroup",
                label=row.group,
                deterministic_key=("group_id", group_key),
                properties={"scope": scope, "term": snapshot.term},
            )
            entities.append(group)
            relations.extend(
                [
                    (person, "MEMBER_OF_GROUP" if is_current else "GROUP_EVIDENCE", group),
                    (group, "GROUP_AT", body),
                ]
            )
        for subject, relation, obj in relations:
            assertion = make_assertion(
                adapter, raw, subject, relation, obj, valid_from=snapshot.observed_at
            )
            assertion.assertion_id = hash_entity_id(
                "roster-assertion",
                snapshot_id,
                row.external_id,
                episode_key,
                relation,
                subject.entity_id,
                obj.entity_id,
            )
            assertion.provenance.evidence_channel = "structured"
            assertion.provenance.validity_basis = "roster_observation"
            assertion.provenance.roster_snapshot_id = snapshot_id
            assertion.provenance.evidence_document_id = row.evidence_hash
            assertion.provenance.evidence_member = row.locator
            assertion.provenance.source_url = row.evidence_url
            assertions.append(assertion)
    return NormalizedRecord(
        content_hash=payload_hash(raw.payload),
        kind="structured",
        assertions=assertions,
        entities=entities,
        errors=sum(bool(m.conflicts) for m in snapshot.members),
    )
