# tests/unit/test_extractor.py | v1.0.0 | introduced by WP-22
"""Extractor unit tests per Doc 2 §8.7.1–§8.7.4 (WP-22).

Covers `OpenRouterExtractor` with a fake client (no network), the shared
response parsing (schema, ontology, offset mapping, AC-13 evidence spans),
batching under both limits, and the laptop-only `OllamaExtractor` with a
respx-mocked local endpoint. The ontology is loaded from the committed
artifact — the artifact is the validation authority.
"""

import json

import respx
from httpx import Response

from limes.config import Settings
from limes.errors import ExtractionError
from limes.extraction.base import PASSAGES_CLOSE, PASSAGES_OPEN, batch_passages
from limes.extraction.ollama import OllamaExtractor
from limes.extraction.openrouter import OpenRouterExtractor
from limes.ontology.registry import load_ontology
from limes.types import Passage

ONTOLOGY = load_ontology(__import__("pathlib").Path("ontology/ontology.yaml"))

# A two-sentence German document: the first sentence names a PublicBody and a
# LegalAct in an ADOPTED relation; the third sentence is unrelated.
TEXT = (
    "Die Bundesregierung hat am Montag ein neues Gesetz vorgeschlagen. "
    "Der Entwurf wird nun im Bundestag beraten. Das Wetter bleibt wechselhaft."
)
PASSAGES = [Passage(index=0, text=TEXT, doc_start=100, doc_end=100 + len(TEXT))]

ADOPTED_ITEM = {
    "passage_index": 0,
    "subject": {"surface": "Bundesregierung", "type": "PublicBody"},
    "relation": "ADOPTED",
    "object": {"surface": "Gesetz", "type": "LegalAct"},
    "confidence": 0.9,
    "evidence_start": 0,
    "evidence_end": 58,
    "valid_from": None,
    "valid_to": None,
}


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
        openrouter_api_key="sk-test",
        extraction_model="test/extraction-model",
        extraction_max_passages_per_call=2,
        extraction_max_input_tokens=6000,
    )
    base.update(overrides)
    return Settings(**base)


class FakeClient:
    """A complete() stand-in that records calls and returns canned responses."""

    def __init__(self, responses: list[tuple[str, int, int]]) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    def complete(self, messages, model_id, purpose, json_schema=None):
        self.calls.append({"messages": messages, "model_id": model_id,
                           "purpose": purpose, "json_schema": json_schema})
        if not self.responses:
            raise AssertionError("FakeClient.complete called more often than responses supplied")
        return self.responses.pop(0)


def test_extract_batches_and_parses_assertions():
    client = FakeClient([(json.dumps([ADOPTED_ITEM]), 100, 50)])
    extractor = OpenRouterExtractor(_settings(), client)
    result = extractor.extract(PASSAGES, ONTOLOGY, "1.0.0", "1.0.0")

    assert len(result.assertions) == 1
    assertion = result.assertions[0]
    assert assertion.subject.surface == "Bundesregierung"
    assert assertion.subject.type == "PublicBody"
    assert assertion.relation == "ADOPTED"
    assert assertion.object.type == "LegalAct"
    # Offsets are mapped to document offsets through doc_start (AC-13).
    assert assertion.evidence_start == 100
    assert assertion.evidence_end == 158
    assert result.input_tokens == 100
    assert result.output_tokens == 50
    assert result.parse_errors == []


def test_prompt_contains_ontology_and_delimited_passages():
    client = FakeClient([(json.dumps([]), 1, 1)])
    extractor = OpenRouterExtractor(_settings(), client)
    extractor.extract(PASSAGES, ONTOLOGY, "1.0.0", "1.0.0")

    messages = client.calls[0]["messages"]
    assert len(messages) == 1
    content = messages[0]["content"]
    assert ONTOLOGY.version in content
    assert PASSAGES_OPEN in content
    assert PASSAGES_CLOSE in content
    assert "[0]" in content
    assert "Bundesregierung" in content


def test_batching_splits_on_passage_count():
    passages = [Passage(index=i, text="s" * 200, doc_start=0, doc_end=200) for i in range(5)]
    batches = batch_passages(
        passages, max_passages_per_call=2, max_input_tokens=6000, prompt_overhead_tokens=100
    )
    assert [len(b) for b in batches] == [2, 2, 1]
    assert [b[0].index for b in batches] == [0, 2, 4]


def test_batching_splits_on_input_tokens():
    passages = [Passage(index=i, text="x" * 3000, doc_start=0, doc_end=3000) for i in range(3)]
    # 3000 chars ≈ 750 tokens each; two fit under 1600 with 100 overhead, the
    # third needs its own batch.
    batches = batch_passages(
        passages, max_passages_per_call=8, max_input_tokens=1600, prompt_overhead_tokens=100
    )
    assert [len(b) for b in batches] == [2, 1]


def test_single_passage_larger_than_budget_stays_its_own_batch():
    passages = [Passage(index=0, text="x" * 10000, doc_start=0, doc_end=10000)]
    batches = batch_passages(
        passages, max_passages_per_call=8, max_input_tokens=100, prompt_overhead_tokens=50
    )
    assert [len(b) for b in batches] == [1]


def test_schema_rejection_is_counted():
    bad_item = dict(ADOPTED_ITEM)
    del bad_item["confidence"]
    client = FakeClient([(json.dumps([bad_item]), 1, 1)])
    result = OpenRouterExtractor(_settings(), client).extract(PASSAGES, ONTOLOGY, "1.0.0", "1.0.0")
    assert result.assertions == []
    assert any(error.startswith("SCHEMA:") for error in result.parse_errors)


def test_unknown_relation_is_rejected_with_reason():
    bad_item = dict(ADOPTED_ITEM)
    bad_item["relation"] = "FLIES_TO"
    client = FakeClient([(json.dumps([bad_item]), 1, 1)])
    result = OpenRouterExtractor(_settings(), client).extract(PASSAGES, ONTOLOGY, "1.0.0", "1.0.0")
    assert result.assertions == []
    assert any("UNKNOWN_RELATION: item 0: 'FLIES_TO'" in error for error in result.parse_errors)


def test_domain_violation_is_rejected_with_reason():
    bad_item = dict(ADOPTED_ITEM)
    bad_item["object"] = {
        "surface": "Gesetz",
        "type": "Corporation",
    }  # ADOPTED range is LegalAct|Document
    client = FakeClient([(json.dumps([bad_item]), 1, 1)])
    result = OpenRouterExtractor(_settings(), client).extract(PASSAGES, ONTOLOGY, "1.0.0", "1.0.0")
    assert result.assertions == []
    assert any("ONTOLOGY_REJECTED: item 0:" in error for error in result.parse_errors)


def test_unknown_mention_type_is_rejected():
    bad_item = dict(ADOPTED_ITEM)
    bad_item["subject"] = {"surface": "Bundesregierung", "type": "Kingdom"}
    client = FakeClient([(json.dumps([bad_item]), 1, 1)])
    result = OpenRouterExtractor(_settings(), client).extract(PASSAGES, ONTOLOGY, "1.0.0", "1.0.0")
    assert result.assertions == []
    assert any(
        "UNKNOWN_TYPE: item 0: subject type 'Kingdom'" in error for error in result.parse_errors
    )


def test_evidence_span_not_containing_surfaces_is_rejected():
    # The span covers only the third (weather) sentence — neither surface.
    bad_item = dict(ADOPTED_ITEM)
    bad_item["evidence_start"] = 76
    bad_item["evidence_end"] = 102
    client = FakeClient([(json.dumps([bad_item]), 1, 1)])
    result = OpenRouterExtractor(_settings(), client).extract(PASSAGES, ONTOLOGY, "1.0.0", "1.0.0")
    assert result.assertions == []
    assert any("EVIDENCE_SPAN_MISMATCH" in error for error in result.parse_errors)


def test_evidence_span_containing_subject_surface_is_accepted():
    # The span covers the first sentence only (the subject lives there).
    good_item = dict(ADOPTED_ITEM)
    good_item["evidence_start"] = 0
    good_item["evidence_end"] = 52
    client = FakeClient([(json.dumps([good_item]), 1, 1)])
    result = OpenRouterExtractor(_settings(), client).extract(PASSAGES, ONTOLOGY, "1.0.0", "1.0.0")
    assert len(result.assertions) == 1


def test_out_of_bounds_evidence_span_is_rejected():
    bad_item = dict(ADOPTED_ITEM)
    bad_item["evidence_start"] = 0
    bad_item["evidence_end"] = 100000
    client = FakeClient([(json.dumps([bad_item]), 1, 1)])
    result = OpenRouterExtractor(_settings(), client).extract(PASSAGES, ONTOLOGY, "1.0.0", "1.0.0")
    assert result.assertions == []
    assert any("EVIDENCE_SPAN_MISMATCH" in error for error in result.parse_errors)


def test_unknown_passage_index_is_rejected():
    bad_item = dict(ADOPTED_ITEM)
    bad_item["passage_index"] = 7
    client = FakeClient([(json.dumps([bad_item]), 1, 1)])
    result = OpenRouterExtractor(_settings(), client).extract(PASSAGES, ONTOLOGY, "1.0.0", "1.0.0")
    assert result.assertions == []
    assert any("UNKNOWN_PASSAGE: item 0: passage_index 7" in error for error in result.parse_errors)


def test_unparseable_date_is_rejected():
    bad_item = dict(ADOPTED_ITEM)
    bad_item["valid_from"] = "not-a-date"
    client = FakeClient([(json.dumps([bad_item]), 1, 1)])
    result = OpenRouterExtractor(_settings(), client).extract(PASSAGES, ONTOLOGY, "1.0.0", "1.0.0")
    assert result.assertions == []
    assert any("UNPARSEABLE_DATE" in error for error in result.parse_errors)


def test_valid_dates_are_parsed_into_assertions():
    dated_item = dict(ADOPTED_ITEM)
    dated_item["valid_from"] = "2026-07-27"
    client = FakeClient([(json.dumps([dated_item]), 1, 1)])
    result = OpenRouterExtractor(_settings(), client).extract(PASSAGES, ONTOLOGY, "1.0.0", "1.0.0")
    assertion = result.assertions[0]
    assert assertion.valid_from is not None
    assert assertion.valid_from.year == 2026


def test_markdown_fenced_response_is_tolerated():
    client = FakeClient([("```json\n" + json.dumps([ADOPTED_ITEM]) + "\n```", 1, 1)])
    result = OpenRouterExtractor(_settings(), client).extract(PASSAGES, ONTOLOGY, "1.0.0", "1.0.0")
    assert len(result.assertions) == 1


def test_non_array_response_is_rejected():
    client = FakeClient([('{"assertions": []}', 1, 1)])
    result = OpenRouterExtractor(_settings(), client).extract(PASSAGES, ONTOLOGY, "1.0.0", "1.0.0")
    assert result.assertions == []
    assert any("RESPONSE_NOT_ARRAY" in error for error in result.parse_errors)


def test_extract_refuses_without_pinned_model():
    client = FakeClient([])
    extractor = OpenRouterExtractor(_settings(extraction_model=""), client)
    try:
        extractor.extract(PASSAGES, ONTOLOGY, "1.0.0", "1.0.0")
    except ExtractionError as exc:
        assert "no extraction model pinned" in str(exc)
    else:
        raise AssertionError("expected ExtractionError without a pinned model")


def test_extract_refuses_unsupported_schema_version():
    client = FakeClient([])
    extractor = OpenRouterExtractor(_settings(), client)
    try:
        extractor.extract(PASSAGES, ONTOLOGY, "1.0.0", "9.9.9")
    except ExtractionError as exc:
        assert "unsupported extraction schema version" in str(exc)
    else:
        raise AssertionError("expected ExtractionError for an unsupported schema version")


def test_extract_refuses_missing_prompt_file():
    client = FakeClient([])
    extractor = OpenRouterExtractor(_settings(), client)
    try:
        extractor.extract(PASSAGES, ONTOLOGY, "9.9.9", "1.0.0")
    except ExtractionError as exc:
        assert "extraction prompt file missing" in str(exc)
    else:
        raise AssertionError("expected ExtractionError for a missing prompt file")


def test_ollama_extractor_parses_local_response():
    response = {
        "message": {"content": json.dumps([ADOPTED_ITEM])},
        "prompt_eval_count": 120,
        "eval_count": 40,
    }
    with respx.mock:
        route = respx.post("http://localhost:11434/api/chat").mock(
            return_value=Response(200, json=response)
        )
        extractor = OllamaExtractor(_settings())
        result = extractor.extract(PASSAGES, ONTOLOGY, "1.0.0", "1.0.0")

    assert route.call_count == 1
    wire_schema = json.loads(route.calls[0].request.content)["format"]
    from jsonschema import Draft202012Validator

    assert Draft202012Validator(wire_schema).is_valid([ADOPTED_ITEM])
    assert not Draft202012Validator(wire_schema).is_valid(ADOPTED_ITEM)
    assert len(result.assertions) == 1
    assert result.assertions[0].relation == "ADOPTED"
    assert result.input_tokens == 120
    assert result.output_tokens == 40


def test_ollama_extractor_retries_on_5xx():
    response = {"message": {"content": "[]"}, "prompt_eval_count": 1, "eval_count": 1}
    with respx.mock:
        route = respx.post("http://localhost:11434/api/chat").mock(
            side_effect=[
                Response(503, json={}),
                Response(200, json=response),
            ]
        )
        extractor = OllamaExtractor(_settings())
        result = extractor.extract(PASSAGES, ONTOLOGY, "1.0.0", "1.0.0")

    assert route.call_count == 2
    assert result.assertions == []


def test_wire_schema_matches_array_parser_for_both_versions():
    from jsonschema import Draft202012Validator

    for version in ("1.0.0", "2.0.0"):
        client = FakeClient([("[]", 1, 1)])
        result = OpenRouterExtractor(_settings(), client).extract(
            PASSAGES, ONTOLOGY, "1.0.0", version
        )
        validator = Draft202012Validator(client.calls[0]["json_schema"])
        assert validator.is_valid([])
        item = dict(ADOPTED_ITEM)
        if version == "2.0.0":
            item["qualifiers"] = None
        assert validator.is_valid([item])
        assert not validator.is_valid(item)
        assert not validator.is_valid([{}])
        assert result.parse_errors == []
