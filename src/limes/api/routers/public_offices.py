"""Authenticated roster/coverage reads with bounded, institution-neutral filters."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from limes.api.deps import get_driver
from limes.graph.driver import GraphDriver
from limes.public_offices.catalogue import BY_CODE
from limes.public_offices.models import OfficesResponse
from limes.public_offices.service import read_offices

router = APIRouter(tags=["public offices"])


@router.get("/public-offices", response_model=OfficesResponse)
def public_offices(
    driver: Annotated[GraphDriver, Depends(get_driver)],
    scope: Annotated[str | None, Query(max_length=16)] = None,
    term: Annotated[str | None, Query(max_length=200)] = None,
    as_of: datetime | None = None,
    believed: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    include_members: bool = True,
) -> OfficesResponse:
    if scope is not None and scope not in BY_CODE:
        raise HTTPException(422, detail="unknown public office scope")
    if any(t is not None and t.tzinfo is None for t in (as_of, believed)):
        raise HTTPException(422, detail="time filters must include a timezone")
    return read_offices(
        driver,
        scope=scope,
        term=term,
        as_of=as_of,
        believed=believed,
        limit=limit,
        include_members=include_members,
    )
