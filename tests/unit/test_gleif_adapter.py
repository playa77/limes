# tests/unit/test_gleif_adapter.py | v1.0.0 | introduced by WP-11
"""GLEIF adapter tests per Technical Specification §8.5.2.

Fixtures are plain CSVs in tests/fixtures/gleif/; the test assembles the zip
archives in memory (io.BytesIO + zipfile.ZipFile) and pins the two golden
copy URLs with respx — no live network. Asserts the exact expected record
set: deterministic keys (`lei`, `coordinate_hash`, `nuts_code`), labels,
relation names, source attribution (`source_id="gleif"`, `source_trust=1.00`),
the postal-lookup behavior, deterministic assertion ids, and parse errors on
malformed payloads.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import UTC, datetime

import respx
from httpx import Response
from structlog.testing import capture_logs

from limes.errors import SourceParseError
from limes.sources.gleif import (
    PUBLICATIONS_URL,
    GleifAdapter,
)
from limes.types import EntityEndpoint, RawRecord

FIXTURES = __import__("pathlib").Path(__file__).parents[1] / "fixtures" / "gleif"
NOW = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)

ENTITY_ZIP_URL = "https://goldencopy.gleif.org/storage/golden-copy-files/test-lei2.csv.zip"
RELATIONSHIP_ZIP_URL = "https://goldencopy.gleif.org/storage/golden-copy-files/test-rr.csv.zip"
ADAPTER = GleifAdapter()

LEI_DE = "5493000TEST000000001"  # Beispiel AG, Stuttgart (DE)
LEI_FI = "5493000TEST000000002"  # Esimerkki Oyj, Helsinki (FI)
LEI_NL = "5493000TEST000000003"  # Standalone B.V., no HQ address
LEI_LAPSED = "5493000TEST000000004"  # Alte GmbH, LAPSED

STUTTGART_HASH = hashlib.sha256(b"DE|70173|Stuttgart").hexdigest()
HELSINKI_HASH = hashlib.sha256(b"FI|00100|Helsinki").hexdigest()


def _zip_bytes(csv_member: str, csv_text: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(csv_member, csv_text)
    return buffer.getvalue()


def _record(payload: bytes, url: str) -> RawRecord:
    return RawRecord(
        payload=payload,
        content_type="application/zip",
        source_url=url,
        fetched_at=NOW,
    )


def _entity_record() -> RawRecord:
    csv_text = (FIXTURES / "entities.csv").read_text()
    return _record(_zip_bytes("lei2-goldencopy.csv", csv_text), ENTITY_ZIP_URL)


def _relationship_record() -> RawRecord:
    csv_text = (FIXTURES / "relationships.csv").read_text()
    return _record(_zip_bytes("lei2-relationships-goldencopy.csv", csv_text), RELATIONSHIP_ZIP_URL)


def test_fetch_archives_originals_then_yields_csv_chunks():
    with respx.mock:
        respx.get(PUBLICATIONS_URL).mock(
            return_value=Response(
                200,
                json={
                    "data": [
                        {
                            "lei2": {"full_file": {"csv": {"url": ENTITY_ZIP_URL}}},
                            "rr": {"full_file": {"csv": {"url": RELATIONSHIP_ZIP_URL}}},
                        }
                    ]
                },
            )
        )
        respx.get(ENTITY_ZIP_URL).mock(return_value=Response(200, content=_entity_record().payload))
        respx.get(RELATIONSHIP_ZIP_URL).mock(
            return_value=Response(200, content=_relationship_record().payload)
        )
        records = list(ADAPTER.fetch(None, None))
    assert [r.source_url for r in records] == [
        ENTITY_ZIP_URL,
        ENTITY_ZIP_URL,
        RELATIONSHIP_ZIP_URL,
        RELATIONSHIP_ZIP_URL,
    ]
    assert [r.content_type for r in records] == [
        "application/zip",
        "text/csv",
        "application/zip",
        "text/csv",
    ]
    assert records[0].acquisition_context["archive_only"]
    assert (
        records[1].acquisition_context["source_archive_hash"]
        == hashlib.sha256(records[0].payload).hexdigest()
    )
    assert all(r.fetched_at.tzinfo is not None for r in records)


def test_entity_normalize_produces_expected_records():
    normalized = ADAPTER.normalize(_entity_record())

    assert normalized.kind == "structured"
    assert normalized.lookup_rows == []
    assert normalized.content_hash == hashlib.sha256(_entity_record().payload).hexdigest()
    assert len(normalized.assertions) == 2

    by_subject = {a.subject.entity_id: a for a in normalized.assertions}
    assert set(by_subject) == {f"lei:{LEI_DE}", f"lei:{LEI_FI}"}

    hq_de = by_subject[f"lei:{LEI_DE}"]
    assert hq_de.relation == "HEADQUARTERED_IN"
    assert hq_de.subject.label == "Beispiel AG"
    assert hq_de.subject.type == "Corporation"
    assert hq_de.subject.deterministic_key == ("lei", LEI_DE)
    assert hq_de.object.entity_id == f"coordinate_hash:{STUTTGART_HASH}"
    assert hq_de.object.deterministic_key == ("coordinate_hash", STUTTGART_HASH)
    assert hq_de.object.label == "Stuttgart"
    assert hq_de.object.type == "Location"

    hq_fi = by_subject[f"lei:{LEI_FI}"]
    assert hq_fi.subject.label == "Esimerkki Oyj"
    assert hq_fi.object.entity_id == f"coordinate_hash:{HELSINKI_HASH}"
    assert hq_fi.object.label == "Helsinki"

    for assertion in normalized.assertions:
        assert assertion.validity.valid_from == NOW
        assert assertion.validity.recorded_at == NOW
        assert assertion.validity.valid_to is None
        assert assertion.provenance.source_id == "gleif"
        assert assertion.provenance.source_trust == 1.00
        assert assertion.provenance.confidence == 1.0
        assert assertion.provenance.ontology_version is not None

    assert normalized.entities == [
        EntityEndpoint(
            entity_id=f"lei:{LEI_NL}",
            type="Corporation",
            label="Standalone B.V.",
            deterministic_key=("lei", LEI_NL),
        )
    ]


def test_inactive_entity_skipped_and_counted():
    with capture_logs() as captured:
        normalized = ADAPTER.normalize(_entity_record())
    skipped = [e for e in captured if e.get("event") == "gleif: non-ACTIVE entity skipped"]
    assert len(skipped) == 1
    assert skipped[0]["lei"] == LEI_LAPSED
    assert skipped[0]["status"] == "LAPSED"
    all_ids = [a.subject.entity_id for a in normalized.assertions]
    all_ids += [a.object.entity_id for a in normalized.assertions]
    all_ids += [e.entity_id for e in normalized.entities]
    assert f"lei:{LEI_LAPSED}" not in all_ids


def test_no_postal_lookup_means_no_located_in_and_summary_logged():
    with capture_logs() as captured:
        normalized = ADAPTER.normalize(_entity_record())
    assert all(a.relation != "LOCATED_IN" for a in normalized.assertions)
    summary = [
        e
        for e in captured
        if e.get("event") == "gisco correspondence missing for N addresses; region unassigned"
    ]
    assert len(summary) == 1
    assert summary[0]["addresses"] == 2


def test_postal_lookup_emits_located_in_for_hits_only():
    def lookup(country: str, postal: str) -> str | None:
        if (country, postal) == ("DE", "70173"):
            return "DE11"
        return None

    with capture_logs() as captured:
        normalized = ADAPTER.normalize(_entity_record(), postal_lookup=lookup)

    located = [a for a in normalized.assertions if a.relation == "LOCATED_IN"]
    assert len(located) == 1
    region = located[0].object
    assert region.entity_id == "nuts_code:DE11"
    assert region.deterministic_key == ("nuts_code", "DE11")
    assert region.label == "DE11"
    assert region.type == "AdministrativeRegion"
    assert located[0].subject.entity_id == f"coordinate_hash:{STUTTGART_HASH}"
    assert located[0].validity.valid_from == NOW

    summary = [
        e
        for e in captured
        if e.get("event") == "gisco correspondence missing for N addresses; region unassigned"
    ]
    assert len(summary) == 1
    assert summary[0]["addresses"] == 1  # Helsinki has no correspondence in the fixture


def test_relationships_normalize_produces_expected_records():
    normalized = ADAPTER.normalize(_relationship_record())

    assert normalized.kind == "structured"
    assert normalized.entities == []
    assert len(normalized.assertions) == 3

    by_relation: dict[str, list] = {}
    for assertion in normalized.assertions:
        by_relation.setdefault(assertion.relation, []).append(assertion)

    subsidiary = sorted(by_relation["SUBSIDIARY_OF"], key=lambda a: a.subject.entity_id)
    assert len(subsidiary) == 2
    assert [(a.subject.entity_id, a.object.entity_id) for a in subsidiary] == [
        (f"lei:{LEI_DE}", f"lei:{LEI_FI}"),
        (f"lei:{LEI_FI}", f"lei:{LEI_DE}"),
    ]
    # The row with a period start date takes the source-stated date; the
    # dateless row falls back to the fetch instant.
    assert subsidiary[0].validity.valid_from == datetime(2021, 6, 1, tzinfo=UTC)
    assert subsidiary[1].validity.valid_from == NOW
    # Relationship-only endpoints carry the LEI as label: the relationship
    # file has no name columns.
    assert all(a.subject.label == a.subject.entity_id.removeprefix("lei:") for a in subsidiary)

    ownership = by_relation["OWNS_STAKE_IN"]
    assert len(ownership) == 1
    assert ownership[0].subject.entity_id == f"lei:{LEI_FI}"  # the parent owns the subsidiary
    assert ownership[0].object.entity_id == f"lei:{LEI_DE}"
    assert ownership[0].validity.valid_from == datetime(2021, 6, 1, tzinfo=UTC)

    for assertion in normalized.assertions:
        assert assertion.provenance.source_id == "gleif"
        assert assertion.provenance.source_trust == 1.00
        assert assertion.provenance.confidence == 1.0
        assert assertion.validity.recorded_at == NOW
        assert assertion.validity.valid_to is None


def test_assertion_ids_are_deterministic_across_calls():
    for record in (_entity_record(), _relationship_record()):
        first = [a.assertion_id for a in ADAPTER.normalize(record).assertions]
        second = [a.assertion_id for a in ADAPTER.normalize(record).assertions]
        assert first == second
        assert len(set(first)) == len(first)


def test_non_zip_payload_raises_source_parse_error():
    try:
        ADAPTER.normalize(_record(b"this is not a zip archive", ENTITY_ZIP_URL))
    except SourceParseError:
        pass
    else:
        raise AssertionError("expected SourceParseError")


def test_zip_without_csv_member_raises_source_parse_error():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("README.txt", "no csv member in this zip")
    try:
        ADAPTER.normalize(_record(buffer.getvalue(), ENTITY_ZIP_URL))
    except SourceParseError:
        pass
    else:
        raise AssertionError("expected SourceParseError")


def test_zip_with_unrecognized_csv_header_raises_source_parse_error():
    payload = _zip_bytes("unexpected-file.csv", "Something,Else\n1,2\n")
    try:
        ADAPTER.normalize(_record(payload, ENTITY_ZIP_URL))
    except SourceParseError:
        pass
    else:
        raise AssertionError("expected SourceParseError")


def test_entity_row_without_lei_skipped_and_counted():
    csv_text = (
        "LEI,Entity.EntityStatus,Entity.LegalName,"
        "Entity.HeadquartersAddress.Country,Entity.HeadquartersAddress.PostalCode,"
        "Entity.HeadquartersAddress.City\n"
        ",ACTIVE,Ohne Lei,DE,70173,Stuttgart\n"
        f"{LEI_DE},ACTIVE,Beispiel AG,DE,70173,Stuttgart\n"
    )
    payload = _zip_bytes("lei2-goldencopy.csv", csv_text)
    with capture_logs() as captured:
        normalized = ADAPTER.normalize(_record(payload, ENTITY_ZIP_URL))
    assert len(normalized.assertions) == 1  # HEADQUARTERED_IN; no lookup, so no LOCATED_IN
    assert len(normalized.entities) == 0
    skipped = [e for e in captured if e.get("event") == "gleif: entity row without LEI skipped"]
    assert len(skipped) == 1
    summary = [e for e in captured if e.get("event") == "gleif: entity file normalized"][0]
    assert summary["malformed_skipped"] == 1


_REL_HEADER = (
    "Relationship.RecordID,Relationship.RelationshipType,Relationship.StartNodeID,"
    "Relationship.EndNodeID,Relationship.Periods.StartDate,"
    "Relationship.Ownership.DirectPercentage"
)


def test_non_subsidiary_relationship_skipped_and_counted():
    csv_text = (
        f"{_REL_HEADER}\n"
        "R2,OWNS,5493000TEST000000001,5493000TEST000000002,,100\n"
        f"R3,IS_SUBSIDIARY_OF,{LEI_DE},{LEI_FI},2021-06-01,\n"
    )
    payload = _zip_bytes("lei2-relationships-goldencopy.csv", csv_text)
    with capture_logs() as captured:
        normalized = ADAPTER.normalize(_record(payload, RELATIONSHIP_ZIP_URL))
    assert [a.relation for a in normalized.assertions] == ["SUBSIDIARY_OF"]
    skipped = [
        e for e in captured if e.get("event") == "gleif: non-subsidiary relationship skipped"
    ]
    assert len(skipped) == 1
    assert skipped[0]["relationship_type"] == "OWNS"


def test_relationship_with_unmaterializable_endpoint_skipped():
    csv_text = (
        f"{_REL_HEADER}\n"
        "R4,IS_SUBSIDIARY_OF,123,5493000TEST000000002,,\n"
        f"R5,IS_SUBSIDIARY_OF,{LEI_DE},{LEI_FI},2021-06-01,50\n"
    )
    payload = _zip_bytes("lei2-relationships-goldencopy.csv", csv_text)
    with capture_logs() as captured:
        normalized = ADAPTER.normalize(_record(payload, RELATIONSHIP_ZIP_URL))
    assert [a.relation for a in normalized.assertions] == ["SUBSIDIARY_OF", "OWNS_STAKE_IN"]
    skipped = [
        e
        for e in captured
        if e.get("event") == "gleif: relationship endpoint LEI cannot be materialized; skipped"
    ]
    assert len(skipped) == 1


def test_unparseable_period_start_falls_back_and_is_counted():
    csv_text = f"{_REL_HEADER}\nR6,IS_SUBSIDIARY_OF,{LEI_DE},{LEI_FI},not-a-date,\n"
    payload = _zip_bytes("lei2-relationships-goldencopy.csv", csv_text)
    with capture_logs() as captured:
        normalized = ADAPTER.normalize(_record(payload, RELATIONSHIP_ZIP_URL))
    assert normalized.assertions[0].validity.valid_from == NOW
    skipped = [
        e
        for e in captured
        if e.get("event") == "gleif: unparseable period start date; falling back to fetch time"
    ]
    assert len(skipped) == 1
    summary = [e for e in captured if e.get("event") == "gleif: relationship file normalized"][0]
    assert summary["date_fallback"] == 1


def test_unparseable_direct_percentage_skipped_and_counted():
    csv_text = f"{_REL_HEADER}\nR7,IS_SUBSIDIARY_OF,{LEI_DE},{LEI_FI},2021-06-01,lots\n"
    payload = _zip_bytes("lei2-relationships-goldencopy.csv", csv_text)
    with capture_logs() as captured:
        normalized = ADAPTER.normalize(_record(payload, RELATIONSHIP_ZIP_URL))
    assert [a.relation for a in normalized.assertions] == ["SUBSIDIARY_OF"]
    skipped = [
        e
        for e in captured
        if e.get("event") == "gleif: unparseable direct percentage; no ownership assertion"
    ]
    assert len(skipped) == 1
    summary = [e for e in captured if e.get("event") == "gleif: relationship file normalized"][0]
    assert summary["unparseable_percentages"] == 1


def test_zip_with_multiple_csv_members_uses_first_and_warns():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("a-entities.csv", "LEI,Entity.EntityStatus\n" + f"{LEI_DE},ACTIVE\n")
        archive.writestr("b-entities.csv", "LEI,Entity.EntityStatus\n")
    with capture_logs() as captured:
        normalized = ADAPTER.normalize(_record(buffer.getvalue(), ENTITY_ZIP_URL))
    assert len(normalized.entities) == 1
    warnings = [
        e
        for e in captured
        if e.get("event") == "gleif: zip has multiple CSV members; using the first"
    ]
    assert len(warnings) == 1
    assert warnings[0]["member"] == "a-entities.csv"


def test_csv_without_data_rows_raises_source_parse_error():
    payload = _zip_bytes("lei2-goldencopy.csv", "LEI,Entity.EntityStatus\n")
    try:
        ADAPTER.normalize(_record(payload, ENTITY_ZIP_URL))
    except SourceParseError:
        pass
    else:
        raise AssertionError("expected SourceParseError")
