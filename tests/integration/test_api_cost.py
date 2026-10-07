# tests/integration/test_api_cost.py | v1.0.0 | introduced by WP-32
"""`GET /cost/ledger` per Doc 2 §6: period spend read from the graph via
the ledger's own read path, remaining budget from the monthly governor,
and the period's entries. The ledger entry is written through the
production path (`cost/ledger.write_entry` — the same function the
OpenRouter client calls)."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from tests.fixtures.graph_data import make_api_client, make_driver
from tests.integration.conftest import Neo4jInstance

PERIOD = "2026-07"


def test_cost_ledger_returns_period_spend_and_entries(
    neo4j_instance: Neo4jInstance, tmp_path: Path
):
    from limes.cost.ledger import write_entry
    from limes.types import CostLedgerEntry

    driver = make_driver(neo4j_instance)
    write_entry(
        driver,
        CostLedgerEntry(
            ledger_id="ledger-1",
            period=PERIOD,
            purpose="nl2cypher",
            model_id="test/model",
            input_tokens=100,
            output_tokens=20,
            cost_usd=Decimal("0.001"),
            cost_eur=Decimal("0.00092"),
            created_at=datetime(2026, 7, 15, tzinfo=UTC),
        ),
    )
    driver.close()

    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.get("/cost/ledger", params={"period": PERIOD})
        assert response.status_code == 200
        body = response.json()
        assert body["period"] == PERIOD
        assert body["spend_eur"] == pytest.approx(0.00092)
        assert len(body["entries"]) == 1
        entry = body["entries"][0]
        assert entry["ledger_id"] == "ledger-1"
        assert entry["purpose"] == "nl2cypher"
        assert entry["input_tokens"] == 100
        assert body["remaining_eur"] is None


def test_cost_ledger_invalid_period_is_rejected(neo4j_instance: Neo4jInstance, tmp_path: Path):
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.get("/cost/ledger", params={"period": "july"})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
