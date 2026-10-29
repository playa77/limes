"""Shared source-section snapshot construction; no disappearance-based retraction."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from limes.enrichment.models import AcquisitionTarget, SectionStatus
from limes.sources.base import hash_entity_id, make_assertion, payload_hash
from limes.types import Assertion, EntityEndpoint, NormalizedRecord, RawRecord


def date(value: Any) -> datetime | None:
    value = raw(value)
    if value is None or isinstance(value, bool):
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, UTC)
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    except (ValueError, OverflowError, OSError):
        return None


def raw(value: Any) -> Any:
    return value.get("raw") if isinstance(value, dict) else value


def snapshot(
    adapter: Any,
    record: RawRecord,
    status: SectionStatus,
    observations: list[dict[str, Any]],
    *,
    extra: dict[str, Any] | None = None,
    version_key: str | None = None,
) -> NormalizedRecord:
    context = record.acquisition_context or {}
    target = AcquisitionTarget.model_validate(context["target"])
    digest = payload_hash(record.payload)
    # Identical payloads replay to identical observations, regardless of fetch time.
    identity = hash_entity_id(
        "enrichment",
        adapter.source_id,
        target.entity.entity_id,
        status.section,
        status.status,
        json.dumps(target.selection.model_dump(mode="json"), sort_keys=True),
        version_key or digest,
    )
    base = {
        "source_id": adapter.source_id,
        "source_trust": adapter.trust_rank,
        "section": status.section,
        "status": status.status,
        "reason": status.reason,
        "complete": status.complete,
        "source_as_of": status.source_as_of,
        "recorded_at": record.fetched_at,
        "valid_from": status.source_as_of or record.fetched_at,
        "retrieved_at": record.fetched_at,
        "evidence_document_id": digest,
        "source_url": record.source_url,
        "entity_mapping": target.selection.model_dump_json(),
        "target_id": target.entity.entity_id,
        "company_id": target.entity.entity_id if target.entity.type == "Corporation" else None,
        "mapping_status": "operator_reviewed",
        "wikidata_qid": target.selection.qid,
        "rows": len(observations),
        **(extra or {}),
    }
    node = EntityEndpoint(
        entity_id=identity,
        type="EnrichmentSnapshot",
        label=f"{adapter.name}: {status.section}",
        deterministic_key=("snapshot_id", identity),
        properties=base,
    )
    entities = [node]
    assertions: list[Assertion] = []

    def link(subject: EntityEndpoint, relation: str, object_: EntityEndpoint) -> None:
        assertion = make_assertion(adapter, record, subject, relation, object_)
        assertion.assertion_id = hash_entity_id(
            "observation-edge", identity, relation, subject.entity_id, object_.entity_id
        )
        assertion.provenance.evidence_channel = "structured"
        assertion.provenance.source_url = record.source_url
        assertion.provenance.evidence_member = status.section
        row = object_.properties.get("evidence_row")
        if isinstance(row, int):
            assertion.provenance.evidence_row = row
        assertion.provenance.source_recorded_at = status.source_as_of
        assertions.append(assertion)

    link(target.entity, "HAS_ENRICHMENT", node)
    if adapter.source_id == "yahoo_finance" and status.section == "price" and observations:
        selection = target.selection
        listing_id = f"yahoo:{selection.exchange}:{selection.symbol}"
        listing = EntityEndpoint(
            entity_id=listing_id,
            type="SecurityListing",
            label=selection.symbol or listing_id,
            deterministic_key=("listing_id", listing_id),
            properties={
                "symbol": selection.symbol,
                "exchange": selection.exchange,
                "provider": "yahoo_finance",
            },
        )
        entities.append(listing)
        link(target.entity, "HAS_LISTING", listing)
        if selection.isin:
            security = EntityEndpoint(
                entity_id=f"isin:{selection.isin}",
                type="Security",
                label=selection.share_class or selection.isin,
                deterministic_key=("isin", selection.isin),
                properties={"share_class": selection.share_class},
            )
            entities.append(security)
            link(listing, "REPRESENTS_SECURITY", security)
    for index, fields in enumerate(observations):
        oid = hash_entity_id("observation", identity, str(index))
        observation = EntityEndpoint(
            entity_id=oid,
            type="EnrichmentObservation",
            label=str(fields.get("name") or fields.get("kind") or status.section),
            deterministic_key=("observation_id", oid),
            properties={
                **base,
                **fields,
                "evidence_row": index,
                "snapshot_id": identity,
                "observation_id": oid,
            },
        )
        entities.append(observation)
        link(node, "HAS_OBSERVATION", observation)
    return NormalizedRecord(
        content_hash=digest,
        kind="structured",
        entities=entities,
        assertions=assertions,
        errors=int(status.status in ("failed", "ambiguous")),
    )
