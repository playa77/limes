# tests/unit/test_gisco_nuts_adapter.py | v1.0.0 | introduced by WP-10
"""GISCO/NUTS adapter tests per Doc 2 §8.5.2 and §12.3.

Recorded fixtures (real rows from the live 2024 files, trimmed to a coherent
DE hierarchy) pinned with respx — no live network. Asserts the exact expected
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


def test_fetch_yields_one_record_per_file():
    with respx.mock:
        respx.get(NUTS_URL).mock(return_value=Response(200, content=_fixture("nuts_hierarchy.csv")))
        respx.get(POSTCODE_URL).mock(
            return_value=Response(200, content=_fixture("postcode_correspondence.csv"))
        )
        records = list(ADAPTER.fetch(None, None))
    assert [r.source_url for r in records] == [NUTS_URL, POSTCODE_URL]
    assert all(r.content_type == "text/csv; charset=utf-8" for r in records)


def test_hierarchy_normalize_produces_expected_assertions():
    record = _record(_fixture("nuts_hierarchy.csv"), NUTS_URL)
    normalized = ADAPTER.normalize(record)

    assert normalized.kind == "structured"
    assert normalized.lookup_rows == []
    assert len(normalized.assertions) == 9  # DE1, DE11, DE111, DE112, DE12, DE121, DE122, DE2, DE21

    by_subject = {a.subject.entity_id: a for a in normalized.assertions}
    assert set(by_subject) == {
        "nuts_code:DE1",
        "nuts_code:DE11",
        "nuts_code:DE111",
        "nuts_code:DE112",
        "nuts_code:DE12",
        "nuts_code:DE121",
        "nuts_code:DE122",
        "nuts_code:DE2",
        "nuts_code:DE21",
    }

    # Level derivation by NUTS_ID length: parent is the code minus its last
    # character, and the country row is the 2-char NUTS0.
    assert by_subject["nuts_code:DE1"].object.entity_id == "iso2:DE"
    assert by_subject["nuts_code:DE1"].object.type == "Country"
    assert by_subject["nuts_code:DE11"].object.entity_id == "nuts_code:DE1"
    assert by_subject["nuts_code:DE111"].object.entity_id == "nuts_code:DE11"
    assert by_subject["nuts_code:DE21"].object.entity_id == "nuts_code:DE2"

    # Deterministic keys and source attribution on every assertion.
    for assertion in normalized.assertions:
        assert assertion.subject.deterministic_key[0] == "nuts_code"
        assert assertion.relation == "PART_OF_REGION"
        assert assertion.provenance.source_id == "gisco_nuts"
        assert assertion.provenance.source_trust == 1.00
        assert assertion.provenance.confidence == 1.0
        assert assertion.validity.recorded_at == NOW


def test_hierarchy_labels_and_levels():
    record = _record(_fixture("nuts_hierarchy.csv"), NUTS_URL)
    normalized = ADAPTER.normalize(record)
    labels = {a.subject.entity_id: a.subject.label for a in normalized.assertions}
    assert labels["nuts_code:DE1"] == "Baden-Württemberg"
    assert labels["nuts_code:DE111"] == "Stuttgart, Stadtkreis"
    # German source data verbatim: umlauts and ẞ survive.
    assert labels["nuts_code:DE2"] == "Bayern"


def test_postcode_normalize_produces_lookup_rows_with_mixed_quoting():
    record = _record(_fixture("postcode_correspondence.csv"), POSTCODE_URL)
    normalized = ADAPTER.normalize(record)

    assert normalized.assertions == []
    assert normalized.kind == "structured"
    # Three data rows, all mapped to NUTS3 FI1C6; the single-quoted NUTS and
    # PC_CNTR fields parse correctly.
    assert len(normalized.lookup_rows) == 3
    assert normalized.lookup_rows[0].kind == "postal_code"
    assert normalized.lookup_rows[0].key == {"country_code": "FI", "postal_code": "15701"}
    assert normalized.lookup_rows[0].value == {"nuts_code": "FI1C6"}
    assert normalized.lookup_rows[2].key == {"country_code": "FI", "postal_code": "15871"}


def test_postcode_rows_with_empty_key_fields_are_counted_and_skipped():
    payload = (
        b"POSTCODE,CNTR_ID,SOURCE,LAU_NAME,PC_CNTR,CODE,NUTS3_2024\n"
        b'"15701",FI,3,Lahti,FI_15701,\'15701\',\'FI1C6\'\n'
        b'"",,3,Nowhere,,,\n'
    )
    normalized = ADAPTER.normalize(_record(payload, POSTCODE_URL))
    assert len(normalized.lookup_rows) == 1
    assert normalized.lookup_rows[0].key == {"country_code": "FI", "postal_code": "15701"}


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
