# desktop/tests/unit/test_main_window_support.py | v0.1.0 | shared FakeClient stub
from __future__ import annotations

from typing import Any

from limes_desktop.api.errors import ApiError
from limes_desktop.api.models import EntityDetail, GraphNeighbors, HealthInfo, SearchHit


class FakeClient:
    """Stub injected at the MainWindow boundary (respx coverage lives in Task 2)."""

    def __init__(
        self, hits: list[SearchHit] | None = None, fail: bool = False
    ) -> None:
        self.hits = (
            hits
            if hits is not None
            else [
                SearchHit(kind="entity", id="e1", label="Acme GmbH", score=0.9),
                SearchHit(kind="entity", id="e2", label="Acme AG", score=0.8),
            ]
        )
        self.fail = fail
        self.search_calls: list[str] = []
        self.health_calls = 0
        self.ontology_calls = 0
        self.entity_calls: list[str] = []
        self.ontology_payload: dict[str, Any] = {
            "relation_types": [{"name": "LOCATED_IN"}, {"name": "MEMBER_OF"}]
        }
        self.entity_payload: dict[str, Any] = {
            "entity": {
                "entity_id": "e1",
                "type": "Organization",
                "label": "ACME",
                "properties": {"country": "DE"},
                "ontology_version": "1.0.0",
                "created_at": None,
            },
            "edge_summary": {"out": {}, "in": {}},
        }

    def health(self) -> Any:
        self.health_calls += 1
        if self.fail:
            raise ApiError(500, "boom")
        return HealthInfo(status="ok", neo4j=True, ontology_version="1.0.0")

    def ontology(self) -> Any:
        self.ontology_calls += 1
        if self.fail:
            raise ApiError(500, "boom")
        return self.ontology_payload

    def entity(self, entity_id: str) -> Any:
        self.entity_calls.append(entity_id)
        if self.fail:
            raise ApiError(500, "boom")
        payload = dict(self.entity_payload)
        payload["entity"] = dict(payload["entity"], entity_id=entity_id)
        return EntityDetail.from_api(payload)

    def entity_neighbors(self, entity_id: str) -> GraphNeighbors:
        detail = EntityDetail.from_api(self.entity_payload)
        return GraphNeighbors(entity=detail.entity, neighbors=[])

    def search(
        self, query: str, kind: str | None = None, limit: int = 50
    ) -> list[SearchHit]:
        self.search_calls.append(query)
        if self.fail:
            raise ApiError(500, "boom")
        return self.hits

    def close(self) -> None:
        pass
