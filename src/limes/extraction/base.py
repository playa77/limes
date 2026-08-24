# src/limes/extraction/base.py | v1.0.0 | introduced by WP-22
"""Extractor protocol and shared extraction plumbing per Technical
Specification §8.7.1 and §8.7.4.

`Extractor` is the seam the pipeline run (WP-27) and the evaluation harness
(WP-30) consume; `ExtractionResult` is the pre-resolution output carrying
mentions, never identified endpoints (Doc 1 §5.5). The two implementations —
`OpenRouterExtractor` (paid, metered, ledgered) and `OllamaExtractor`
(laptop-only, C-05) — share the batching and message-building helpers below.

Batching (Doc 2 §8.7.4): one call per document carrying up to
`LIMES_EXTRACTION_MAX_PASSAGES_PER_CALL` passages, capped at
`LIMES_EXTRACTION_MAX_INPUT_TOKENS`; a document exceeding either bound splits
into multiple calls. The cache key has no batch index, so the per-document
result is the merge of every batch's assertions — one cache entry per
document, never per call.

Message shape (Doc 1 §7.5): one system message whose instruction portion
holds the prompt template with the ontology serialized in, and whose passage
block is explicitly delimited — the untrusted text is data inside a named
block, never concatenated into the instruction.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from limes.ontology.model import Ontology
from limes.types import ExtractedAssertion, Passage

# The delimiters around the untrusted passage block; both the prompt template
# and the message builder reference them, so an instruction-injection attempt
# inside a passage cannot smuggle its way past the model's delimiter prompt
# without also being visible here.
PASSAGES_OPEN = "<PASSAGES>"
PASSAGES_CLOSE = "</PASSAGES>"

# Rough character-per-token estimate for batching and governor pre-checks;
# good enough to keep a call under the token cap without counting tokens.
CHARS_PER_TOKEN = 4

# A conservative default for the *estimated* output tokens used by the
# governor's pre-call check; Doc 1 §9.3 measured ~350 output tokens for a
# passage-level extraction call. The ledger entry always uses the provider's
# reported usage, never this estimate.
ESTIMATED_OUTPUT_TOKENS = 350


def prompt_path(filename: str) -> Path:
    """Absolute path of a prompt file in `extraction/prompts/`.

    One resolver for every consumer of the prompt directory — the extractor,
    the adjudicator, and NL-to-Cypher all read templates from here, so a
    relocated prompt directory is a one-module change. Callers keep their own
    missing-file errors (the message names the prompt's role).
    """
    return Path(__file__).parent / "prompts" / filename


def strip_model_fence(raw: str, *, tag: str = "json") -> str:
    """Strip a whole-text markdown fence a model may wrap its answer in.

    The strict policy shared by the extraction-schema pass, the adjudication
    parser, and the NL2Cypher evaluation harness: the *entire* stripped
    response must be one fenced block (an optional language tag is tolerated)
    and only its body is judged; anything outside a fence stays verbatim.
    The lenient line-based variant used by `nlq.generate` is deliberately
    different and lives there.
    """
    match = re.match(r"^```(?:" + tag + r")?\s*(.*?)\s*```$", raw.strip(), re.S)
    return match.group(1) if match else raw.strip()


@runtime_checkable
class Extractor(Protocol):
    """A schema-constrained extractor of typed pre-resolution assertions.

    `runtime_checkable` so the composition root can `isinstance`-check an
    extractor; the check is structural (the `model_id` attribute and
    `extract` method), which is exactly the honesty the seam needs.
    """

    model_id: str

    def extract(
        self,
        passages: list[Passage],
        ontology: Ontology,
        prompt_version: str,
        schema_version: str,
    ) -> ExtractionResult: ...


class ExtractionResult(BaseModel):
    """The extractor's output: pre-resolution assertions plus metering and
    parse diagnostics. `parse_errors` is the count of rejected items — the
    evidence-span and ontology rejections are visible here, never silent
    (Doc 2 §11 governing principle)."""

    assertions: list[ExtractedAssertion]
    input_tokens: int
    output_tokens: int
    raw_response: str
    parse_errors: list[str]


def batch_passages(
    passages: list[Passage],
    max_passages_per_call: int,
    max_input_tokens: int,
    prompt_overhead_tokens: int,
) -> list[list[Passage]]:
    """Split passages into call batches under both bounds.

    Greedy: accumulate while the count is below `max_passages_per_call` and
    the estimated tokens (passages plus the per-call prompt and ontology
    overhead) are below `max_input_tokens`. A single passage larger than the
    budget is still its own batch — the cap is a soft target, never a reason
    to drop a passage (that would be a silent loss).
    """
    batches: list[list[Passage]] = []
    current: list[Passage] = []
    current_tokens = prompt_overhead_tokens
    for passage in passages:
        passage_tokens = len(passage.text) // CHARS_PER_TOKEN
        if current and (
            len(current) >= max_passages_per_call
            or current_tokens + passage_tokens > max_input_tokens
        ):
            batches.append(current)
            current = []
            current_tokens = prompt_overhead_tokens
        current.append(passage)
        current_tokens += passage_tokens
    if current:
        batches.append(current)
    return batches


def build_extraction_messages(
    passages: list[Passage],
    prompt_template: str,
    ontology_serialized: str,
) -> list[dict[str, str]]:
    """The single system message for one batch: the instruction portion with
    the ontology serialized in, and the passages inside the explicit data
    delimiters (Doc 1 §7.5). Passage indices in the block are the passages'
    original `index` values, so a returned `passage_index` resolves against
    the document's full passage list, not the batch's.
    """
    block = "\n\n".join(f"[{passage.index}]\n{passage.text}" for passage in passages)
    content = prompt_template.replace("{ontology}", ontology_serialized).replace(
        "{passages}", f"{PASSAGES_OPEN}\n{block}\n{PASSAGES_CLOSE}"
    )
    return [{"role": "system", "content": content}]
