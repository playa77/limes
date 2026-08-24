# src/limes/extraction/openrouter_client.py | v1.0.0 | introduced by WP-22
"""The single OpenRouter client per Technical Specification §8.7.6, §11.

One client for all OpenRouter interaction: chat completions, embeddings, and
the model catalogue. It calls `governor.check` before every request and
`governor.commit` after, using the provider's reported token usage, and is
therefore the only module that writes `:CostLedgerEntry` (via the governor —
§15.2). The API key is sent in the Authorization header and never enters a
log line: no request body, header, or URL is ever logged.

Pricing comes from the model catalogue (`GET /models`), fetched lazily and
cached per model id; a model absent from the catalogue falls back to a
deliberately conservative constant and logs a warning — overestimating the
price makes the governor refuse early, the safe direction. The fallback is
why a price can be wrong in a test or a network partition, but never silently
cheap.

Retry policy per §11: exponential backoff from 2 s, factor 2, jittered, at
most 4 attempts, on connection errors, timeouts, 429, and 5xx — never on
other 4xx. A request that exhausts its attempts surfaces as `ExtractionError`
naming the model and purpose. `governor.check` runs once per logical call
before the first attempt; `governor.commit` runs once per call that returned
token usage — ledger entries are written only for attempts that returned
usage (§8.7.6), so a call that died on its last retry never costs anything.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal, cast

import structlog

from limes.config import Settings
from limes.cost.governor import Governor
from limes.errors import ExtractionError
from limes.extraction.base import ESTIMATED_OUTPUT_TOKENS
from limes.sources.base import PermanentStatus, RetryExhausted, request_with_retry
from limes.types import CostLedgerEntry

logger = structlog.get_logger(__name__)

# Fallback per-token USD prices (per million tokens) for models absent from
# the catalogue. Conservative on purpose: an overestimate refuses a call
# early; an underestimate would silently breach the budget.
FALLBACK_USD_PER_MILLION_INPUT = 0.50
FALLBACK_USD_PER_MILLION_OUTPUT = 0.50

# The cost purposes the ledger accepts (§5.5 `CostLedgerEntry.purpose`).
PURPOSES = ("extraction", "adjudication", "embedding", "nl2cypher")


def post_json_with_retry(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout_s: float,
) -> dict[str, Any]:
    """POST a JSON payload with the §11 retry policy (`request_with_retry`),
    returning the parsed JSON response. After the last attempt raises
    `ExtractionError` naming the URL; a non-retryable 4xx raises it
    immediately."""
    try:
        response = request_with_retry(
            "POST", url, json_body=payload, headers=headers, timeout_s=timeout_s, log=logger
        )
    except PermanentStatus as exc:
        raise ExtractionError(f"call failed: {exc.url} returned HTTP {exc.status_code}") from exc
    except RetryExhausted as exc:
        raise ExtractionError(
            f"call failed after {exc.attempts} attempts: {exc.url} ({exc.reason})"
        ) from exc
    body: dict[str, Any] = response.json()
    return body


class OpenRouterClient:
    """One client for chat completions, embeddings, and the catalogue; the
    only module that writes `:CostLedgerEntry` (via the governor)."""

    def __init__(self, settings: Settings, governor: Governor) -> None:
        self._settings = settings
        self._governor = governor
        # model_id -> (usd_per_input_token, usd_per_output_token, usd_per_request)
        self._prices: dict[str, tuple[float, float, float]] = {}

    def complete(
        self,
        messages: list[dict[str, str]],
        model_id: str,
        purpose: str,
        json_schema: dict[str, Any] | None = None,
    ) -> tuple[str, int, int]:
        """One chat completion. Returns (content, input_tokens, output_tokens)
        with the call checked and committed against the governor."""
        if purpose not in PURPOSES:
            raise ValueError(f"unknown ledger purpose: {purpose!r}")
        input_price, output_price, request_fee = self._price_for(model_id)
        estimate_in = sum(len(str(m.get("content") or "")) for m in messages) // 4
        self._governor.check(
            _cost_eur(
                estimate_in,
                ESTIMATED_OUTPUT_TOKENS,
                input_price,
                output_price,
                request_fee,
                self._governor,
            )
        )

        payload: dict[str, Any] = {"model": model_id, "messages": messages}
        if json_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "response", "schema": json_schema},
            }
        response = post_json_with_retry(
            f"{self._settings.openrouter_base_url}/chat/completions",
            payload,
            self._headers(),
            self._settings.http_timeout_seconds,
        )
        content = _content_of(response)
        usage = response.get("usage") if isinstance(response, dict) else None
        input_tokens = int((usage or {}).get("prompt_tokens", 0))
        output_tokens = int((usage or {}).get("completion_tokens", 0))
        purpose_literal = cast(
            Literal["extraction", "adjudication", "embedding", "nl2cypher"], purpose
        )
        self._commit(
            purpose_literal,
            model_id,
            input_tokens,
            output_tokens,
            input_price,
            output_price,
            request_fee,
        )
        logger.info(
            "openrouter call completed",
            purpose=purpose,
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        return content, input_tokens, output_tokens

    def embed(self, texts: list[str], model_id: str) -> list[list[float]]:
        """One embedding request. Checked and committed like `complete`;
        embeddings bill prompt tokens only."""
        input_price, _, _ = self._price_for(model_id)
        estimate_in = sum(len(t) for t in texts) // 4
        self._governor.check(_cost_eur(estimate_in, 0, input_price, 0.0, 0.0, self._governor))
        response = post_json_with_retry(
            f"{self._settings.openrouter_base_url}/embeddings",
            {"model": model_id, "input": texts},
            self._headers(),
            self._settings.http_timeout_seconds,
        )
        data = response.get("data") if isinstance(response, dict) else None
        if not isinstance(data, list):
            raise ExtractionError("embedding response carries no data list")
        embeddings: list[list[float]] = []
        for item in data:
            if not isinstance(item, dict) or not isinstance(item.get("embedding"), list):
                raise ExtractionError("embedding response item carries no embedding list")
            embeddings.append([float(v) for v in item["embedding"]])
        usage = response.get("usage") if isinstance(response, dict) else None
        input_tokens = int((usage or {}).get("prompt_tokens", 0))
        self._commit("embedding", model_id, input_tokens, 0, input_price, 0.0, 0.0)
        return embeddings

    def catalogue(self) -> list[dict[str, Any]]:
        """The live model catalogue (`GET /models`) as a list of model dicts.
        Not a paid call: no governor check or commit. Fresh on every call —
        model selection (WP-29) wants the current state; `complete`/`embed`
        use the per-client price cache."""
        url = f"{self._settings.openrouter_base_url}/models"
        try:
            response = request_with_retry(
                "GET",
                url,
                headers=self._headers(),
                timeout_s=self._settings.http_timeout_seconds,
                log=logger,
            )
        except PermanentStatus as exc:
            raise ExtractionError(
                f"catalogue failed: {exc.url} returned HTTP {exc.status_code}"
            ) from exc
        except RetryExhausted as exc:
            raise ExtractionError(
                f"catalogue failed after {exc.attempts} attempts: {exc.url} ({exc.reason})"
            ) from exc
        payload: dict[str, Any] = response.json()
        data = payload.get("data")
        if not isinstance(data, list):
            raise ExtractionError("catalogue response carries no data list")
        return [entry for entry in data if isinstance(entry, dict)]

    def _price_for(self, model_id: str) -> tuple[float, float, float]:
        """Per-token USD prices for a model: from the cached catalogue, else
        the conservative fallback (logged — the price affects the ledger and
        the governor, so a fallback must never be silent)."""
        cached = self._prices.get(model_id)
        if cached is not None:
            return cached
        fallback = (
            FALLBACK_USD_PER_MILLION_INPUT / 1e6,
            FALLBACK_USD_PER_MILLION_OUTPUT / 1e6,
            0.0,
        )
        try:
            for entry in self.catalogue():
                if entry.get("id") != model_id:
                    continue
                pricing = entry.get("pricing") or {}
                try:
                    # Catalogue prices are per token already; the fallback
                    # constants are per million and get divided here.
                    price = (
                        float(pricing.get("prompt") or FALLBACK_USD_PER_MILLION_INPUT / 1e6),
                        float(pricing.get("completion") or FALLBACK_USD_PER_MILLION_OUTPUT / 1e6),
                        float(pricing.get("request") or 0.0),
                    )
                except (TypeError, ValueError):
                    break
                self._prices[model_id] = price
                return price
        except ExtractionError as exc:
            logger.warning(
                "model pricing unavailable; using conservative fallback",
                model_id=model_id,
                reason=str(exc),
            )
        self._prices[model_id] = fallback
        logger.warning(
            "model absent from catalogue; using conservative fallback price",
            model_id=model_id,
        )
        return fallback

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }

    def _commit(
        self,
        purpose: Literal["extraction", "adjudication", "embedding", "nl2cypher"],
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        input_price: float,
        output_price: float,
        request_fee: float,
    ) -> None:
        """One ledger entry via the governor — only when the call returned
        token usage (§8.7.6). A response without usage is logged with a
        warning: an unmetered call is visible, never silent."""
        if input_tokens == 0 and output_tokens == 0:
            logger.warning("openrouter call returned no token usage; not ledgered")
            return
        now = datetime.now(UTC)
        cost_usd = Decimal(
            str(input_tokens * input_price + output_tokens * output_price + request_fee)
        )
        entry = CostLedgerEntry(
            ledger_id=uuid.uuid4().hex,
            period=now.strftime("%Y-%m"),
            purpose=purpose,
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            cost_eur=cost_usd * Decimal(str(self._settings.usd_eur_rate)),
            created_at=now,
        )
        self._governor.commit(entry)


def _cost_eur(
    input_tokens: int,
    output_tokens: int,
    input_price: float,
    output_price: float,
    request_fee: float,
    governor: Governor,
) -> Decimal:
    usd = Decimal(str(input_tokens * input_price + output_tokens * output_price + request_fee))
    return usd * Decimal(str(governor.usd_eur_rate))


def _content_of(response: dict[str, Any]) -> str:
    """The assistant message content of a chat completion, or `ExtractionError`
    when the shape is unexpected — a malformed provider response must not
    surface as an empty string."""
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ExtractionError(f"chat completion response has no content: {exc}") from exc
    if not isinstance(content, str):
        raise ExtractionError("chat completion content is not a string")
    return content
