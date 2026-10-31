# tests/unit/test_transparency_register_adapter.py | v1.0.0 | introduced by WP-15
"""EU Transparency Register adapter tests per Technical Specification §8.5.

The fixture export.xml under tests/fixtures/transparency_register/ is a
recorded export payload; the download URL is pinned with respx — no live
network. Asserts the exact expected record set: deterministic keys
(`transparency_register_id`, the shared `code` topic convention), name-hashed
person identities, labels, relation names, source attribution
(`source_id="transparency_register"`, `source_trust=1.00`), deterministic
assertion ids, and parse errors on malformed payloads.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
import respx
from httpx import Response
from structlog.testing import capture_logs

from limes.errors import SourceParseError
from limes.sources.transparency_register import EXPORT_URL, TransparencyRegisterAdapter
from limes.types import RawRecord

FIXTURES = __import__("pathlib").Path(__file__).parents[1] / "fixtures" / "transparency_register"
NOW = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)

ADAPTER = TransparencyRegisterAdapter()

GROUP_ID = "123456789012-34"
HEADLESS_GROUP_ID = "987654321098-76"

# The same digests hash_entity_id("person", ...) produces: 32 hex chars of
# SHA-256 over the pipe-joined parts, under the "person" namespace.
HEAD_HASH = hashlib.sha256(b"Erna|Mustermann").hexdigest()[:32]
OFFICIAL_HASH = hashlib.sha256(b"Anna Kowalski").hexdigest()[:32]


def _record() -> RawRecord:
    return RawRecord(
        payload=(FIXTURES / "export.xml").read_bytes(),
        content_type="application/xml",
        source_url=EXPORT_URL,
        fetched_at=NOW,
    )


def test_fetch_yields_one_record_via_respx():
    with respx.mock:
        respx.get(EXPORT_URL).mock(return_value=Response(200, content=_record().payload))
        records = list(ADAPTER.fetch(None, None))
    assert [r.source_url for r in records] == [EXPORT_URL]
    assert all(r.content_type == "application/xml" for r in records)
    assert all(r.fetched_at.tzinfo is not None for r in records)


def test_normalize_produces_expected_records():
    normalized = ADAPTER.normalize(_record())

    assert normalized.kind == "structured"
    assert normalized.entities == []
    assert normalized.lookup_rows == []
    assert normalized.content_hash == hashlib.sha256(_record().payload).hexdigest()
    assert len(normalized.assertions) == 4

    by_triple = {
        (a.relation, a.subject.entity_id, a.object.entity_id): a for a in normalized.assertions
    }

    group = f"transparency_register_id:{GROUP_ID}"
    member_of = by_triple[("MEMBER_OF", f"person:{HEAD_HASH}", group)]
    assert member_of.subject.type == "Person"
    assert member_of.subject.label == "Erna Mustermann"
    assert member_of.subject.deterministic_key is None
    assert member_of.object.type == "InterestGroup"
    assert member_of.object.label == "Acme Lobby GmbH"
    assert member_of.object.deterministic_key == ("transparency_register_id", GROUP_ID)
    assert member_of.validity.valid_from == datetime(2021, 6, 11, tzinfo=UTC)

    trade = by_triple[("LOBBIES_FOR", group, "topic:EU_TR:10")]
    assert trade.subject.label == "Acme Lobby GmbH"
    assert trade.object.type == "Topic"
    assert trade.object.label == "Trade"
    assert trade.object.deterministic_key == ("code", "10")
    assert trade.validity.valid_from == NOW

    environment = by_triple[("LOBBIES_FOR", group, "topic:EU_TR:20")]
    assert environment.object.label == "Environment"
    assert environment.object.deterministic_key == ("code", "20")

    met_with = by_triple[("MET_WITH", group, f"person:{OFFICIAL_HASH}")]
    assert met_with.object.type == "Person"
    assert met_with.object.label == "Anna Kowalski"
    assert met_with.object.deterministic_key is None
    assert met_with.validity.valid_from == datetime(2023, 6, 13, tzinfo=UTC)

    for assertion in normalized.assertions:
        assert assertion.validity.recorded_at == NOW
        assert assertion.validity.valid_to is None
        assert assertion.provenance.source_id == "transparency_register"
        assert assertion.provenance.source_trust == 1.00
        assert assertion.provenance.confidence == 1.0
        assert assertion.provenance.ontology_version is not None


def test_headless_interestless_organisation_emits_nothing():
    normalized = ADAPTER.normalize(_record())
    ids = [a.subject.entity_id for a in normalized.assertions]
    ids += [a.object.entity_id for a in normalized.assertions]
    assert f"transparency_register_id:{HEADLESS_GROUP_ID}" not in ids


def test_organisation_without_id_skipped_and_counted():
    with capture_logs() as captured:
        normalized = ADAPTER.normalize(_record())
    skipped = [
        e
        for e in captured
        if e.get("event") == "transparency_register: organisation without id skipped"
    ]
    assert len(skipped) == 1
    summaries = [
        e for e in captured if e.get("event") == "transparency_register: export normalized"
    ]
    assert len(summaries) == 1
    summary = summaries[0]
    assert summary["organisations"] == 3
    assert summary["organisations_skipped_no_id"] == 1
    assert summary["organisations_skipped_no_name"] == 0
    assert summary["persons_indexed"] == 1
    assert summary["head_refs_unmatched"] == 0
    assert summary["member_of_assertions"] == 1
    assert summary["interests"] == 2
    assert summary["lobbies_for_assertions"] == 2
    assert summary["meetings"] == 1
    assert summary["met_with_assertions"] == 1
    # The headless organisation has no EntryDate, so its membership date
    # falls back to the fetch instant and is counted.
    assert summary["date_fallbacks"] == 1
    ids = [a.subject.entity_id for a in normalized.assertions]
    ids += [a.object.entity_id for a in normalized.assertions]
    groups = {i for i in ids if i.startswith("transparency_register_id:")}
    assert groups == {f"transparency_register_id:{GROUP_ID}"}


def test_assertion_ids_are_deterministic_across_calls():
    first = [a.assertion_id for a in ADAPTER.normalize(_record()).assertions]
    second = [a.assertion_id for a in ADAPTER.normalize(_record()).assertions]
    assert first == second
    assert len(set(first)) == len(first)


def test_non_xml_payload_raises_source_parse_error():
    record = _record()
    record.payload = b"this is not xml"
    try:
        ADAPTER.normalize(record)
    except SourceParseError:
        pass
    else:
        raise AssertionError("expected SourceParseError")


def test_wrong_root_raises_source_parse_error():
    record = _record()
    record.payload = b"<?xml version='1.0'?><SomethingElse/>"
    try:
        ADAPTER.normalize(record)
    except SourceParseError:
        pass
    else:
        raise AssertionError("expected SourceParseError")


_SKIPPED_EXPORT = """<?xml version="1.0" encoding="UTF-8"?>
<Templates>
  <Person/>
  <Person id="p-bad"/>
  <Person id="p-noname">
    <PersonName><FirstName>Nur</FirstName></PersonName>
  </Person>
  <Person id="p-good">
    <PersonName><FirstName>Erna</FirstName><FamilyName>Mustermann</FamilyName></PersonName>
  </Person>
  <Organisation id="org-good">
    <OrganisationName><TransliteratedName>Gute GmbH</TransliteratedName></OrganisationName>
    <EntryDate>2021-06-11</EntryDate>
    <Head><PersonRef id="p-good"/></Head>
    <Interests>
      <Interest><Code>10</Code><Label>Trade</Label></Interest>
      <Interest><Code>20</Code></Interest>
      <Interest><Label>Ohne Code</Label></Interest>
    </Interests>
    <Meetings>
      <Meeting><Target>Anna Kowalski</Target><Date>13/06/2023</Date></Meeting>
      <Meeting><Date>13/06/2023</Date></Meeting>
      <Meeting><Target>Bernd Beispiel</Target><Date>not-a-date</Date></Meeting>
    </Meetings>
  </Organisation>
  <Organisation id="org-no-name">
    <OrganisationName></OrganisationName>
  </Organisation>
  <Organisation id="org-unmatched-head">
    <OrganisationName><TransliteratedName>Ohne Kopf</TransliteratedName></OrganisationName>
    <Head><PersonRef id="p-missing"/></Head>
  </Organisation>
</Templates>
"""


def test_skipped_facets_are_counted_by_reason():
    record = RawRecord(
        payload=_SKIPPED_EXPORT.encode("utf-8"),
        content_type="application/xml",
        source_url=EXPORT_URL,
        fetched_at=NOW,
    )
    with capture_logs() as captured:
        normalized = ADAPTER.normalize(record)

    assert len(normalized.assertions) == 5  # 1 MEMBER_OF + 2 LOBBIES_FOR + 2 MET_WITH
    summary = [e for e in captured if e.get("event") == "transparency_register: export normalized"][
        0
    ]
    assert summary["organisations"] == 3
    assert summary["organisations_skipped_no_id"] == 0
    assert summary["organisations_skipped_no_name"] == 1
    assert summary["persons_indexed"] == 1
    assert summary["persons_skipped_no_id"] == 1
    assert summary["persons_skipped_no_name"] == 2
    assert summary["head_persons"] == 2
    assert summary["head_refs_unmatched"] == 1
    assert summary["member_of_assertions"] == 1
    assert summary["interests"] == 3
    assert summary["interests_skipped_no_code"] == 1
    assert summary["interest_labels_fallback"] == 1
    assert summary["lobbies_for_assertions"] == 2
    assert summary["meetings"] == 3
    assert summary["meetings_skipped_no_target"] == 1
    assert summary["met_with_assertions"] == 2
    assert summary["date_fallbacks"] == 2  # the unmatched-head org and Bernd's meeting

    label_fallbacks = [
        e
        for e in captured
        if e.get("event") == "transparency_register: interest without label; code used as label"
    ]
    assert len(label_fallbacks) == 1

    met = [a for a in normalized.assertions if a.relation == "MET_WITH"]
    by_label = {a.object.label: a.validity.valid_from for a in met}
    assert by_label["Anna Kowalski"] == datetime(2023, 6, 13, tzinfo=UTC)
    assert by_label["Bernd Beispiel"] == NOW


@pytest.mark.parametrize("bad", [b"&#2;", b"&#x02;", b"\x02"])
def test_current_export_repairs_control_but_keeps_original_identity(bad):
    from limes.sources.base import payload_hash

    payload = (
        b"<ListOfIRPublicDetail><exportDate>2026-10-30</exportDate><numberOfIR>1</numberOfIR>"
        b"<interestRepresentative><identificationCode>TEST</identificationCode>"
        b"<originalName>Alpha" + bad + b"Beta</originalName></interestRepresentative>"
        b"</ListOfIRPublicDetail>"
    )
    record = RawRecord(payload=payload, content_type="application/xml", source_url=EXPORT_URL,
                       fetched_at=NOW)
    result = TransparencyRegisterAdapter().normalize(record)
    assert result.entities[0].label == "Alpha Beta"
    assert result.content_hash == payload_hash(payload)
    assert record.payload == payload
    with pytest.raises(SourceParseError, match="incomplete export"):
        TransparencyRegisterAdapter().normalize(record.model_copy(update={
            "payload": payload.replace(b"<numberOfIR>1", b"<numberOfIR>2")
        }))


def test_control_repair_does_not_recover_structure_or_rewrite_cdata():
    from limes.sources.transparency_register import _repair_xml_controls

    assert _repair_xml_controls(b"<x><![CDATA[&#2;]]><!-- &#2; -->&#2;</x>") == (
        b"<x><![CDATA[&#2;]]><!-- &#2; --> </x>"
    )
    record = RawRecord(payload=b"<Templates><broken>&#2;</Templates>",
                       content_type="application/xml", source_url=EXPORT_URL, fetched_at=NOW)
    with pytest.raises(SourceParseError, match="not parseable XML"):
        TransparencyRegisterAdapter().normalize(record)
