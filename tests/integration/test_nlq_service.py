# tests/integration/test_nlq_service.py | v1.0.0 | introduced by WP-33
"""The NL-to-Cypher service end-to-end against the real Neo4j container:
generation (a stubbed client — no live inference), validation, exactly one
regeneration on failure, plan gating, execution, and the `NlqOutcome`
shape with editable Cypher in every outcome (AC-26)."""

from pathlib import Path

import pytest

from limes.composition import NlqContext
from tests.fixtures.graph_data import (
    load_corporation_graph,
    load_ontology_artifact,
    make_driver,
)
from tests.integration.conftest import Neo4jInstance


class StubClient:
    """The paid-inference seam, stubbed: records calls, returns crafted
    Cypher. The governor and ledger are untouched — no paid call, no
    `:CostLedgerEntry`."""

    def __init__(self) -> None:
        self.replies: list[str] = []
        self.calls: list[str] = []
        self.purposes: list[str] = []

    def complete(self, messages, model_id, purpose, json_schema=None):
        self.calls.append(model_id)
        self.purposes.append(purpose)
        if not self.replies:
            raise AssertionError("no reply queued")
        return self.replies.pop(0), 10, 5

    def embed(self, texts, model_id):
        raise AssertionError("no embedding on the query path")


@pytest.fixture(scope="module")
def seeded(neo4j_instance: Neo4jInstance) -> None:
    driver = make_driver(neo4j_instance)
    ontology = load_ontology_artifact()
    load_corporation_graph(driver, ontology)
    driver.close()


def _ctx(neo4j_instance: Neo4jInstance, tmp_path: Path, client: StubClient) -> NlqContext:
    from limes.composition import build_nlq_context
    from tests.fixtures.graph_data import api_settings

    settings = api_settings(neo4j_instance, tmp_path)
    driver = make_driver(neo4j_instance)
    ontology = load_ontology_artifact()
    ctx = build_nlq_context(settings, ontology, driver)
    return NlqContext(
        settings=ctx.settings,
        ontology=ctx.ontology,
        driver=ctx.driver,
        client=client,
        recorder=ctx.recorder,
    )


def test_answer_executes_generated_cypher(
    neo4j_instance: Neo4jInstance, tmp_path: Path, seeded: None
):
    from limes.nlq.service import answer

    client = StubClient()
    client.replies = ["MATCH (a:Corporation {lei: 'LEI-ALPHA'}) RETURN a"]
    ctx = _ctx(neo4j_instance, tmp_path, client)
    try:
        outcome = answer("Who is Alpha?", ctx)
    finally:
        ctx.driver.close()

    assert client.purposes == ["nl2cypher"]
    assert outcome.validation_errors == []
    assert outcome.plan_rejection is None
    assert outcome.results is not None
    assert outcome.results.counts["rows"] == 1
    node = outcome.results.nodes[0]
    assert node.label == "Alpha Industries"
    assert node.type == "Corporation"
    # AC-26: the Cypher is returned and editable.
    assert "MATCH (a:Corporation" in outcome.cypher
    assert "LIMIT" in outcome.cypher  # the validator injects the bound


def test_answer_regenerates_exactly_once_on_validation_failure(
    neo4j_instance: Neo4jInstance, tmp_path: Path, seeded: None
):
    from limes.nlq.service import answer

    client = StubClient()
    client.replies = [
        "MATCH (a:NotAType) RETURN a",
        "MATCH (a:Corporation {lei: 'LEI-ALPHA'}) RETURN a",
    ]
    ctx = _ctx(neo4j_instance, tmp_path, client)
    try:
        outcome = answer("Who is Alpha?", ctx)
    finally:
        ctx.driver.close()

    # Exactly two completions: the original and the single regeneration.
    assert len(client.calls) == 2
    assert outcome.validation_errors == []
    assert outcome.results is not None


def test_answer_reports_validation_failure_with_cypher(
    neo4j_instance: Neo4jInstance, tmp_path: Path, seeded: None
):
    from limes.nlq.service import answer

    client = StubClient()
    client.replies = [
        "MATCH (a:NotAType) RETURN a",
        "CREATE (a:Corporation)",
    ]
    ctx = _ctx(neo4j_instance, tmp_path, client)
    try:
        outcome = answer("Who is Alpha?", ctx)
    finally:
        ctx.driver.close()

    assert len(client.calls) == 2
    assert outcome.results is None
    # The outcome carries the *final* attempt's errors — the regeneration
    # replaced the first attempt's UNKNOWN_LABEL with its own WRITE_CLAUSE.
    assert any("WRITE_CLAUSE" in error for error in outcome.validation_errors)
    # AC-26: the (rejected) Cypher is still returned, editable.
    assert outcome.cypher.strip() == "CREATE (a:Corporation) LIMIT 500"


def test_answer_plan_rejection_returns_summary(
    neo4j_instance: Neo4jInstance, tmp_path: Path, seeded: None
):
    from limes.nlq.service import answer

    client = StubClient()
    client.replies = ["MATCH (a) MATCH (b) RETURN a, b"]
    ctx = _ctx(neo4j_instance, tmp_path, client)
    try:
        outcome = answer("Who is Alpha?", ctx)
    finally:
        ctx.driver.close()

    assert outcome.results is None
    assert outcome.plan_rejection is not None
    assert outcome.plan_rejection.has_cartesian_product is True
    assert outcome.cypher  # still returned, editable


def test_answer_execute_false_stops_after_validation(
    neo4j_instance: Neo4jInstance, tmp_path: Path, seeded: None
):
    from limes.nlq.service import answer

    client = StubClient()
    client.replies = ["MATCH (a:Corporation) RETURN a"]
    ctx = _ctx(neo4j_instance, tmp_path, client)
    try:
        outcome = answer("Who is Alpha?", ctx, execute=False)
    finally:
        ctx.driver.close()

    assert len(client.calls) == 1
    assert outcome.results is None
    assert outcome.validation_errors == []
