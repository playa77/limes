# tests/unit/test_coverage_diagnose.py | v1.0.0 | introduced by WP-34
"""Empty-result diagnosis unit tests per Doc 2 §8.11.

The decomposition happy paths (first empty clause named, per-relation
counts) are covered by the integration suite; these tests pin the edge
surface: a statement whose only MATCH clause is also the last clause, a
clause with neither entity types nor relations, and the offset helper
boundaries.
"""

from limes.coverage.diagnose import _end_pos, _statement_end, diagnose
from limes.nlq.validate import tokenize


class FakeDriver:
    """Every clause counts zero rows — the first clause fails."""

    def __init__(self) -> None:
        self.queries: list[str] = []

    def read(self, cypher: str, params: dict, timeout_s: int) -> list[dict]:
        self.queries.append(cypher)
        return [{"n": 0}]


def test_diagnose_names_the_only_match_clause():
    # The MATCH clause is also the last clause of the statement: its end is
    # the statement's end, not the next clause keyword.
    driver = FakeDriver()
    result = diagnose(driver, "MATCH (n)", {})
    assert result.failing_clause == "MATCH (n)"
    assert result.clause_index == 0
    assert driver.queries == ["MATCH (n) RETURN count(*) AS n"]


def test_diagnose_clause_without_types_gets_the_generic_note():
    driver = FakeDriver()
    result = diagnose(driver, "MATCH (n)", {})
    assert result.note == "no data matches the clause's pattern"


def test_end_pos_past_the_last_token_uses_the_statement_end():
    tokens = tokenize("MATCH (n)")
    assert _end_pos(tokens, len(tokens)) == len("MATCH (n)")


def test_statement_end_of_empty_tokens_is_zero():
    assert _statement_end([]) == 0
