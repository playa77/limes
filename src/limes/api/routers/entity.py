# src/limes/api/routers/entity.py | v1.0.0 | introduced by WP-32
"""Entity endpoints per Technical Specification §6: one entity with its
properties, loader stamps, and edge summary; and one-hop neighborhood
expansion with relation and temporal filters. The temporal filters are
composed from `graph/temporal.py` fragments — the only sanctioned source of
those Cypher fragments (Doc 2 §5.7)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from limes.api.deps import get_driver, get_ontology
from limes.api.models import EdgeRef, EntityRef, edge_ref, entity_ref
from limes.graph.driver import GraphDriver
from limes.graph.temporal import (
    as_believed as as_believed_fragment,
)
from limes.graph.temporal import (
    as_believed_params,
    as_of_params,
)
from limes.graph.temporal import (
    as_of as as_of_fragment,
)
from limes.ontology.model import Ontology

router = APIRouter(tags=["entity"])

_ENTITY_FETCH = "MATCH (n:Entity {entity_id: $id}) RETURN n"

_EDGE_SUMMARY = """
MATCH (n:Entity {entity_id: $id})-[r]->(m)
RETURN 'out' AS direction, type(r) AS rel, count(*) AS count
UNION ALL
MATCH (n:Entity {entity_id: $id})<-[r]-(m)
RETURN 'in' AS direction, type(r) AS rel, count(*) AS count
"""


class NeighborRow(BaseModel):
    """One hop of the neighborhood expansion: the edge with its full
    provenance and the neighbor node."""

    edge: EdgeRef
    neighbor: EntityRef


class NeighborResponse(BaseModel):
    """The entity and its one-hop neighborhood."""

    entity: EntityRef
    neighbors: list[NeighborRow]


@router.get("/entity/{entity_id}")
def get_entity(
    entity_id: str,
    driver: Annotated[GraphDriver, Depends(get_driver)],
    ontology: Annotated[Ontology, Depends(get_ontology)],
) -> dict[str, object]:
    """The entity with its properties, loader stamps, and a per-relation
    edge summary in each direction. 404 when the id is unknown."""
    rows = driver.read(_ENTITY_FETCH, {"id": entity_id}, 30)
    if not rows:
        raise HTTPException(
            404, detail={"code": "ENTITY_NOT_FOUND", "message": f"entity {entity_id!r} not found"}
        )
    entity = entity_ref(rows[0]["n"], ontology)
    summary: dict[str, dict[str, int]] = {"out": {}, "in": {}}
    for row in driver.read(_EDGE_SUMMARY, {"id": entity_id}, 30):
        summary[str(row["direction"])][str(row["rel"])] = int(row["count"])
    return {"entity": entity, "edge_summary": summary}


@router.get("/entity/{entity_id}/neighbors")
def get_entity_neighbors(
    entity_id: str,
    driver: Annotated[GraphDriver, Depends(get_driver)],
    ontology: Annotated[Ontology, Depends(get_ontology)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    relation: Annotated[str | None, Query(description="restrict to one relation type")] = None,
    as_of: Annotated[datetime | None, Query(description="validity instant (ISO)")] = None,
    believed: Annotated[datetime | None, Query(description="belief instant (ISO)")] = None,
) -> NeighborResponse:
    """One-hop expansion of an entity, optionally restricted to one relation
    and to an `as_of` validity instant and/or a `believed` belief instant.
    404 when the id is unknown."""
    fetch = driver.read(_ENTITY_FETCH, {"id": entity_id}, 30)
    if not fetch:
        raise HTTPException(
            404, detail={"code": "ENTITY_NOT_FOUND", "message": f"entity {entity_id!r} not found"}
        )
    conditions: list[str] = []
    params: dict[str, object] = {"id": entity_id, "relation": relation, "limit": limit}
    if as_of is not None:
        conditions.append(as_of_fragment("r", as_of))
        params.update(as_of_params("r", as_of))
    if believed is not None:
        conditions.append(as_believed_fragment("r", believed))
        params.update(as_believed_params("r", believed))
    where = "WHERE ($relation IS NULL OR type(r) = $relation)"
    if conditions:
        where += "\n  AND " + "\n  AND ".join(conditions)
    cypher = (
        "MATCH (n:Entity {entity_id: $id})-[r]-(m)\n" + where + "\nRETURN type(r) AS rel, r, m,\n"
        "       startNode(r).entity_id AS from_id,\n"
        "       endNode(r).entity_id AS to_id\n"
        "ORDER BY r.recorded_at DESC\n"
        "LIMIT $limit"
    )
    rows = driver.read(cypher, params, 30)
    neighbors = [
        NeighborRow(edge=edge_ref(row["r"]), neighbor=entity_ref(row["m"], ontology))
        for row in rows
    ]
    return NeighborResponse(entity=entity_ref(fetch[0]["n"], ontology), neighbors=neighbors)
