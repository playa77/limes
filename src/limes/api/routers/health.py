# src/limes/api/routers/health.py | v1.0.0 | introduced by WP-32
"""Liveness endpoint per Technical Specification §6: reports Neo4j
reachability and the ontology version, returning 503 while the database is
unreachable — the app starts regardless, and the database's return needs no
restart."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from limes.api.deps import get_driver, get_ontology, get_settings
from limes.config import Settings
from limes.graph.driver import GraphDriver
from limes.ontology.model import Ontology

router = APIRouter(tags=["health"])

_REACHABILITY_PROBE = "RETURN 1 AS one"


@router.get("/health")
def health(
    driver: Annotated[GraphDriver, Depends(get_driver)],
    ontology: Annotated[Ontology, Depends(get_ontology)],
) -> dict[str, object]:
    """Liveness: 200 with the ontology version when Neo4j answers a trivial
    read; 503 with the failure reason while it does not."""
    try:
        driver.read(_REACHABILITY_PROBE, {}, 30)
    except Exception as exc:
        raise HTTPException(
            503,
            detail={"code": "NEO4J_UNREACHABLE", "message": f"Neo4j unreachable: {exc}"},
        ) from exc
    return {"status": "ok", "neo4j": True, "ontology_version": ontology.version}


@router.get("/version")
def version(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, str]:
    return {"revision": settings.revision}
