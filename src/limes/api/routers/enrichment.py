"""Authenticated acquired enrichment/context, never live provider reads."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from limes.api.deps import get_driver
from limes.enrichment.models import EnrichmentResponse
from limes.enrichment.service import read_enrichment
from limes.graph.driver import GraphDriver

router = APIRouter(tags=["enrichment"])


@router.get("/entity/{entity_id}/enrichment", response_model=EnrichmentResponse)
def enrichment(
    entity_id: str,
    driver: Annotated[GraphDriver, Depends(get_driver)],
    source: Literal["wikipedia", "yahoo_finance"] | None = None,
    section: Annotated[str | None, Query(max_length=64)] = None,
    as_of: datetime | None = None,
    believed: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> EnrichmentResponse:
    return read_enrichment(
        driver,
        entity_id,
        source=source,
        section=section,
        as_of=as_of,
        believed=believed,
        limit=limit,
    )
