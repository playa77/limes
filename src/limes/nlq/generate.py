# src/limes/nlq/generate.py | v1.0.0 | introduced by WP-33
"""Cypher generation per Technical Specification §8.10: one OpenRouter
chat completion carrying the serialized ontology (§8.2's
`serialize_for_prompt`), the question as delimited data (Doc 2 §7.5 — the
question is operator input and never concatenated into the instruction
portion), and the temporal helpers. Paid inference, metered by the client
against the monthly ceiling like every other call (purpose `nl2cypher`).

The prompt contains no example questions (NG-08): the reference questions
in `reference_questions/questions.yaml` are a generation-quality metric and
must not surface in the prompt. `feedback` is the regeneration channel —
the first validation's failure reasons, supplied verbatim (Doc 2 §8.10),
delimited like the question so a model-injected instruction inside them
cannot reach the instruction portion either.
"""

from __future__ import annotations

from pathlib import Path

from limes.errors import ExtractionError
from limes.extraction.openrouter_client import OpenRouterClient
from limes.ontology.model import Ontology

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "extraction" / "prompts"


def generate(
    question: str,
    ontology: Ontology,
    client: OpenRouterClient,
    model_id: str,
    prompt_version: str,
    feedback: str | None = None,
) -> str:
    """Generate candidate Cypher for `question`. Returns the completion
    content with any code-fence markup stripped; the validator's job is to
    judge what remains."""
    if not model_id:
        raise ExtractionError("no NL-to-Cypher model pinned (LIMES_NL2CYPHER_MODEL)")
    path = PROMPTS_DIR / f"nl2cypher_v{prompt_version}.md"
    if not path.exists():
        raise ExtractionError(f"nl2cypher prompt file missing: {path}")
    prompt = path.read_text(encoding="utf-8")
    prompt_text = prompt.replace("{ontology}", ontology.serialize_for_prompt())
    if feedback:
        prompt_text = prompt_text.replace(
            "{feedback}",
            "The previous attempt was rejected by deterministic validation. "
            "Failure reasons (verbatim):\n<FEEDBACK>\n"
            f"{feedback}\n"
            "</FEEDBACK>",
        )
    else:
        prompt_text = prompt_text.replace("{feedback}", "")
    messages = [
        {"role": "system", "content": prompt_text},
        {
            "role": "user",
            "content": "<QUESTION>\n" + question + "\n</QUESTION>",
        },
    ]
    content, _, _ = client.complete(messages, model_id, "nl2cypher")
    return _strip_fences(content)


def _strip_fences(content: str) -> str:
    """Remove a code fence a model may wrap its answer in: a leading
    ```lang line and a trailing ``` line. The validator then judges the
    bare statement."""
    stripped = content.strip()
    if not stripped.startswith("```"):
        return stripped
    first_newline = stripped.find("\n")
    if first_newline == -1:
        return ""
    body = stripped[first_newline + 1 :]
    if body.rstrip().endswith("```"):
        body = body.rstrip()[: -len("```")]
    return body.strip()
