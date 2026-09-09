# desktop/tests/unit/test_main_window_support.py | v0.1.0 | shared FakeClient stub
from __future__ import annotations

from typing import Any

from limes_desktop.api.errors import ApiError
from limes_desktop.api.models import HealthInfo, SearchHit


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

    def health(self) -> Any:
        self.health_calls += 1
        if self.fail:
            raise ApiError(500, "boom")
        return HealthInfo(status="ok", neo4j=True, ontology_version="1.0.0")

    def search(
        self, query: str, kind: str | None = None, limit: int = 50
    ) -> list[SearchHit]:
        self.search_calls.append(query)
        if self.fail:
            raise ApiError(500, "boom")
        return self.hits

    def close(self) -> None:
        pass
