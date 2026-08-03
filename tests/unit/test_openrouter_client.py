# tests/unit/test_openrouter_client.py | v1.0.0 | introduced by WP-22
"""OpenRouter client tests per Doc 2 §8.7.6, §11 (WP-22).

The acceptance: `governor.check` before and `governor.commit` after every
request; the §11 retry policy (429/5xx retried with backoff, other 4xx never);
the API key never reaching a log line; ledger entries only for attempts that
returned token usage; pricing from the catalogue with a conservative
fallback. All transport is respx-mocked — no live network.
"""

import logging
from decimal import Decimal

import httpx
import pytest
import respx
from httpx import Response

from limes.config import Settings
from limes.cost.governor import Governor
from limes.errors import BudgetExhausted, ExtractionError
from limes.extraction.openrouter_client import (
    FALLBACK_USD_PER_MILLION_INPUT,
    FALLBACK_USD_PER_MILLION_OUTPUT,
    OpenRouterClient,
)

BASE_URL = "https://openrouter.test/api/v1"
MODEL = "test/extraction-model"
API_KEY = "sk-live-super-secret-test-key"
CATALOGUE_URL = f"{BASE_URL}/models"
COMPLETIONS_URL = f"{BASE_URL}/chat/completions"
EMBEDDINGS_URL = f"{BASE_URL}/embeddings"

# A catalogue entry with recognizable per-token prices (USD per million).
CATALOGUE = {
    "data": [
        {
            "id": MODEL,
            "pricing": {
                "prompt": "0.000000250",  # 0.25 USD per million input tokens
                "completion": "0.000000750",  # 0.75 USD per million output tokens
                "request": "0.000001000",  # 1e-6 USD per request
            },
        }
    ]
}

USAGE = {"prompt_tokens": 4000, "completion_tokens": 1000, "total_tokens": 5000}
COMPLETION = {"choices": [{"message": {"content": "[]"}}], "usage": USAGE}


def _settings(**overrides) -> Settings:
    base = dict(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="limes",
        neo4j_password="pw",
        ontology_path="/tmp/ontology.yaml",
        feeds_config_path="/tmp/feeds.yaml",
        gold_set_path="/tmp/gold_set.jsonl",
        baseline_path="/tmp/baseline.json",
        archive_path="/tmp/archive",
        openrouter_api_key=API_KEY,
        openrouter_base_url=BASE_URL,
        http_timeout_seconds=10,
        usd_eur_rate=0.92,
    )
    base.update(overrides)
    return Settings(**base)


class MockGovernor:
    """Records check/commit calls; can be armed to refuse a check."""

    def __init__(self) -> None:
        self.checks: list[Decimal] = []
        self.commits: list = []
        self.refuse: Decimal | None = None

    @property
    def usd_eur_rate(self) -> float:
        return 0.92

    def check(self, estimated_cost_eur: Decimal) -> None:
        self.checks.append(estimated_cost_eur)
        if self.refuse is not None and estimated_cost_eur > self.refuse:
            raise BudgetExhausted(f"budget exhausted at {estimated_cost_eur}")

    def commit(self, actual) -> None:
        self.commits.append(actual)

    def remaining(self) -> Decimal:
        return Decimal("1")


def _client(governor: Governor | None = None) -> tuple[OpenRouterClient, MockGovernor]:
    gov = governor if governor is not None else MockGovernor()
    return OpenRouterClient(_settings(), gov), gov


def test_complete_checks_before_and_commits_after():
    with respx.mock:
        respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=CATALOGUE))
        respx.post(COMPLETIONS_URL).mock(return_value=Response(200, json=COMPLETION))
        client, governor = _client()
        content, input_tokens, output_tokens = client.complete(
            [{"role": "system", "content": "extract"}], MODEL, "extraction"
        )

    assert content == "[]"
    assert input_tokens == 4000
    assert output_tokens == 1000
    assert len(governor.checks) == 1
    assert len(governor.commits) == 1
    entry = governor.commits[0]
    assert entry.purpose == "extraction"
    assert entry.model_id == MODEL
    assert entry.input_tokens == 4000
    assert entry.output_tokens == 1000
    # 4000 * 2.5e-7 + 1000 * 7.5e-7 + 1e-6 request = 0.001751 USD
    assert entry.cost_usd == Decimal("0.001751")
    assert entry.cost_eur == Decimal("0.00161092")
    assert entry.period.startswith("20")


def test_retry_on_429_then_success():
    with respx.mock:
        respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=CATALOGUE))
        route = respx.post(COMPLETIONS_URL).mock(
            side_effect=[
                Response(429, json={"error": "rate limited"}),
                Response(200, json=COMPLETION),
            ]
        )
        client, governor = _client()
        client.complete([{"role": "user", "content": "x"}], MODEL, "extraction")

    assert route.call_count == 2
    assert len(governor.commits) == 1


def test_retry_on_5xx_then_success():
    with respx.mock:
        respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=CATALOGUE))
        route = respx.post(COMPLETIONS_URL).mock(
            side_effect=[
                Response(503, json={"error": "unavailable"}),
                Response(200, json=COMPLETION),
            ]
        )
        client, _ = _client()
        client.complete([{"role": "user", "content": "x"}], MODEL, "extraction")

    assert route.call_count == 2


def test_no_retry_on_other_4xx():
    with respx.mock:
        respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=CATALOGUE))
        route = respx.post(COMPLETIONS_URL).mock(return_value=Response(400, json={"error": "bad"}))
        client, governor = _client()
        try:
            client.complete([{"role": "user", "content": "x"}], MODEL, "extraction")
        except ExtractionError:
            pass
        else:
            raise AssertionError("expected ExtractionError on 400")

    assert route.call_count == 1
    assert governor.commits == []


def test_exhausted_retries_raise_extraction_error():
    with respx.mock:
        respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=CATALOGUE))
        route = respx.post(COMPLETIONS_URL).mock(return_value=Response(429, json={}))
        client, _ = _client()
        try:
            client.complete([{"role": "user", "content": "x"}], MODEL, "extraction")
        except ExtractionError as exc:
            assert "429" in str(exc)
        else:
            raise AssertionError("expected ExtractionError after retries")

    assert route.call_count == 4  # the §11 maximum


def test_api_key_never_reaches_a_log_line(caplog):
    with respx.mock:
        respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=CATALOGUE))
        route = respx.post(COMPLETIONS_URL).mock(return_value=Response(200, json=COMPLETION))
        client, _ = _client()
        with caplog.at_level(logging.INFO):
            client.complete([{"role": "user", "content": "x"}], MODEL, "extraction")

    assert API_KEY not in caplog.text
    # The key is present in the wire request (that is its purpose) but never
    # in a log line: assert the request carried it so the test cannot pass by
    # the key simply not being used at all.
    assert any(API_KEY in str(call.request.headers.get("authorization")) for call in route.calls)


def test_no_ledger_entry_when_usage_missing():
    no_usage = {"choices": [{"message": {"content": "[]"}}]}
    with respx.mock:
        respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=CATALOGUE))
        respx.post(COMPLETIONS_URL).mock(return_value=Response(200, json=no_usage))
        client, governor = _client()
        client.complete([{"role": "user", "content": "x"}], MODEL, "extraction")

    assert governor.commits == []
    assert len(governor.checks) == 1


def test_unknown_purpose_is_rejected_before_any_request():
    with respx.mock:
        respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=CATALOGUE))
        client, governor = _client()
        try:
            client.complete([{"role": "user", "content": "x"}], MODEL, "nonsense")
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError for an unknown purpose")
    assert governor.checks == []


def test_budget_exhausted_refuses_without_issuing_request():
    with respx.mock:
        respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=CATALOGUE))
        route = respx.post(COMPLETIONS_URL).mock(return_value=Response(200, json=COMPLETION))
        governor = MockGovernor()
        governor.refuse = Decimal("0.0000001")
        client = OpenRouterClient(_settings(), governor)
        try:
            client.complete([{"role": "user", "content": "x"}], MODEL, "extraction")
        except BudgetExhausted:
            pass
        else:
            raise AssertionError("expected BudgetExhausted")

    assert route.call_count == 0
    assert governor.commits == []


def test_fallback_pricing_when_model_absent_from_catalogue():
    empty_catalogue = {"data": []}
    with respx.mock:
        respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=empty_catalogue))
        respx.post(COMPLETIONS_URL).mock(return_value=Response(200, json=COMPLETION))
        client, governor = _client()
        client.complete([{"role": "user", "content": "x"}], MODEL, "extraction")

    entry = governor.commits[0]
    expected_usd = Decimal(str(4000 * (FALLBACK_USD_PER_MILLION_INPUT / 1e6))) + Decimal(
        str(1000 * (FALLBACK_USD_PER_MILLION_OUTPUT / 1e6))
    )
    assert entry.cost_usd == expected_usd


def test_embed_checks_and_commits():
    embedding_response = {
        "data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}],
        "usage": {"prompt_tokens": 120, "total_tokens": 120},
    }
    with respx.mock:
        respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=CATALOGUE))
        respx.post(EMBEDDINGS_URL).mock(return_value=Response(200, json=embedding_response))
        client, governor = _client()
        embeddings = client.embed(["text one", "text two"], MODEL)

    assert embeddings == [[0.1, 0.2], [0.3, 0.4]]
    assert len(governor.checks) == 1
    assert len(governor.commits) == 1
    assert governor.commits[0].purpose == "embedding"
    assert governor.commits[0].output_tokens == 0


def test_catalogue_returns_model_list():
    with respx.mock:
        respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=CATALOGUE))
        client, _ = _client()
        models = client.catalogue()
    assert models == CATALOGUE["data"]


def test_complete_retries_on_connection_error_then_fails():
    with respx.mock:
        respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=CATALOGUE))
        route = respx.post(COMPLETIONS_URL).mock(side_effect=httpx.ConnectError("refused"))
        client, governor = _client()
        try:
            client.complete([{"role": "user", "content": "x"}], MODEL, "extraction")
        except ExtractionError as exc:
            assert "call failed after" in str(exc)
        else:
            raise AssertionError("expected ExtractionError after connection errors")
    assert route.call_count == 4
    assert governor.commits == []


def test_embed_response_without_data_list_raises():
    with respx.mock:
        respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=CATALOGUE))
        respx.post(EMBEDDINGS_URL).mock(return_value=Response(200, json={"usage": {}}))
        client, _ = _client()
        with pytest.raises(ExtractionError, match="no data list"):
            client.embed(["text"], MODEL)


def test_embed_item_without_embedding_list_raises():
    with respx.mock:
        respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=CATALOGUE))
        respx.post(EMBEDDINGS_URL).mock(
            return_value=Response(200, json={"data": [{"embedding": "nope"}], "usage": {}})
        )
        client, _ = _client()
        with pytest.raises(ExtractionError, match="no embedding list"):
            client.embed(["text"], MODEL)


def test_catalogue_retries_on_429_then_fails():
    with respx.mock:
        route = respx.get(CATALOGUE_URL).mock(return_value=Response(429, json={}))
        client, _ = _client()
        with pytest.raises(ExtractionError, match="catalogue failed after"):
            client.catalogue()
    assert route.call_count == 4


def test_catalogue_retries_on_connection_error_then_fails():
    with respx.mock:
        route = respx.get(CATALOGUE_URL).mock(side_effect=httpx.ConnectError("refused"))
        client, _ = _client()
        with pytest.raises(ExtractionError, match="catalogue failed after"):
            client.catalogue()
    assert route.call_count == 4


def test_catalogue_non_retryable_4xx_fails_immediately():
    with respx.mock:
        route = respx.get(CATALOGUE_URL).mock(return_value=Response(400, json={"error": "bad"}))
        client, _ = _client()
        with pytest.raises(ExtractionError, match="catalogue failed: .* HTTP 400"):
            client.catalogue()
    assert route.call_count == 1


def test_catalogue_without_data_list_raises():
    with respx.mock:
        respx.get(CATALOGUE_URL).mock(return_value=Response(200, json={"data": "nope"}))
        client, _ = _client()
        with pytest.raises(ExtractionError, match="no data list"):
            client.catalogue()


def test_price_falls_back_when_catalogue_pricing_is_unfloatable():
    broken = {"data": [{"id": MODEL, "pricing": {"prompt": "abc", "completion": "0.000000750"}}]}
    with respx.mock:
        respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=broken))
        respx.post(COMPLETIONS_URL).mock(return_value=Response(200, json=COMPLETION))
        client, governor = _client()
        client.complete([{"role": "user", "content": "x"}], MODEL, "extraction")
    entry = governor.commits[0]
    expected_usd = Decimal(str(4000 * (FALLBACK_USD_PER_MILLION_INPUT / 1e6))) + Decimal(
        str(1000 * (FALLBACK_USD_PER_MILLION_OUTPUT / 1e6))
    )
    assert entry.cost_usd == expected_usd


def test_price_falls_back_when_catalogue_call_fails():
    with respx.mock:
        respx.get(CATALOGUE_URL).mock(return_value=Response(503, json={}))
        respx.post(COMPLETIONS_URL).mock(return_value=Response(200, json=COMPLETION))
        client, governor = _client()
        client.complete([{"role": "user", "content": "x"}], MODEL, "extraction")
    entry = governor.commits[0]
    expected_usd = Decimal(str(4000 * (FALLBACK_USD_PER_MILLION_INPUT / 1e6))) + Decimal(
        str(1000 * (FALLBACK_USD_PER_MILLION_OUTPUT / 1e6))
    )
    assert entry.cost_usd == expected_usd


def test_completion_without_choices_raises():
    with respx.mock:
        respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=CATALOGUE))
        respx.post(COMPLETIONS_URL).mock(return_value=Response(200, json={"usage": {}}))
        client, _ = _client()
        with pytest.raises(ExtractionError, match="has no content"):
            client.complete([{"role": "user", "content": "x"}], MODEL, "extraction")


def test_completion_with_non_string_content_raises():
    with respx.mock:
        respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=CATALOGUE))
        respx.post(COMPLETIONS_URL).mock(
            return_value=Response(200, json={"choices": [{"message": {"content": 123}}]})
        )
        client, _ = _client()
        with pytest.raises(ExtractionError, match="content is not a string"):
            client.complete([{"role": "user", "content": "x"}], MODEL, "extraction")
