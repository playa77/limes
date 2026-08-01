# tests/unit/test_types.py | v1.0.0 | introduced by WP-02
"""Serialization round-trips and default-value contracts for §5.5 types."""

import json
from datetime import UTC, datetime
from decimal import Decimal

from limes.types import (
    Assertion,
    CostLedgerEntry,
    DocumentPayload,
    EntityEndpoint,
    ExtractedAssertion,
    GateDecision,
    IngestionRunRecord,
    LookupRow,
    Mention,
    NerSpan,
    NormalizedRecord,
    Passage,
    PlanSummary,
    Provenance,
    RawRecord,
    SourceRecord,
    ValidationError,
    Validity,
    WriteResult,
)

NOW = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)


def _assertion() -> Assertion:
    return Assertion(
        assertion_id="a1",
        subject=EntityEndpoint(entity_id="e1", type="Corporation", label="ACME"),
        relation="SUBSIDIARY_OF",
        object=EntityEndpoint(entity_id="e2", type="Corporation", label="MEGA"),
        validity=Validity(valid_from=NOW, recorded_at=NOW),
        provenance=Provenance(
            source_id="gleif",
            source_trust=1.0,
            confidence=1.0,
            ontology_version="1.0.0",
        ),
    )


def test_all_types_instantiate_with_valid_data():
    types = {
        "Mention": Mention(surface="ACME", type="Corporation"),
        "EntityEndpoint": EntityEndpoint(entity_id="e1", type="Corporation", label="ACME"),
        "Provenance": Provenance(
            source_id="s", source_trust=1.0, confidence=0.9, ontology_version="1.0.0"
        ),
        "Validity": Validity(valid_from=NOW, recorded_at=NOW),
        "ExtractedAssertion": ExtractedAssertion(
            passage_index=0,
            subject=Mention(surface="ACME", type="Corporation"),
            relation="SUBSIDIARY_OF",
            object=Mention(surface="MEGA", type="Corporation"),
            confidence=0.9,
            evidence_start=0,
            evidence_end=10,
        ),
        "Assertion": _assertion(),
        "LookupRow": LookupRow(
            kind="postal_code", key={"country_code": "DE"}, value={"nuts_code": "DE1"}
        ),
        "DocumentPayload": DocumentPayload(
            content_hash="h", title="t", body="b", language="de", published_at=NOW
        ),
        "Passage": Passage(index=0, text="t", doc_start=0, doc_end=1),
        "RawRecord": RawRecord(payload=b"x", content_type="text/csv", fetched_at=NOW),
        "NerSpan": NerSpan(text="t", label="PER", start=0, end=1),
        "GateDecision": GateDecision(passed=True, reason="ok", passages=[]),
        "ValidationError": ValidationError(assertion_index=0, reason="r", detail={}),
        "WriteResult": WriteResult(
            statements_executed=1, nodes_created=2, relationships_created=3, properties_set=4
        ),
        "PlanSummary": PlanSummary(
            operators=["Scan"],
            max_estimated_rows=1,
            total_estimated_rows=2,
            has_cartesian_product=False,
            max_varlength_hops=None,
        ),
        "CostLedgerEntry": CostLedgerEntry(
            ledger_id="l1",
            period="2026-08",
            purpose="extraction",
            model_id="m",
            input_tokens=100,
            output_tokens=10,
            cost_usd=Decimal("0.01"),
            cost_eur=Decimal("0.0092"),
            created_at=NOW,
        ),
        "SourceRecord": SourceRecord(source_id="s", name="S", kind="structured", trust_rank=1.0),
        "IngestionRunRecord": IngestionRunRecord(
            run_id="r1",
            source_id="s",
            mode="ingest",
            started_at=NOW,
        ),
    }
    for name, instance in types.items():
        assert instance is not None, name


def test_normalized_record_defaults():
    record = NormalizedRecord(content_hash="h", kind="structured")
    assert record.assertions == []
    assert record.entities == []
    assert record.lookup_rows == []
    assert record.document is None


def test_serialization_round_trip_assertion():
    assertion = _assertion()
    restored = Assertion.model_validate_json(assertion.model_dump_json())
    assert restored == assertion


def test_serialization_round_trip_lookup_row():
    row = LookupRow(
        kind="postal_code",
        key={"country_code": "DE", "postal_code": "10115"},
        value={"nuts_code": "DE300"},
    )
    restored = LookupRow.model_validate_json(row.model_dump_json())
    assert restored == row


def test_serialization_round_trip_json_dump_matches_model():
    assertion = _assertion()
    dumped = json.loads(assertion.model_dump_json())
    assert dumped["relation"] == "SUBSIDIARY_OF"
    assert dumped["subject"]["entity_id"] == "e1"
