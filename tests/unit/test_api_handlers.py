# tests/unit/test_api_handlers.py | v1.0.0 | introduced by WP-40
"""Exception-handler coverage per Doc 2 §6 and §11's HTTP mapping.

The handlers are registered once in `create_app`; each is exercised here
through a request that actually raises the mapped exception. The driver
dependency is the seam: `dependency_overrides[get_driver]` swaps in a
stand-in whose `read` raises the exception under test, driving the request
through the real handler. The generic `Exception` handler lives in
Starlette's `ServerErrorMiddleware`, which re-raises after producing the
response — the client must run with `raise_server_exceptions=False` for
that case. The startup-fatal path (a non-connectivity provisioning
failure) is a separate test — the app must not start at all then.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from limes.api.deps import get_driver
from limes.api.main import create_app
from limes.config import Settings
from limes.errors import OntologyError
from tests.fixtures.graph_data import ONTOLOGY_PATH


def _settings(tmp_path: Path) -> Settings:
    """Settings pointing at an unreachable database: the app starts and
    /health reports 503, which is exactly the state these tests need."""
    return Settings(
        api_token="test-api-token",
        neo4j_uri="bolt://127.0.0.1:1",
        neo4j_user="u",
        neo4j_password="p",
        ontology_path=ONTOLOGY_PATH,
        feeds_config_path=ONTOLOGY_PATH.parent / "feeds.yaml",
        gold_set_path=tmp_path / "gold_set.jsonl",
        baseline_path=tmp_path / "baseline.json",
        archive_path=tmp_path / "archive",
    )


class _RaiseDriver:
    """A driver whose every read raises the configured exception — the
    request-level stand-in for a database failure."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def read(self, cypher: str, params: dict, timeout_s: int) -> list[dict]:
        raise self._exc

    def close(self) -> None:
        pass


@pytest.fixture(autouse=True)
def offline_startup(monkeypatch: pytest.MonkeyPatch):
    # Unit handler tests must not wait on a live driver's connection retries.
    monkeypatch.setattr(
        "limes.api.main.GraphDriver",
        lambda *args: _RaiseDriver(ServiceUnavailable("database unreachable")),
    )
    monkeypatch.setattr("limes.api.main.provision", lambda *args: None)


class _Neo4jErrorWithCode(Neo4jError):
    """Neo4jError with a controllable `code` — the driver's constructor
    derives the code from the server response, so a test builds the
    exception directly."""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self._neo4j_code = code


@pytest.mark.parametrize(
    ("exc", "status", "code"),
    [
        (ServiceUnavailable("database unreachable"), 503, "NEO4J_UNREACHABLE"),
        (
            _Neo4jErrorWithCode(
                "query timed out", "Neo4j.TransientError.Transaction.TransactionTimedOut"
            ),
            504,
            "NEO4J_TIMEOUT",
        ),
        (
            _Neo4jErrorWithCode("constraint violation", "Neo4j.ConstraintError"),
            500,
            "NEO4J_ERROR",
        ),
    ],
)
def test_request_database_failures_map_to_the_defined_envelope(
    tmp_path: Path, exc: Exception, status: int, code: str
):
    with TestClient(
        create_app(_settings(tmp_path)), headers={"Authorization": "Bearer test-api-token"}
    ) as client:
        client.app.dependency_overrides[get_driver] = lambda: _RaiseDriver(exc)
        response = client.get("/entity/some-entity")
        assert response.status_code == status
        body = response.json()
        assert body["error"]["code"] == code
        assert body["error"]["message"]


def test_unhandled_exception_maps_to_500_internal_error(tmp_path: Path):
    # The catch-all Exception handler is the ServerErrorMiddleware's 500
    # handler, which re-raises after producing the response; the client
    # must not re-raise it back into the test.
    with TestClient(
        create_app(_settings(tmp_path)),
        raise_server_exceptions=False,
        headers={"Authorization": "Bearer test-api-token"},
    ) as client:
        client.app.dependency_overrides[get_driver] = lambda: _RaiseDriver(RuntimeError("boom"))
        response = client.get("/entity/some-entity")
        assert response.status_code == 500
        body = response.json()
        assert body["error"]["code"] == "INTERNAL_ERROR"
        assert "boom" in body["error"]["message"]


def test_plain_detail_http_exception_maps_to_http_error(tmp_path: Path):
    # The envelope's plain-detail branch: an HTTPException whose detail is
    # not the §6 dict shape (the dict branch is the integration suite's
    # 404 surface) still lands in the envelope.
    def _raise_plain():
        from fastapi import HTTPException

        raise HTTPException(400, "plain message")

    with TestClient(
        create_app(_settings(tmp_path)), headers={"Authorization": "Bearer test-api-token"}
    ) as client:
        client.app.dependency_overrides[get_driver] = _raise_plain
        response = client.get("/entity/some-entity")
        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "HTTP_ERROR"
        assert body["error"]["message"] == "plain message"


def test_provisioning_failure_that_is_not_connectivity_aborts_startup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # The §4.3 downgrade guard and artifact errors are fatal: a stale
    # ontology must not serve a graph it no longer describes (AC-01). The
    # connectivity branch (app stays up) is covered by the /health 503
    # integration test; this is the fatal branch.
    def explode(driver: Any, ontology: Any, dimensions: int) -> None:
        raise OntologyError("artifact is older than the graph")

    # `main` imports the name at module top; the patch must replace the
    # attribute there, not the schema module's.
    monkeypatch.setattr("limes.api.main.provision", explode)
    with pytest.raises(OntologyError, match="older than the graph"):
        with TestClient(
            create_app(_settings(tmp_path)), headers={"Authorization": "Bearer test-api-token"}
        ):
            pass


def test_builder_spec_whose_translation_fails_validation_maps_to_400(
    tmp_path: Path,
):
    # A config whose default limit exceeds its own maximum produces
    # generated Cypher that the validator rejects — the builder's
    # translation is validated like any other query, and the failure is a
    # 400 naming the validation errors.
    settings = _settings(tmp_path).model_copy(
        update={"query_default_limit": 6000, "query_max_limit": 5000}
    )
    with TestClient(
        create_app(settings), headers={"Authorization": "Bearer test-api-token"}
    ) as client:
        response = client.post(
            "/query/builder",
            json={"start_type": "Corporation", "hops": []},
        )
        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "CYPHER_VALIDATION_FAILED"
        assert "LIMIT_EXCEEDS_MAX" in body["error"]["message"]
