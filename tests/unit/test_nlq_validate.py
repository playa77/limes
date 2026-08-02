# tests/unit/test_nlq_validate.py | v1.0.0 | introduced by WP-33
"""Validator unit tests per Doc 2 §8.10: every validation code (AC-20) is
produced by a crafted query and blocks execution; parse-level detection is
proven by the obfuscation corpus (comments, strings, case) that substring
search would miss; LIMIT injection and partial-verification notes behave as
specified."""

from pathlib import Path

from limes.config import Settings
from limes.nlq.validate import relation_types_in, tokenize, validate
from limes.ontology.registry import load_ontology

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY = load_ontology(REPO_ROOT / "ontology" / "ontology.yaml")

SETTINGS = Settings(
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="u",
    neo4j_password="p",
    ontology_path=REPO_ROOT / "ontology" / "ontology.yaml",
    feeds_config_path=REPO_ROOT / "ontology" / "feeds.yaml",
    gold_set_path=REPO_ROOT / "gold_set" / "gold_set.jsonl",
    baseline_path=REPO_ROOT / "gold_set" / "baseline.json",
    archive_path=REPO_ROOT / "data" / "archive",
    query_default_limit=500,
    query_max_limit=5000,
)


def codes(result) -> list[str]:
    return [error.split(":")[0] for error in result.errors]


def test_ac20_every_validation_code_is_produced_and_blocks():
    cases = [
        ("WRITE_CLAUSE", "MATCH (n:Corporation) CREATE (m:Corporation)"),
        ("WRITE_CLAUSE", "MERGE (n:Corporation {entity_id: 'x'})"),
        ("WRITE_CLAUSE", "MATCH (n) DELETE n"),
        ("WRITE_CLAUSE", "MATCH (n) DETACH DELETE n"),
        ("WRITE_CLAUSE", "MATCH (n) SET n.label = 'x'"),
        ("WRITE_CLAUSE", "MATCH (n) REMOVE n.label"),
        ("WRITE_CLAUSE", "LOAD CSV FROM 'file:///x' AS row RETURN row"),
        ("WRITE_CLAUSE", "MATCH (n) CALL { CREATE (m:Corporation) } RETURN n"),
        ("WRITE_CLAUSE", "MATCH (n) FOREACH (x IN [1] | CREATE (m)) RETURN n"),
        ("UNKNOWN_LABEL", "MATCH (n:NotAType) RETURN n"),
        ("UNKNOWN_RELATION", "MATCH (a)-[:NOT_A_RELATION]->(b) RETURN a"),
        (
            "DOMAIN_VIOLATION",
            "MATCH (a:Person)-[:SUBSIDIARY_OF]->(b:Corporation) RETURN a",
        ),
        ("RANGE_VIOLATION", "MATCH (a:Person)-[:DIRECTOR_OF]->(b:Person) RETURN a"),
        (
            "DISALLOWED_PROCEDURE",
            "CALL apoc.cypher.run('RETURN 1', {}) YIELD value RETURN value",
        ),
        ("DISALLOWED_PROCEDURE", "CALL db.index.fulltext.drop('entity_names') RETURN 1"),
        (
            "LIMIT_EXCEEDS_MAX",
            f"MATCH (n:Corporation) RETURN n LIMIT {SETTINGS.query_max_limit + 1}",
        ),
    ]
    for code, query in cases:
        result = validate(query, ONTOLOGY, SETTINGS)
        assert not result.valid, f"{code} must block execution: {query!r}"
        assert code in codes(result), f"{query!r} should produce {code}, got {result.errors}"


def test_read_only_queries_validate():
    valid = [
        "MATCH (a:Corporation)-[:SUBSIDIARY_OF]->(b:Corporation) RETURN a, b",
        "MATCH (a:Corporation) WHERE a.lei = 'x' RETURN a.label",
        "MATCH (a:Corporation) RETURN a ORDER BY a.label SKIP 1 LIMIT 10",
        "MATCH (a:Corporation) WITH a MATCH (a)-[:DIRECTOR_OF]->(b:Corporation) RETURN b",
        "MATCH (n) UNWIND n.aliases AS alias RETURN alias",
        "MATCH (a:Agent)-[:OWNS_STAKE_IN]->(b:Corporation) RETURN b",
        "CALL db.index.fulltext.queryNodes('entity_names', 'alpha') YIELD node, score "
        "RETURN node, score",
        "MATCH (a:Corporation)-[:SUBSIDIARY_OF]->(b:Corporation) "
        "CALL { WITH a MATCH (a)-[:HEADQUARTERED_IN]->(l:Location) RETURN l } "
        "RETURN a, l",
    ]
    for query in valid:
        result = validate(query, ONTOLOGY, SETTINGS)
        assert result.valid, f"{query!r} should validate, got {result.errors}"


def test_write_clause_hidden_in_string_or_comment_cannot_pass():
    # Parse-level detection: a write clause inside a string or a comment is
    # data, not syntax — and must not be flagged. The obfuscation corpus for
    # AC-18's write surface lives in the API tests; here the tokenizer
    # proves the mechanism.
    query = "MATCH (a:Corporation) RETURN a WHERE 'CREATE (x)' = 'CREATE (x)'"
    result = validate(query, ONTOLOGY, SETTINGS)
    assert result.valid, result.errors

    commented = "MATCH (a:Corporation) RETURN a /* CREATE (x) */"
    result = validate(commented, ONTOLOGY, SETTINGS)
    assert result.valid, result.errors

    line_comment = "MATCH (a:Corporation) RETURN a // MERGE (x)"
    result = validate(line_comment, ONTOLOGY, SETTINGS)
    assert result.valid, result.errors

    backticked = "MATCH (a:Corporation) RETURN `CREATE`"
    result = validate(backticked, ONTOLOGY, SETTINGS)
    assert result.valid, result.errors


def test_obfuscated_write_forms_are_still_detected():
    # Case, whitespace, and comment-splitting must not hide a real write
    # clause from the parser.
    for query in [
        "MATCH (n) cReAtE (m:Corporation)",
        "MATCH (n)\n\nDETACH\nDELETE n",
        "MATCH (n) CALL { /* CREATE */ CREATE (m) } RETURN n",
        "MATCH (n) CALL apoc.cypher.run('MATCH (m) DELETE m', {}) YIELD value RETURN value",
    ]:
        result = validate(query, ONTOLOGY, SETTINGS)
        assert not result.valid, query


def test_domain_violation_with_supertype_labels():
    # A supertype label resolves to its concrete types: Person is an Agent,
    # and OWNS_STAKE_IN admits Agent, so the query is valid — while the same
    # relation on a type outside the domain is not.
    ok = validate("MATCH (a:Agent)-[:OWNS_STAKE_IN]->(b:Corporation) RETURN b", ONTOLOGY, SETTINGS)
    assert ok.valid, ok.errors

    violation = validate(
        "MATCH (a:Topic)-[:OWNS_STAKE_IN]->(b:Corporation) RETURN b", ONTOLOGY, SETTINGS
    )
    assert "DOMAIN_VIOLATION" in codes(violation)


def test_untyped_position_attaches_partial_verification_note():
    result = validate("MATCH (a:Corporation)-[:SUBSIDIARY_OF]->(b) RETURN b", ONTOLOGY, SETTINGS)
    assert result.valid, result.errors
    assert any("range check skipped" in note for note in result.notes)


def test_limit_injected_when_absent():
    result = validate("MATCH (n:Corporation) RETURN n", ONTOLOGY, SETTINGS)
    assert result.valid
    assert result.cypher.endswith(f"LIMIT {SETTINGS.query_default_limit}")

    semicolon = validate("MATCH (n:Corporation) RETURN n;", ONTOLOGY, SETTINGS)
    assert semicolon.cypher.endswith(f"LIMIT {SETTINGS.query_default_limit};")

    present = validate(
        f"MATCH (n:Corporation) RETURN n LIMIT {SETTINGS.query_default_limit}",
        ONTOLOGY,
        SETTINGS,
    )
    assert present.cypher.count("LIMIT") == 1


def test_empty_statement_rejected():
    result = validate("  ", ONTOLOGY, SETTINGS)
    assert not result.valid
    assert result.errors[0].startswith("EMPTY_STATEMENT")


def test_tokenize_handles_strings_comments_and_backticks():
    query = """
    // comment with CREATE inside
    MATCH (n:`Corporation`) WHERE n.name = 'CREATE x'
    /* block with MERGE inside */
    RETURN n
    """
    tokens = tokenize(query)
    values = [token.value for token in tokens]
    assert "Corporation" in values
    assert "CREATE" not in values  # inside the string only
    assert "MERGE" not in values  # inside the comment only
    assert "MATCH" in values


def test_relation_types_in_only_sees_bracket_types():
    cypher = "MATCH (a:Corporation {label: 'x'})-[:SUBSIDIARY_OF]->(b) RETURN b LIMIT 1"
    assert relation_types_in(cypher) == ["SUBSIDIARY_OF"]

    map_only = "MATCH (a {x: y}) RETURN a"
    assert relation_types_in(map_only) == []


def test_union_branches_are_validated_separately():
    good = "MATCH (a:Corporation) RETURN a UNION MATCH (b:Person) RETURN b"
    result = validate(good, ONTOLOGY, SETTINGS)
    assert result.valid, result.errors

    bad = "MATCH (a:Corporation) RETURN a UNION MATCH (b:NotAType) RETURN b"
    result = validate(bad, ONTOLOGY, SETTINGS)
    assert "UNKNOWN_LABEL" in codes(result)
