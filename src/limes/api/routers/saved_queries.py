# src/limes/api/routers/saved_queries.py | v1.0.0 | introduced by WP-35
"""The self-accreting query library per Technical Specification §6 and
§7.3: `:SavedQuery` create per executed query (FR-14, AC-30), and
create/delete per operator action. This module is the sole writer of
`:SavedQuery` (§15.2) and contains two of the API's three enumerated write
paths — the AC-18 grep expects CREATE and DELETE to appear here and nowhere
else in `src/limes/api/`.

`saved_query_id` is generated here (a UUID), never supplied by the
operator. A duplicate is defined as an identical (question, cypher) pair —
the self-accreting library would otherwise fill with exact re-runs.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from limes.api.deps import get_driver, get_ontology
from limes.api.models import native_datetime
from limes.errors import LimesError
from limes.graph.driver import GraphDriver
from limes.ontology.model import Ontology

router = APIRouter(tags=["saved-queries"])

_DUPLICATE_CHECK = """
MATCH (q:SavedQuery {question: $question, cypher: $cypher})
RETURN q.saved_query_id AS saved_query_id
LIMIT 1
"""

_CREATE = """
CREATE (q:SavedQuery {
    saved_query_id: $saved_query_id,
    question: $question,
    cypher: $cypher,
    ontology_version: $ontology_version,
    result_count: $result_count,
    created_at: $created_at,
    pinned: $pinned
})
"""

_LIST = """
MATCH (q:SavedQuery)
RETURN q
ORDER BY q.created_at DESC
"""

_EXISTS = """
MATCH (q:SavedQuery {saved_query_id: $saved_query_id})
RETURN q.saved_query_id AS saved_query_id
LIMIT 1
"""

_DELETE = """
MATCH (q:SavedQuery {saved_query_id: $saved_query_id})
DELETE q
"""


class SavedQueryCreate(BaseModel):
    """An operator-created saved query. The auto-persisted per-execution
    writes (FR-14) flow through `persist` instead and are not operator
    input."""

    question: str
    cypher: str
    result_count: int = 0
    pinned: bool = False


class SavedQueryView(BaseModel):
    """One saved query as returned to the UI."""

    saved_query_id: str
    question: str
    cypher: str
    ontology_version: str
    result_count: int
    created_at: str
    pinned: bool


class DuplicateSavedQuery(LimesError):
    """A saved query with the same (question, cypher) pair already exists;
    maps to 409."""


def persist(
    driver: GraphDriver,
    *,
    question: str,
    cypher: str,
    ontology_version: str,
    result_count: int,
    pinned: bool = False,
    allow_duplicate: bool = False,
) -> str:
    """Write one `:SavedQuery` node — the per-execution write of §7.3
    (FR-14, AC-30) — and return its id. Raises `DuplicateSavedQuery` for an
    identical (question, cypher) pair for manual saves. Automatic execution
    history permits repeated pairs so every execution has its own observation."""
    if not allow_duplicate:
        _check_duplicate(driver, question, cypher)
    saved_query_id = uuid.uuid4().hex
    driver.write_batch(
        [
            (
                _CREATE,
                {
                    "saved_query_id": saved_query_id,
                    "question": question,
                    "cypher": cypher,
                    "ontology_version": ontology_version,
                    "result_count": result_count,
                    "created_at": datetime.now(UTC),
                    "pinned": pinned,
                },
            )
        ]
    )
    return saved_query_id


@router.get("/saved-queries")
def list_saved_queries(driver: Annotated[GraphDriver, Depends(get_driver)]) -> list[SavedQueryView]:
    """Every saved query, newest first."""
    views: list[SavedQueryView] = []
    for row in driver.read(_LIST, {}, 30):
        query = row["q"]
        created = native_datetime(query["created_at"])
        views.append(
            SavedQueryView(
                saved_query_id=str(query["saved_query_id"]),
                question=str(query["question"]),
                cypher=str(query["cypher"]),
                ontology_version=str(query["ontology_version"]),
                result_count=int(query.get("result_count") or 0),
                created_at=created.isoformat() if created is not None else "",
                pinned=bool(query.get("pinned") or False),
            )
        )
    return views


@router.post("/saved-queries")
def create_saved_query(
    body: SavedQueryCreate,
    driver: Annotated[GraphDriver, Depends(get_driver)],
    ontology: Annotated[Ontology, Depends(get_ontology)],
) -> dict[str, str]:
    """Create one saved query. 409 when the (question, cypher) pair already
    exists."""
    try:
        saved_query_id = persist(
            driver,
            question=body.question,
            cypher=body.cypher,
            ontology_version=ontology.version,
            result_count=body.result_count,
            pinned=body.pinned,
        )
    except DuplicateSavedQuery as exc:
        raise HTTPException(
            409, detail={"code": "DUPLICATE_SAVED_QUERY", "message": str(exc)}
        ) from exc
    return {"saved_query_id": saved_query_id}


@router.delete("/saved-queries/{saved_query_id}")
def delete_saved_query(
    saved_query_id: str,
    driver: Annotated[GraphDriver, Depends(get_driver)],
) -> dict[str, str]:
    """Delete one saved query; 404 when it does not exist."""
    if not driver.read(_EXISTS, {"saved_query_id": saved_query_id}, 30):
        raise HTTPException(
            404,
            detail={
                "code": "SAVED_QUERY_NOT_FOUND",
                "message": f"saved query {saved_query_id!r} not found",
            },
        )
    driver.write_batch([(_DELETE, {"saved_query_id": saved_query_id})])
    return {"deleted": saved_query_id}


def _check_duplicate(driver: GraphDriver, question: str, cypher: str) -> None:
    rows = driver.read(_DUPLICATE_CHECK, {"question": question, "cypher": cypher}, 30)
    if rows:
        raise DuplicateSavedQuery("a saved query with the same question and Cypher already exists")
