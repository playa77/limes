# tests/unit/test_gdelt_adapter.py | v1.0.0 | introduced by WP-21
"""GDELT adapter tests per Doc 2 §8.5.2, §12.3 (WP-21).

The acceptance: GDELT event rows become `Event` nodes with `ACTOR_IN`,
`TARGET_OF`, and `OCCURRED_IN` edges carrying the directional asymmetry
(Doc 1 §5.4 — Actor1 is the actor, Actor2 the target, the action geography
the location), with row-scoped evidence and no synthetic document. The ontology gap —
sovereign states have no Agent type — is exercised by counting untyped actors
instead of inventing a type.
"""

import io
import zipfile
from datetime import UTC, datetime, timedelta

import pytest
import respx
import structlog
from httpx import Response

from limes.errors import SourceParseError
from limes.sources.gdelt import FILE_URL_TEMPLATE, GdeltAdapter, _parse_float
from limes.types import RawRecord

FIXTURES = __import__("pathlib").Path(__file__).parents[1] / "fixtures" / "gdelt"
FETCHED_AT = datetime(2026, 8, 1, 16, 5, 0, tzinfo=UTC)


def _csv_row(**fields: str) -> list[str]:
    from limes.sources.gdelt import _GDELT_FIELDS

    row = [""] * len(_GDELT_FIELDS)
    for name, value in fields.items():
        row[_GDELT_FIELDS.index(name)] = value
    return row


def _zip(payload: bytes, name: str = "20260801154500.export.CSV") -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(name, payload)
    return stream.getvalue()


def _record(payload: bytes | None = None) -> RawRecord:
    return RawRecord(
        payload=_zip((FIXTURES / "events.tsv").read_bytes()) if payload is None else payload,
        content_type="application/zip",
        source_url="https://data.gdeltproject.org/gdeltv2/20260801154500.export.CSV.zip",
        fetched_at=FETCHED_AT,
    )


def test_fetch_yields_one_record_per_15_minute_slot_in_window():
    since = datetime(2026, 8, 1, 15, 31, 0, tzinfo=UTC)
    until = datetime(2026, 8, 1, 16, 0, 0, tzinfo=UTC)
    slot_urls = [
        FILE_URL_TEMPLATE.format(slot=since.replace(minute=45)),
        FILE_URL_TEMPLATE.format(slot=until),
    ]
    with respx.mock:
        for url in slot_urls:
            respx.get(url).mock(return_value=Response(200, content=b"x"))
        records = list(GdeltAdapter().fetch(since, until))
    assert [r.source_url for r in records] == slot_urls
    assert [r.content_type for r in records] == ["application/zip", "application/zip"]


def test_fetch_window_rounds_up_to_next_slot_boundary():
    since = datetime(2026, 8, 1, 15, 0, 0, tzinfo=UTC)
    until = since + timedelta(minutes=45)
    with respx.mock:
        for minutes in (0, 15, 30, 45):
            slot = since + timedelta(minutes=minutes)
            respx.get(FILE_URL_TEMPLATE.format(slot=slot)).mock(
                return_value=Response(200, content=b"x")
            )
        records = list(GdeltAdapter().fetch(since, until))
    assert len(records) == 4


def test_fetch_empty_window_yields_nothing():
    since = datetime(2026, 8, 1, 16, 0, 0, tzinfo=UTC)
    until = datetime(2026, 8, 1, 15, 0, 0, tzinfo=UTC)
    with respx.mock:
        records = list(GdeltAdapter().fetch(since, until))
    assert records == []


def test_normalize_emits_event_with_actor_target_and_location_edges():
    normalized = GdeltAdapter().normalize(_record())
    assert normalized.kind == "structured"
    assertions = normalized.assertions

    by_relation: dict[str, list] = {}
    for assertion in assertions:
        by_relation.setdefault(assertion.relation, []).append(assertion)

    # Directional asymmetry: UNITED STATES is the actor, RUSSIA untyped (a
    # sovereign state has no Agent type), the event occurred in the US.
    actor_in = by_relation["ACTOR_IN"]
    assert len(actor_in) == 2
    assert {a.subject.label for a in actor_in} == {"UNITED STATES", "CHINA"}
    assert all(a.object.type == "Event" for a in actor_in)

    target_of = by_relation["TARGET_OF"]
    assert len(target_of) == 1
    assert target_of[0].subject.label == "VOLKSWAGEN"
    assert target_of[0].object.type == "Event"

    occurred_in = by_relation["OCCURRED_IN"]
    assert len(occurred_in) == 2
    assert {a.object.type for a in occurred_in} == {"Country", "Location"}
    assert all(a.subject.type == "Event" for a in occurred_in)


def test_actor_typing_follows_gdelt_type_codes():
    assertions = GdeltAdapter().normalize(_record()).assertions
    actor_in = [a for a in assertions if a.relation == "ACTOR_IN"]
    types = {a.subject.label: a.subject.type for a in actor_in}
    assert types == {"UNITED STATES": "PublicBody", "CHINA": "PublicBody"}
    target_of = [a for a in assertions if a.relation == "TARGET_OF"]
    assert target_of[0].subject.type == "Corporation"
    # The sovereign state (RUSSIA) and UNKNOWN are skipped, never typed.
    assert all(a.subject.label != "RUSSIA" for a in assertions if a.relation == "ACTOR_IN")


def test_event_identity_encodes_full_identity_and_declared_key():
    assertions = GdeltAdapter().normalize(_record()).assertions
    actor_in = [a for a in assertions if a.relation == "ACTOR_IN"][0]
    event = actor_in.object
    assert event.type == "Event"
    assert event.deterministic_key == ("source_event_id", "1000001")
    assert event.entity_id.startswith("event:")
    # The full identity (id + occurred_at) is encoded in the digest: the same
    # event id on a different date yields a different entity_id.
    from limes.sources.gdelt import _event as event_endpoint

    assert event.entity_id == event_endpoint("1000001", datetime(2026, 7, 31, tzinfo=UTC)).entity_id
    assert event.entity_id != event_endpoint("1000001", datetime(2026, 8, 1, tzinfo=UTC)).entity_id


def test_occurred_in_country_uses_iso2_key():
    assertions = GdeltAdapter().normalize(_record()).assertions
    occurred_in = [a for a in assertions if a.relation == "OCCURRED_IN"]
    country = next(a.object for a in occurred_in if a.object.type == "Country")
    assert country.deterministic_key == ("iso2", "US")
    assert country.entity_id == "iso2:US"
    assert country.label == "United States"


def test_occurred_in_city_uses_coordinate_hash_location():
    assertions = GdeltAdapter().normalize(_record()).assertions
    occurred_in = [a for a in assertions if a.relation == "OCCURRED_IN"]
    location = next(a.object for a in occurred_in if a.object.type == "Location")
    assert location.deterministic_key == ("coordinate_hash", location.entity_id.split(":")[1])
    assert location.label == "Berlin"


def test_export_has_no_synthetic_document():
    assert GdeltAdapter().normalize(_record()).document is None


def test_assertion_ids_are_deterministic_across_calls():
    adapter = GdeltAdapter()
    raw = _record()
    first = [a.assertion_id for a in adapter.normalize(raw).assertions]
    second = [a.assertion_id for a in adapter.normalize(raw).assertions]
    assert first == second


def test_provenance_is_deterministic_with_source_trust():
    assertions = GdeltAdapter().normalize(_record()).assertions
    for assertion in assertions:
        assert assertion.provenance.source_id == "gdelt"
        assert assertion.provenance.source_trust == 0.50
        assert assertion.provenance.confidence == 1.0
        assert assertion.validity.valid_from is not None


def _csv_payload(rows: list[list[str]]) -> bytes:
    return _zip("\n".join("\t".join(row) for row in rows).encode("utf-8"))


def test_rows_without_event_id_or_valid_date_are_skipped_and_counted():
    rows = [
        _csv_row(Actor1Name="kein Event", SQLDATE="20260731"),
        _csv_row(GLOBALEVENTID="2000004", Actor1Name="kurzes Datum", SQLDATE="123"),
        _csv_row(GLOBALEVENTID="2000005", Actor1Name="unmoegliches Datum", SQLDATE="20269999"),
        _csv_row(
            GLOBALEVENTID="2000006",
            SQLDATE="20260731",
            Actor1Name="Bundeswehr",
            Actor1Type1Code="MIL",
            ActionGeo_Type="1",
            ActionGeo_FullName="Germany",
            ActionGeo_CountryCode="GM",
        ),
    ]
    with structlog.testing.capture_logs() as captured:
        normalized = GdeltAdapter().normalize(_record(_csv_payload(rows)))

    assert len(normalized.assertions) == 2  # ACTOR_IN + OCCURRED_IN for the good row
    summary = [e for e in captured if e.get("event") == "gdelt: event file normalized"][0]
    assert summary["events"] == 1
    assert summary["malformed_skipped"] == 3


def test_non_utf8_payload_raises_source_parse_error():
    with pytest.raises(SourceParseError):
        GdeltAdapter().normalize(_record(b"\xff\xfe\x00\x01"))


def test_oversized_csv_field_raises_source_parse_error():
    # A field beyond the csv module's field-size limit makes the reader raise
    # csv.Error — the malformed-CSV branch of the parser.
    rows = [
        _csv_row(GLOBALEVENTID="2000007", SQLDATE="20260731", SOURCEURL="x" * 200_000),
    ]
    with pytest.raises(SourceParseError):
        GdeltAdapter().normalize(_record(_csv_payload(rows)))


def test_action_geo_type_1_with_invalid_country_code_skipped():
    rows = [
        _csv_row(
            GLOBALEVENTID="2000008",
            SQLDATE="20260731",
            Actor1Name="Bundeswehr",
            Actor1Type1Code="MIL",
            ActionGeo_Type="1",
            ActionGeo_FullName="United States of America",
            ActionGeo_CountryCode="USA",
        ),
    ]
    with structlog.testing.capture_logs() as captured:
        normalized = GdeltAdapter().normalize(_record(_csv_payload(rows)))

    assert all(a.relation != "OCCURRED_IN" for a in normalized.assertions)
    summary = [e for e in captured if e.get("event") == "gdelt: event file normalized"][0]
    assert summary["location_skipped"] == 1


def test_action_geo_type_2_with_unparseable_coordinates_skipped():
    rows = [
        _csv_row(
            GLOBALEVENTID="2000009",
            SQLDATE="20260731",
            Actor1Name="Bundeswehr",
            Actor1Type1Code="MIL",
            ActionGeo_Type="2",
            ActionGeo_FullName="Irgendwo",
            ActionGeo_Lat="not-a-number",
            ActionGeo_Long="13.4",
        ),
    ]
    with structlog.testing.capture_logs() as captured:
        normalized = GdeltAdapter().normalize(_record(_csv_payload(rows)))

    assert all(a.relation != "OCCURRED_IN" for a in normalized.assertions)
    summary = [e for e in captured if e.get("event") == "gdelt: event file normalized"][0]
    assert summary["location_skipped"] == 1


def test_parse_float_rejects_non_string():
    # CSV rows always yield strings, so the non-string branch is unreachable
    # through normalize; the helper is called directly with a number.
    assert _parse_float(1.5) is None
