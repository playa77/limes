# src/limes/api/main.py | v1.0.0 | introduced by WP-32
"""The FastAPI application per Technical Specification §8.12 and §15.3
Trace 3, and the API's second sanctioned infrastructure construction site
(§15.2's FastAPI row: the startup handler constructs settings, the
ontology, and the driver — the AC-40 grep in test_composition_root.py
carries this exemption).

Startup: load settings and ontology, construct the read-mode driver,
`provision()` — idempotent, and it applies the §4.3 downgrade guard, so a
stale artifact fails startup (AC-01) — and verify Neo4j reachability. A
connectivity failure does not abort startup: §6's `/health` is specified to
report 503 when Neo4j is unreachable, which requires a running app. A
failure of `provision` that is not a connectivity failure (the downgrade
guard) stays fatal.

Every response carries `X-LIMES-Ontology-Version` (Doc 2 §6), and every
error response uses the §6 envelope
`{"error": {"code": ..., "message": ..., "details": {}}}` with the §11 HTTP
mapping: `CypherValidationFailed` 400, `QueryPlanRejected` 422,
unauthorized 401, not found 404, Neo4j timeout 504, unreachable 503,
unhandled 500.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from secrets import compare_digest
from typing import Any

import structlog
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from limes.api.builder import BuilderSpecRejected
from limes.api.routers import (
    cost,
    coverage,
    entity,
    health,
    ingest_status,
    ontology,
    query,
    saved_queries,
    search,
    sources,
)
from limes.config import Settings, load_settings
from limes.errors import (
    ConfigurationError,
    CypherValidationFailed,
    OntologyError,
    QueryPlanRejected,
)
from limes.graph.driver import GraphDriver
from limes.graph.schema import provision
from limes.ontology.registry import load_ontology

logger = structlog.get_logger(__name__)

_REACHABILITY_PROBE = "RETURN 1 AS one"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application. `settings` is injectable for tests; the
    production entry point passes None and the startup handler loads from
    the environment exactly once (AC-01)."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        loaded = settings or load_settings()
        if not loaded.api_token.get_secret_value():
            raise ConfigurationError("LIMES_API_TOKEN must be set to serve the API")
        ontology_model = load_ontology(loaded.ontology_path)
        driver = GraphDriver(
            loaded.neo4j_uri,
            loaded.neo4j_user,
            loaded.neo4j_password,
            loaded.neo4j_database,
        )
        try:
            provision(driver, ontology_model, loaded.embedding_dimensions)
            _verify_reachability(driver)
        except (OntologyError, TypeError, ValueError):
            driver.close()
            raise
        except Exception as exc:
            # Connectivity failure: the app stays up and /health reports
            # 503 until the database returns. The failure is logged with
            # its type — an unreachable database is an operational state,
            # not a configuration error.
            logger.warning(
                "neo4j unreachable at startup; /health will report 503",
                error_type=type(exc).__name__,
                error=str(exc),
            )
        app.state.settings = loaded
        app.state.ontology = ontology_model
        app.state.driver = driver
        logger.info(
            "limes api started",
            ontology_version=ontology_model.version,
            neo4j_uri=loaded.neo4j_uri,
        )
        yield
        driver.close()

    app = FastAPI(
        title="LIMES Query API",
        lifespan=lifespan,
        dependencies=[Depends(HTTPBearer())],
        # The §6 envelope replaces FastAPI's default error shapes; the
        # default OpenAPI docs remain useful for an operator.
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    @app.middleware("http")
    async def authenticate_and_version(request: Request, call_next: Any) -> Any:
        loaded = getattr(request.app.state, "settings", None)
        expected = loaded.api_token.get_secret_value() if loaded is not None else ""
        supplied = request.headers.get("Authorization", "")
        scheme, _, credential = supplied.partition(" ")
        if (
            not expected
            or scheme.lower() != "bearer"
            or not compare_digest(credential.encode(), expected.encode())
        ):
            response = JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "valid bearer token required",
                        "details": {},
                    }
                },
                headers={"WWW-Authenticate": "Bearer"},
            )
        else:
            response = await call_next(request)
        state = request.app.state
        if hasattr(state, "ontology"):
            response.headers["X-LIMES-Ontology-Version"] = state.ontology.version
        return response

    _register_exception_handlers(app)

    for router in (
        health.router,
        ontology.router,
        entity.router,
        search.router,
        sources.router,
        cost.router,
        ingest_status.router,
        query.router,
        coverage.router,
        saved_queries.router,
    ):
        app.include_router(router)
    return app


def _register_exception_handlers(app: FastAPI) -> None:
    """The §11 HTTP mapping, all wrapped in the §6 error envelope."""

    def envelope(
        status: int, code: str, message: str, details: dict[str, Any] | None = None
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status,
            content={"error": {"code": code, "message": message, "details": details or {}}},
        )

    @app.exception_handler(CypherValidationFailed)
    def _cypher_validation_failed(_request: Request, exc: CypherValidationFailed) -> JSONResponse:
        return envelope(400, "CYPHER_VALIDATION_FAILED", str(exc))

    @app.exception_handler(QueryPlanRejected)
    def _query_plan_rejected(_request: Request, exc: QueryPlanRejected) -> JSONResponse:
        code = getattr(exc, "code", "QUERY_PLAN_REJECTED")
        return envelope(422, "QUERY_PLAN_REJECTED", str(exc), {"code": code})

    @app.exception_handler(BuilderSpecRejected)
    def _builder_rejected(_request: Request, exc: BuilderSpecRejected) -> JSONResponse:
        return envelope(400, "BUILDER_INVALID_SPEC", str(exc))

    @app.exception_handler(HTTPException)
    def _http_exception(_request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail and "message" in detail:
            return envelope(exc.status_code, str(detail["code"]), str(detail["message"]))
        return envelope(exc.status_code, "HTTP_ERROR", str(detail))

    @app.exception_handler(RequestValidationError)
    def _request_validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return envelope(
            422, "VALIDATION_ERROR", "request validation failed", {"errors": exc.errors()}
        )

    @app.exception_handler(ServiceUnavailable)
    def _neo4j_unreachable(_request: Request, exc: ServiceUnavailable) -> JSONResponse:
        logger.warning("neo4j unreachable", error=str(exc))
        return envelope(503, "NEO4J_UNREACHABLE", f"Neo4j unreachable: {exc}")

    @app.exception_handler(Neo4jError)
    def _neo4j_error(_request: Request, exc: Neo4jError) -> JSONResponse:
        code = getattr(exc, "code", "") or ""
        if "Timeout" in code or "TimedOut" in code:
            return envelope(504, "NEO4J_TIMEOUT", f"Neo4j query timed out: {exc}", {"code": code})
        logger.error("neo4j query failed", neo4j_code=code, error=str(exc))
        return envelope(500, "NEO4J_ERROR", f"Neo4j query failed: {exc}", {"code": code})

    @app.exception_handler(Exception)
    def _unhandled(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled api error", error_type=type(exc).__name__, error=str(exc))
        return envelope(500, "INTERNAL_ERROR", f"unhandled error: {exc}")


def _verify_reachability(driver: GraphDriver) -> None:
    """One trivial read at startup; raises on connectivity failure."""
    driver.read(_REACHABILITY_PROBE, {}, 30)
