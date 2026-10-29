"""Authenticated investigations, bounded claim filtering and archive-backed evidence."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AwareDatetime

from limes.api.deps import get_archive, get_driver, get_settings
from limes.api.models import native_datetime
from limes.api.routers.operations import require_operator
from limes.archive.store import ArchiveStore
from limes.config import Settings
from limes.graph.driver import GraphDriver
from limes.graph.loader import save_event_match_review, save_news_review
from limes.news.developments import (
    DevelopmentView,
    MatchReview,
    ReviewView,
    developments,
    known_dependent,
    properties,
)
from limes.news.models import EvaluationReview, Investigation, NewsClaimView, TrackingRequest
from limes.news.store import TrackingStore
from limes.news.targets import queries_for

router = APIRouter(prefix="/news", tags=["news"])


def tracking(settings: Annotated[Settings, Depends(get_settings)]) -> TrackingStore:
    return TrackingStore(settings.jobs_path)


@router.get("/investigations", response_model=list[Investigation])
def investigations(store: Annotated[TrackingStore, Depends(tracking)]) -> list[Investigation]:
    return store.list()


@router.put(
    "/investigations/{key}", response_model=Investigation, dependencies=[Depends(require_operator)]
)
def track(
    key: str,
    request: TrackingRequest,
    driver: Annotated[GraphDriver, Depends(get_driver)],
    store: Annotated[TrackingStore, Depends(tracking)],
) -> Investigation:
    if key != request.investigation_id:
        raise HTTPException(422, "investigation ID mismatch")
    try:
        queries_for(driver, request)  # Identity existence and work bound before saving.
        return store.save(request)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except OverflowError as exc:
        raise HTTPException(429, str(exc)) from exc


@router.post(
    "/investigations/{key}/replay",
    response_model=Investigation,
    dependencies=[Depends(require_operator)],
)
def replay(key: str, store: Annotated[TrackingStore, Depends(tracking)]) -> Investigation:
    try:
        return store.replay(key)
    except KeyError as exc:
        raise HTTPException(404, "investigation not found") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/claims", response_model=list[NewsClaimView])
def claims(
    driver: Annotated[GraphDriver, Depends(get_driver)],
    investigation_id: str | None = None,
    entity_id: str | None = None,
    include_retracted: bool = False,
    as_of: datetime | None = None,
    believed: datetime | None = None,
    modality: Literal["asserted", "reported", "denied", "proposed", "conditional", "unknown"]
    | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict[str, object]]:
    rows = driver.read(
        "MATCH (c:NewsClaim) WHERE ($investigation IS NULL OR c.investigation_id=$investigation) "
        "AND ($entity IS NULL OR c.subject_id=$entity OR c.object_id=$entity) "
        "AND ($modality IS NULL OR c.modality=$modality) "
        "AND ($believed IS NOT NULL OR $include_retracted OR c.retracted_at IS NULL) "
        "AND ($as_of IS NULL OR (c.valid_from IS NOT NULL AND c.valid_from <= $as_of "
        "AND (c.valid_to IS NULL OR c.valid_to > $as_of))) "
        "AND ($believed IS NULL OR (c.recorded_at <= $believed "
        "AND (c.retracted_at IS NULL OR c.retracted_at > $believed))) "
        "RETURN properties(c) AS claim ORDER BY c.recorded_at DESC, c.claim_id LIMIT $limit",
        {
            "investigation": investigation_id,
            "entity": entity_id,
            "modality": modality,
            "include_retracted": include_retracted,
            "as_of": as_of,
            "believed": believed,
            "limit": limit,
        },
        30,
    )
    return [
        {
            k: native_datetime(v) if hasattr(v, "to_native") else v
            for k, v in row["claim"].items()
            if k in NewsClaimView.model_fields
        }
        for row in rows
    ]


@router.get("/documents/{document_id}")
def document(
    document_id: str, driver: Annotated[GraphDriver, Depends(get_driver)]
) -> dict[str, object]:
    rows = driver.read(
        "MATCH (d:NewsDocument {document_id: $id}) RETURN properties(d) AS doc",
        {"id": document_id},
        30,
    )
    if not rows:
        raise HTTPException(404, "news document not found")
    data = dict(rows[0]["doc"])
    for key, value in data.items():
        if hasattr(value, "to_native"):
            data[key] = native_datetime(value)
    data["metadata"] = json.loads(data.get("metadata") or "{}")
    return data


@router.get("/evaluation")
def evaluation_pool(
    driver: Annotated[GraphDriver, Depends(get_driver)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict[str, object]]:
    """An evolving review pool; unreviewed examples are never gold labels."""
    return driver.read(
        "MATCH (d:NewsDocument) RETURN d.document_id AS document_id, d.label AS title, "
        "d.evaluation_status AS status, d.evaluation_review AS review "
        "ORDER BY d.recorded_at DESC LIMIT $limit",
        {"limit": limit},
        30,
    )


@router.put("/documents/{document_id}/review", dependencies=[Depends(require_operator)])
def review_document(
    document_id: str,
    review: EvaluationReview,
    driver: Annotated[GraphDriver, Depends(get_driver)],
) -> dict[str, str]:
    if not driver.read(
        "MATCH (d:NewsDocument {document_id:$id}) RETURN d.document_id AS id",
        {"id": document_id},
        30,
    ):
        raise HTTPException(404, "news document not found")
    save_news_review(driver, document_id, review.model_dump_json())
    return {"status": "reviewed"}


@router.get("/investigations/{key}/developments", response_model=DevelopmentView)
def investigation_developments(
    key: str,
    driver: Annotated[GraphDriver, Depends(get_driver)],
    store: Annotated[TrackingStore, Depends(tracking)],
    as_of: AwareDatetime | None = None,
    believed: AwareDatetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> DevelopmentView:
    item = store.get_investigation(key)
    if item is None:
        raise HTTPException(404, "investigation not found")
    return developments(driver, item, as_of, believed, limit)


@router.post(
    "/investigations/{key}/event-match-reviews",
    response_model=ReviewView,
    dependencies=[Depends(require_operator)],
)
def review_event_match(
    key: str,
    review: MatchReview,
    driver: Annotated[GraphDriver, Depends(get_driver)],
    store: Annotated[TrackingStore, Depends(tracking)],
) -> ReviewView:
    item = store.get_investigation(key)
    if item is None:
        raise HTTPException(404, "investigation not found")
    # Validate the exact evidence against investigation targets without temporal filters.
    view = developments(driver, item, references=[review.left, review.right])
    evidence = {e.evidence_id: e for e in view.evidence}
    if review.left not in evidence or review.right not in evidence:
        raise HTTPException(422, "evidence must be present in the bounded investigation view")
    left, right = evidence[review.left], evidence[review.right]
    if review.independence == "independent" and known_dependent(left, right):
        raise HTTPException(422, "known dependent reporting cannot be marked independent")
    payload = review.model_dump(mode="json")
    save_event_match_review(driver, key, payload)
    rows = driver.read(
        "MATCH (r:EventMatchReview {request_id:$id}) RETURN properties(r) AS review",
        {"id": str(review.request_id)},
        30,
    )
    saved = ReviewView.model_validate(properties(rows[0]["review"]))
    if saved.investigation_id != key or any(
        saved.model_dump(mode="json")[field] != value for field, value in payload.items()
    ):
        raise HTTPException(409, "review request ID already used; submit a new ID for a revision")
    return saved


@router.get("/assertions/{assertion_id}/evidence")
def assertion_evidence(
    assertion_id: str,
    driver: Annotated[GraphDriver, Depends(get_driver)],
    archive: Annotated[ArchiveStore, Depends(get_archive)],
) -> dict[str, object]:
    rows = driver.read(
        "MATCH ()-[r]->() WHERE r.assertion_id=$id RETURN properties(r) AS evidence LIMIT 2",
        {"id": assertion_id},
        30,
    )
    if not rows:
        raise HTTPException(404, "assertion not found")
    if len(rows) != 1:
        raise HTTPException(409, "ambiguous assertion identity")
    data = properties(rows[0]["evidence"])
    key = data.get("evidence_document_id")
    result: dict[str, object] = {"provenance": data, "archive_status": "unavailable"}
    if key:
        try:
            payload, truncated = archive.preview(str(key))
        except (FileNotFoundError, ValueError):
            return result
        result.update(
            archive_status="available",
            preview=payload.decode("utf-8", errors="replace"),
            truncated=truncated,
            preview_encoding="utf-8 with replacement; original may be binary",
        )
    return result
