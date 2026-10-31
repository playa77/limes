# src/limes/extraction/ollama.py | v1.0.0 | introduced by WP-22
"""The laptop-only Ollama extractor (C-05).

A local-model overflow path for the operator's laptop: same `Extractor`
protocol as `OpenRouterExtractor`, same batching and the same deterministic
response parsing — only the transport differs. It calls a local Ollama server
and never goes through the governor or the ledger: local inference is free,
so there is nothing to meter (Doc 1 §8.2: a locally hosted German relation
extraction model needs 6–8 GB resident and does not fit the deployment
envelope; this path is for manual, laptop-side work only).

Laptop-only is a statement of intent, not a lock: nothing here prevents a
deployed run from using it. The composition root (WP-26) is the seam that
keeps the paid path default and this one explicit.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

from limes.config import Settings
from limes.errors import ExtractionError
from limes.extraction.base import (
    ExtractionResult,
    batch_passages,
    build_extraction_messages,
)
from limes.extraction.schema import (
    SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    parse_extraction_response,
    response_schema_for_version,
)
from limes.ontology.model import Ontology
from limes.sources.base import PermanentStatus, RetryExhausted, request_with_retry
from limes.types import ExtractedAssertion, Passage

logger = structlog.get_logger(__name__)

# The local endpoint defaults. No configuration keys are added (the config
# surface is §4.2's, and this path is laptop-only); the constructor accepts
# overrides for a non-default local server.
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.1:8b"


class OllamaExtractor:
    """Laptop-only local extractor: same protocol, free inference, no ledger."""

    def __init__(
        self,
        settings: Settings,
        model_id: str = DEFAULT_OLLAMA_MODEL,
        base_url: str = DEFAULT_OLLAMA_BASE_URL,
    ) -> None:
        self._settings = settings
        self._model_id = model_id
        self._base_url = base_url
        self._prompt = _load_prompt()

    @property
    def model_id(self) -> str:
        """The local model name (the constructor's default or override)."""
        return self._model_id

    def extract(
        self,
        passages: list[Passage],
        ontology: Ontology,
        prompt_version: str,
        schema_version: str,
    ) -> ExtractionResult:
        if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise ExtractionError(
                f"unsupported extraction schema version {schema_version!r}; "
                f"this extractor implements {SCHEMA_VERSION!r}"
            )
        ontology_serialized = ontology.serialize_for_prompt()
        prompt_text = self._prompt.replace("{ontology}", ontology_serialized)
        prompt_overhead = (len(prompt_text) + len(ontology_serialized)) // 4

        batches = batch_passages(
            passages,
            self._settings.extraction_max_passages_per_call,
            self._settings.extraction_max_input_tokens,
            prompt_overhead,
        )
        assertions: list[ExtractedAssertion] = []
        parse_errors: list[str] = []
        input_tokens = 0
        output_tokens = 0
        raw_responses: list[str] = []
        for batch in batches:
            messages = build_extraction_messages(batch, prompt_text, ontology_serialized)
            response = self._chat(messages, schema_version)
            raw = _content_of(response)
            batch_input = int(response.get("prompt_eval_count", 0))
            batch_output = int(response.get("eval_count", 0))
            batch_assertions, batch_errors = parse_extraction_response(
                raw, passages, ontology, schema_version
            )
            assertions.extend(batch_assertions)
            parse_errors.extend(batch_errors)
            input_tokens += batch_input
            output_tokens += batch_output
            raw_responses.append(raw)
        return ExtractionResult(
            assertions=assertions,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            raw_response="\n".join(raw_responses),
            parse_errors=parse_errors,
        )

    def _chat(
        self, messages: list[dict[str, str]], schema_version: str = "1.0.0"
    ) -> dict[str, Any]:
        """One local chat call with the §11 retry policy (inference calls are
        retried like any other); no governor, no ledger."""
        payload: dict[str, Any] = {
            "model": self._model_id,
            "messages": messages,
            "stream": False,
            "format": response_schema_for_version(schema_version),
            "options": {"temperature": 0},
        }
        url = f"{self._base_url}/api/chat"

        try:
            response = request_with_retry(
                "POST",
                url,
                json_body=payload,
                timeout_s=self._settings.http_timeout_seconds,
                follow_redirects=False,
                log=logger,
            )
        except PermanentStatus as exc:
            raise ExtractionError(f"ollama call failed: HTTP {exc.status_code}") from exc
        except RetryExhausted as exc:
            raise ExtractionError(
                f"ollama call failed after retries: {exc.url} ({exc.reason})"
            ) from exc
        body: dict[str, Any] = response.json()
        return body


def _content_of(response: dict[str, Any]) -> str:
    """The assistant message content of an Ollama chat response."""
    try:
        content = response["message"]["content"]
    except (KeyError, TypeError) as exc:
        raise ExtractionError(f"ollama response has no message content: {exc}") from exc
    if not isinstance(content, str):
        raise ExtractionError("ollama response content is not a string")
    return content


def _load_prompt() -> str:
    """The extraction prompt template. Unlike the OpenRouter extractor, the
    template is fixed at construction: this laptop path has no pinned prompt
    version of its own and deliberately shares the shipped v1.0.0 file."""
    path = Path(__file__).parent / "prompts" / "extraction_v1.0.0.md"
    if not path.exists():
        raise ExtractionError(f"extraction prompt file missing: {path}")
    return path.read_text(encoding="utf-8")
