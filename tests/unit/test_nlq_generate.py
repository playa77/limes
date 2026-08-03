# tests/unit/test_nlq_generate.py | v1.0.0 | introduced by WP-33
"""Generation unit tests: the prompt is loaded by version and carries the
serialized ontology and the temporal helpers but **no example questions**
(NG-08 — the reference questions are a metric, never a prompt fixture);
the question travels as delimited data; regeneration feedback is supplied
verbatim; code fences are stripped."""

from pathlib import Path

import pytest

from limes.errors import ExtractionError
from limes.nlq.generate import generate
from limes.ontology.registry import load_ontology

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY = load_ontology(REPO_ROOT / "ontology" / "ontology.yaml")

PROMPT = (REPO_ROOT / "src" / "limes" / "extraction" / "prompts" / "nl2cypher_v1.0.0.md").read_text(
    encoding="utf-8"
)


class FakeClient:
    """Records the messages it received and returns a canned completion."""

    def __init__(self, reply: str = "MATCH (n:Corporation) RETURN n") -> None:
        self.reply = reply
        self.last_messages: list[dict[str, str]] = []
        self.last_model: str | None = None
        self.last_purpose: str | None = None

    def complete(self, messages, model_id, purpose, json_schema=None):
        self.last_messages = messages
        self.last_model = model_id
        self.last_purpose = purpose
        return self.reply, 100, 20


def test_ng08_prompt_contains_no_example_questions():
    # NG-08: the prompt must not carry example questions; the reference
    # questions are a generation-quality metric and must not surface here.
    # The question itself travels in the user message, delimited.
    assert "{ontology}" in PROMPT
    assert "<QUESTION>" in PROMPT
    # The temporal helpers are documented...
    assert "as_of" in PROMPT and "currently" in PROMPT and "as_believed" in PROMPT
    # ...and no question-shaped example exists anywhere in the file.
    assert "?" not in PROMPT


def test_generate_sends_question_as_delimited_data():
    client = FakeClient()
    generate("Which corporations does Alpha own?", ONTOLOGY, client, "test/model", "1.0.0")
    user_content = client.last_messages[-1]["content"]
    assert "<QUESTION>\nWhich corporations does Alpha own?\n</QUESTION>" == user_content
    assert client.last_model == "test/model"
    assert client.last_purpose == "nl2cypher"
    system = client.last_messages[0]["content"]
    assert "Ontology version 1.0.0" in system
    assert "SUBSIDIARY_OF" in system


def test_generate_passes_feedback_verbatim():
    client = FakeClient()
    generate(
        "Which corporations does Alpha own?",
        ONTOLOGY,
        client,
        "test/model",
        "1.0.0",
        feedback="WRITE_CLAUSE: CREATE at offset 12",
    )
    system = client.last_messages[0]["content"]
    assert "WRITE_CLAUSE: CREATE at offset 12" in system
    assert "<FEEDBACK>" in system


def test_generate_strips_code_fences():
    client = FakeClient(reply="```cypher\nMATCH (n:Corporation) RETURN n\n```")
    cypher = generate("question", ONTOLOGY, client, "test/model", "1.0.0")
    assert cypher == "MATCH (n:Corporation) RETURN n"


def test_generate_fence_without_newline_yields_empty():
    # A bare fence marker with no body: there is no content between the
    # opening and closing markers, so nothing survives the strip.
    client = FakeClient(reply="```")
    cypher = generate("question", ONTOLOGY, client, "test/model", "1.0.0")
    assert cypher == ""


def test_generate_missing_prompt_version_fails_loudly():
    client = FakeClient()
    with pytest.raises(ExtractionError, match="prompt file missing"):
        generate("question", ONTOLOGY, client, "test/model", "99.0.0")


def test_generate_empty_model_fails_loudly():
    client = FakeClient()
    with pytest.raises(ExtractionError, match="no NL-to-Cypher model pinned"):
        generate("question", ONTOLOGY, client, "", "1.0.0")
