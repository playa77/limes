"""Bounded target preparation and source/section reads; no provider calls on reads."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from limes.enrichment.models import AcquisitionTarget, EnrichmentResponse, EnrichmentSelection
from limes.errors import LimesError
from limes.graph.driver import GraphDriver
from limes.ontology.model import Ontology
from limes.sources.base import SourceAdapter
from limes.types import EntityEndpoint, NormalizedRecord, RawRecord


def prepare_targets(
    driver: GraphDriver,
    selections: list[EnrichmentSelection],
    source: str,
) -> list[AcquisitionTarget]:
    if not 1 <= len(selections) <= 10:
        raise LimesError("select one to ten reviewed entities")
    if len({s.entity_id + ":" + str(s.symbol) for s in selections}) != len(selections):
        raise LimesError("duplicate enrichment selection")
    targets = []
    for selection in selections:
        rows = driver.read(
            "MATCH (n:Entity {entity_id:$id}) RETURN n.entity_id AS id, n.label AS label, "
            "labels(n) AS labels, n.wikidata_qid AS qid",
            {"id": selection.entity_id},
            30,
        )
        if not rows:
            raise LimesError("enrichment target must be an existing graph entity")
        row = rows[0]
        if row.get("qid") and selection.qid and row["qid"] != selection.qid:
            raise LimesError("reviewed QID conflicts with existing registry identity")
        if source == "yahoo_finance" and "Corporation" not in row["labels"]:
            raise LimesError("Yahoo selection must be a corporation")
        # Concrete type is read from the existing graph, never inferred from a ticker.
        concrete = next(
            (v for v in row["labels"] if v not in ("Entity", "Agent", "Place", "Artifact")), None
        )
        if concrete is None:
            raise LimesError("target has no concrete ontology type")
        targets.append(
            AcquisitionTarget(
                selection=selection,
                entity=EntityEndpoint(entity_id=row["id"], type=concrete, label=row["label"]),
            )
        )
    return targets


def read_enrichment(
    driver: GraphDriver,
    entity_id: str,
    *,
    source: str | None = None,
    section: str | None = None,
    as_of: datetime | None = None,
    believed: datetime | None = None,
    limit: int = 100,
) -> EnrichmentResponse:
    rows = driver.read(
        "MATCH (:Entity {entity_id:$id})-[:HAS_ENRICHMENT]->(s:EnrichmentSnapshot) "
        "WHERE ($source IS NULL OR s.source_id=$source) "
        "AND ($section IS NULL OR s.section=$section) "
        "AND ($as_of IS NULL OR s.source_as_of IS NULL OR s.source_as_of <= $as_of) "
        "AND ($believed IS NULL OR s.recorded_at <= $believed) "
        "OPTIONAL MATCH (c:EnrichmentCheck {snapshot_id:s.entity_id}) "
        "WHERE ($believed IS NULL OR c.checked_at <= $believed) "
        "WITH s, max(c.checked_at) AS checked "
        "RETURN properties(s) AS snapshot, checked "
        "ORDER BY coalesce(checked, s.recorded_at) DESC, s.entity_id LIMIT $limit",
        {
            "id": entity_id,
            "source": source,
            "section": section,
            "as_of": as_of,
            "believed": believed,
            "limit": limit + 1,
        },
        30,
    )
    result = EnrichmentResponse(entity_id=entity_id, truncated=len(rows) > limit)
    cutoff = datetime.now(UTC) - timedelta(days=30)
    for row in rows[:limit]:
        snapshot: dict[str, Any] = dict(row["snapshot"])
        snapshot["last_checked_at"] = row.get("checked") or snapshot["retrieved_at"]
        for key, value in snapshot.items():
            if hasattr(value, "to_native"):
                snapshot[key] = value.to_native()
        observations = driver.read(
            "MATCH (:EnrichmentSnapshot {entity_id:$id})-[:HAS_OBSERVATION]->"
            "(o:EnrichmentObservation) "
            "WHERE ($as_of IS NULL OR o.source_as_of IS NULL OR o.source_as_of <= $as_of) "
            "RETURN properties(o) AS observation ORDER BY o.evidence_row LIMIT 1002",
            {"id": snapshot["entity_id"], "as_of": as_of},
            30,
        )
        snapshot["observations"] = [
            {
                k: v.to_native() if hasattr(v, "to_native") else v
                for k, v in r["observation"].items()
            }
            for r in observations[:1001]
        ]
        for observation in snapshot["observations"]:
            source_date = observation.get("source_as_of")
            observation["stale"] = source_date < cutoff if source_date else None
            observation["freshness_basis"] = "source_as_of" if source_date else "unknown"
        snapshot["observations_truncated"] = len(observations) > 1001
        # Staleness is a display diagnosis, never a retraction or zero-ownership fact.
        snapshot["stale"] = (snapshot.get("source_as_of") or snapshot["last_checked_at"]) < cutoff
        snapshot["freshness_basis"] = (
            "source_as_of" if snapshot.get("source_as_of") else "acquisition_only"
        )
        result.snapshots.append(snapshot)
    if not rows:
        result.diagnosis.append("No acquired enrichment for this selection/filter.")
    if result.truncated:
        result.diagnosis.append(
            "Snapshot result limit reached; narrow source/section/time filters."
        )
    result.diagnosis.append(
        "Secondary partial snapshots; unknown identity and absent rows do not establish "
        "ownership completeness, disposal or resignation. "
        "Overlapping holder lists must not be summed."
    )
    return result


def resolve_observation_candidates(driver: GraphDriver, entities: list[EntityEndpoint]) -> None:
    from limes.resolution.resolve import observation_identity_candidates

    for entity in entities:
        if (
            entity.type != "EnrichmentObservation"
            or entity.properties.get("identity_status") != "unresolved"
        ):
            continue
        kind = "Person" if entity.properties.get("kind") == "governance" else "Corporation"
        candidates = observation_identity_candidates(
            driver, str(entity.properties.get("name") or ""), kind
        )
        entity.properties["identity_candidates"] = json.dumps(candidates)


def validate_normalized_section(
    adapter: SourceAdapter,
    raw: RawRecord,
    normalized: NormalizedRecord,
    ontology: Ontology,
) -> NormalizedRecord:
    """Provider scalar drift becomes a durable failed section, never a stuck run."""
    from limes.enrichment.common import snapshot
    from limes.enrichment.models import SectionStatus
    from limes.graph.loader import validate_entity_properties

    endpoints = list(normalized.entities)
    endpoints.extend(e for a in normalized.assertions for e in (a.subject, a.object))
    try:
        validate_entity_properties(endpoints, ontology)
    except ValueError:
        return snapshot(
            adapter,
            raw,
            SectionStatus(
                section=str((raw.acquisition_context or {}).get("section", "unknown")),
                status="failed",
                reason="provider properties violate ontology types",
            ),
            [],
        )
    return normalized
