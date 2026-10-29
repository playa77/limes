# src/limes/extraction/openrouter.py | v1.0.0 | introduced by WP-22
"""The OpenRouter extractor per Technical Specification §8.7.1–§8.7.4.

`OpenRouterExtractor` is the production `Extractor`: schema-constrained calls
ledgered by the client, batching passages under
`LIMES_EXTRACTION_MAX_PASSAGES_PER_CALL` and `LIMES_EXTRACTION_MAX_INPUT_TOKENS`
(Doc 2 §8.7.4). Every batch response passes the deterministic half —
`parse_extraction_response` (schema → ontology → offset mapping → evidence
span) — and every rejection lands in `ExtractionResult.parse_errors`, so the
pipeline run can count them (AC-13).

The prompt file is loaded by version: `extraction_v{prompt_version}.md`. A
missing file is an `ExtractionError`, not a silent fallback — a prompt bump
that forgets the file must fail loudly, because the cache key includes the
version (WP-23) and a mismatched file would serve stale results under a new
version.
"""

from __future__ import annotations

import structlog

from limes.config import Settings
from limes.errors import ExtractionError
from limes.extraction.base import (
    ExtractionResult,
    batch_passages,
    build_extraction_messages,
    prompt_path,
)
from limes.extraction.openrouter_client import OpenRouterClient
from limes.extraction.schema import (
    SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    parse_extraction_response,
    schema_for_version,
)
from limes.ontology.model import Ontology
from limes.types import ExtractedAssertion, Passage

logger = structlog.get_logger(__name__)


class OpenRouterExtractor:
    """The paid, metered, ledgered extractor (Doc 1 §4.5)."""

    def __init__(self, settings: Settings, client: OpenRouterClient) -> None:
        self._settings = settings
        self._client = client

    @property
    def model_id(self) -> str:
        """The pinned extraction model; empty until `select-models` has run
        (Doc 2 §8.7.2), in which case `extract` refuses loudly."""
        return self._settings.extraction_model

    def extract(
        self,
        passages: list[Passage],
        ontology: Ontology,
        prompt_version: str,
        schema_version: str,
    ) -> ExtractionResult:
        if not self.model_id:
            raise ExtractionError("no extraction model pinned; run select-models first")
        if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise ExtractionError(
                f"unsupported extraction schema version {schema_version!r}; "
                f"this extractor implements {SCHEMA_VERSION!r}"
            )
        prompt = _load_prompt(prompt_version)
        ontology_serialized = ontology.serialize_for_prompt()
        prompt_text = prompt.replace("{ontology}", ontology_serialized)
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
            raw, batch_input, batch_output = self._client.complete(
                messages,
                self.model_id,
                "extraction",
                json_schema=schema_for_version(schema_version),
            )
            batch_assertions, batch_errors = parse_extraction_response(
                raw, passages, ontology, schema_version
            )
            assertions.extend(batch_assertions)
            parse_errors.extend(batch_errors)
            input_tokens += batch_input
            output_tokens += batch_output
            raw_responses.append(raw)
            logger.info(
                "extraction call completed",
                model_id=self.model_id,
                batch_passages=len(batch),
                assertions=batch_assertions.__len__(),
                rejected=len(batch_errors),
                input_tokens=batch_input,
                output_tokens=batch_output,
            )
        return ExtractionResult(
            assertions=assertions,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            raw_response="\n".join(raw_responses),
            parse_errors=parse_errors,
        )


def _load_prompt(prompt_version: str) -> str:
    """The extraction prompt template for a version, or `ExtractionError` when
    the file is absent — version bumps must ship the file (see the module
    docstring)."""
    path = prompt_path(f"extraction_v{prompt_version}.md")
    if not path.exists():
        raise ExtractionError(f"extraction prompt file missing: {path}")
    return path.read_text(encoding="utf-8")
