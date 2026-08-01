# tests/unit/test_resolution_adjudicate.py | v1.0.0 | introduced by WP-25
"""Adjudication tests per Doc 2 §8.8.3: one call, pairwise against the top
candidate, confidence capped at 0.90; a false verdict, a malformed response,
or a schema violation is `(None, 0.0)` — the caller mints (WP-25).
"""

import pytest

from limes.errors import ExtractionError
from limes.resolution.adjudicate import MAX_ADJUDICATION_CONFIDENCE, adjudicate
from limes.types import Mention

CANDIDATES = [
    {"entity_id": "lei:AAA", "label": "Volkswagen AG", "score": 0.90},
    {"entity_id": "lei:BBB", "label": "VW AG", "score": 0.88},
]
MENTION = Mention(surface="Volkswagen", type="Corporation")
PROMPT_VERSION = "1.0.0"
MODEL = "test/adjudicator"


class StubClient:
    """A client whose `complete` returns a canned adjudication response;
    the built message is captured for shape assertions."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.messages: list[dict] = []

    def complete(self, messages, model_id, purpose, json_schema=None):
        self.messages = messages
        return self.response, 10, 5


def test_same_verdict_links_top_candidate():
    client = StubClient('{"same": true, "confidence": 0.85}')
    entity_id, confidence = adjudicate(MENTION, CANDIDATES, client, PROMPT_VERSION, MODEL)
    assert entity_id == "lei:AAA"
    assert confidence == 0.85
    assert client.messages[0]["role"] == "system"
    assert "Volkswagen" in client.messages[0]["content"]
    assert "Volkswagen AG" in client.messages[0]["content"]
    assert "lei:BBB" not in client.messages[0]["content"]  # candidate list as context, not B


def test_confidence_capped_at_090():
    client = StubClient('{"same": true, "confidence": 0.95}')
    entity_id, confidence = adjudicate(MENTION, CANDIDATES, client, PROMPT_VERSION, MODEL)
    assert entity_id == "lei:AAA"
    assert confidence == MAX_ADJUDICATION_CONFIDENCE


def test_false_verdict_is_no_match():
    client = StubClient('{"same": false, "confidence": 0.8}')
    assert adjudicate(MENTION, CANDIDATES, client, PROMPT_VERSION, MODEL) == (None, 0.0)


def test_fenced_json_is_tolerated():
    client = StubClient('```json\n{"same": true, "confidence": 0.7}\n```')
    entity_id, confidence = adjudicate(MENTION, CANDIDATES, client, PROMPT_VERSION, MODEL)
    assert entity_id == "lei:AAA"
    assert confidence == 0.7


def test_malformed_response_is_no_match():
    client = StubClient("not json at all")
    assert adjudicate(MENTION, CANDIDATES, client, PROMPT_VERSION, MODEL) == (None, 0.0)


def test_schema_violation_is_no_match():
    client = StubClient('{"same": true}')
    assert adjudicate(MENTION, CANDIDATES, client, PROMPT_VERSION, MODEL) == (None, 0.0)
    client = StubClient('{"same": "yes", "confidence": 0.5}')
    assert adjudicate(MENTION, CANDIDATES, client, PROMPT_VERSION, MODEL) == (None, 0.0)


def test_empty_candidates_is_no_match():
    client = StubClient('{"same": true, "confidence": 0.9}')
    assert adjudicate(MENTION, [], client, PROMPT_VERSION, MODEL) == (None, 0.0)


def test_empty_model_refuses_loudly():
    client = StubClient('{"same": true, "confidence": 0.9}')
    with pytest.raises(ExtractionError, match="adjudication model"):
        adjudicate(MENTION, CANDIDATES, client, PROMPT_VERSION, "")


def test_missing_prompt_file_fails_loudly():
    client = StubClient('{"same": true, "confidence": 0.9}')
    with pytest.raises(ExtractionError, match="prompt file missing"):
        adjudicate(MENTION, CANDIDATES, client, "9.9.9", MODEL)
