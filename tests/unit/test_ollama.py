# tests/unit/test_ollama.py | v1.0.0 | introduced by WP-22
"""Ollama extractor error-path tests per Doc 2 §8.7.1-§8.7.4.

The happy path (batching, parsing, token metering) is covered by
test_extractor.py with a respx-mocked local endpoint; these tests pin the
failure surface: the schema-version refusal, the §11 retry policy on the
local chat call, the malformed-response guards, and the missing-prompt-file
constructor failure.
"""

from pathlib import Path

import pytest
import respx
from httpx import ConnectError, Response

from limes.config import Settings
from limes.errors import ExtractionError
from limes.extraction import ollama
from limes.extraction.ollama import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    OllamaExtractor,
    _is_retryable,
)
from limes.ontology.registry import load_ontology
from limes.types import Passage

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY = load_ontology(REPO_ROOT / "ontology" / "ontology.yaml")
PASSAGES = [Passage(index=0, text="Alpha owns Beta.", doc_start=0, doc_end=16)]
CHAT_URL = f"{DEFAULT_OLLAMA_BASE_URL}/api/chat"


def _settings(**overrides) -> Settings:
    base = dict(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="u",
        neo4j_password="p",
        ontology_path=REPO_ROOT / "ontology" / "ontology.yaml",
        feeds_config_path=REPO_ROOT / "ontology" / "feeds.yaml",
        gold_set_path=REPO_ROOT / "gold_set" / "gold_set.jsonl",
        baseline_path=REPO_ROOT / "gold_set" / "baseline.json",
        archive_path=REPO_ROOT / "data" / "archive",
        http_timeout_seconds=10,
    )
    base.update(overrides)
    return Settings(**base)


def test_model_id_property_returns_the_constructed_name():
    assert OllamaExtractor(_settings()).model_id == DEFAULT_OLLAMA_MODEL
    assert OllamaExtractor(_settings(), model_id="local/model").model_id == "local/model"


def test_unsupported_schema_version_is_refused_before_any_call():
    with respx.mock:
        route = respx.post(CHAT_URL).mock(return_value=Response(200, json={}))
        extractor = OllamaExtractor(_settings())
        with pytest.raises(ExtractionError, match="unsupported extraction schema version"):
            extractor.extract(PASSAGES, ONTOLOGY, "1.0.0", "9.9.9")
    assert route.call_count == 0


def test_is_retryable_accepts_connect_errors_only():
    assert _is_retryable(ConnectError("refused")) is True
    assert _is_retryable(ValueError("no")) is False


def test_connection_error_retries_then_fails_loudly():
    with respx.mock:
        route = respx.post(CHAT_URL).mock(side_effect=ConnectError("connection refused"))
        extractor = OllamaExtractor(_settings())
        with pytest.raises(ExtractionError, match="ollama call failed after retries"):
            extractor.extract(PASSAGES, ONTOLOGY, "1.0.0", "1.0.0")
    assert route.call_count == ollama.HTTP_MAX_ATTEMPTS


def test_non_retryable_4xx_fails_immediately():
    with respx.mock:
        route = respx.post(CHAT_URL).mock(return_value=Response(400, json={"error": "bad"}))
        extractor = OllamaExtractor(_settings())
        with pytest.raises(ExtractionError, match="ollama call failed: HTTP 400"):
            extractor.extract(PASSAGES, ONTOLOGY, "1.0.0", "1.0.0")
    assert route.call_count == 1


def test_response_without_message_content_is_rejected():
    with respx.mock:
        respx.post(CHAT_URL).mock(return_value=Response(200, json={"message": {}}))
        extractor = OllamaExtractor(_settings())
        with pytest.raises(ExtractionError, match="no message content"):
            extractor.extract(PASSAGES, ONTOLOGY, "1.0.0", "1.0.0")


def test_non_string_content_is_rejected():
    with respx.mock:
        respx.post(CHAT_URL).mock(return_value=Response(200, json={"message": {"content": 123}}))
        extractor = OllamaExtractor(_settings())
        with pytest.raises(ExtractionError, match="content is not a string"):
            extractor.extract(PASSAGES, ONTOLOGY, "1.0.0", "1.0.0")


def test_missing_prompt_file_fails_at_construction(monkeypatch):
    monkeypatch.setattr("limes.extraction.ollama.Path.exists", lambda self: False)
    with pytest.raises(ExtractionError, match="extraction prompt file missing"):
        OllamaExtractor(_settings())
