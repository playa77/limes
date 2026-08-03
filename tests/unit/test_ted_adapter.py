# tests/unit/test_ted_adapter.py | v1.0.0 | introduced by WP-14
"""TED adapter tests per Technical Specification §8.5.2 (source: `ted`).

Fixtures are minimal but realistic notice XML documents in
tests/fixtures/ted/ (namespaced, so the `local-name()` parsing is what is
under test). The notice search POST and the per-notice GETs are pinned with
respx — no live network. Asserts the exact expected record set:
deterministic keys (`ted_notice_id`, the `ted_buyer_id` surrogate, `lei`,
`coordinate_hash`, `nuts_code`, the multi-key CPV Topic identity), labels,
relation names, source attribution, the BUYER_NUTS-preference and
postal-lookup behaviors, deterministic assertion ids, and parse errors on
malformed payloads. The malformed payload is built in-test, not stored as a
fixture.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pytest
import respx
from httpx import Response
from structlog.testing import capture_logs

from limes.errors import SourceParseError
from limes.sources.ted import FETCH_LIMIT, SEARCH_URL, TedAdapter
from limes.types import RawRecord

FIXTURES = __import__("pathlib").Path(__file__).parents[1] / "fixtures" / "ted"
NOW = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)

ADAPTER = TedAdapter()

NOTICE_URI_LEI = "https://ted.europa.eu/api/v3/notices/123456-2025/raw"
NOTICE_URI_NAME = "https://ted.europa.eu/api/v3/notices/654321-2025/raw"

LEI_CONTRACTOR = "529900TEST0000000001"


def _sha256_hex(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


BUYER_KOELN_DIGEST = _sha256_hex("DE", "Stadt Köln")
KOELN_ADDR_HASH = _sha256_hex("DE", "50667", "Köln")
BUYER_BERLIN_DIGEST = _sha256_hex("DE", "Senatsverwaltung Berlin")
BERLIN_ADDR_HASH = _sha256_hex("DE", "10115", "Berlin")
NAME_ONLY_DIGEST = _sha256_hex("Druckerei Beispiel GmbH")[:32]


def _notice_record(payload: bytes, uri: str) -> RawRecord:
    return RawRecord(
        payload=payload,
        content_type="application/xml",
        source_url=uri,
        fetched_at=NOW,
    )


def _lei_notice() -> RawRecord:
    return _notice_record((FIXTURES / "award_lei.xml").read_bytes(), NOTICE_URI_LEI)


def _name_only_notice() -> RawRecord:
    return _notice_record((FIXTURES / "award_name_only.xml").read_bytes(), NOTICE_URI_NAME)


def _search_payload() -> bytes:
    return json.dumps(
        {
            "results": [
                {"id": "123456-2025", "uri": NOTICE_URI_LEI},
                {"id": "654321-2025", "uri": NOTICE_URI_NAME},
            ]
        }
    ).encode()


def test_fetch_yields_one_raw_record_per_notice_and_honors_window():
    since = datetime(2025, 1, 1, tzinfo=UTC)
    until = datetime(2025, 12, 31, tzinfo=UTC)
    with respx.mock:
        search = respx.post(SEARCH_URL).mock(return_value=Response(200, content=_search_payload()))
        respx.get(NOTICE_URI_LEI).mock(return_value=Response(200, content=_lei_notice().payload))
        respx.get(NOTICE_URI_NAME).mock(
            return_value=Response(200, content=_name_only_notice().payload)
        )
        records = list(ADAPTER.fetch(since, until))
        body = json.loads(search.calls[0].request.content)

    assert [r.source_url for r in records] == [NOTICE_URI_LEI, NOTICE_URI_NAME]
    assert all(r.content_type == "application/xml" for r in records)
    assert all(r.fetched_at.tzinfo is not None for r in records)
    # The window is compiled into the search query text as an ISO date range.
    assert body["query"] == "publication_date:[2025-01-01 TO 2025-12-31]"
    assert body["limit"] == FETCH_LIMIT


def test_fetch_without_window_sends_match_all_query():
    with respx.mock:
        search = respx.post(SEARCH_URL).mock(return_value=Response(200, content=_search_payload()))
        respx.get(NOTICE_URI_LEI).mock(return_value=Response(200, content=_lei_notice().payload))
        respx.get(NOTICE_URI_NAME).mock(
            return_value=Response(200, content=_name_only_notice().payload)
        )
        records = list(ADAPTER.fetch(None, None))
        body = json.loads(search.calls[0].request.content)

    assert len(records) == 2
    assert body["query"] == "*"


def test_fetch_empty_search_yields_no_records_and_logs():
    with respx.mock:
        respx.post(SEARCH_URL).mock(return_value=Response(200, json={"results": []}))
        with capture_logs() as captured:
            records = list(ADAPTER.fetch(None, None))
    assert records == []
    summary = [e for e in captured if e.get("event") == "ted: search returned no notices"]
    assert len(summary) == 1


def test_search_hits_without_id_or_uri_are_skipped_and_counted():
    hits = [
        {"id": "123456-2025", "uri": NOTICE_URI_LEI},
        42,
        {"uri": NOTICE_URI_NAME},
        {"id": "999999-2025"},
        {"id": "888888-2025", "uri": "  "},
    ]
    with respx.mock:
        respx.post(SEARCH_URL).mock(return_value=Response(200, json={"results": hits}))
        respx.get(NOTICE_URI_LEI).mock(return_value=Response(200, content=_lei_notice().payload))
        with capture_logs() as captured:
            records = list(ADAPTER.fetch(None, None))
    assert [r.source_url for r in records] == [NOTICE_URI_LEI]
    skipped = [
        e for e in captured if e.get("event") == "ted: search hits without id or uri skipped"
    ]
    assert len(skipped) == 1
    assert skipped[0]["skipped"] == 4


def test_search_response_that_is_not_json_raises():
    with respx.mock:
        respx.post(SEARCH_URL).mock(return_value=Response(200, content=b"not json"))
        with pytest.raises(SourceParseError):
            list(ADAPTER.fetch(None, None))


def test_search_response_without_results_list_raises():
    with respx.mock:
        respx.post(SEARCH_URL).mock(return_value=Response(200, json={"results": "nope"}))
        with pytest.raises(SourceParseError):
            list(ADAPTER.fetch(None, None))


def test_normalize_lei_notice_produces_expected_records():
    normalized = ADAPTER.normalize(_lei_notice())

    assert normalized.kind == "structured"
    assert normalized.entities == []
    assert normalized.lookup_rows == []
    assert normalized.content_hash == hashlib.sha256(_lei_notice().payload).hexdigest()
    assert len(normalized.assertions) == 5

    expected = {
        (
            "BUYER_OF",
            f"ted_buyer_id:{BUYER_KOELN_DIGEST}",
            "ted_notice_id:123456-2025",
            "2025-01-15T00:00:00+00:00",
        ),
        (
            "ABOUT_TOPIC",
            "ted_notice_id:123456-2025",
            "topic:CPV:45221110",
            "2025-01-15T00:00:00+00:00",
        ),
        (
            "AWARDED_TO",
            "ted_notice_id:123456-2025",
            f"lei:{LEI_CONTRACTOR}",
            "2025-04-01T00:00:00+00:00",
        ),
        (
            "HEADQUARTERED_IN",
            f"ted_buyer_id:{BUYER_KOELN_DIGEST}",
            f"coordinate_hash:{KOELN_ADDR_HASH}",
            "2025-01-15T00:00:00+00:00",
        ),
        (
            "LOCATED_IN",
            f"coordinate_hash:{KOELN_ADDR_HASH}",
            "nuts_code:DEA23",
            "2025-01-15T00:00:00+00:00",
        ),
    }
    got = {
        (a.relation, a.subject.entity_id, a.object.entity_id, a.validity.valid_from.isoformat())
        for a in normalized.assertions
    }
    assert got == expected

    by_triple = {
        (a.relation, a.subject.entity_id, a.object.entity_id): a for a in normalized.assertions
    }

    contract = by_triple[("ABOUT_TOPIC", "ted_notice_id:123456-2025", "topic:CPV:45221110")].subject
    assert contract.type == "Contract"
    assert contract.label == "Sanierung Rathausbrücke Köln"
    assert contract.deterministic_key == ("ted_notice_id", "123456-2025")

    buyer = by_triple[
        ("BUYER_OF", f"ted_buyer_id:{BUYER_KOELN_DIGEST}", "ted_notice_id:123456-2025")
    ].subject
    assert buyer.type == "PublicBody"
    assert buyer.label == "Stadt Köln"
    assert buyer.deterministic_key == ("ted_buyer_id", BUYER_KOELN_DIGEST)

    topic = by_triple[("ABOUT_TOPIC", "ted_notice_id:123456-2025", "topic:CPV:45221110")].object
    assert topic.type == "Topic"
    assert topic.label == "45221110"
    assert topic.deterministic_key == ("code", "45221110")

    corporation = by_triple[
        ("AWARDED_TO", "ted_notice_id:123456-2025", f"lei:{LEI_CONTRACTOR}")
    ].object
    assert corporation.type == "Corporation"
    assert corporation.label == "Bau AG Beispiel"
    assert corporation.deterministic_key == ("lei", LEI_CONTRACTOR)

    hq_location = by_triple[
        (
            "HEADQUARTERED_IN",
            f"ted_buyer_id:{BUYER_KOELN_DIGEST}",
            f"coordinate_hash:{KOELN_ADDR_HASH}",
        )
    ].object
    assert hq_location.type == "Location"
    assert hq_location.label == "Köln"
    assert hq_location.deterministic_key == ("coordinate_hash", KOELN_ADDR_HASH)

    region = by_triple[
        ("LOCATED_IN", f"coordinate_hash:{KOELN_ADDR_HASH}", "nuts_code:DEA23")
    ].object
    assert region.type == "AdministrativeRegion"
    assert region.label == "DEA23"
    assert region.deterministic_key == ("nuts_code", "DEA23")

    for assertion in normalized.assertions:
        assert assertion.validity.valid_to is None
        assert assertion.validity.recorded_at == NOW
        assert assertion.provenance.source_id == "ted"
        assert assertion.provenance.source_trust == 1.00
        assert assertion.provenance.confidence == 1.0
        assert assertion.provenance.ontology_version is not None


def test_name_only_notice_uses_hash_identity_and_lookup_region():
    def lookup(country: str, postal: str) -> str | None:
        if (country, postal) == ("DE", "10115"):
            return "DE300"
        return None

    normalized = ADAPTER.normalize(_name_only_notice(), postal_lookup=lookup)

    assert len(normalized.assertions) == 6

    awarded = [a for a in normalized.assertions if a.relation == "AWARDED_TO"]
    assert len(awarded) == 1
    assert awarded[0].object.entity_id == f"corporation:{NAME_ONLY_DIGEST}"
    assert awarded[0].object.label == "Druckerei Beispiel GmbH"
    assert awarded[0].object.type == "Corporation"
    assert awarded[0].object.deterministic_key is None
    # No AWARD_DATE in the AWARDED_CONTRACT variant: the publication date
    # stands in, and the AWARDED_CONTRACT element name parses too.
    assert awarded[0].validity.valid_from == datetime(2025, 2, 20, tzinfo=UTC)

    topics = [a for a in normalized.assertions if a.relation == "ABOUT_TOPIC"]
    assert {a.object.entity_id for a in topics} == {"topic:CPV:30199730", "topic:CPV:30199763"}

    located = [a for a in normalized.assertions if a.relation == "LOCATED_IN"]
    assert len(located) == 1
    assert located[0].subject.entity_id == f"coordinate_hash:{BERLIN_ADDR_HASH}"
    assert located[0].object.entity_id == "nuts_code:DE300"
    assert located[0].object.deterministic_key == ("nuts_code", "DE300")

    hq = [a for a in normalized.assertions if a.relation == "HEADQUARTERED_IN"]
    assert len(hq) == 1
    assert hq[0].subject.entity_id == f"ted_buyer_id:{BUYER_BERLIN_DIGEST}"


def test_buyer_nuts_preferred_over_postal_lookup():
    def lookup(country: str, postal: str) -> str | None:
        return "DE111"  # would win if consulted

    with capture_logs() as captured:
        normalized = ADAPTER.normalize(_lei_notice(), postal_lookup=lookup)

    located = [a for a in normalized.assertions if a.relation == "LOCATED_IN"]
    assert len(located) == 1
    assert located[0].object.entity_id == "nuts_code:DEA23"
    # A notice with its own BUYER_NUTS is not a missing region.
    summary = [
        e
        for e in captured
        if e.get("event") == "gisco correspondence missing for N addresses; region unassigned"
    ]
    assert summary == []


def test_postal_lookup_none_means_no_located_in_and_summary_logged():
    with capture_logs() as captured:
        normalized = ADAPTER.normalize(_name_only_notice())

    assert all(a.relation != "LOCATED_IN" for a in normalized.assertions)
    # BUYER_OF, two ABOUT_TOPIC, AWARDED_TO, HEADQUARTERED_IN — the region
    # is the only thing the missing lookup costs.
    assert len(normalized.assertions) == 5
    summary = [
        e
        for e in captured
        if e.get("event") == "gisco correspondence missing for N addresses; region unassigned"
    ]
    assert len(summary) == 1
    assert summary[0]["addresses"] == 1


def test_assertion_ids_are_deterministic_across_calls():
    for record in (_lei_notice(), _name_only_notice()):
        first = [a.assertion_id for a in ADAPTER.normalize(record).assertions]
        second = [a.assertion_id for a in ADAPTER.normalize(record).assertions]
        assert first == second
        assert len(set(first)) == len(first)


def test_malformed_xml_raises_source_parse_error():
    try:
        ADAPTER.normalize(_notice_record(_lei_notice().payload[:40], NOTICE_URI_LEI))
    except SourceParseError:
        pass
    else:
        raise AssertionError("expected SourceParseError")


def test_notice_without_notice_id_is_skipped_and_counted():
    payload = b"<TED_EXPORT><DT_PUBLISH>20250301</DT_PUBLISH></TED_EXPORT>"
    with capture_logs() as captured:
        normalized = ADAPTER.normalize(_notice_record(payload, "https://ted.europa.eu/notices/x"))

    assert normalized.kind == "structured"
    assert normalized.assertions == []
    assert normalized.content_hash == hashlib.sha256(payload).hexdigest()
    skipped = [e for e in captured if e.get("event") == "ted: notice without NO_DOC_OJS skipped"]
    assert len(skipped) == 1


def test_notice_without_buyer_still_normalizes_contract():
    payload = b"""<TED_EXPORT>
      <NO_DOC_OJS>999999-2025</NO_DOC_OJS>
      <DT_PUBLISH>20250301</DT_PUBLISH>
      <TITLE><VALUE>Rahmenvereinbarung IT-Dienstleistungen</VALUE></TITLE>
      <OBJECT_CONTRACT><CPV_MAIN><CPV_CODE CODE="72000000"/></CPV_MAIN></OBJECT_CONTRACT>
      <AWARD_CONTRACT><AWARD_DATE><VALUE>20250501</VALUE></AWARD_DATE>
        <CONTRACTORS><CONTRACTOR><ADDRESS_CONTRACTOR>
          <OFFICIALNAME>IT Services Beispiel GmbH</OFFICIALNAME>
          <LEI>549300TEST0000000002</LEI>
        </ADDRESS_CONTRACTOR></CONTRACTOR></CONTRACTORS>
      </AWARD_CONTRACT>
    </TED_EXPORT>"""
    with capture_logs() as captured:
        normalized = ADAPTER.normalize(_notice_record(payload, "https://ted.europa.eu/notices/x"))

    assert {
        (a.relation, a.subject.entity_id, a.object.entity_id) for a in normalized.assertions
    } == {
        ("ABOUT_TOPIC", "ted_notice_id:999999-2025", "topic:CPV:72000000"),
        ("AWARDED_TO", "ted_notice_id:999999-2025", "lei:549300TEST0000000002"),
    }
    summary = [e for e in captured if e.get("event") == "ted: notice normalized"][0]
    assert summary["no_buyer"] == 1


def test_notice_without_publish_date_falls_back_to_fetched_at():
    payload = b"""<TED_EXPORT>
      <NO_DOC_OJS>777777-2025</NO_DOC_OJS>
      <TITLE><VALUE>Ohne Datum</VALUE></TITLE>
      <OBJECT_CONTRACT><CPV_MAIN><CPV_CODE CODE="71000000"/></CPV_MAIN></OBJECT_CONTRACT>
    </TED_EXPORT>"""
    with capture_logs() as captured:
        normalized = ADAPTER.normalize(_notice_record(payload, "https://ted.europa.eu/notices/x"))

    assert len(normalized.assertions) == 1
    assert normalized.assertions[0].validity.valid_from == NOW
    summary = [e for e in captured if e.get("event") == "ted: notice normalized"][0]
    assert summary["date_fallback"] == 1


def test_cpv_code_without_code_attribute_skipped_and_counted():
    payload = b"""<TED_EXPORT>
      <NO_DOC_OJS>666666-2025</NO_DOC_OJS>
      <DT_PUBLISH>20250301</DT_PUBLISH>
      <OBJECT_CONTRACT><CPV_MAIN><CPV_CODE/><CPV_CODE CODE="72000000"/></CPV_MAIN></OBJECT_CONTRACT>
    </TED_EXPORT>"""
    with capture_logs() as captured:
        normalized = ADAPTER.normalize(_notice_record(payload, "https://ted.europa.eu/notices/x"))

    assert [a.relation for a in normalized.assertions] == ["ABOUT_TOPIC"]
    summary = [e for e in captured if e.get("event") == "ted: notice normalized"][0]
    assert summary["skipped_cpv_code"] == 1


def test_contractor_without_officialname_skipped_and_counted():
    payload = b"""<TED_EXPORT>
      <NO_DOC_OJS>555555-2025</NO_DOC_OJS>
      <DT_PUBLISH>20250301</DT_PUBLISH>
      <AWARD_CONTRACT><AWARD_DATE><VALUE>20250501</VALUE></AWARD_DATE>
        <CONTRACTORS><CONTRACTOR><ADDRESS_CONTRACTOR>
          <LEI>549300TEST0000000003</LEI>
        </ADDRESS_CONTRACTOR></CONTRACTOR>
        <CONTRACTOR><ADDRESS_CONTRACTOR>
          <OFFICIALNAME>Benannte GmbH</OFFICIALNAME>
        </ADDRESS_CONTRACTOR></CONTRACTOR></CONTRACTORS>
      </AWARD_CONTRACT>
    </TED_EXPORT>"""
    with capture_logs() as captured:
        normalized = ADAPTER.normalize(_notice_record(payload, "https://ted.europa.eu/notices/x"))

    awarded = [a for a in normalized.assertions if a.relation == "AWARDED_TO"]
    assert len(awarded) == 1
    assert awarded[0].object.label == "Benannte GmbH"
    summary = [e for e in captured if e.get("event") == "ted: notice normalized"][0]
    assert summary["skipped_contractor_name"] == 1


def test_buyer_without_officialname_skipped_and_counted():
    payload = b"""<TED_EXPORT>
      <NO_DOC_OJS>444444-2025</NO_DOC_OJS>
      <DT_PUBLISH>20250301</DT_PUBLISH>
      <CONTRACTING_BODY><ADDRESS_CONTRACTING_BODY>
        <POSTAL_CODE>10115</POSTAL_CODE>
      </ADDRESS_CONTRACTING_BODY></CONTRACTING_BODY>
      <OBJECT_CONTRACT><CPV_MAIN><CPV_CODE CODE="72000000"/></CPV_MAIN></OBJECT_CONTRACT>
    </TED_EXPORT>"""
    with capture_logs() as captured:
        normalized = ADAPTER.normalize(_notice_record(payload, "https://ted.europa.eu/notices/x"))

    assert all(a.relation != "BUYER_OF" for a in normalized.assertions)
    skipped = [
        e
        for e in captured
        if e.get("event") == "ted: buyer without OFFICIALNAME; buyer assertions skipped"
    ]
    assert len(skipped) == 1
    summary = [e for e in captured if e.get("event") == "ted: notice normalized"][0]
    assert summary["no_buyer"] == 1


def test_contracting_body_without_address_leaves_buyer_unassigned():
    payload = b"""<TED_EXPORT>
      <NO_DOC_OJS>333333-2025</NO_DOC_OJS>
      <DT_PUBLISH>20250301</DT_PUBLISH>
      <CONTRACTING_BODY><OFFICIALNAME>Namenlos</OFFICIALNAME></CONTRACTING_BODY>
      <OBJECT_CONTRACT><CPV_MAIN><CPV_CODE CODE="72000000"/></CPV_MAIN></OBJECT_CONTRACT>
    </TED_EXPORT>"""
    with capture_logs() as captured:
        normalized = ADAPTER.normalize(_notice_record(payload, "https://ted.europa.eu/notices/x"))

    assert all(a.relation != "BUYER_OF" for a in normalized.assertions)
    skipped = [
        e for e in captured if e.get("event") == "ted: notice without CONTRACTING_BODY buyer"
    ]
    assert len(skipped) == 1


def test_buyer_without_country_or_postal_region_unassigned():
    payload = b"""<TED_EXPORT>
      <NO_DOC_OJS>222222-2025</NO_DOC_OJS>
      <DT_PUBLISH>20250301</DT_PUBLISH>
      <CONTRACTING_BODY><ADDRESS_CONTRACTING_BODY>
        <OFFICIALNAME>Stadt Ohne Plz</OFFICIALNAME><TOWN>Irgendwo</TOWN>
      </ADDRESS_CONTRACTING_BODY></CONTRACTING_BODY>
      <OBJECT_CONTRACT><CPV_MAIN><CPV_CODE CODE="72000000"/></CPV_MAIN></OBJECT_CONTRACT>
    </TED_EXPORT>"""
    with capture_logs() as captured:
        normalized = ADAPTER.normalize(_notice_record(payload, "https://ted.europa.eu/notices/x"))

    relations = {a.relation for a in normalized.assertions}
    assert relations == {"ABOUT_TOPIC", "BUYER_OF"}
    summary = [e for e in captured if e.get("event") == "ted: notice normalized"][0]
    assert summary["no_buyer_address"] == 1
    assert summary["missing_regions"] == 0


def test_unparseable_award_date_falls_back_to_publication_date():
    payload = b"""<TED_EXPORT>
      <NO_DOC_OJS>111111-2025</NO_DOC_OJS>
      <DT_PUBLISH>20250301</DT_PUBLISH>
      <AWARD_CONTRACT><AWARD_DATE><VALUE>not-a-date</VALUE></AWARD_DATE>
        <CONTRACTORS><CONTRACTOR><ADDRESS_CONTRACTOR>
          <OFFICIALNAME>Benannte GmbH</OFFICIALNAME>
        </ADDRESS_CONTRACTOR></CONTRACTOR></CONTRACTORS>
      </AWARD_CONTRACT>
    </TED_EXPORT>"""
    with capture_logs() as captured:
        normalized = ADAPTER.normalize(_notice_record(payload, "https://ted.europa.eu/notices/x"))

    awarded = [a for a in normalized.assertions if a.relation == "AWARDED_TO"]
    assert awarded[0].validity.valid_from == datetime(2025, 3, 1, tzinfo=UTC)
    summary = [e for e in captured if e.get("event") == "ted: notice normalized"][0]
    assert summary["date_fallback"] == 1


def test_buyer_without_address_element_is_counted(monkeypatch):
    import limes.sources.ted as ted_module

    real_buyer = ted_module._buyer

    def buyer_without_address(root):
        buyer, _ = real_buyer(root)
        return buyer, None

    # `_buyer` can only return (None, None) or (None, address) or (buyer,
    # address): the no-address-with-buyer branch of normalize is unreachable
    # through payloads, so the helper is patched to force it.
    monkeypatch.setattr(ted_module, "_buyer", buyer_without_address)
    with capture_logs() as captured:
        normalized = ADAPTER.normalize(_lei_notice())

    assert any(a.relation == "BUYER_OF" for a in normalized.assertions)
    summary = [e for e in captured if e.get("event") == "ted: notice normalized"][0]
    assert summary["no_buyer_address"] == 1


def test_namespaced_cpv_attribute_read_by_local_name():
    payload = b"""<TED_EXPORT xmlns:z="urn:test">
      <NO_DOC_OJS>999000-2025</NO_DOC_OJS>
      <DT_PUBLISH>20250301</DT_PUBLISH>
      <OBJECT_CONTRACT><CPV_MAIN><CPV_CODE z:CODE="72000000"/></CPV_MAIN></OBJECT_CONTRACT>
    </TED_EXPORT>"""
    normalized = ADAPTER.normalize(_notice_record(payload, "https://ted.europa.eu/notices/x"))
    assert {(a.relation, a.object.entity_id) for a in normalized.assertions} == {
        ("ABOUT_TOPIC", "topic:CPV:72000000")
    }
