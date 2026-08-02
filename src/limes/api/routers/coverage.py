# src/limes/api/routers/coverage.py | v1.0.0 | introduced by WP-35
"""The coverage endpoint per Technical Specification §6: a coverage report
for a relation set or for a query (its relation types extracted by the
parser). The same report attaches automatically to every executed query —
this endpoint is the standalone access the UI's coverage panel uses."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from limes.api.deps import get_driver
from limes.coverage.report import report_for_relations
from limes.graph.driver import GraphDriver
from limes.nlq.validate import relation_types_in

router = APIRouter(tags=["coverage"])


class CoverageRequest(BaseModel):
    """Either a relation set or a query — exactly one must be supplied."""

    relation_types: list[str] | None = None
    query: str | None = None
    params: dict[str, Any] = {}


@router.post("/coverage")
def coverage(
    body: CoverageRequest,
    driver: Annotated[GraphDriver, Depends(get_driver)],
) -> dict[str, Any]:
    """The coverage report for the given relations, or for the relations a
    query uses. 400 when neither is supplied."""
    if body.relation_types is not None:
        relation_types = body.relation_types
    elif body.query:
        relation_types = relation_types_in(body.query)
    else:
        raise HTTPException(
            400,
            detail={
                "code": "COVERAGE_REQUEST_INVALID",
                "message": "supply either relation_types or a query",
            },
        )
    return report_for_relations(driver, relation_types).model_dump(mode="json")
