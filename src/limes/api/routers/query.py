# src/limes/api/routers/query.py | v1.0.0 | introduced by WP-35
"""The three query endpoints per Technical Specification §6, §7.3, and
§15.3 Trace 3.

- `POST /query/cypher`: operator-supplied Cypher, deterministically
  validated (400 on rejection), plan-gated (422), executed read-only.
- `POST /query/nl`: a question through the four-stage NL service, with
  coverage attached, diagnosis on empty results, and the executed query
  persisted as a `:SavedQuery` (FR-14, AC-30) — one of the API's three
  enumerated writes, performed by `saved_queries.persist`.
- `POST /query/builder`: a `BuilderSpec`, rejected precisely when it would
  violate a domain or range (AC-24), translated to parameterized Cypher,
  validated and plan-gated like any other query, executed read-only.

All three return the executed (or generated) Cypher — editable in every
outcome, including failures (AC-26). Coverage attaches to every executed
result (AC-23) and diagnosis runs automatically on zero rows (AC-22).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from limes.api.builder import translate_spec
from limes.api.deps import get_driver, get_nlq_context, get_ontology, get_settings
from limes.api.models import BuilderSpec, GraphResult
from limes.api.routers.saved_queries import persist
from limes.composition import NlqContext
from limes.config import Settings
from limes.coverage.diagnose import diagnose
from limes.coverage.report import report_for_relations
from limes.errors import CypherValidationFailed
from limes.graph.driver import GraphDriver
from limes.nlq.plan import explain_gate
from limes.nlq.service import answer
from limes.nlq.validate import relation_types_in, validate
from limes.ontology.model import Ontology

router = APIRouter(tags=["query"])


class CypherQuery(BaseModel):
    """An operator-supplied query. `params` are the query's Cypher
    parameters; they travel as parameters end-to-end and never reach query
    text."""

    cypher: str
    params: dict[str, Any] = {}


class NlQuestion(BaseModel):
    """A natural-language question for the four-stage service."""

    question: str


class QueryResponse(BaseModel):
    """One executed query: the (validated) Cypher, the normalized result
    graph, the coverage report, the empty-result diagnosis when applicable,
    and any partial-verification notes."""

    cypher: str
    results: GraphResult
    coverage: dict[str, Any]
    diagnosis: dict[str, Any] | None = None
    notes: list[str] = []


@router.post("/query/cypher")
def query_cypher(
    body: CypherQuery,
    driver: Annotated[GraphDriver, Depends(get_driver)],
    ontology: Annotated[Ontology, Depends(get_ontology)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> QueryResponse:
    """Validate, plan-gate, execute, and annotate an operator-supplied
    query."""
    result = validate(body.cypher, ontology, settings)
    if not result.valid:
        raise CypherValidationFailed("Cypher validation failed: " + "; ".join(result.errors))
    explain_gate(driver, result.cypher, body.params, settings)
    rows = driver.read(result.cypher, body.params, settings.query_timeout_seconds)
    return _annotate(result.cypher, rows, body.params, ontology, driver, result.notes)


@router.post("/query/nl")
def query_nl(
    body: NlQuestion,
    nlq_context: Annotated[NlqContext, Depends(get_nlq_context)],
    ontology: Annotated[Ontology, Depends(get_ontology)],
) -> dict[str, Any]:
    """Generate, validate, plan-gate, execute — and persist the executed
    query (FR-14, AC-30)."""
    outcome = answer(body.question, nlq_context, execute=True)
    response: dict[str, Any] = {
        "question": outcome.question,
        "cypher": outcome.cypher,
        "results": outcome.results,
        "validation_errors": outcome.validation_errors,
        "plan_rejection": outcome.plan_rejection,
        "notes": outcome.notes,
    }
    if outcome.results is None:
        # Validation failed or the plan was rejected: nothing executed,
        # nothing to cover, nothing to persist.
        response["coverage"] = None
        response["diagnosis"] = None
        return response

    annotated = _annotate(
        outcome.cypher,
        [],
        {},
        ontology,
        nlq_context.driver,
        outcome.notes,
        prebuilt=outcome.results,
    )
    response["coverage"] = annotated.coverage
    response["diagnosis"] = annotated.diagnosis
    persist(
        nlq_context.driver,
        question=body.question,
        cypher=outcome.cypher,
        ontology_version=ontology.version,
        result_count=outcome.results.counts.get("rows", 0),
    )
    return response


@router.post("/query/builder")
def query_builder(
    spec: BuilderSpec,
    driver: Annotated[GraphDriver, Depends(get_driver)],
    ontology: Annotated[Ontology, Depends(get_ontology)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> QueryResponse:
    """Translate a validated builder spec to Cypher, then validate,
    plan-gate, execute, and annotate it like any other query."""
    cypher, params = translate_spec(spec, ontology, settings)
    result = validate(cypher, ontology, settings)
    if not result.valid:
        raise CypherValidationFailed(
            "generated Cypher failed validation: " + "; ".join(result.errors)
        )
    explain_gate(driver, result.cypher, params, settings)
    rows = driver.read(result.cypher, params, settings.query_timeout_seconds)
    return _annotate(result.cypher, rows, params, ontology, driver, result.notes)


def _annotate(
    cypher: str,
    rows: list[dict[str, Any]],
    params: dict[str, Any],
    ontology: Ontology,
    driver: GraphDriver,
    notes: list[str],
    *,
    prebuilt: GraphResult | None = None,
) -> QueryResponse:
    """Attach coverage to every executed result and diagnosis to empty
    ones. `prebuilt` carries the NL service's already-converted result; the
    cypher and builder paths convert the rows here. Emptiness is judged by
    the converted result's row count, so the two paths agree."""
    if prebuilt is None:
        prebuilt = GraphResult.from_rows(rows, ontology)
    coverage = report_for_relations(driver, relation_types_in(cypher))
    diagnosis: dict[str, Any] | None = None
    if prebuilt.counts.get("rows", 0) == 0:
        diag = diagnose(driver, cypher, params)
        diagnosis = diag.model_dump(mode="json")
    return QueryResponse(
        cypher=cypher,
        results=prebuilt,
        coverage=coverage.model_dump(mode="json"),
        diagnosis=diagnosis,
        notes=notes,
    )
