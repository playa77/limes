# desktop/src/limes_desktop/api/client.py | v0.1.0 | typed HTTP client (FR-DC-002)
"""The one HTTP seam between the desktop client and the LIMES API.

Every call goes through `_request`: connection-level failures map to
`ApiUnreachable`, non-2xx responses to `ApiError(status, detail)` with the
body preserved verbatim, and 2xx responses are parsed and converted into the
mirrored models of `limes_desktop.api.models`. No view ever imports httpx
(architecture §2.2).
"""

from __future__ import annotations

from typing import Any

import httpx

from limes_desktop.api.errors import ApiError, ApiUnreachable
from limes_desktop.api.models import (
    CostLedger,
    CoverageReport,
    EntityDetail,
    GraphNeighbors,
    HealthInfo,
    IngestRun,
    QueryOutcome,
    SavedQuery,
    SearchHit,
    SourceInfo,
)

_TIMEOUT = httpx.Timeout(30.0)


class ApiClient:
    """Typed client for the LIMES API surface (§6). One `httpx.Client` per
    instance; reuse one instance per connection profile."""

    def __init__(self, base_url: str, timeout_s: float = 30.0) -> None:
        # follow_redirects=True: a 3xx must be followed to the final response,
        # never surface as an unparseable non-JSON body
        self._client = httpx.Client(
            base_url=base_url, timeout=httpx.Timeout(timeout_s), follow_redirects=True
        )

    def close(self) -> None:
        self._client.close()

    # -- liveness -----------------------------------------------------------

    def health(self) -> HealthInfo:
        return HealthInfo.from_api(self._request("GET", "/health"))

    # -- ontology -----------------------------------------------------------

    def ontology(self) -> dict[str, Any]:
        data: dict[str, Any] = self._request("GET", "/ontology")
        return data

    def ontology_versions(self) -> list[str]:
        rows: list[dict[str, Any]] = self._request("GET", "/ontology/versions")
        return [str(row["version"]) for row in rows]

    def builder_schema(self) -> dict[str, Any]:
        data: dict[str, Any] = self._request("GET", "/builder/schema")
        return data

    # -- queries ------------------------------------------------------------

    def query_cypher(self, cypher: str, params: dict[str, Any] | None = None) -> QueryOutcome:
        return QueryOutcome.from_api(
            self._request("POST", "/query/cypher", json={"cypher": cypher, "params": params or {}})
        )

    def query_nl(self, question: str) -> QueryOutcome:
        return QueryOutcome.from_api(
            self._request("POST", "/query/nl", json={"question": question})
        )

    def query_builder(self, spec: dict[str, Any]) -> QueryOutcome:
        return QueryOutcome.from_api(self._request("POST", "/query/builder", json=spec))

    # -- entities -----------------------------------------------------------

    def entity(self, entity_id: str) -> EntityDetail:
        return EntityDetail.from_api(self._request("GET", f"/entity/{entity_id}"))

    def entity_neighbors(
        self, entity_id: str, filters: dict[str, Any] | None = None
    ) -> GraphNeighbors:
        return GraphNeighbors.from_api(
            self._request("GET", f"/entity/{entity_id}/neighbors", params=filters or {})
        )

    # -- search & coverage ----------------------------------------------------

    def search(
        self, query: str, kind: str | None = None, limit: int = 50
    ) -> list[SearchHit]:
        params: dict[str, Any] = {"q": query, "limit": limit}
        if kind is not None:
            params["kind"] = kind
        return [SearchHit.from_api(h) for h in self._request("GET", "/search", params=params)]

    def coverage(self, request: dict[str, Any]) -> CoverageReport:
        return CoverageReport.from_api(self._request("POST", "/coverage", json=request))

    # -- saved queries --------------------------------------------------------

    def saved_queries(self) -> list[SavedQuery]:
        return [SavedQuery.from_api(q) for q in self._request("GET", "/saved-queries")]

    def save_query(self, name: str, surface: str, payload: dict[str, Any]) -> str:
        body = self._request(
            "POST",
            "/saved-queries",
            json={"question": name, "cypher": surface, "result_count": 0, "pinned": False}
            | dict(payload),
        )
        return str(body["saved_query_id"])

    def delete_saved_query(self, saved_query_id: str) -> None:
        self._request("DELETE", f"/saved-queries/{saved_query_id}")

    # -- operational surfaces ---------------------------------------------------

    def sources(self) -> list[SourceInfo]:
        return [SourceInfo.from_api(s) for s in self._request("GET", "/sources")]

    def cost_ledger(self, period: str | None = None) -> CostLedger:
        params: dict[str, Any] = {} if period is None else {"period": period}
        return CostLedger.from_api(self._request("GET", "/cost/ledger", params=params))

    def ingest_status(self) -> list[IngestRun]:
        return [IngestRun.from_api(r) for r in self._request("GET", "/ingest/status")]

    # -- transport ----------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        try:
            response = self._client.request(method, path, json=json, params=params)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise ApiUnreachable(str(exc)) from exc
        if response.status_code >= 400:
            try:
                detail: Any = response.json()
            except ValueError:
                detail = response.text
            if isinstance(detail, dict):
                detail = detail.get("detail", response.text)
            raise ApiError(response.status_code, str(detail))
        return response.json()
