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

from limes.errors import SourceFetchError, SourceParseError
from limes.sources.base import hash_entity_id
from limes.sources.bundestag_dip import PERSON_URL, WAHLPERIODE_STARTS, BundestagDipAdapter
from limes.types import RawRecord

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
    assert "f.known" not in params
    assert "apikey" not in params
    assert "f.aktualisiert" not in params


def test_fetch_sends_apikey_when_configured():
    adapter = BundestagDipAdapter(api_key="operator-secret-key")
    with respx.mock:
        route = respx.get(PERSON_URL).mock(return_value=Response(200, content=_payload()))
        list(adapter.fetch(None, None))
    params = route.calls[0].request.url.params
    assert "apikey" not in params
    assert route.calls[0].request.headers["Authorization"] == "ApiKey operator-secret-key"
    assert "f.known" not in params


def test_current_person_snapshot_does_not_filter_internal_update_dates():
    since = datetime(2025, 1, 1, tzinfo=UTC)
    until = datetime(2025, 12, 31, tzinfo=UTC)
    with respx.mock:
        route = respx.get(PERSON_URL).mock(return_value=Response(200, content=_payload()))
        list(ADAPTER.fetch(since, until))
    assert "f.aktualisiert.start" not in route.calls[0].request.url.params
    assert "f.aktualisiert.end" not in route.calls[0].request.url.params


def test_fetch_401_raises_source_fetch_error():
    with respx.mock:
        respx.get(PERSON_URL).mock(return_value=Response(401, content=b"unauthorized"))
        with pytest.raises(SourceFetchError):
            list(ADAPTER.fetch(None, None))


def test_normalize_preserves_ids_and_corrects_historical_semantics():
    normalized = ADAPTER.normalize(_record())
    assert normalized.kind == "structured"
    assert normalized.content_hash == hashlib.sha256(_payload()).hexdigest()
    assert {e.entity_id for e in normalized.entities} == {PERSON_1, PERSON_2, PERSON_3}
    participation = [a for a in normalized.assertions if a.relation == "PARTICIPATED_IN_TERM"]
    assert {(a.subject.entity_id, a.object.entity_id) for a in participation} == {
        (PERSON_1, _office_id(20)),
        (PERSON_1, _office_id(21)),
        (PERSON_2, _office_id(19)),
    }
    offices = {a.object.entity_id: a.object for a in participation}
    assert offices[_office_id(20)].deterministic_key[0] == "office_key"
    assert offices[_office_id(20)].deterministic_key != offices[_office_id(21)].deterministic_key
    at = [a for a in normalized.assertions if a.relation == "OFFICE_AT"]
    assert all(a.object.entity_id == "institution_id:DE:bt" for a in at)
    groups = [a for a in normalized.assertions if a.relation == "GROUP_EVIDENCE"]
    assert [(a.subject.entity_id, a.object.label) for a in groups] == [(PERSON_2, "CDU/CSU")]
    assert all(a.object.type != "PoliticalParty" for a in normalized.assertions)
    assert not any(a.relation in ("MEMBER_OF", "HOLDS_OFFICE") for a in normalized.assertions)
    assert all(a.validity.valid_from == NOW for a in normalized.assertions)
    assert all(
        a.provenance.validity_basis == "historical_term_reference" for a in normalized.assertions
    )


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


def test_unknown_wahlperiode_retains_evidence_without_inventing_dates():
    payload = json.dumps(
        {
            "documents": [
                {"id": 42, "vorname": "Erika", "nachname": "Mustermann", "wahlperiode": [25]}
            ]
        }
    ).encode()
    record = _record().model_copy(update={"payload": payload})
    normalized = ADAPTER.normalize(record)
    assert normalized.errors == 0
    assert {a.relation for a in normalized.assertions} == {"PARTICIPATED_IN_TERM", "OFFICE_AT"}
    assert all(a.validity.valid_from == NOW for a in normalized.assertions)
    assert all(a.validity.valid_to is None for a in normalized.assertions)


def test_non_object_json_payload_raises_source_parse_error():
    record = RawRecord(
        payload=b"[1, 2, 3]",
        content_type="application/json",
        source_url=PERSON_URL,
        fetched_at=NOW,
    )
    with pytest.raises(SourceParseError):
        ADAPTER.normalize(record)


def test_malformed_and_unnamed_rows_block_checkpoint_without_losing_valid_people():
    payload = json.dumps(
        {
            "documents": [
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
            ]
        }
    ).encode()
    normalized = ADAPTER.normalize(_record().model_copy(update={"payload": payload}))
    assert normalized.errors == 3
    assert [e.entity_id for e in normalized.entities] == ["bundestag_id:9"]
    assert {a.relation for a in normalized.assertions} == {
        "PARTICIPATED_IN_TERM",
        "OFFICE_AT",
        "GROUP_EVIDENCE",
        "GROUP_AT",
    }


def test_dated_live_dip_shape_preserves_name_history_and_update_provenance():
    import gzip

    metadata = json.loads((FIXTURES / "persons-live-2026-11-07.manifest.json").read_text())
    payload = gzip.decompress((FIXTURES / metadata["file"]).read_bytes())
    assert hashlib.sha256(payload).hexdigest() == metadata["sha256"]
    normalized = ADAPTER.normalize(
        RawRecord(
            payload=payload,
            content_type="application/json",
            fetched_at=NOW,
            source_url=metadata["url"],
        )
    )
    assert normalized.errors == 0
    renamed = next(e for e in normalized.entities if e.entity_id == "bundestag_id:8257")
    assert renamed.label == "Jan Krampe"
    assert "Jan Köstering" in renamed.aliases
    assert all(a.provenance.source_recorded_at is not None for a in normalized.assertions)
