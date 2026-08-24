# src/limes/extraction/schema.py | v1.0.0 | introduced by WP-22
"""Versioned extraction output schema and response parsing per Technical
Specification §8.7.3, §8.7.4, AC-13.

The JSON Schema is the extraction contract: `additionalProperties: false`
throughout, the seven required assertion fields, mentions requiring `surface`
and `type`. `relation` and mention `type` are validated against the ontology
*after* parsing — an out-of-ontology value yields a precise rejection naming
the value, not a generic schema error (Doc 2 §8.7.3).

`parse_extraction_response` is the deterministic half of every extractor:
JSON → schema → ontology → offset mapping → evidence-span check. The evidence
span check (AC-13) is the zero-cost catch for the most common extraction
failure — a plausible assertion attached to the wrong sentence. Returned
offsets are passage-local; they are mapped to document offsets through each
passage's `doc_start` before the check runs on the document slice.

Rejection reasons are stable prefixes so the pipeline can count by reason:
`SCHEMA`, `UNKNOWN_RELATION`, `UNKNOWN_TYPE`, `ONTOLOGY_REJECTED`,
`UNKNOWN_PASSAGE`, `UNPARSEABLE_DATE`, and `EVIDENCE_SPAN_MISMATCH` (AC-13).
Nothing is dropped without an entry in `parse_errors`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from limes.extraction.base import strip_model_fence
from limes.ontology.model import Ontology
from limes.types import ExtractedAssertion, Mention, Passage

SCHEMA_VERSION = "1.0.0"

_EXTRACTION_MENTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["surface", "type"],
    "properties": {
        "surface": {"type": "string", "minLength": 1},
        "type": {"type": "string", "minLength": 1},
        "deterministic_key": {
            "anyOf": [
                {"type": "null"},
                {
                    "type": "array",
                    "prefixItems": [{"type": "string"}, {"type": "string"}],
                    "minItems": 2,
                    "maxItems": 2,
                },
            ]
        },
    },
}

EXTRACTION_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "passage_index",
        "subject",
        "relation",
        "object",
        "confidence",
        "evidence_start",
        "evidence_end",
    ],
    "properties": {
        "passage_index": {"type": "integer", "minimum": 0},
        "subject": _EXTRACTION_MENTION_SCHEMA,
        "relation": {"type": "string", "minLength": 1},
        "object": _EXTRACTION_MENTION_SCHEMA,
        "valid_from": {"anyOf": [{"type": "null"}, {"type": "string"}]},
        "valid_to": {"anyOf": [{"type": "null"}, {"type": "string"}]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "evidence_start": {"type": "integer", "minimum": 0},
        "evidence_end": {"type": "integer", "minimum": 0},
    },
}


def parse_extraction_response(
    raw: str,
    passages: list[Passage],
    ontology: Ontology,
) -> tuple[list[ExtractedAssertion], list[str]]:
    """Parse one extractor response into pre-resolution assertions.

    Returns `(assertions, errors)`; every rejected item is represented by one
    error string, never dropped silently. The evidence-span check runs on the
    mapped document span: the span must contain the subject surface or the
    object surface, case-insensitively (AC-13's literal reading).
    """
    parsed = _parse_json(raw)
    if not isinstance(parsed, list):
        return [], ["RESPONSE_NOT_ARRAY: response is not a JSON array"]
    if not parsed:
        return [], []

    validator = Draft202012Validator(EXTRACTION_SCHEMA)
    assertions: list[ExtractedAssertion] = []
    errors: list[str] = []
    for index, item in enumerate(parsed):
        if not isinstance(item, dict):
            errors.append(f"SCHEMA: item {index} is not an object")
            continue
        schema_error = next(
            iter(sorted(validator.iter_errors(item), key=lambda e: str(e.path))), None
        )
        if schema_error is not None:
            errors.append(f"SCHEMA: item {index}: {schema_error.message}")
            continue

        relation = str(item["relation"])
        if relation not in ontology.relation_types:
            errors.append(f"UNKNOWN_RELATION: item {index}: {relation!r}")
            continue
        subject_type = str(item["subject"]["type"])
        object_type = str(item["object"]["type"])
        if subject_type not in ontology.entity_types:
            errors.append(f"UNKNOWN_TYPE: item {index}: subject type {subject_type!r}")
            continue
        if object_type not in ontology.entity_types:
            errors.append(f"UNKNOWN_TYPE: item {index}: object type {object_type!r}")
            continue
        if not ontology.permits(relation, subject_type, object_type):
            errors.append(
                f"ONTOLOGY_REJECTED: item {index}: {subject_type} -[{relation}]-> {object_type}"
            )
            continue

        passage_index = int(item["passage_index"])
        if not (0 <= passage_index < len(passages)):
            errors.append(f"UNKNOWN_PASSAGE: item {index}: passage_index {passage_index}")
            continue
        passage = passages[passage_index]

        evidence_start = int(item["evidence_start"])
        evidence_end = int(item["evidence_end"])
        if not (0 <= evidence_start <= evidence_end <= len(passage.text)):
            errors.append(
                f"EVIDENCE_SPAN_MISMATCH: item {index}: span {evidence_start}:{evidence_end} "
                f"outside passage {passage_index}"
            )
            continue
        span_text = passage.text[evidence_start:evidence_end].casefold()
        subject_surface = str(item["subject"]["surface"]).casefold()
        object_surface = str(item["object"]["surface"]).casefold()
        if subject_surface not in span_text and object_surface not in span_text:
            errors.append(
                f"EVIDENCE_SPAN_MISMATCH: item {index}: span does not contain the subject "
                f"or object surface"
            )
            continue

        valid_from: datetime | None = None
        valid_to: datetime | None = None
        try:
            valid_from = _parse_date(item.get("valid_from"))
            valid_to = _parse_date(item.get("valid_to"))
        except ValueError:
            errors.append(
                f"UNPARSEABLE_DATE: item {index}: {item.get('valid_from')!r} / "
                f"{item.get('valid_to')!r}"
            )
            continue

        assertions.append(
            ExtractedAssertion(
                passage_index=passage_index,
                subject=_mention(item["subject"]),
                relation=relation,
                object=_mention(item["object"]),
                valid_from=valid_from,
                valid_to=valid_to,
                confidence=float(item["confidence"]),
                evidence_start=passage.doc_start + evidence_start,
                evidence_end=passage.doc_start + evidence_end,
            )
        )
    return assertions, errors


def _parse_date(raw: Any) -> datetime | None:
    """An ISO instant or None; anything else raises `ValueError`, which the
    caller converts into a counted rejection."""
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw:
        raise ValueError(f"not a date: {raw!r}")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        raise ValueError(f"not a date: {raw!r}") from None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _mention(raw: dict[str, Any]) -> Mention:
    deterministic_key = raw.get("deterministic_key")
    return Mention(
        surface=str(raw["surface"]),
        type=str(raw["type"]),
        deterministic_key=(
            (str(deterministic_key[0]), str(deterministic_key[1]))
            if isinstance(deterministic_key, list) and len(deterministic_key) == 2
            else None
        ),
    )


def _parse_json(raw: str) -> Any:
    """The response with markdown fences stripped, parsed as JSON. A response
    that is not JSON at all surfaces as a `RESPONSE_NOT_ARRAY`-style error at
    the call site (the raw text stays in `ExtractionResult.raw_response` for
    diagnosis)."""
    text = strip_model_fence(raw)
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
