# src/limes/api/routers/ontology.py | v1.0.0 | introduced by WP-32
"""Ontology endpoints per Technical Specification §6: the full serialized
ontology, the versions present in the graph with counts, and the builder
schema projection — registered here because it is an ontology projection,
with its logic in `api/builder.py` (WP-32 registers the route; WP-35 owns
the projection)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from limes.api.builder import project_for_builder
from limes.api.deps import get_driver, get_ontology
from limes.graph.driver import GraphDriver
from limes.ontology.model import Ontology

router = APIRouter(tags=["ontology"])

_VERSIONS_QUERY = """
MATCH (n:Entity)
WHERE n.ontology_version IS NOT NULL
RETURN n.ontology_version AS version, count(*) AS count
ORDER BY version
"""


@router.get("/ontology")
def get_ontology_full(ontology: Annotated[Ontology, Depends(get_ontology)]) -> dict[str, object]:
    """The full serialized ontology, exactly as loaded and self-validated."""
    return ontology.model_dump(mode="json")


@router.get("/ontology/versions")
def get_ontology_versions(
    driver: Annotated[GraphDriver, Depends(get_driver)],
) -> list[dict[str, object]]:
    """Every ontology version stamped on an `:Entity` node, with counts."""
    rows = driver.read(_VERSIONS_QUERY, {}, 30)
    return [{"version": str(row["version"]), "count": int(row["count"])} for row in rows]


@router.get("/builder/schema")
def get_builder_schema(ontology: Annotated[Ontology, Depends(get_ontology)]) -> dict[str, object]:
    """The ontology projection the UI renders the query builder from
    (FR-09). Generated at runtime from the loaded ontology, never authored."""
    return project_for_builder(ontology)
