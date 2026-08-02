# src/limes/nlq/validate.py | v1.0.0 | introduced by WP-33
"""Deterministic Cypher validation per Technical Specification §7.2 and
§8.10 — the primary read-only defense, and the only one that inspects
intent.

Rejection is by **inspection of the parsed statement**, never substring
search: the module tokenizes Cypher (strings, comments, backticked
identifiers, parameters) and walks the clause structure, so a write hidden
in a comment or a label smuggled inside a string literal is invisible to
the token stream and cannot pass. This is also the module the coverage and
diagnosis services parse queries with, which is why the tokenizer and the
pattern walker live here rather than in a second parser.

Validation codes (§8.10): `UNKNOWN_LABEL`, `UNKNOWN_RELATION`,
`DOMAIN_VIOLATION`, `RANGE_VIOLATION`, `WRITE_CLAUSE`,
`DISALLOWED_PROCEDURE`, `LIMIT_EXCEEDS_MAX`. Where a pattern position is
untyped, the domain/range check is skipped and a note records the partial
verification — silent partial verification would be worse than none.

`validate` also injects `LIMIT` when the statement lacks one (the
`LIMES_QUERY_DEFAULT_LIMIT` ceiling below `LIMES_QUERY_MAX_LIMIT`), so
every executed query is bounded by construction.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from limes.config import Settings
from limes.ontology.model import Ontology, RelationTypeSpec

# Top-level clause starters. `WHERE` is a continuation of MATCH/WITH, not a
# new statement. The write clauses are rejected by keyword; everything else
# is read-only surface (patterns, WHERE, RETURN, ORDER BY, SKIP, LIMIT,
# UNWIND, WITH, YIELD, UNION, USING, OPTIONAL).
_READ_CLAUSES = frozenset(
    {
        "MATCH",
        "OPTIONAL",
        "WHERE",
        "WITH",
        "RETURN",
        "UNWIND",
        "YIELD",
        "UNION",
        "ORDER",
        "SKIP",
        "LIMIT",
        "USING",
        "CALL",
    }
)
_WRITE_CLAUSES = frozenset(
    {"CREATE", "MERGE", "DELETE", "DETACH", "SET", "REMOVE", "FOREACH", "DROP", "LOAD"}
)
_ALL_CLAUSES = _READ_CLAUSES | _WRITE_CLAUSES

# Read-only procedures an operator-supplied or generated query may call.
# Everything else — every `apoc.*` and every unlisted `db.*` — is refused.
_PROCEDURE_ALLOWLIST = frozenset(
    {"db.index.fulltext.queryNodes", "db.index.fulltext.queryRelationships", "db.labels"}
)

_ROLE_LABELS = frozenset({"Entity"})


@dataclass(frozen=True)
class Token:
    """One lexical unit of a Cypher statement. `pos` is the character offset
    in the original text, so clause decomposition can slice the source.
    `kind` is `word` (bare or backticked identifier), `string`, `number`,
    `param`, or `punct`. Backticked identifiers keep a distinct kind from
    bare words only in the parser's keyword checks: `ident` never starts a
    clause, so a variable named `create` cannot trip the write clause."""

    kind: str  # word | ident | string | number | param | punct
    value: str
    pos: int


class ValidationResult(BaseModel):
    """The outcome of one validation pass: valid/invalid, the error codes
    with their messages, the (possibly LIMIT-injected) Cypher, and the
    partial-verification notes."""

    valid: bool
    errors: list[str]
    cypher: str
    notes: list[str]


def tokenize(cypher: str) -> list[Token]:
    """Tokenize a Cypher statement. Comments and whitespace are discarded;
    strings and backticked identifiers are single tokens, so a write clause
    hidden inside one cannot be mistaken for real syntax."""
    tokens: list[Token] = []
    index = 0
    length = len(cypher)
    while index < length:
        char = cypher[index]
        if char.isspace():
            index += 1
            continue
        if char == "/" and index + 1 < length and cypher[index + 1] == "/":
            index = _skip_line_comment(cypher, index)
            continue
        if char == "/" and index + 1 < length and cypher[index + 1] == "*":
            index = _skip_block_comment(cypher, index)
            continue
        if char in ("'", '"'):
            value, index = _scan_string(cypher, index)
            tokens.append(Token("string", value, index - len(value) - 2))
            continue
        if char == "`":
            value, index = _scan_backtick(cypher, index)
            tokens.append(Token("ident", value, index - len(value) - 2))
            continue
        if char == "$":
            value, index = _scan_param(cypher, index)
            tokens.append(Token("param", value, index - len(value) - 1))
            continue
        if char.isdigit():
            value, index = _scan_number(cypher, index)
            tokens.append(Token("number", value, index - len(value)))
            continue
        if char.isalpha() or char == "_":
            value, index = _scan_word(cypher, index)
            tokens.append(Token("word", value, index - len(value)))
            continue
        tokens.append(Token("punct", char, index))
        index += 1
    return tokens


def validate(cypher: str, ontology: Ontology, settings: Settings) -> ValidationResult:
    """Validate one statement against the ontology and the write surface.
    Returns a `ValidationResult`; never raises for a *rejected* statement —
    rejection is a result, not an exception (the HTTP mapping differs by
    caller: operator-supplied Cypher raises `CypherValidationFailed` in the
    router, the NL service retries once)."""
    errors: list[str] = []
    notes: list[str] = []
    cypher = cypher.strip()
    if not cypher:
        return ValidationResult(
            valid=False, errors=["EMPTY_STATEMENT: no Cypher provided"], cypher=cypher, notes=[]
        )

    tokens = tokenize(cypher)
    for sequence in _split_sequences(tokens):
        _validate_clause_sequence(sequence, ontology, errors, notes)

    if _limit_exceeds_max(tokens, settings.query_max_limit):
        errors.append(f"LIMIT_EXCEEDS_MAX: LIMIT above the maximum of {settings.query_max_limit}")
    if not _has_limit(tokens):
        cypher = _inject_limit(cypher, settings.query_default_limit)

    return ValidationResult(valid=not errors, errors=errors, cypher=cypher, notes=notes)


def relation_types_in(cypher: str) -> list[str]:
    """The relationship types a statement uses, in first-appearance order —
    the coverage service's input. A type is only recognized inside a
    relationship pattern's square brackets, so a map key like `{x: y}` never
    counts."""
    seen: list[str] = []
    tokens = tokenize(cypher)
    square_depth = 0
    for index, token in enumerate(tokens):
        if token.value == "[":
            square_depth += 1
            continue
        if token.value == "]":
            square_depth = max(0, square_depth - 1)
            continue
        if square_depth == 1 and token.value == ":":
            nxt = tokens[index + 1] if index + 1 < len(tokens) else None
            if nxt is not None and nxt.kind == "word" and nxt.value not in seen:
                seen.append(nxt.value)
    return seen


def _validate_clause_sequence(
    tokens: list[Token],
    ontology: Ontology,
    errors: list[str],
    notes: list[str],
) -> None:
    """One top-level clause sequence (or one `CALL {}` subquery body). The
    walker reacts to every clause keyword; `CALL {}` subquery bodies are
    validated recursively and then skipped, so no token is judged twice."""
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.kind != "word":
            index += 1
            continue
        keyword = token.value.upper()
        if keyword in _WRITE_CLAUSES:
            errors.append(f"WRITE_CLAUSE: {token.value} at offset {token.pos}")
            index += 1
            continue
        if keyword == "CALL":
            if index + 1 < len(tokens) and tokens[index + 1].value == "{":
                body, end = _subquery_body(tokens, index)
                _validate_clause_sequence(body, ontology, errors, notes)
                index = end + 1
                continue
            procedure = _procedure_name(tokens, index + 1)
            if procedure is None:
                errors.append(f"DISALLOWED_PROCEDURE: malformed CALL at offset {token.pos}")
            elif procedure not in _PROCEDURE_ALLOWLIST:
                errors.append(
                    f"DISALLOWED_PROCEDURE: {procedure!r} is not on the read-only allowlist"
                )
            index += 1
            continue
        if keyword == "MATCH":
            index = _validate_patterns(tokens, index, ontology, errors, notes)
            continue
        index += 1


def _validate_patterns(
    tokens: list[Token],
    start: int,
    ontology: Ontology,
    errors: list[str],
    notes: list[str],
) -> int:
    """Walk the patterns of one MATCH clause: every node pattern and every
    relationship pattern in order, checking labels, types, and the
    domain/range contract per typed relationship. Returns the index of the
    first token after the clause (a following clause keyword at depth 0)."""
    nodes: list[NodePattern] = []
    rels: list[RelPattern] = []
    index = start + 1
    paren_depth = 0
    while index < len(tokens):
        token = tokens[index]
        if token.value == "(":
            paren_depth += 1
        elif token.value == ")":
            paren_depth = max(0, paren_depth - 1)
        if token.kind == "word" and token.value.upper() in _ALL_CLAUSES and paren_depth == 0:
            break
        if _is_node_pattern_start(tokens, index):
            node, index = _scan_node_pattern(tokens, index)
            paren_depth = max(0, paren_depth - 1)
            nodes.append(node)
            continue
        if _is_rel_pattern_start(tokens, index):
            rel, index = _scan_rel_pattern(tokens, index)
            rels.append(rel)
            continue
        index += 1

    for node in nodes:
        for label in node.labels:
            if (
                label not in ontology.entity_types
                and label not in ontology.supertypes
                and label not in _ROLE_LABELS
            ):
                errors.append(f"UNKNOWN_LABEL: {label!r} at offset {node.pos}")

    for rel in rels:
        if rel.type_name is None:
            continue
        if rel.type_name not in ontology.relation_types:
            errors.append(f"UNKNOWN_RELATION: {rel.type_name!r} at offset {rel.pos}")
            continue
        left = _node_before(nodes, rel)
        right = _node_after(nodes, rel)
        if left is None or right is None:
            continue
        relation_spec = ontology.relation_types[rel.type_name]
        # The arrow decides which side is the subject. For an undirected
        # relationship both orientations are semantically possible, so a
        # check passes when either orientation is admitted — and a note
        # records when only one is.
        if rel.direction == "in":
            subject, object_ = right, left
        else:
            subject, object_ = left, right
        subject_types = _admissible_types(subject, ontology)
        object_types = _admissible_types(object_, ontology)
        if subject_types is None:
            notes.append(f"pattern position untyped; domain check skipped for {rel.type_name}")
        if object_types is None:
            notes.append(f"pattern position untyped; range check skipped for {rel.type_name}")
        if rel.direction == "undirected" and subject_types and object_types:
            _check_undirected(
                ontology,
                relation_spec,
                subject_types,
                object_types,
                subject,
                object_,
                rel,
                errors,
                notes,
            )
            continue
        if subject_types is not None and not _admitted(
            ontology, relation_spec.domain, subject_types
        ):
            errors.append(
                f"DOMAIN_VIOLATION: {rel.type_name!r} does not admit subject type "
                f"{_describe(subject)} at offset {rel.pos}"
            )
        if object_types is not None and not _admitted(ontology, relation_spec.range, object_types):
            errors.append(
                f"RANGE_VIOLATION: {rel.type_name!r} does not admit object type "
                f"{_describe(object_)} at offset {rel.pos}"
            )
    return index


def _check_undirected(
    ontology: Ontology,
    relation_spec: RelationTypeSpec,
    subject_types: list[str],
    object_types: list[str],
    subject: NodePattern,
    object_: NodePattern,
    rel: RelPattern,
    errors: list[str],
    notes: list[str],
) -> None:
    """An undirected pattern is valid when either orientation is admitted;
    a note records when only one is (partial verification, §8.10)."""
    forward = _admitted(ontology, relation_spec.domain, subject_types) and _admitted(
        ontology, relation_spec.range, object_types
    )
    backward = _admitted(ontology, relation_spec.domain, object_types) and _admitted(
        ontology, relation_spec.range, subject_types
    )
    if forward or backward:
        if not (forward and backward):
            notes.append(f"undirected pattern admits only one orientation for {rel.type_name}")
        return
    errors.append(
        f"DOMAIN_VIOLATION: {rel.type_name!r} does not admit {_describe(subject)} or "
        f"{_describe(object_)} as subject at offset {rel.pos}"
    )


def _node_before(nodes: list[NodePattern], rel: RelPattern) -> NodePattern | None:
    """The node pattern immediately preceding a relationship pattern."""
    before = [node for node in nodes if node.pos < rel.pos]
    return before[-1] if before else None


def _node_after(nodes: list[NodePattern], rel: RelPattern) -> NodePattern | None:
    """The node pattern immediately following a relationship pattern."""
    after = [node for node in nodes if node.pos > rel.pos]
    return after[0] if after else None


def _admissible_types(node: NodePattern, ontology: Ontology) -> list[str] | None:
    """The concrete types a node pattern admits: its labels expanded to
    concrete types. None for an untyped position or a bare `Entity` label —
    the check is then skipped with a note. A supertype label (e.g. `Agent`)
    expands to all concrete types under it; the check passes when any of
    them is admitted."""
    if not node.labels:
        return None
    types: list[str] = []
    for label in node.labels:
        if label in ontology.entity_types:
            types.append(label)
        elif label == "Entity":
            return None
        elif label in ontology.supertypes:
            types.extend(_concrete_under(ontology, label))
    if not types:
        return None
    return list(dict.fromkeys(types))


def _concrete_under(ontology: Ontology, supertype: str) -> list[str]:
    """Every concrete entity type whose supertype chain includes
    `supertype`."""
    result: list[str] = []
    for name, spec in ontology.entity_types.items():
        current = spec.supertype
        while current is not None:
            if current == supertype:
                result.append(name)
                break
            if current not in ontology.entity_types:
                break
            current = ontology.entity_types[current].supertype
    return result


def _admitted(ontology: Ontology, declared: list[str], types: list[str]) -> bool:
    """True when any of the node pattern's concrete types (or its
    supertype) is in the relation's declared domain/range."""
    for type_name in types:
        if type_name in declared:
            return True
        current = ontology.entity_types[type_name].supertype
        while current is not None:
            if current in declared:
                return True
            if current not in ontology.entity_types:
                break
            current = ontology.entity_types[current].supertype
    return False


def _describe(node: NodePattern) -> str:
    return " or ".join(node.labels) if node.labels else "untyped"


def _split_sequences(tokens: list[Token]) -> list[list[Token]]:
    """Split a statement into sequences at top-level `UNION` keywords (a
    `UNION` inside a `CALL {}` body is handled by the subquery recursion).
    `WHERE` and the other continuation keywords stay inside their sequence —
    the clause walker reacts to every keyword regardless."""
    sequences: list[list[Token]] = [[]]
    for token in tokens:
        if token.kind == "word" and token.value.upper() == "UNION":
            sequences.append([])
        else:
            sequences[-1].append(token)
    return [sequence for sequence in sequences if sequence]


def _subquery_body(tokens: list[Token], start: int) -> tuple[list[Token], int]:
    """The tokens between `CALL {` and its matching `}` (with the index of
    the closing brace), for recursive validation."""
    depth = 0
    for index in range(start + 1, len(tokens)):
        if tokens[index].value == "{":
            depth += 1
        elif tokens[index].value == "}":
            depth -= 1
            if depth == 0:
                return tokens[start + 2 : index], index
    return tokens[start + 2 :], len(tokens)


def _procedure_name(tokens: list[Token], start: int) -> str | None:
    """The dotted procedure name after `CALL`, or None for a malformed
    call."""
    parts: list[str] = []
    index = start
    while index < len(tokens) and tokens[index].kind == "word":
        parts.append(tokens[index].value)
        index += 1
        if index < len(tokens) and tokens[index].value == ".":
            index += 1
            continue
        break
    return ".".join(parts) if parts else None


def _limit_exceeds_max(tokens: list[Token], max_limit: int) -> bool:
    for index, token in enumerate(tokens):
        if token.kind == "word" and token.value.upper() == "LIMIT":
            if index + 1 < len(tokens) and tokens[index + 1].kind == "number":
                if int(tokens[index + 1].value) > max_limit:
                    return True
    return False


def _has_limit(tokens: list[Token]) -> bool:
    return any(token.kind == "word" and token.value.upper() == "LIMIT" for token in tokens)


def _inject_limit(cypher: str, default_limit: int) -> str:
    """Append `LIMIT <default>` before a trailing semicolon, if any. The
    value is config-derived, never operator input, so the literal is safe."""
    stripped = cypher.rstrip()
    if stripped.endswith(";"):
        return stripped[:-1].rstrip() + f" LIMIT {default_limit};"
    return stripped + f" LIMIT {default_limit}"


def _skip_line_comment(cypher: str, index: int) -> int:
    newline = cypher.find("\n", index)
    return len(cypher) if newline == -1 else newline + 1


def _skip_block_comment(cypher: str, index: int) -> int:
    close = cypher.find("*/", index + 2)
    return len(cypher) if close == -1 else close + 2


def _scan_string(cypher: str, index: int) -> tuple[str, int]:
    quote = cypher[index]
    end = index + 1
    while end < len(cypher):
        if cypher[end] == quote and cypher[end - 1] != "\\":
            break
        end += 1
    return cypher[index + 1 : end], end + 1


def _scan_backtick(cypher: str, index: int) -> tuple[str, int]:
    end = cypher.find("`", index + 1)
    if end == -1:
        end = len(cypher)
    return cypher[index + 1 : end], end + 1


def _scan_param(cypher: str, index: int) -> tuple[str, int]:
    end = index + 1
    while end < len(cypher) and (cypher[end].isalnum() or cypher[end] == "_"):
        end += 1
    return cypher[index + 1 : end], end


def _scan_number(cypher: str, index: int) -> tuple[str, int]:
    """Scan an integer or float literal. A `.` is consumed only when it is
    followed by a digit — `1..5` is a range bound, not a float, and must
    split into `1`, `.`, `.`, `5`."""
    end = index
    while end < len(cypher) and cypher[end].isdigit():
        end += 1
    if end + 1 < len(cypher) and cypher[end] == "." and cypher[end + 1].isdigit():
        end += 1
        while end < len(cypher) and cypher[end].isdigit():
            end += 1
    if end < len(cypher) and cypher[end] in "eE":
        end += 1
        while end < len(cypher) and (cypher[end].isdigit() or cypher[end] in "+-"):
            end += 1
    return cypher[index:end], end


def _scan_word(cypher: str, index: int) -> tuple[str, int]:
    end = index
    while end < len(cypher) and (cypher[end].isalnum() or cypher[end] == "_"):
        end += 1
    return cypher[index:end], end


@dataclass(frozen=True)
class NodePattern:
    """One node pattern: position, variable, labels."""

    pos: int
    variable: str | None
    labels: list[str]


@dataclass(frozen=True)
class RelPattern:
    """One relationship pattern: position, variable, type, and direction —
    `out` for `-[:T]->`, `in` for `<-[:T]-`, `undirected` for `-[:T]-`.
    The direction decides which node pattern is the subject: for `in`, the
    subject is the node *after* the relationship."""

    pos: int
    variable: str | None
    type_name: str | None
    direction: str  # out | in | undirected


def _is_node_pattern_start(tokens: list[Token], index: int) -> bool:
    """True when `(` at `index` opens a node pattern rather than a function
    call or a parenthesized expression: the token before must be a clause
    keyword, a pattern connector (`-`, `>`, `<`), `,`, `]`, `)`, or the
    start of the statement — never a plain word (a function name)."""
    if tokens[index].value != "(":
        return False
    if index == 0:
        return True
    previous = tokens[index - 1]
    if previous.kind == "word":
        return previous.value.upper() in _ALL_CLAUSES
    return previous.value in (",", "]", ")", "}", "-", ">", "<")


def _scan_node_pattern(tokens: list[Token], start: int) -> tuple[NodePattern, int]:
    """Parse `(var:Label1:Label2 {props})` from `(` to the matching `)`.
    Returns the pattern and the index after the closing paren."""
    depth = 0
    variable: str | None = None
    labels: list[str] = []
    index = start
    while index < len(tokens):
        token = tokens[index]
        if token.value == "(":
            depth += 1
            index += 1
            continue
        if token.value == ")":
            depth -= 1
            if depth == 0:
                return NodePattern(pos=start, variable=variable, labels=labels), index + 1
            index += 1
            continue
        if token.kind == "word" and variable is None and not labels and depth == 1:
            variable = token.value
            index += 1
            continue
        if token.value == ":" and depth == 1:
            nxt = tokens[index + 1] if index + 1 < len(tokens) else None
            if nxt is not None and nxt.kind == "word":
                labels.append(nxt.value)
                index += 2
                continue
        index += 1
    return NodePattern(pos=start, variable=variable, labels=labels), len(tokens)


def _is_rel_pattern_start(tokens: list[Token], index: int) -> bool:
    """True when `[` at `index` opens a relationship pattern: preceded by
    `-` (possibly after `<`)."""
    if tokens[index].value != "[":
        return False
    if index == 0:
        return False
    previous = tokens[index - 1].value
    return previous == "-" or previous == "<"


def _scan_rel_pattern(tokens: list[Token], start: int) -> tuple[RelPattern, int]:
    """Parse `[var:Type]` from `[` to the matching `]` (including
    variable-length bounds, which the plan gate inspects separately). The
    direction is read from the tokens before the bracket: `<` `-` is
    incoming, plain `-` is outgoing, and `-` with no arrow at either end
    (decided from the token after the closing `]`) is undirected."""
    direction = "in" if start > 0 and tokens[start - 1].value == "<" else "out"
    depth = 0
    variable: str | None = None
    type_name: str | None = None
    index = start
    while index < len(tokens):
        token = tokens[index]
        if token.value == "[":
            depth += 1
            index += 1
            continue
        if token.value == "]":
            depth -= 1
            if depth == 0:
                # `-[:T]-`: the closing bracket is followed by `-` without
                # `>` or `<` — an undirected pattern.
                if direction == "out":
                    nxt = tokens[index + 1] if index + 1 < len(tokens) else None
                    if (
                        nxt is not None
                        and nxt.value == "-"
                        and (index + 2 >= len(tokens) or tokens[index + 2].value not in (">", "<"))
                    ):
                        direction = "undirected"
                return (
                    RelPattern(
                        pos=start,
                        variable=variable,
                        type_name=type_name,
                        direction=direction,
                    ),
                    index + 1,
                )
            index += 1
            continue
        if token.kind == "word" and variable is None and not type_name and depth == 1:
            variable = token.value
            index += 1
            continue
        if token.value == ":" and depth == 1:
            nxt = tokens[index + 1] if index + 1 < len(tokens) else None
            if nxt is not None and nxt.kind == "word":
                type_name = nxt.value
                index += 2
                continue
        index += 1
    return RelPattern(pos=start, variable=variable, type_name=type_name, direction=direction), len(
        tokens
    )
