# tests/unit/test_nlq_plan.py | v1.0.0 | introduced by WP-33
"""Plan-gate unit tests per Doc 2 §8.10: every plan-gate rejection (AC-21)
is produced by a crafted query and blocks execution. The EXPLAIN plan and
the variable-length bounds are the gate's two inputs; the former is faked
here (a driver stub — the real `EXPLAIN` integration is covered by the
service tests), the latter is parsed from the query text."""

from pathlib import Path

import pytest

from limes.config import Settings
from limes.errors import QueryPlanRejected
from limes.nlq.plan import explain_gate
from limes.types import PlanSummary

REPO_ROOT = Path(__file__).resolve().parents[2]

SETTINGS = Settings(
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="u",
    neo4j_password="p",
    ontology_path=REPO_ROOT / "ontology" / "ontology.yaml",
    feeds_config_path=REPO_ROOT / "ontology" / "feeds.yaml",
    gold_set_path=REPO_ROOT / "gold_set" / "gold_set.jsonl",
    baseline_path=REPO_ROOT / "gold_set" / "baseline.json",
    archive_path=REPO_ROOT / "data" / "archive",
    query_max_varlength_hops=4,
    query_max_estimated_rows_operator=5_000_000,
    query_max_estimated_rows_total=20_000_000,
)


class FakeDriver:
    """A driver stub returning a fixed plan summary — the gate's plan input
    — while the query-text inspection runs for real."""

    def __init__(self, summary: PlanSummary) -> None:
        self._summary = summary
        self.last_cypher: str | None = None

    def explain(self, cypher: str, params: dict[str, object]) -> PlanSummary:
        self.last_cypher = cypher
        return self._summary


def plan(**overrides) -> PlanSummary:
    base = dict(
        operators=["Expand(All)"],
        max_estimated_rows=100,
        total_estimated_rows=1000,
        has_cartesian_product=False,
        max_varlength_hops=None,
    )
    base.update(overrides)
    return PlanSummary(**base)


def rejected_code(exc: QueryPlanRejected) -> str:
    return getattr(exc, "code", "")


def test_ac21_cartesian_product_rejected():
    driver = FakeDriver(plan(has_cartesian_product=True))
    with pytest.raises(QueryPlanRejected) as exc:
        explain_gate(driver, "MATCH (a) MATCH (b) RETURN a, b", {}, SETTINGS)
    assert rejected_code(exc.value) == "CARTESIAN_PRODUCT"


def test_ac21_operator_rows_exceeded_rejected():
    driver = FakeDriver(plan(max_estimated_rows=SETTINGS.query_max_estimated_rows_operator + 1))
    with pytest.raises(QueryPlanRejected) as exc:
        explain_gate(driver, "MATCH (n:Corporation) RETURN n", {}, SETTINGS)
    assert rejected_code(exc.value) == "OPERATOR_ROWS_EXCEEDED"


def test_ac21_total_rows_exceeded_rejected():
    driver = FakeDriver(plan(total_estimated_rows=SETTINGS.query_max_estimated_rows_total + 1))
    with pytest.raises(QueryPlanRejected) as exc:
        explain_gate(driver, "MATCH (n:Corporation) RETURN n", {}, SETTINGS)
    assert rejected_code(exc.value) == "TOTAL_ROWS_EXCEEDED"


def test_ac21_unbounded_expansion_rejected():
    driver = FakeDriver(plan())
    for query in (
        "MATCH p = (a:Corporation)-[:SUBSIDIARY_OF*]->(b) RETURN p",
        "MATCH p = (a:Corporation)-[:SUBSIDIARY_OF*1..]->(b) RETURN p",
        "MATCH p = (a:Corporation)-[:SUBSIDIARY_OF*..]->(b) RETURN p",
    ):
        with pytest.raises(QueryPlanRejected) as exc:
            explain_gate(driver, query, {}, SETTINGS)
        assert rejected_code(exc.value) == "UNBOUNDED_EXPANSION", query


def test_ac21_expansion_too_deep_rejected():
    driver = FakeDriver(plan())
    with pytest.raises(QueryPlanRejected) as exc:
        explain_gate(
            driver,
            f"MATCH p = (a:Corporation)-[:SUBSIDIARY_OF*1.."
            f"{SETTINGS.query_max_varlength_hops + 1}]->(b) RETURN p",
            {},
            SETTINGS,
        )
    assert rejected_code(exc.value) == "EXPANSION_TOO_DEEP"

    # An exact bound above the ceiling is too deep as well.
    with pytest.raises(QueryPlanRejected) as exc:
        explain_gate(
            driver,
            f"MATCH p = (a:Corporation)-[:SUBSIDIARY_OF*"
            f"{SETTINGS.query_max_varlength_hops + 1}]->(b) RETURN p",
            {},
            SETTINGS,
        )
    assert rejected_code(exc.value) == "EXPANSION_TOO_DEEP"


def test_bounded_expansions_within_ceiling_pass():
    driver = FakeDriver(plan())
    summary = explain_gate(
        driver,
        f"MATCH p = (a:Corporation)-[:SUBSIDIARY_OF*1.."
        f"{SETTINGS.query_max_varlength_hops}]->(b) RETURN p",
        {},
        SETTINGS,
    )
    assert summary.max_estimated_rows == 100
    assert driver.last_cypher is not None


def test_rejection_carries_plan_summary():
    summary = plan(has_cartesian_product=True)
    driver = FakeDriver(summary)
    with pytest.raises(QueryPlanRejected) as exc:
        explain_gate(driver, "MATCH (a) MATCH (b) RETURN a, b", {}, SETTINGS)
    assert getattr(exc.value, "plan_summary", None) is summary


def test_star_at_statement_end_is_not_an_unbounded_expansion():
    # A trailing `*` with no following token cannot be a variable-length
    # form; the gate must not reject what it cannot parse.
    driver = FakeDriver(plan())
    summary = explain_gate(driver, "MATCH (a)-[*", {}, SETTINGS)
    assert summary.max_estimated_rows == 100


def test_bounded_expansion_with_open_lower_bound_passes():
    # `[*..5]` has an upper bound and is therefore not unbounded.
    driver = FakeDriver(plan())
    summary = explain_gate(driver, "MATCH (a)-[*..5]->(b) RETURN a", {}, SETTINGS)
    assert summary.max_estimated_rows == 100
