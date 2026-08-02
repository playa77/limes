# src/limes/coverage/diagnose.py | v1.0.0 | introduced by WP-34
"""Empty-result diagnosis per Technical Specification §8.11 and Doc 1 §6.3:
when a query returns zero rows, decompose it into its individual `MATCH`
clauses, execute each independently, and name the first that returns
nothing — the clause that emptied the query (AC-22).

The decomposition reuses the `nlq/validate.py` tokenizer so the clause
boundaries are the parser's, not a string split's. Each clause runs as
`<clause> RETURN count(*) AS n` with the query's original parameters; an
unbound variable inside a later clause simply matches afresh, which is
exactly the isolation the diagnosis wants. The diagnosis also carries
graph-wide counts for the relations the failing clause involves and a
plain-language note, e.g. "No entities of type Corporation found matching
the given filter".
"""

from __future__ import annotations

from typing import Any

from limes.api.models import Diagnosis
from limes.coverage.report import report_for_relations
from limes.graph.driver import GraphDriver
from limes.nlq.validate import Token, relation_types_in, tokenize

_TIMEOUT_S = 30


def diagnose(driver: GraphDriver, cypher: str, params: dict[str, Any]) -> Diagnosis:
    """Decompose `cypher` into its MATCH clauses and report the first that
    returns nothing, with graph-wide relation counts and a plain-language
    note. A query without MATCH clauses (e.g. a bare `RETURN`) cannot be
    decomposed; the diagnosis then names the whole query."""
    clauses = _match_clauses(cypher)
    if not clauses:
        return Diagnosis(
            failing_clause="",
            clause_index=-1,
            note="query returned no rows and contains no MATCH clause to decompose",
        )

    for index, clause in enumerate(clauses):
        rows = driver.read(f"{clause} RETURN count(*) AS n", params, _TIMEOUT_S)
        if rows and int(rows[0]["n"]) == 0:
            relation_counts = report_for_relations(
                driver, relation_types_in(clause)
            ).relation_counts
            return Diagnosis(
                failing_clause=clause,
                clause_index=index,
                relation_counts=relation_counts,
                note=_note_for(clause),
            )

    return Diagnosis(
        failing_clause="",
        clause_index=-1,
        note="every decomposed clause matches individually, but the combined query returns no rows",
    )


def _match_clauses(cypher: str) -> list[str]:
    """The statement's `MATCH` clauses as source slices. A clause runs from
    its `MATCH` keyword to the next top-level clause keyword; `OPTIONAL
    MATCH` starts at its `OPTIONAL` keyword, which precedes `MATCH`."""
    tokens = tokenize(cypher)
    clauses: list[tuple[int, int]] = []
    boundary_indexes: list[int] = []
    for index, token in enumerate(tokens):
        if token.kind == "word" and token.value.upper() in _CLAUSE_KEYWORDS:
            boundary_indexes.append(index)
    boundaries = boundary_indexes + [len(tokens)]
    for position, index in enumerate(boundary_indexes):
        if tokens[index].value.upper() != "MATCH":
            continue
        end = boundaries[position + 1]
        clauses.append((tokens[index].pos, _end_pos(tokens, end)))
    return [cypher[start:end].strip() for start, end in clauses]


_CLAUSE_KEYWORDS = frozenset(
    {
        "MATCH",
        "WHERE",
        "WITH",
        "RETURN",
        "UNWIND",
        "CALL",
        "ORDER",
        "SKIP",
        "LIMIT",
        "YIELD",
        "CREATE",
        "MERGE",
        "DELETE",
        "SET",
        "REMOVE",
    }
)


def _end_pos(tokens: list[Token], index: int) -> int:
    """The character offset where a clause ends: the position of the next
    clause keyword, or the statement's end."""
    if index >= len(tokens):
        return _statement_end(tokens)
    return tokens[index].pos


def _statement_end(tokens: list[Token]) -> int:
    """The offset just past the last token — the source slice must not
    swallow a trailing `;`."""
    if not tokens:
        return 0
    last = tokens[-1]
    return last.pos + len(last.value)


def _note_for(clause: str) -> str:
    """A plain-language note for a failing clause, derived from its
    patterns: entity types for node patterns, relation names for
    relationships."""
    types = _entity_types_in(clause)
    relations = relation_types_in(clause)
    parts: list[str] = []
    if types:
        parts.append(f"No entities of type {' or '.join(types)} found matching the given filter")
    if relations:
        parts.append(f"No {' or '.join(relations)} relationships exist between the given entities")
    if not parts:
        return "no data matches the clause's pattern"
    return "; ".join(parts)


def _entity_types_in(clause: str) -> list[str]:
    """The node-pattern labels of a clause, in first-appearance order, via
    the tokenizer — a label inside a string literal never counts."""
    seen: list[str] = []
    tokens = tokenize(clause)
    paren_depth = 0
    for index, token in enumerate(tokens):
        if token.value == "(":
            paren_depth += 1
        elif token.value == ")":
            paren_depth = max(0, paren_depth - 1)
        if paren_depth == 1 and token.value == ":":
            nxt = tokens[index + 1] if index + 1 < len(tokens) else None
            if nxt is not None and nxt.kind == "word" and nxt.value not in seen:
                seen.append(nxt.value)
    return seen
