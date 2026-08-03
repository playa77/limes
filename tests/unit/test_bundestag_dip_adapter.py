# tests/unit/test_bundestag_dip_adapter.py | v1.0.0 | introduced by WP-16
"""Bundestag DIP adapter tests per Technical Specification §8.5.2 (WP-16).

The person search response is a recorded fixture (tests/fixtures/bundestag_dip/
persons.json) in the real DIP response shape; `fetch` is pinned with respx —
no live network. Asserts the exact expected record set: deterministic person
keys, hashed party and reified-office ids (body + title + interval), the
temporal validity of HOLDS_OFFICE/OFFICE_AT, MEMBER_OF (Person →
PoliticalParty), source attribution, deterministic assertion ids, the apikey
parameter, the honest 401 surface, and parse errors on malformed payloads.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pytest
import respx
from httpx import Response
from structlog.testing import capture_logs

from limes.errors import SourceFetchError, SourceParseError
from limes.sources.base import hash_entity_id
from limes.sources.bundestag_dip import PERSON_URL, WAHLPERIODE_STARTS, BundestagDipAdapter
from limes.types import EntityEndpoint, RawRecord

FIXTURES = __import__("pathlib").Path(__file__).parents[1] / "fixtures" / "bundestag_dip"
NOW = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)

ADAPTER = BundestagDipAdapter()

PERSON_1 = "bundestag_id:11004755"  # Saskia Weber, SPD, Wahlperioden 20+21
PERSON_2 = "bundestag_id:11003611"  # Martin Fischer, CDU/CSU, Wahlperiode 19
PERSON_3 = "bundestag_id:11005230"  # Julia Becker, no fraktion, no Wahlperiode

SPD = hash_entity_id("politicalparty", "SPD")
CDU_CSU = hash_entity_id("politicalparty", "CDU/CSU")


def _period_start(period: int) -> datetime:
    return datetime.fromisoformat(WAHLPERIODE_STARTS[period]).replace(tzinfo=UTC)


def _office_id(period: int) -> str:
    title = f"Mitglied des Deutschen Bundestages (Wahlperiode {period})"
    return hash_entity_id("office", "BT", title, _period_start(period).isoformat())


def _payload() -> bytes:
    return (FIXTURES / "persons.json").read_bytes()


def _record() -> RawRecord:
    return RawRecord(
        payload=_payload(),
        content_type="application/json",
        source_url=PERSON_URL,
        fetched_at=NOW,
    )


def test_fetch_yields_one_record_via_respx():
    with respx.mock:
        route = respx.get(PERSON_URL).mock(return_value=Response(200, content=_payload()))
        records = list(ADAPTER.fetch(None, None))
    assert len(records) == 1
    record = records[0]
    assert record.payload == _payload()
    assert record.content_type == "application/json"
    assert record.fetched_at.tzinfo is not None
    params = route.calls[0].request.url.params
    assert params["f.known"] == "true"
    assert "apikey" not in params
    assert "f.aktualisiert" not in params


def test_fetch_sends_apikey_when_configured():
    adapter = BundestagDipAdapter(api_key="operator-secret-key")
    with respx.mock:
        route = respx.get(PERSON_URL).mock(return_value=Response(200, content=_payload()))
        list(adapter.fetch(None, None))
    params = route.calls[0].request.url.params
    assert params["apikey"] == "operator-secret-key"
    assert params["f.known"] == "true"


def test_fetch_window_adds_aktualisiert_filter():
    since = datetime(2025, 1, 1, tzinfo=UTC)
    until = datetime(2025, 12, 31, tzinfo=UTC)
    with respx.mock:
        route = respx.get(PERSON_URL).mock(return_value=Response(200, content=_payload()))
        list(ADAPTER.fetch(since, until))
    assert route.calls[0].request.url.params["f.aktualisiert"] == "2025-01-01..2025-12-31"


def test_fetch_401_raises_source_fetch_error():
    with respx.mock:
        respx.get(PERSON_URL).mock(return_value=Response(401, content=b"unauthorized"))
        with pytest.raises(SourceFetchError):
            list(ADAPTER.fetch(None, None))


def test_normalize_produces_exact_expected_records():
    normalized = ADAPTER.normalize(_record())

    assert normalized.kind == "structured"
    assert normalized.lookup_rows == []
    assert normalized.content_hash == hashlib.sha256(_payload()).hexdigest()

    by_triple = {
        (a.subject.entity_id, a.relation, a.object.entity_id): a for a in normalized.assertions
    }
    expected_triples = {
        (PERSON_1, "MEMBER_OF", SPD),
        (PERSON_1, "HOLDS_OFFICE", _office_id(20)),
        (_office_id(20), "OFFICE_AT", SPD),
        (PERSON_1, "HOLDS_OFFICE", _office_id(21)),
        (_office_id(21), "OFFICE_AT", SPD),
        (PERSON_2, "MEMBER_OF", CDU_CSU),
        (PERSON_2, "HOLDS_OFFICE", _office_id(19)),
        (_office_id(19), "OFFICE_AT", CDU_CSU),
    }
    assert set(by_triple) == expected_triples
    assert len(by_triple) == len(normalized.assertions)  # no duplicate triples

    holds_20 = by_triple[(PERSON_1, "HOLDS_OFFICE", _office_id(20))]
    assert holds_20.subject.label == "Saskia Weber"
    assert holds_20.subject.type == "Person"
    assert holds_20.subject.deterministic_key == ("bundestag_id", "11004755")
    office_20 = holds_20.object
    assert office_20.type == "Office"
    assert office_20.deterministic_key == ("body_id", "BT")
    assert office_20.label == "Mitglied des Deutschen Bundestages (Wahlperiode 20)"
    assert office_20.aliases == [office_20.label]
    assert holds_20.validity.valid_from == _period_start(20)
    assert holds_20.validity.valid_to is None

    # The interval is part of the office identity: period 21 is a distinct node.
    assert _office_id(20) != _office_id(21)
    assert by_triple[
        (PERSON_1, "HOLDS_OFFICE", _office_id(21))
    ].validity.valid_from == _period_start(21)

    office_at_20 = by_triple[(_office_id(20), "OFFICE_AT", SPD)]
    assert office_at_20.subject == office_20
    assert office_at_20.object.type == "PoliticalParty"
    assert office_at_20.object.label == "SPD"
    assert office_at_20.validity.valid_from == _period_start(20)
    assert office_at_20.validity.valid_to is None

    membership = by_triple[(PERSON_1, "MEMBER_OF", SPD)]
    assert membership.validity.valid_from == NOW

    holds_19 = by_triple[(PERSON_2, "HOLDS_OFFICE", _office_id(19))]
    assert holds_19.subject.label == "Martin Fischer"
    assert holds_19.validity.valid_from == _period_start(19)
    assert by_triple[(_office_id(19), "OFFICE_AT", CDU_CSU)].object.label == "CDU/CSU"

    for assertion in normalized.assertions:
        assert assertion.provenance.source_id == "bundestag_dip"
        assert assertion.provenance.source_trust == 1.00
        assert assertion.provenance.confidence == 1.0
        assert assertion.provenance.ontology_version is not None
        assert assertion.validity.recorded_at == NOW

    assert normalized.entities == [
        EntityEndpoint(
            entity_id=PERSON_3,
            type="Person",
            label="Julia Becker",
            deterministic_key=("bundestag_id", "11005230"),
        )
    ]


def test_assertion_ids_are_deterministic_across_calls():
    first = [a.assertion_id for a in ADAPTER.normalize(_record()).assertions]
    second = [a.assertion_id for a in ADAPTER.normalize(_record()).assertions]
    assert first == second
    assert len(set(first)) == len(first)


def test_malformed_json_raises_source_parse_error():
    record = RawRecord(
        payload=b"{not json",
        content_type="application/json",
        source_url=PERSON_URL,
        fetched_at=NOW,
    )
    with pytest.raises(SourceParseError):
        ADAPTER.normalize(record)


def test_response_without_rows_list_raises_source_parse_error():
    record = RawRecord(
        payload=json.dumps({"numFound": 0}).encode("utf-8"),
        content_type="application/json",
        source_url=PERSON_URL,
        fetched_at=NOW,
    )
    with pytest.raises(SourceParseError):
        ADAPTER.normalize(record)


def test_skips_are_counted_in_normalize_summary():
    with capture_logs() as captured:
        ADAPTER.normalize(_record())
    summary = [e for e in captured if e.get("event") == "bundestag_dip: person file normalized"]
    assert len(summary) == 1
    assert summary[0]["rows"] == 3
    assert summary[0]["persons"] == 3
    assert summary[0]["memberships"] == 2
    assert summary[0]["holds_office"] == 3
    assert summary[0]["office_at"] == 3
    assert summary[0]["no_fraktion"] == 1
    assert summary[0]["no_wahlperioden"] == 1
    assert summary[0]["unknown_period"] == 0
    assert summary[0]["standalone_persons"] == 1


def test_unknown_wahlperiode_skips_office_assertions_never_invented():
    payload = json.dumps(
        {
            "numFound": 1,
            "start": 0,
            "rows": [
                {
                    "id": 42,
                    "typ": "Person",
                    "vorname": "Erika",
                    "nachname": "Mustermann",
                    "fraktion": "Grüne",
                    "wahlperioden": [25],
                    "geburtsjahr": 1980,
                    "wkrName": None,
                    "verstorben": None,
                }
            ],
            "facets": {},
        }
    ).encode("utf-8")
    record = RawRecord(
        payload=payload,
        content_type="application/json",
        source_url=PERSON_URL,
        fetched_at=NOW,
    )
    with capture_logs() as captured:
        normalized = ADAPTER.normalize(record)
    assert len(normalized.assertions) == 1  # MEMBER_OF only, no invented office
    assert all(a.relation not in ("HOLDS_OFFICE", "OFFICE_AT") for a in normalized.assertions)
    skips = [
        e
        for e in captured
        if e.get("event") == "bundestag_dip: Wahlperiode without a known start skipped"
    ]
    assert len(skips) == 1
    assert skips[0]["period"] == 25


def test_non_object_json_payload_raises_source_parse_error():
    record = RawRecord(
        payload=b"[1, 2, 3]",
        content_type="application/json",
        source_url=PERSON_URL,
        fetched_at=NOW,
    )
    with pytest.raises(SourceParseError):
        ADAPTER.normalize(record)


def test_malformed_and_unnamed_rows_are_skipped_and_counted():
    payload = json.dumps(
        {
            "numFound": 4,
            "start": 0,
            "rows": [
                "not an object",
                {"id": 7},
                {"vorname": "Ohne", "nachname": "Id"},
                {
                    "id": 9,
                    "vorname": "Erika",
                    "nachname": "Mustermann",
                    "fraktion": "Grüne",
                    "wahlperioden": [21],
                },
            ],
            "facets": {},
        }
    ).encode("utf-8")
    record = RawRecord(
        payload=payload,
        content_type="application/json",
        source_url=PERSON_URL,
        fetched_at=NOW,
    )
    with capture_logs() as captured:
        normalized = ADAPTER.normalize(record)

    assert len(normalized.assertions) == 3  # MEMBER_OF + HOLDS_OFFICE + OFFICE_AT
    assert normalized.entities == []
    summary = [e for e in captured if e.get("event") == "bundestag_dip: person file normalized"][0]
    assert summary["rows"] == 4
    assert summary["persons"] == 1
    assert summary["malformed_skipped"] == 1
    assert summary["no_name_skipped"] == 2
