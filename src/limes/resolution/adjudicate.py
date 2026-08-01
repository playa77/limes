# src/limes/resolution/adjudicate.py | v1.0.0 | introduced by WP-25
"""The adjudication call per Technical Specification §8.8.3.

When vector blocking lands in the ambiguous band — `0.82 ≤ cosine < 0.93`,
or `≥ 0.93` with margin below the threshold — one adjudication call decides
whether the mention is the same entity as its top candidate. The call is
paid and ledgered as `purpose="adjudication"` through the OpenRouter client.

The adjudication prompt (v1.0.0) is pairwise: Mention A (the mention) versus
Mention B (the top candidate). The remaining candidates ride along in the
prompt's context slot as evidence — the roadmap says the call carries "the
mention and top candidates" — and the model returns `{"same", "confidence"}`.
A `same: true` verdict links to the top candidate with the adjudicator's
confidence capped at 0.90 (§8.8.3); anything else — `false`, a malformed
response, a schema violation — is `(None, 0.0)` and the caller mints. The
failure cases are logged with a reason, never silent.

`model_id` is passed explicitly because the adjudication model lives in
Settings, not in the roadmap's four-parameter signature; the resolver holds
the same settings object and supplies it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import structlog
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from limes.errors import ExtractionError
from limes.extraction.openrouter_client import OpenRouterClient
from limes.types import Mention

logger = structlog.get_logger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "extraction" / "prompts"

# The §8.8.3 cap on adjudicator confidence.
MAX_ADJUDICATION_CONFIDENCE = 0.90

ADJUDICATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["same", "confidence"],
    "properties": {
        "same": {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}

# A JSON response wrapped in markdown fences is tolerated; anything else
# inside the fences is rejected by the schema pass.
_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.S)


def adjudicate(
    mention: Mention,
    candidates: list[dict[str, str | float]],
    client: OpenRouterClient,
    prompt_version: str,
    model_id: str,
) -> tuple[str | None, float]:
    """Adjudicate `mention` against its top candidate.

    Returns `(top_candidate_entity_id, confidence)` with confidence capped
    at `MAX_ADJUDICATION_CONFIDENCE`, or `(None, 0.0)` when the adjudicator
    says the mention is a different entity or the response is unusable.
    """
    if not candidates:
        return None, 0.0
    if not model_id:
        raise ExtractionError("no adjudication model pinned; run select-models first")
    top = candidates[0]
    prompt = _load_prompt(prompt_version)
    context = "; ".join(
        f"{candidate['label']} (score {candidate['score']:.3f})" for candidate in candidates
    )
    content = prompt.format(
        a_surface=mention.surface,
        a_type=mention.type,
        b_surface=str(top["label"]),
        b_type=mention.type,
        context=context,
    )
    raw, _, _ = client.complete(
        [{"role": "system", "content": content}],
        model_id,
        "adjudication",
        json_schema=ADJUDICATION_SCHEMA,
    )
    verdict = _parse_verdict(raw, mention, candidates)
    if verdict is None:
        logger.warning(
            "adjudication response unusable; treated as no-match",
            surface=mention.surface,
            top_candidate=str(top.get("entity_id")),
        )
        return None, 0.0
    same, confidence = verdict
    if not same:
        return None, 0.0
    return str(top["entity_id"]), min(confidence, MAX_ADJUDICATION_CONFIDENCE)


def _parse_verdict(
    raw: str,
    mention: Mention,
    candidates: list[dict[str, str | float]],
) -> tuple[bool, float] | None:
    """`(same, confidence)` from the adjudicator's JSON, or None when the
    response does not satisfy the schema — a malformed response is a
    no-match, never a guess."""
    text = raw.strip()
    fence = _FENCE.match(text)
    if fence is not None:
        text = fence.group(1).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    if next(iter(Draft202012Validator(ADJUDICATION_SCHEMA).iter_errors(parsed)), None) is not None:
        return None
    return bool(parsed["same"]), float(parsed["confidence"])


def _load_prompt(prompt_version: str) -> str:
    """The adjudication prompt template for a version, or `ExtractionError`
    when the file is absent — a version bump must ship the file, and a
    missing file must fail loudly rather than adjudicate on a stale
    template."""
    path = PROMPTS_DIR / f"adjudication_v{prompt_version}.md"
    if not path.exists():
        raise ExtractionError(f"adjudication prompt file missing: {path}")
    return path.read_text(encoding="utf-8")
