# src/limes/ui/api_client.py | v1.0.0 | introduced by WP-36
"""The UI's only HTTP surface (Doc 2 §8.13, Doc 1 §4.13).

One function per API endpoint (Doc 2 §6); no other UI module performs HTTP.
The UI holds no credentials (Doc 1 §7.4): the base URL is the single
`LIMES_API_BASE_URL` environment variable read here, and nothing else — the
UI never loads `Settings` and never parses `.env`, which carries the
OpenRouter key and the database password. The base URL defaults to a bare
local run's `127.0.0.1:8000`; the compose `ui` service supplies its own
value through the environment (D-09).

Every function raises `ApiError` with the §6 envelope's `code` and
`message` on a non-2xx response, so callbacks can display the API's own
diagnosis instead of a guessed one.
"""

from __future__ import annotations

import os
from typing import Any, cast

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
_TIMEOUT_S = 30.0


class ApiError(RuntimeError):
    """A non-2xx API response, carrying the §6 envelope's code and message."""

    def __init__(self, code: str, message: str, status: int) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.status = status


def api_base_url() -> str:
    """The API base URL: `LIMES_API_BASE_URL` or the local default."""
    return os.environ.get("LIMES_API_BASE_URL", DEFAULT_BASE_URL)


def _request(
    method: str, path: str, *, json: Any = None, params: dict[str, Any] | None = None
) -> Any:
    with httpx.Client(base_url=api_base_url(), timeout=_TIMEOUT_S) as client:
        response = client.request(method, path, json=json, params=params)
    if response.status_code >= 400:
        error = (
            response.json().get("error", {})
            if response.headers.get("content-type", "").startswith("application/json")
            else {}
        )
        raise ApiError(
            str(error.get("code") or "HTTP_ERROR"),
            str(error.get("message") or response.text),
            response.status_code,
        )
    return response.json()


def get_health() -> dict[str, Any]:
    """Liveness: database reachability and the ontology version."""
    return cast(dict[str, Any], _request("GET", "/health"))


def get_ontology() -> dict[str, Any]:
    """The full serialized ontology."""
    return cast(dict[str, Any], _request("GET", "/ontology"))


def get_builder_schema() -> dict[str, Any]:
    """The ontology projection the builder renders from."""
    return cast(dict[str, Any], _request("GET", "/builder/schema"))


def post_query_cypher(cypher: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute operator-supplied Cypher; returns the QueryResponse body."""
    return cast(
        dict[str, Any],
        _request("POST", "/query/cypher", json={"cypher": cypher, "params": params or {}}),
    )


def post_query_nl(question: str) -> dict[str, Any]:
    """Generate, validate, plan, execute from a question."""
    return cast(dict[str, Any], _request("POST", "/query/nl", json={"question": question}))


def post_query_builder(spec: dict[str, Any]) -> dict[str, Any]:
    """Execute a structured builder specification; returns the QueryResponse body."""
    return cast(dict[str, Any], _request("POST", "/query/builder", json=spec))


def get_entity(entity_id: str) -> dict[str, Any]:
    """One entity with properties, stamps, and its edge summary."""
    return cast(dict[str, Any], _request("GET", f"/entity/{entity_id}"))


def get_entity_neighbors(entity_id: str, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """One-hop expansion, with the caller-supplied relation/temporal filters
    as query parameters (`as_of`, `believed`, `relation`, `limit`)."""
    return cast(
        dict[str, Any], _request("GET", f"/entity/{entity_id}/neighbors", params=filters or {})
    )


def search(query: str, kind: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Full-text over entity labels (and document text when such nodes
    exist)."""
    params: dict[str, Any] = {"q": query, "limit": limit}
    if kind is not None:
        params["kind"] = kind
    return cast(list[dict[str, Any]], _request("GET", "/search", params=params))


def post_coverage(
    relation_types: list[str] | None = None, query: str | None = None
) -> dict[str, Any]:
    """A coverage report for a relation set or a query."""
    return cast(
        dict[str, Any],
        _request("POST", "/coverage", json={"relation_types": relation_types, "query": query}),
    )


def get_saved_queries() -> list[dict[str, Any]]:
    """Every saved query, newest first."""
    return cast(list[dict[str, Any]], _request("GET", "/saved-queries"))


def post_saved_query(
    question: str, cypher: str, result_count: int = 0, pinned: bool = False
) -> dict[str, Any]:
    """Create one saved query; returns its id."""
    return cast(
        dict[str, Any],
        _request(
            "POST",
            "/saved-queries",
            json={
                "question": question,
                "cypher": cypher,
                "result_count": result_count,
                "pinned": pinned,
            },
        ),
    )


def delete_saved_query(saved_query_id: str) -> dict[str, Any]:
    """Delete one saved query."""
    return cast(dict[str, Any], _request("DELETE", f"/saved-queries/{saved_query_id}"))


def get_sources() -> list[dict[str, Any]]:
    """Every registered source with trust rank and last refresh."""
    return cast(list[dict[str, Any]], _request("GET", "/sources"))


def get_cost_ledger(period: str | None = None) -> dict[str, Any]:
    """Period spend, remaining budget, and entries."""
    return cast(
        dict[str, Any],
        _request("GET", "/cost/ledger", params={"period": period} if period else None),
    )


def get_ingest_status() -> list[dict[str, Any]]:
    """The latest ingestion run per source with counts and errors."""
    return cast(list[dict[str, Any]], _request("GET", "/ingest/status"))
