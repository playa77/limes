# src/limes/nlq/service.py | v1.0.0 | introduced by WP-33
"""The NL-to-Cypher orchestrator per Technical Specification §8.10 and
§15.3 Trace 3: generate → validate → plan-gate → execute read-only.

The four stages are strict: generation is paid inference (metered by the
client), validation is deterministic and runs before anything touches the
database, the plan gate runs `EXPLAIN` (never executes), and execution
happens in a read-mode session. On validation failure there is exactly one
regeneration with the failure reasons supplied verbatim (Doc 2 §8.10); a
second failure is final — the outcome carries the errors and the Cypher
(AC-26). On plan rejection the outcome carries the plan summary. The
Cypher is returned in every outcome, so it is always editable.
"""

from __future__ import annotations

import structlog

from limes.api.models import GraphResult, NlqOutcome
from limes.composition import NlqContext
from limes.errors import QueryPlanRejected
from limes.nlq.generate import generate
from limes.nlq.plan import explain_gate
from limes.nlq.validate import validate

logger = structlog.get_logger(__name__)


def answer(question: str, ctx: NlqContext, execute: bool = True) -> NlqOutcome:
    """One natural-language query end-to-end. `execute=False` stops after
    validation (plan and execution skipped) — the shape the reference
    questions' expressibility check and evaluation use."""
    model_id = ctx.settings.nl2cypher_model
    prompt_version = ctx.settings.nl2cypher_prompt_version

    cypher = generate(question, ctx.ontology, ctx.client, model_id, prompt_version)
    result = validate(cypher, ctx.ontology, ctx.settings)
    if not result.valid:
        regenerated = generate(
            question,
            ctx.ontology,
            ctx.client,
            model_id,
            prompt_version,
            feedback="\n".join(result.errors),
        )
        result = validate(regenerated, ctx.ontology, ctx.settings)
        logger.info(
            "nl2cypher regeneration issued",
            regenerated=True,
            question_length=len(question),
        )
    if not result.valid:
        return NlqOutcome(
            question=question,
            cypher=result.cypher,
            validation_errors=result.errors,
            notes=result.notes,
        )

    if not execute:
        return NlqOutcome(question=question, cypher=result.cypher, notes=result.notes)

    try:
        summary = explain_gate(ctx.driver, result.cypher, {}, ctx.settings)
    except QueryPlanRejected as exc:
        return NlqOutcome(
            question=question,
            cypher=result.cypher,
            plan_rejection=getattr(exc, "plan_summary", None),
            notes=result.notes + [str(exc)],
        )

    rows = ctx.driver.read(result.cypher, {}, ctx.settings.query_timeout_seconds)
    results = GraphResult.from_rows(rows, ctx.ontology)
    outcome = NlqOutcome(
        question=question,
        cypher=result.cypher,
        results=results,
        notes=result.notes,
    )
    logger.info(
        "nl2cypher query executed",
        rows=len(rows),
        nodes=len(results.nodes),
        edges=len(results.edges),
        plan_operators=len(summary.operators),
    )
    return outcome
