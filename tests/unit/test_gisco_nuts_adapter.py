# tests/unit/test_gisco_nuts_adapter.py | v1.0.0 | introduced by WP-10
"""GISCO/NUTS adapter tests per Doc 2 §8.5.2 and §12.3.

NRW fixtures in the official 2024 layouts (BE-59), pinned with respx — no live
network; out-of-scope rows prove the NRW reduction. Asserts the exact expected
record set: deterministic keys (`nuts_code` for regions, `iso2` for the
country, `(country_code, postal_code)` for lookup rows), source attribution
(`source_id`, `source_trust`), the level-derived parent chain, and the mixed
single/double quoting of the postcode file.
"""

from datetime import UTC, datetime

import respx
from httpx import Response

from limes.errors import SourceParseError
from limes.sources.gisco_nuts import (
    NUTS_URL,
    POSTCODE_URL,
    GiscoNutsAdapter,
)
from limes.types import RawRecord

FIXTURES = __import__("pathlib").Path(__file__).parents[1] / "fixtures" / "gisco_nuts"
NOW = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)

ADAPTER = GiscoNutsAdapter()


def _record(payload: bytes, url: str) -> RawRecord:
    return RawRecord(payload=payload, content_type="text/csv", source_url=url, fetched_at=NOW)


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_fetch_reads_hierarchy_and_emits_pinned_nrw_postcodes_without_download():
    with respx.mock:
        respx.get(NUTS_URL).mock(return_value=Response(200, content=_fixture("nuts_hierarchy.csv")))
        records = list(ADAPTER.fetch(None, None))
        # BE-59: the 127 MB EU-wide postcode file is never requested.
        assert [call.request.url for call in respx.calls] == [NUTS_URL]
    assert [r.source_url for r in records] == [NUTS_URL, POSTCODE_URL]
    pinned = records[1]
    assert pinned.acquisition_context["pinned_reference"] == "nrw_postcodes_gisco_2024.csv"
    assert pinned.fetched_at.year == 2026  # extraction instant, not this run's clock
    rows = ADAPTER.normalize(pinned).lookup_rows
    assert len(rows) == 874
    assert {row.value["nuts_code"][:3] for row in rows} == {"DEA"}


def test_hierarchy_keeps_only_germany_and_the_nrw_subtree():
    record = _record(_fixture("nuts_hierarchy.csv"), NUTS_URL)
    normalized = ADAPTER.normalize(record)

    assert normalized.kind == "structured"
    assert normalized.lookup_rows == []
    by_subject = {a.subject.entity_id: a for a in normalized.assertions}
    assert set(by_subject) == {
        "nuts_code:DEA",
        "nuts_code:DEA1",
        "nuts_code:DEA11",
        "nuts_code:DEA13",
        "nuts_code:DEA2",
        "nuts_code:DEA23",
        "nuts_code:DEA2D",
    }
    # Level derivation by NUTS_ID length: parent is the code minus its last
    # character, and the country row is the 2-char NUTS0.
    assert by_subject["nuts_code:DEA"].object.entity_id == "iso2:DE"
    assert by_subject["nuts_code:DEA"].object.type == "Country"
    assert by_subject["nuts_code:DEA1"].object.entity_id == "nuts_code:DEA"
    assert by_subject["nuts_code:DEA23"].object.entity_id == "nuts_code:DEA2"

    # Deterministic keys and source attribution on every assertion.
    for assertion in normalized.assertions:
        assert assertion.subject.deterministic_key[0] == "nuts_code"
        assert assertion.relation == "PART_OF_REGION"
        assert assertion.provenance.source_id == "gisco_nuts"
        assert assertion.provenance.source_trust == 1.00
        assert assertion.provenance.confidence == 1.0
        assert assertion.validity.recorded_at == NOW
    assert normalized.errors == 0


def test_hierarchy_labels_are_source_verbatim():
    record = _record(_fixture("nuts_hierarchy.csv"), NUTS_URL)
    normalized = ADAPTER.normalize(record)
    labels = {a.subject.entity_id: a.subject.label for a in normalized.assertions}
    assert labels["nuts_code:DEA"] == "Nordrhein-Westfalen"
    # German source data verbatim: umlauts survive.
    assert labels["nuts_code:DEA23"] == "Köln, Kreisfreie Stadt"
    assert labels["nuts_code:DEA2D"] == "Städteregion Aachen"


def test_postcode_normalize_keeps_nrw_rows_with_mixed_quoting():
    record = _record(_fixture("postcode_correspondence.csv"), POSTCODE_URL)
    with __import__("structlog").testing.capture_logs() as captured:
        normalized = ADAPTER.normalize(record)

    assert normalized.assertions == []
    # Single-quoted NUTS fields parse; Stuttgart and Lahti are outside NRW.
    assert [(r.key["postal_code"], r.value["nuts_code"]) for r in normalized.lookup_rows] == [
        ("50667", "DEA23"),
        ("40213", "DEA11"),
    ]
    assert normalized.lookup_rows[0].kind == "postal_code"
    assert normalized.lookup_rows[0].key == {"country_code": "DE", "postal_code": "50667"}
    summary = [e for e in captured if e.get("event") == "gisco_nuts: postcodes normalized"][0]
    assert summary["outside_nrw"] == 2


def test_postcode_rows_with_empty_key_fields_are_counted_and_skipped():
    payload = (
        b"POSTCODE,CNTR_ID,SOURCE,LAU_NAME,PC_CNTR,CODE,NUTS3_2024\n"
        b"\"50667\",DE,3,Koeln,DE_50667,'50667','DEA23'\n"
        b'"",,3,Nowhere,,,\n'
    )
    normalized = ADAPTER.normalize(_record(payload, POSTCODE_URL))
    assert len(normalized.lookup_rows) == 1
    assert normalized.lookup_rows[0].key == {"country_code": "DE", "postal_code": "50667"}


def test_normalize_rejects_unrecognized_payload():
    try:
        ADAPTER.normalize(_record(b"garbage,that,is,not,a,source,file", "https://example/x"))
    except SourceParseError:
        pass
    else:
        raise AssertionError("expected SourceParseError")


def test_empty_payload_raises_source_parse_error():
    try:
        ADAPTER.normalize(_record(b"", NUTS_URL))
    except SourceParseError:
        pass
    else:
        raise AssertionError("expected SourceParseError")


def test_assertion_ids_are_deterministic_across_calls():
    record = _record(_fixture("nuts_hierarchy.csv"), NUTS_URL)
    first = [a.assertion_id for a in ADAPTER.normalize(record).assertions]
    second = [a.assertion_id for a in ADAPTER.normalize(record).assertions]
    assert first == second
    assert len(set(first)) == len(first)


def test_hierarchy_file_without_data_rows_raises_source_parse_error():
    try:
        ADAPTER.normalize(_record(b"NUTS_ID,CNTR_CODE,NAME_2024\n", NUTS_URL))
    except SourceParseError:
        pass
    else:
        raise AssertionError("expected SourceParseError")


def test_postcode_file_without_data_rows_raises_source_parse_error():
    try:
        ADAPTER.normalize(
            _record(b"POSTCODE,CNTR_ID,SOURCE,LAU_NAME,PC_CNTR,CODE,NUTS3_2024\n", POSTCODE_URL)
        )
    except SourceParseError:
        pass
    else:
        raise AssertionError("expected SourceParseError")


def test_postcode_row_with_too_few_fields_is_skipped_and_counted():
    payload = (
        b"POSTCODE,CNTR_ID,SOURCE,LAU_NAME,PC_CNTR,CODE,NUTS3_2024\n"
        b"\"50667\",DE,3,Koeln,DE_50667,'50667','DEA23'\n"
        b"short,row,only,three\n"
    )
    with __import__("structlog").testing.capture_logs() as captured:
        normalized = ADAPTER.normalize(_record(payload, POSTCODE_URL))
    assert len(normalized.lookup_rows) == 1
    summary = [e for e in captured if e.get("event") == "gisco_nuts: postcodes normalized"][0]
    assert summary["skipped"] == 1


def test_blank_line_in_csv_is_ignored():
    payload = (
        b"POSTCODE,CNTR_ID,SOURCE,LAU_NAME,PC_CNTR,CODE,NUTS3_2024\n"
        b"\n"
        b"\"50667\",DE,3,Koeln,DE_50667,'50667','DEA23'\n"
    )
    normalized = ADAPTER.normalize(_record(payload, POSTCODE_URL))
    assert len(normalized.lookup_rows) == 1


def test_missing_hierarchy_parent_retains_region_but_blocks_complete_outcome():
    result = ADAPTER.normalize(_record(
        b"CNTR_CODE,NUTS_ID,NAME_LATN\nDE,DEA11,Duesseldorf\n", NUTS_URL
    ))
    assert result.errors == 1
    assert result.assertions == []
    assert [entity.entity_id for entity in result.entities] == ["nuts_code:DEA11"]


def test_oversized_csv_field_raises_source_parse_error():
    # A field beyond the csv module's field-size limit makes the reader raise
    # csv.Error — the unparseable-line branch of the parser.
    payload = b"NUTS_ID,CNTR_CODE,NAME_2024\n" + b"DE,DEA," + b"x" * 200_000 + b"\n"
    try:
        ADAPTER.normalize(_record(payload, NUTS_URL))
    except SourceParseError:
        pass
    else:
        raise AssertionError("expected SourceParseError")
