# tests/unit/test_gesetze_im_internet_adapter.py | v1.0.0 | introduced by WP-17
"""Gesetze im Internet adapter tests per Technical Specification §8.5.2.

Fixtures are the recorded TOC (two law entries) and two law XML files in
tests/fixtures/gesetze_im_internet/; the test assembles the law zips in
memory (io.BytesIO + zipfile.ZipFile) and pins the TOC URL and both zip
links with respx — no live network. Asserts the exact expected record set:
the bgb_citation deterministic key (with the trailing-period citation
normalization), the multi-key Topic identity (`topic:Sachgebiet:<code>`),
labels, relation names, source attribution (`source_id="gesetze_im_internet"`,
`source_trust=1.00`), deterministic assertion ids, the standalone-entity
rule for topic-less laws, and SourceParseError on non-law payloads.
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
from limes.sources.gesetze_im_internet import (
    LAW_CONTENT_TYPE,
    TOC_CONTENT_TYPE,
    TOC_URL,
    GesetzeImInternetAdapter,
)
from limes.types import EntityEndpoint, RawRecord

FIXTURES = __import__("pathlib").Path(__file__).parents[1] / "fixtures" / "gesetze_im_internet"
NOW = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)

ADAPTER = GesetzeImInternetAdapter()

LAW_WITH_TOPICS_LINK = "http://www.gesetze-im-internet.de/1-dm-goldm_nzg/xml.zip"
LAW_WITHOUT_TOPICS_LINK = "http://www.gesetze-im-internet.de/egovg/xml.zip"

MEMBER_WITH_TOPICS = "BJNR204500000.xml"
MEMBER_WITHOUT_TOPICS = "BJNR104200013.xml"

_FIXTURE_BY_MEMBER = {
    MEMBER_WITH_TOPICS: "gesetz_mit_sachgebiet.xml",
    MEMBER_WITHOUT_TOPICS: "gesetz_ohne_sachgebiet.xml",
}


def _toc() -> bytes:
    return (FIXTURES / "gii-toc.xml").read_bytes()


def _law_zip_bytes(member: str) -> bytes:
    xml = (FIXTURES / _FIXTURE_BY_MEMBER[member]).read_bytes()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member, xml)
    return buffer.getvalue()


def _law_record(payload: bytes, url: str) -> RawRecord:
    return RawRecord(
        payload=payload,
        content_type=LAW_CONTENT_TYPE,
        source_url=url,
        fetched_at=NOW,
    )


def test_fetch_yields_toc_then_one_record_per_law():
    with_zip = _law_zip_bytes(MEMBER_WITH_TOPICS)
    without_zip = _law_zip_bytes(MEMBER_WITHOUT_TOPICS)
    with respx.mock:
        respx.get(TOC_URL).mock(return_value=Response(200, content=_toc()))
        respx.get(LAW_WITH_TOPICS_LINK).mock(return_value=Response(200, content=with_zip))
        respx.get(LAW_WITHOUT_TOPICS_LINK).mock(return_value=Response(200, content=without_zip))
        records = list(ADAPTER.fetch(None, None))

    expected_urls = [TOC_URL, LAW_WITH_TOPICS_LINK, LAW_WITHOUT_TOPICS_LINK]
    assert [r.source_url for r in records] == expected_urls
    assert records[0].content_type == TOC_CONTENT_TYPE
    assert all(r.content_type == LAW_CONTENT_TYPE for r in records[1:])
    assert records[0].payload == _toc()
    assert records[1].payload == with_zip
    assert records[2].payload == without_zip
    assert all(r.fetched_at.tzinfo is not None for r in records)


def test_fetch_ignores_the_window():
    with respx.mock:
        respx.get(TOC_URL).mock(return_value=Response(200, content=_toc()))
        respx.get(LAW_WITH_TOPICS_LINK).mock(
            return_value=Response(200, content=_law_zip_bytes(MEMBER_WITH_TOPICS))
        )
        respx.get(LAW_WITHOUT_TOPICS_LINK).mock(
            return_value=Response(200, content=_law_zip_bytes(MEMBER_WITHOUT_TOPICS))
        )
        records = list(
            ADAPTER.fetch(datetime(2025, 1, 1, tzinfo=UTC), datetime(2025, 12, 31, tzinfo=UTC))
        )

    assert len(records) == 3


def test_normalize_law_with_sachgebiet_produces_expected_record_set():
    record = _law_record(_law_zip_bytes(MEMBER_WITH_TOPICS), LAW_WITH_TOPICS_LINK)
    normalized = ADAPTER.normalize(record)

    assert normalized.kind == "structured"
    assert normalized.lookup_rows == []
    assert normalized.content_hash == hashlib.sha256(record.payload).hexdigest()
    assert len(normalized.assertions) == 2
    assert normalized.entities == []

    expected = {
        ("ABOUT_TOPIC", "bgb_citation:BGBl I 2000, 2045", "topic:Sachgebiet:21"),
        ("APPLIES_TO", "bgb_citation:BGBl I 2000, 2045", "topic:Sachgebiet:21"),
    }
    got = {(a.relation, a.subject.entity_id, a.object.entity_id) for a in normalized.assertions}
    assert got == expected

    about = next(a for a in normalized.assertions if a.relation == "ABOUT_TOPIC")
    act = about.subject
    assert act.type == "LegalAct"
    assert act.label == "Gesetz über die Ausprägung einer 1-DM-Goldmünze"
    assert act.deterministic_key == ("bgb_citation", "BGBl I 2000, 2045")
    topic = about.object
    assert topic.type == "Topic"
    assert topic.label == "Geld, Währung"
    assert topic.deterministic_key == ("code", "21")
    assert about.validity.valid_from == datetime(2000, 12, 27, tzinfo=UTC)
    assert about.validity.valid_to is None
    assert about.validity.recorded_at == NOW

    for assertion in normalized.assertions:
        assert assertion.provenance.source_id == "gesetze_im_internet"
        assert assertion.provenance.source_trust == 1.00
        assert assertion.provenance.confidence == 1.0
        assert assertion.provenance.ontology_version is not None


def test_normalize_law_without_sachgebiet_ships_standalone_entity():
    with capture_logs() as logs:
        normalized = ADAPTER.normalize(
            _law_record(_law_zip_bytes(MEMBER_WITHOUT_TOPICS), LAW_WITHOUT_TOPICS_LINK)
        )

    assert normalized.assertions == []
    assert normalized.entities == [
        EntityEndpoint(
            entity_id="bgb_citation:BGBl I 2024, 1",
            type="LegalAct",
            label="Gesetz zur Verbesserung der Verwaltungsleistungen",
            deterministic_key=("bgb_citation", "BGBl I 2024, 1"),
        )
    ]

    summary = [log for log in logs if log["event"] == "gesetze_im_internet: law normalized"][0]
    assert summary["skipped"] == {"no_sachgebiet": 1}
    assert summary["standalone_entity"] is True


def test_assertion_ids_are_deterministic_across_calls():
    record = _law_record(_law_zip_bytes(MEMBER_WITH_TOPICS), LAW_WITH_TOPICS_LINK)
    first = [a.assertion_id for a in ADAPTER.normalize(record).assertions]
    second = [a.assertion_id for a in ADAPTER.normalize(record).assertions]
    assert first == second
    assert len(set(first)) == len(first)


def test_toc_record_is_rejected_with_source_parse_error():
    with capture_logs() as logs:
        try:
            ADAPTER.normalize(
                RawRecord(
                    payload=_toc(),
                    content_type=TOC_CONTENT_TYPE,
                    source_url=TOC_URL,
                    fetched_at=NOW,
                )
            )
        except SourceParseError:
            pass
        else:
            raise AssertionError("expected SourceParseError")

    event = "gesetze_im_internet: payload is not a law zip; skipped"
    warnings = [log for log in logs if log["event"] == event]
    assert len(warnings) == 1
    assert warnings[0]["reason"] == "not_a_law_zip"


def test_malformed_zip_raises_source_parse_error():
    try:
        ADAPTER.normalize(_law_record(b"this is not a zip archive", LAW_WITH_TOPICS_LINK))
    except SourceParseError:
        pass
    else:
        raise AssertionError("expected SourceParseError")


def test_zip_without_law_xml_member_raises_source_parse_error():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("README.txt", "no law xml in this zip")
    try:
        ADAPTER.normalize(_law_record(buffer.getvalue(), LAW_WITH_TOPICS_LINK))
    except SourceParseError:
        pass
    else:
        raise AssertionError("expected SourceParseError")


def test_law_xml_without_metadaten_raises_source_parse_error():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(MEMBER_WITH_TOPICS, b"<gesetz><titel>kein Gesetz</titel></gesetz>")
    try:
        ADAPTER.normalize(_law_record(buffer.getvalue(), LAW_WITH_TOPICS_LINK))
    except SourceParseError:
        pass
    else:
        raise AssertionError("expected SourceParseError")


def test_law_without_fundstelle_is_skipped_and_counted():
    xml = (
        "<gesetz><metadaten><jurabk>XYZG</jurabk>"
        '<ausfertigung-datum manuell="ja">2010-05-01</ausfertigung-datum>'
        "<langue>Gesetz ohne Fundstelle</langue></metadaten></gesetz>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("BJNR999990000.xml", xml)

    with capture_logs() as logs:
        normalized = ADAPTER.normalize(_law_record(buffer.getvalue(), LAW_WITH_TOPICS_LINK))

    assert normalized.assertions == []
    assert normalized.entities == []
    summary = [log for log in logs if log["event"] == "gesetze_im_internet: law normalized"][0]
    assert summary["skipped"] == {"no_fundstelle": 1}
    assert summary["assertions"] == 0
