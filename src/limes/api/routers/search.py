# src/limes/api/routers/search.py | v1.0.0 | introduced by WP-32
"""Full-text search per Technical Specification §6, over the §5.3 `entity_names`
and `document_text` fulltext indexes. The query text is operator input and
travels as a parameter; the fulltext index parses it."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from limes.api.deps import get_driver
from limes.graph.driver import GraphDriver

router = APIRouter(tags=["search"])

_ENTITY_SEARCH = """
CALL db.index.fulltext.queryNodes('entity_names', $q) YIELD node, score
RETURN 'entity' AS kind, node, score
LIMIT $limit
"""

_DOCUMENT_SEARCH = """
CALL db.index.fulltext.queryNodes('document_text', $q) YIELD node, score
RETURN 'document' AS kind, node, score
LIMIT $limit
"""

_SEARCH_BY_KIND = {"entity": _ENTITY_SEARCH, "document": _DOCUMENT_SEARCH}


class SearchHit(BaseModel):
    """One full-text hit: the index it came from, the entity id or document
    content hash, a display label, and the score."""

    kind: Literal["entity", "document"]
    id: str
    label: str
    score: float


@router.get("/search")
def search(
    q: Annotated[str, Query(min_length=1, description="full-text query")],
    driver: Annotated[GraphDriver, Depends(get_driver)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    kind: Annotated[
        Literal["entity", "document"] | None,
        Query(description="restrict to one index; both by default"),
    ] = None,
) -> list[SearchHit]:
    """Full-text search over entity labels and document titles/bodies.
    Without `kind`, both indexes are searched and the results merged in
    index order."""
    params: dict[str, object] = {"q": q, "limit": limit}
    queries = [_ENTITY_SEARCH, _DOCUMENT_SEARCH] if kind is None else [_SEARCH_BY_KIND[kind]]
    hits: list[SearchHit] = []
    for cypher in queries:
        for row in driver.read(cypher, params, 30):
            node = row["node"]
            hits.append(
                SearchHit(
                    kind=str(row["kind"]),  # type: ignore[arg-type]
                    id=str(node.get("entity_id") or node.get("content_hash") or node.element_id),
                    label=str(node.get("label") or node.get("title") or node.element_id),
                    score=float(row["score"]),
                )
            )
    return hits
