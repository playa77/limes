# src/limes/nlq/plan.py | v1.0.0 | introduced by WP-33
"""The plan gate per Technical Specification §8.10: run `EXPLAIN` (never
executes the query) and reject plans that cannot be allowed to run.

Rejection codes: `CARTESIAN_PRODUCT`, `UNBOUNDED_EXPANSION`,
`EXPANSION_TOO_DEEP`, `OPERATOR_ROWS_EXCEEDED`, `TOTAL_ROWS_EXCEEDED`.
Rejections carry the code and the plan summary, and leave the Cypher
editable (AC-26) — `QueryPlanRejected` is raised with both attached so the
NL service and the API can render the rejection without re-parsing.

Variable-length bounds cannot be read from an EXPLAIN plan — the operator
name carries no depth — so the gate inspects the query text itself (via
the `nlq/validate.py` tokenizer) for `[*]` / `[*1..]` unbounded forms and
for the upper bound of bounded expansions. The EXPLAIN plan contributes
the cartesian-product flag and the row estimates.
"""

from __future__ import annotations

from typing import Any, NoReturn

from limes.config import Settings
from limes.errors import QueryPlanRejected
from limes.graph.driver import GraphDriver
from limes.nlq.validate import Token, tokenize
from limes.types import PlanSummary

_UNBOUNDED = "UNBOUNDED_EXPANSION"
_TOO_DEEP = "EXPANSION_TOO_DEEP"
_CARTESIAN = "CARTESIAN_PRODUCT"
_OPERATOR_ROWS = "OPERATOR_ROWS_EXCEEDED"
_TOTAL_ROWS = "TOTAL_ROWS_EXCEEDED"


def explain_gate(
    driver: GraphDriver, cypher: str, params: dict[str, Any], settings: Settings
) -> PlanSummary:
    """Run the plan gate: `EXPLAIN` the query, reject plans that breach the
    configured ceilings, and return the summary on acceptance. On rejection
    raises `QueryPlanRejected` with the code and the plan summary attached
    (`exc.code`, `exc.plan_summary`) — the §11 hierarchy stays untouched,
    the attributes are the documented attachment point."""
    summary = driver.explain(cypher, params)

    upper_bound = _max_upper_bound(cypher)
    if _has_unbounded_expansion(cypher):
        _reject(_UNBOUNDED, "variable-length expansion without an upper bound", summary)
    if upper_bound is not None and upper_bound > settings.query_max_varlength_hops:
        _reject(
            _TOO_DEEP,
            f"variable-length expansion reaches {upper_bound} hops, above the maximum of "
            f"{settings.query_max_varlength_hops}",
            summary,
        )
    if summary.has_cartesian_product:
        _reject(_CARTESIAN, "query plan contains a cartesian product", summary)
    if summary.max_estimated_rows > settings.query_max_estimated_rows_operator:
        _reject(
            _OPERATOR_ROWS,
            f"operator estimates {summary.max_estimated_rows} rows, above the maximum of "
            f"{settings.query_max_estimated_rows_operator}",
            summary,
        )
    if summary.total_estimated_rows > settings.query_max_estimated_rows_total:
        _reject(
            _TOTAL_ROWS,
            f"plan estimates {summary.total_estimated_rows} rows in total, above the maximum "
            f"of {settings.query_max_estimated_rows_total}",
            summary,
        )
    return summary


def _has_unbounded_expansion(cypher: str) -> bool:
    """True when the statement contains a variable-length expansion without
    an upper bound: `[*]`, `[*N..]`, or `[*..]` — any form whose upper bound
    is absent."""
    tokens = tokenize(cypher)
    for index, token in enumerate(tokens):
        if token.value != "*":
            continue
        nxt = tokens[index + 1] if index + 1 < len(tokens) else None
        if nxt is None:
            continue
        if nxt.value == "]":
            return True
        if nxt.value == "." and _is_double_dot(tokens, index + 1):
            after = tokens[index + 3] if index + 3 < len(tokens) else None
            if after is None or after.kind != "number":
                return True
            continue
        if nxt.kind == "number" and _is_double_dot(tokens, index + 2):
            after = tokens[index + 4] if index + 4 < len(tokens) else None
            if after is None or after.kind != "number":
                return True
    return False


def _is_double_dot(tokens: list[Token], index: int) -> bool:
    return index + 1 < len(tokens) and tokens[index].value == "." and tokens[index + 1].value == "."


def _max_upper_bound(cypher: str) -> int | None:
    """The largest upper bound of every variable-length expansion: `[*1..5]`
    → 5 and the exact form `[*5]` → 5. None when the statement has none."""
    tokens = tokenize(cypher)
    maximum: int | None = None
    for index, token in enumerate(tokens):
        if token.value != "*":
            continue
        nxt = tokens[index + 1] if index + 1 < len(tokens) else None
        if nxt is None or nxt.kind != "number":
            continue
        lower = int(nxt.value)
        if _is_double_dot(tokens, index + 2):
            upper = tokens[index + 4] if index + 4 < len(tokens) else None
            if upper is not None and upper.kind == "number":
                bound = int(upper.value)
            else:
                continue
        else:
            bound = lower
        maximum = bound if maximum is None else max(maximum, bound)
    return maximum


def _reject(code: str, message: str, summary: PlanSummary) -> NoReturn:
    """Raise `QueryPlanRejected` with the code and the plan summary attached
    — the §11 error class carries the summary by attribute rather than by a
    new subclass, which would grow the specified hierarchy."""
    error = QueryPlanRejected(f"{code}: {message}")
    error.code = code  # type: ignore[attr-defined]
    error.plan_summary = summary  # type: ignore[attr-defined]
    raise error
