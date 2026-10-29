"""Bounded cross-source evidence; event matches are hypotheses, never graph merges."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from itertools import combinations
from typing import Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from limes.api.models import native_datetime
from limes.graph.driver import GraphDriver
from limes.graph.temporal import as_believed, as_believed_params, as_of, as_of_params
from limes.news.models import Investigation


class MatchReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    left: str = Field(min_length=1, max_length=256)
    right: str = Field(min_length=1, max_length=256)
    decision: Literal["unresolved", "same_event", "different_event"]
    assessment: Literal["unassessed", "supports", "challenges", "context"] = "unassessed"
    independence: Literal["unknown", "dependent", "independent"] = "unknown"
    rationale: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def different(self) -> MatchReview:
        if self.left == self.right or not self.rationale.strip():
            raise ValueError("review needs distinct evidence and a nonblank rationale")
        return self


class ReviewView(MatchReview):
    investigation_id: str
    recorded_at: AwareDatetime


class DevelopmentEvidence(BaseModel):
    evidence_id: str
    kind: Literal["claim", "assertion", "coded_observation"]
    subject_id: str
    object_id: str
    subject_label: str
    object_label: str
    relation: str
    properties: dict[str, Any]
    dependency_key: str | None = None


class EventMatch(BaseModel):
    candidate_id: str
    left: str
    right: str
    decision: str = "unresolved"
    assessment: str = "unassessed"
    independence: str = "unknown"
    rationale: str | None = None
    review_id: str | None = None


class DevelopmentView(BaseModel):
    investigation_id: str
    evidence: list[DevelopmentEvidence]
    candidates: list[EventMatch]
    reviews: list[ReviewView]
    coverage: dict[str, int]
    locations: list[dict[str, Any]]
    truncated: bool
    diagnosis: list[str]


def temporal(
    alias: str, valid: datetime | None, believed: datetime | None
) -> tuple[str, dict[str, Any]]:
    parts, params = [], {}
    if valid is not None:
        parts.append(as_of(alias, valid))
        params.update(as_of_params(alias, valid))
    if believed is not None:
        parts.append(as_believed(alias, believed))
        params.update(as_believed_params(alias, believed))
    # Default includes historical/replaced evidence. Explicit instants narrow each axis.
    return " AND ".join(parts) or "true", params


def properties(values: dict[str, Any]) -> dict[str, Any]:
    return {k: native_datetime(v) if hasattr(v, "to_native") else v for k, v in values.items()}


def known_dependent(a: DevelopmentEvidence, b: DevelopmentEvidence) -> bool:
    if a.dependency_key and a.dependency_key == b.dependency_key:
        return True
    for field in ("evidence_document_id", "report_url"):
        if a.properties.get(field) and a.properties.get(field) == b.properties.get(field):
            return True
    return False


def pair_id(left: str, right: str) -> str:
    import json

    return sha256(json.dumps(sorted([left, right])).encode()).hexdigest()


def suggest(evidence: list[DevelopmentEvidence], reviews: list[ReviewView]) -> list[EventMatch]:
    latest = {}
    for review in sorted(reviews, key=lambda r: (r.recorded_at, str(r.request_id))):
        latest[pair_id(review.left, review.right)] = review
    result = []
    by_id = {e.evidence_id: e for e in evidence}
    pairs = {
        pair_id(a.evidence_id, b.evidence_id): (a, b)
        for a, b in combinations(evidence, 2)
        if (a.subject_id, a.relation, a.object_id) == (b.subject_id, b.relation, b.object_id)
    }
    # Human-reviewed pairs may connect different event predicates/participants.
    for key, review in latest.items():
        if review.left in by_id and review.right in by_id:
            pairs[key] = (by_id[review.left], by_id[review.right])
    for key, (a, b) in sorted(pairs.items()):
        chosen = latest.get(key)
        dependent = known_dependent(a, b)
        result.append(
            EventMatch(
                candidate_id=key,
                left=a.evidence_id,
                right=b.evidence_id,
                decision=chosen.decision if chosen else "unresolved",
                assessment=chosen.assessment if chosen else "unassessed",
                independence="dependent"
                if dependent
                else chosen.independence
                if chosen
                else "unknown",
                rationale=chosen.rationale if chosen else None,
                review_id=str(chosen.request_id) if chosen else None,
            )
        )
    return result


def developments(
    driver: GraphDriver,
    investigation: Investigation,
    valid: datetime | None = None,
    believed: datetime | None = None,
    limit: int = 100,
    references: list[str] | None = None,
) -> DevelopmentView:
    ids = list(investigation.entity_ids)
    targets = driver.read(
        "MATCH (s:Entity)-[r]->(o:Entity) WHERE r.assertion_id IN $assertions "
        "RETURN s.entity_id AS subject, o.entity_id AS object",
        {"assertions": investigation.assertion_ids},
        30,
    )
    ids = list(dict.fromkeys(ids + [str(row[k]) for row in targets for k in ("subject", "object")]))
    clause, params = temporal("c", valid, believed)
    rows = driver.read(
        "MATCH (c:NewsClaim) WHERE (c.subject_id IN $ids OR c.object_id IN $ids "
        "OR c.investigation_id=$case) AND ($refs IS NULL OR 'claim:'+c.claim_id IN $refs) AND "
        + clause
        + " RETURN properties(c) AS item ORDER BY c.recorded_at, c.claim_id LIMIT $limit",
        {
            **params,
            "ids": ids,
            "case": investigation.investigation_id,
            "refs": references,
            "limit": limit + 1,
        },
        30,
    )
    evidence = []
    for row in rows[:limit]:
        p = properties(row["item"])
        evidence.append(
            DevelopmentEvidence(
                evidence_id="claim:" + p["claim_id"],
                kind="claim",
                subject_id=p["subject_id"],
                object_id=p["object_id"],
                subject_label=p["subject_label"],
                object_label=p["object_label"],
                relation=p["relation"],
                properties=p,
                dependency_key=p.get("syndication_key"),
            )
        )
    # One bounded hop around tracked targets, not unbounded graph traversal.
    clause, params = temporal("r", valid, believed)
    facts = driver.read(
        "MATCH (s:Entity)-[r]->(o:Entity) WHERE r.assertion_id IS NOT NULL "
        "AND (s.entity_id IN $ids OR o.entity_id IN $ids OR r.assertion_id IN $assertions) "
        "AND ($refs IS NULL OR 'assertion:'+r.assertion_id IN $refs) AND "
        + clause
        + " RETURN properties(r) AS item, type(r) AS relation, "
        "s.entity_id AS subject, s.label AS subject_label, "
        "o.entity_id AS object, o.label AS object_label "
        "ORDER BY r.recorded_at, r.assertion_id LIMIT $limit",
        {
            **params,
            "ids": ids,
            "assertions": investigation.assertion_ids,
            "refs": references,
            "limit": limit + 1,
        },
        30,
    )
    for row in facts[:limit]:
        p = properties(row["item"])
        coded = p.get("evidence_channel") == "coded"
        # Channel names alone never certify an official source or independence.
        evidence.append(
            DevelopmentEvidence(
                evidence_id="assertion:" + p["assertion_id"],
                kind="coded_observation" if coded else "assertion",
                subject_id=row["subject"],
                object_id=row["object"],
                subject_label=row["subject_label"] or row["subject"],
                object_label=row["object_label"] or row["object"],
                relation=row["relation"],
                properties=p,
                dependency_key=(p.get("report_url") or p.get("source_url")) if coded else None,
            )
        )
    review_rows = driver.read(
        "MATCH (r:EventMatchReview {investigation_id:$case}) "
        "WHERE ($believed IS NULL OR r.recorded_at <= $believed) "
        "RETURN properties(r) AS review ORDER BY r.recorded_at DESC, r.request_id DESC LIMIT 1001",
        {"case": investigation.investigation_id, "believed": believed},
        30,
    )
    reviews = [ReviewView.model_validate(properties(row["review"])) for row in review_rows[:1000]]
    truncated = len(rows) > limit or len(facts) > limit or len(review_rows) > 1000
    candidates = suggest(evidence, reviews)
    truncated = truncated or len(candidates) > 500
    coverage = {
        kind: sum(e.kind == kind for e in evidence)
        for kind in ("claim", "assertion", "coded_observation")
    }
    found = driver.read(
        "MATCH (n:Entity) WHERE n.entity_id IN $ids RETURN count(n) AS count",
        {"ids": investigation.entity_ids},
        30,
    )
    coverage.update(
        entity_targets_requested=len(investigation.entity_ids),
        entity_targets_found=int(found[0]["count"]),
        relation_targets_requested=len(investigation.assertion_ids),
        relation_targets_found=len(targets),
    )
    notes = [
        "Chronology does not establish causation or misconduct. Event matches remain hypotheses.",
        "Distinct reports/sources do not establish independent corroboration.",
        "Coverage counts describe this bounded result, not source completeness.",
    ]
    if not evidence:
        notes.append(
            "No evidence matches these targets and times; check acquisition and time precision."
        )
    if valid is not None:
        notes.append("Unknown validity instants are excluded; recorded time is never substituted.")
    if truncated:
        notes.append(
            "Result truncated. Narrow targets/times; candidate and review coverage is partial."
        )
    endpoints = list({v for e in evidence for v in (e.subject_id, e.object_id)})
    location_rows = driver.read(
        "MATCH (n:Entity) WHERE n.entity_id IN $ids "
        "AND n.latitude IS NOT NULL AND n.longitude IS NOT NULL "
        "RETURN n.entity_id AS entity_id, n.label AS label, "
        "n.latitude AS latitude, n.longitude AS longitude ORDER BY n.entity_id LIMIT 401",
        {"ids": endpoints},
        30,
    )
    import math

    locations = [
        row
        for row in location_rows
        if isinstance(row["latitude"], (int, float))
        and isinstance(row["longitude"], (int, float))
        and math.isfinite(row["latitude"])
        and math.isfinite(row["longitude"])
        and -90 <= row["latitude"] <= 90
        and -180 <= row["longitude"] <= 180
    ]
    if not locations:
        notes.append("No directly geolocated evidence endpoints; no positions are inferred.")
    return DevelopmentView(
        investigation_id=investigation.investigation_id,
        evidence=evidence,
        candidates=candidates[:500],
        reviews=reviews,
        coverage=coverage,
        locations=locations,
        truncated=truncated,
        diagnosis=notes,
    )
