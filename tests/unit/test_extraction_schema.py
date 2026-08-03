# tests/unit/test_extraction_schema.py | v1.0.0 | introduced by WP-22
"""Extraction response parsing unit tests per Doc 2 §8.7.3, AC-13.

The parse pipeline (schema → ontology → offset mapping → evidence-span
check) is exercised from the raw response text; the shared happy path is
covered by test_extractor.py. These tests pin the rejection surface:
non-object items, out-of-ontology mention types, unparseable dates, and the
JSON-preamble guard.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from limes.extraction.schema import parse_extraction_response
from limes.ontology.registry import load_ontology
from limes.types import Passage

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY = load_ontology(REPO_ROOT / "ontology" / "ontology.yaml")

PASSAGES = [Passage(index=0, text="Alpha owns Beta.", doc_start=0, doc_end=16)]


def _item(**overrides) -> dict:
    base = {
        "passage_index": 0,
        "subject": {"surface": "Alpha", "type": "Corporation"},
        "relation": "SUBSIDIARY_OF",
        "object": {"surface": "Beta", "type": "Corporation"},
        "confidence": 0.9,
        "evidence_start": 0,
        "evidence_end": 16,
        "valid_from": None,
        "valid_to": None,
    }
    base.update(overrides)
    return base


def test_non_object_item_is_rejected_with_reason():
    assertions, errors = parse_extraction_response(json.dumps([42]), PASSAGES, ONTOLOGY)
    assert assertions == []
    assert errors == ["SCHEMA: item 0 is not an object"]


def test_unknown_object_type_is_rejected_with_reason():
    item = _item(object={"surface": "Beta", "type": "Bogus"})
    assertions, errors = parse_extraction_response(json.dumps([item]), PASSAGES, ONTOLOGY)
    assert assertions == []
    assert errors == ["UNKNOWN_TYPE: item 0: object type 'Bogus'"]


def test_empty_valid_from_is_rejected_as_unparseable():
    # An empty string passes the schema (it is a string) but cannot be a
    # date; the parser converts that into a counted rejection.
    item = _item(valid_from="")
    assertions, errors = parse_extraction_response(json.dumps([item]), PASSAGES, ONTOLOGY)
    assert assertions == []
    assert any(error.startswith("UNPARSEABLE_DATE") for error in errors)


def test_parsed_item_carries_mapped_offsets_and_dates():
    item = _item(
        valid_from="2024-01-15T00:00:00Z",
        valid_to="2024-06-01T00:00:00Z",
        subject={"surface": "Alpha", "type": "Corporation", "deterministic_key": ["lei", "X"]},
    )
    assertions, errors = parse_extraction_response(json.dumps([item]), PASSAGES, ONTOLOGY)
    assert errors == []
    assertion = assertions[0]
    assert assertion.evidence_start == 0
    assert assertion.evidence_end == 16
    assert assertion.valid_from == datetime(2024, 1, 15, tzinfo=UTC)
    assert assertion.valid_to == datetime(2024, 6, 1, tzinfo=UTC)
    assert assertion.subject.deterministic_key == ("lei", "X")


def test_fenced_empty_body_is_not_json():
    assertions, errors = parse_extraction_response("```json\n   \n```", PASSAGES, ONTOLOGY)
    assert assertions == []
    assert errors == ["RESPONSE_NOT_ARRAY: response is not a JSON array"]


def test_malformed_json_is_not_json():
    assertions, errors = parse_extraction_response("{not json", PASSAGES, ONTOLOGY)
    assert assertions == []
    assert errors == ["RESPONSE_NOT_ARRAY: response is not a JSON array"]
