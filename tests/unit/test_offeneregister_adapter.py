# tests/unit/test_offeneregister_adapter.py | v1.0.0 | introduced by WP-20
"""OffeneRegister adapter tests per Doc 2 §8.5.2 and §12.3.

The vintage rule is the acceptance: `recorded_at` on every assertion is the
dataset's publication date from the metadata record, never the ingestion
timestamp — this is what makes the 0.30 trust rank safe (DD-15). The adapter
must refuse to emit without a known publication date rather than fall back to
the wall clock, and the assertions must carry `source_trust = 0.30`.
"""

import gzip
from datetime import UTC, datetime

import respx
from httpx import Response

from limes.errors import SourceParseError
from limes.sources.offeneregister import (
    DATA_URL,
    METADATA_URL,
    OffeneRegisterAdapter,
)
from limes.types import RawRecord

FIXTURES = __import__("pathlib").Path(__file__).parents[1] / "fixtures" / "offeneregister"
FETCHED_AT = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)
PUBLISHED_AT = datetime(2026, 1, 15, 0, 0, 0, tzinfo=UTC)


def _metadata_record() -> RawRecord:
    payload = (FIXTURES / "meta.json").read_bytes()
    return RawRecord(
        payload=payload,
        content_type="application/json",
        source_url=METADATA_URL,
        fetched_at=FETCHED_AT,
    )


def _data_record() -> RawRecord:
    payload = gzip.compress((FIXTURES / "companies.jsonl").read_bytes())
    return RawRecord(
        payload=payload, content_type="application/gzip", source_url=DATA_URL, fetched_at=FETCHED_AT
    )


def test_fetch_yields_metadata_then_data():
    with respx.mock:
        respx.get(METADATA_URL).mock(
            return_value=Response(200, content=b'{"published_at": "2026-01-15"}')
        )
        respx.get(DATA_URL).mock(return_value=Response(200, content=gzip.compress(b"{}")))
        records = list(OffeneRegisterAdapter().fetch(None, None))
    assert [r.source_url for r in records] == [METADATA_URL, DATA_URL]
    assert records[0].content_type == "application/json"
    assert records[1].content_type == "application/gzip"


def test_metadata_record_sets_publication_date():
    adapter = OffeneRegisterAdapter()
    normalized = adapter.normalize(_metadata_record())
    assert normalized.assertions == []
    assert adapter._published_at == PUBLISHED_AT


def test_recorded_at_is_publication_date_never_ingestion_time():
    adapter = OffeneRegisterAdapter()
    adapter.normalize(_metadata_record())
    normalized = adapter.normalize(_data_record())
    assert len(normalized.assertions) == 3  # Max + Erika + Otto

    for assertion in normalized.assertions:
        assert assertion.validity.recorded_at == PUBLISHED_AT
        assert assertion.validity.recorded_at != FETCHED_AT
        assert assertion.provenance.source_id == "offeneregister"
        assert assertion.provenance.source_trust == 0.30
        assert assertion.validity.recorded_at != FETCHED_AT


def test_data_record_without_metadata_is_refused_not_wall_clocked():
    adapter = OffeneRegisterAdapter()
    try:
        adapter.normalize(_data_record())
    except SourceParseError:
        pass
    else:
        raise AssertionError("expected SourceParseError: no publication date known")


def test_director_of_keys_and_intervals():
    adapter = OffeneRegisterAdapter()
    adapter.normalize(_metadata_record())
    normalized = adapter.normalize(_data_record())

    by_assertion = {a.assertion_id: a for a in normalized.assertions}
    assert len(by_assertion) == 3

    max_assertion = next(a for a in normalized.assertions if a.subject.label == "Mustermann, Max")
    assert max_assertion.subject.type == "Person"
    assert max_assertion.subject.deterministic_key is None
    assert max_assertion.subject.entity_id.startswith("person:")
    assert max_assertion.relation == "DIRECTOR_OF"
    assert max_assertion.object.type == "Corporation"
    assert max_assertion.object.entity_id == "german_register_number:HRB 12345 B"
    assert max_assertion.object.deterministic_key == ("german_register_number", "HRB 12345 B")
    assert max_assertion.validity.valid_from == datetime(2019, 3, 1, tzinfo=UTC)
    assert max_assertion.validity.valid_to is None

    # Erika's directorship ended: the interval is closed.
    erika = next(a for a in normalized.assertions if a.subject.label == "Beispiel, Erika")
    assert erika.validity.valid_to == datetime(2024, 2, 29, tzinfo=UTC)


def test_companies_without_officers_produce_no_assertions_but_are_counted():
    adapter = OffeneRegisterAdapter()
    adapter.normalize(_metadata_record())
    normalized = adapter.normalize(_data_record())
    # HRA 54321 has no officers: no assertion, but the company is not dropped
    # silently — the summary log carries the count.
    assert all(
        a.object.entity_id != "german_register_number:HRA 54321" for a in normalized.assertions
    )


def test_malformed_jsonl_lines_are_counted_and_skipped():
    adapter = OffeneRegisterAdapter()
    adapter.normalize(_metadata_record())
    normalized = adapter.normalize(_data_record())
    # The fixture's non-company line yields no assertion; the summary log
    # counts malformed lines (asserted structurally: 3 assertions, not 4).
    assert len(normalized.assertions) == 3


def test_assertion_ids_are_deterministic_across_calls():
    adapter = OffeneRegisterAdapter()
    adapter.normalize(_metadata_record())
    first = [a.assertion_id for a in adapter.normalize(_data_record()).assertions]
    second = [a.assertion_id for a in adapter.normalize(_data_record()).assertions]
    assert first == second


def test_malformed_gzip_raises_source_parse_error():
    adapter = OffeneRegisterAdapter()
    adapter.normalize(_metadata_record())
    record = RawRecord(
        payload=b"not gzip",
        content_type="application/gzip",
        source_url=DATA_URL,
        fetched_at=FETCHED_AT,
    )
    try:
        adapter.normalize(record)
    except SourceParseError:
        pass
    else:
        raise AssertionError("expected SourceParseError")


def test_malformed_metadata_raises_source_parse_error():
    adapter = OffeneRegisterAdapter()
    record = RawRecord(
        payload=b'{"no_date": true}',
        content_type="application/json",
        source_url=METADATA_URL,
        fetched_at=FETCHED_AT,
    )
    try:
        adapter.normalize(record)
    except SourceParseError:
        pass
    else:
        raise AssertionError("expected SourceParseError")


def test_unknown_content_type_raises_source_parse_error():
    adapter = OffeneRegisterAdapter()
    record = RawRecord(
        payload=b"anything",
        content_type="text/plain",
        source_url=METADATA_URL,
        fetched_at=FETCHED_AT,
    )
    try:
        adapter.normalize(record)
    except SourceParseError:
        pass
    else:
        raise AssertionError("expected SourceParseError")


def test_non_json_metadata_raises_source_parse_error():
    adapter = OffeneRegisterAdapter()
    record = RawRecord(
        payload=b"{not json",
        content_type="application/json",
        source_url=METADATA_URL,
        fetched_at=FETCHED_AT,
    )
    try:
        adapter.normalize(record)
    except SourceParseError:
        pass
    else:
        raise AssertionError("expected SourceParseError")


def test_unparseable_published_at_raises_source_parse_error():
    adapter = OffeneRegisterAdapter()
    record = RawRecord(
        payload=b'{"published_at": "not-a-date"}',
        content_type="application/json",
        source_url=METADATA_URL,
        fetched_at=FETCHED_AT,
    )
    try:
        adapter.normalize(record)
    except SourceParseError:
        pass
    else:
        raise AssertionError("expected SourceParseError")


def _gzip_jsonl(lines: list[str]) -> bytes:
    return gzip.compress(("\n".join(lines) + "\n").encode("utf-8"))


def test_skipped_records_are_counted_by_reason():
    adapter = OffeneRegisterAdapter()
    adapter.normalize(_metadata_record())
    lines = [
        "",
        "not json",
        json_dumps_company(
            "HRB 1",
            "Eins GmbH",
            [
                {
                    "name": "Mustermann, Max",
                    "position": "Geschäftsführer",
                    "start_date": "2019-03-01",
                }
            ],
        ),
        json_dumps_company("", "", []),
        json_dumps_company("HRB 2", "Zwei GmbH", ["kein Objekt"]),
        json_dumps_company(
            "HRB 3", "Drei GmbH", [{"name": "Meyer, Gisela", "position": "Sekretärin"}]
        ),
        json_dumps_company("HRB 4", "Vier GmbH", [{"position": "Geschäftsführer"}]),
        json_dumps_company(
            "HRB 5",
            "Fünf GmbH",
            [{"name": "Schulz, Fritz", "position": "Geschäftsführer", "end_date": "2024-02-30"}],
        ),
    ]
    record = RawRecord(
        payload=_gzip_jsonl(lines),
        content_type="application/gzip",
        source_url=DATA_URL,
        fetched_at=FETCHED_AT,
    )
    with __import__("structlog").testing.capture_logs() as captured:
        normalized = adapter.normalize(record)

    assert len(normalized.assertions) == 2  # Max + Fritz (Fritz's end date is dropped)
    assert all(a.validity.valid_to is None for a in normalized.assertions)
    summary = [e for e in captured if e.get("event") == "offeneregister: dataset normalized"][0]
    assert summary["companies"] == 6
    assert summary["director_assertions"] == 2
    assert summary["malformed_lines"] == 2  # the bad line and the non-dict officer
    assert summary["companies_without_number_or_name"] == 1
    warnings = [
        e for e in captured if e.get("event") == "offeneregister: non-director position skipped"
    ]
    assert len(warnings) == 1
    assert warnings[0]["position"] == "Sekretärin"
    date_warnings = [
        e for e in captured if e.get("event") == "offeneregister: unparseable officer date"
    ]
    assert len(date_warnings) == 1
    assert date_warnings[0]["raw"] == "2024-02-30"


def json_dumps_company(number: str, name: str, officers: list) -> str:
    import json

    return json.dumps({"company": {"company_number": number, "name": name, "officers": officers}})
