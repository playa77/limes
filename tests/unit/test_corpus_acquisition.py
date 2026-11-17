"""Recovery and real corpus shapes; network is always mocked in tests."""

from datetime import UTC, datetime

import httpx
import pytest
import respx

from limes.archive.store import ArchiveStore
from limes.errors import SourceFetchError, SourceRunBudgetExceeded
from limes.sources.acquisition import AcquisitionStore
from limes.sources.base import fetch_bytes, now_utc, source_run_scope
from limes.sources.fsd import FsdAdapter
from limes.sources.ted import TedAdapter
from limes.types import RawRecord

NOW = datetime(2026, 11, 10, tzinfo=UTC)


def test_window_network_cache_and_versioned_load_receipts_survive_reopening(tmp_path):
    archive = ArchiveStore(tmp_path / "archive")
    store = AcquisitionStore(archive, tmp_path / "progress")
    url = "https://example.test/snapshot"
    with respx.mock:
        remote = respx.get(url).respond(200, content=b"snapshot")
        with store.session("gleif", {}, "v1") as acquisition:
            window = acquisition.window(None, NOW)
            payload = fetch_bytes(url)
            stamp = now_utc()
            raw = RawRecord(payload=payload, content_type="text/plain",
                            source_url=url, fetched_at=stamp)
            acquisition.acknowledge(raw)
        with store.session("gleif", {}, "v1") as acquisition:
            assert acquisition.window(NOW, None) == window
            assert fetch_bytes(url) == b"snapshot"
            assert now_utc() == stamp
            assert acquisition.is_loaded(raw)
        with store.session("gleif", {}, "v2") as acquisition:
            assert not acquisition.is_loaded(raw)
            assert fetch_bytes(url) == b"snapshot"
        assert remote.call_count == 1


def test_unacknowledged_records_cannot_complete_a_package(tmp_path):
    store = AcquisitionStore(ArchiveStore(tmp_path / "archive"), tmp_path / "progress")
    with store.session("ted", {}, "v1") as acquisition:
        raw = RawRecord(payload=b"one", content_type="text/plain", fetched_at=NOW,
                        acquisition_context={"unit": "package"})
        acquisition.acknowledge(raw)
        acquisition.finish_unit("package", [acquisition.record_key(raw), "unloaded-key"])
        assert not acquisition.unit_loaded("package")


def test_waf_http_202_is_a_failure_not_a_cached_empty_success():
    with respx.mock:
        remote = respx.get("https://example.test/data").respond(
            202, headers={"x-amzn-waf-action": "challenge"}
        )
        with pytest.raises(SourceFetchError, match="WAF challenge"):
            fetch_bytes("https://example.test/data")
        assert remote.call_count == 1


def test_retry_cannot_sleep_past_run_deadline(monkeypatch):
    monkeypatch.setattr("limes.sources.base.time.monotonic", lambda: 100.0)
    with respx.mock, source_run_scope(102, 8):
        route = respx.get("https://example.test/data").respond(
            429, headers={"Retry-After": "60"}
        )
        with pytest.raises(SourceRunBudgetExceeded, match="cooldown"):
            fetch_bytes("https://example.test/data")
        assert route.call_count == 1


def test_current_fsd_export_is_namespace_aware_and_uses_source_generation_date():
    payload = b'''<export xmlns="http://eu.europa.ec/fpi/fsd/export"
      generationDate="2026-07-31T09:00:00+02:00" globalFileId="123">
      <sanctionEntity euReferenceNumber="EU.27.28" logicalId="13">
        <regulation numberTitle="1210/2003 (OJ L169)" programme="IRQ"/>
        <subjectType classificationCode="P"/>
        <nameAlias wholeName="Example Person" strong="true"/>
        <address countryIso2Code="DE" zipCode="50667" city="Koeln"/>
      </sanctionEntity></export>'''
    raw = RawRecord(payload=payload, content_type="application/xml", fetched_at=NOW)
    result = FsdAdapter().normalize(raw)
    assert not result.errors
    assert {a.relation for a in result.assertions} == {"TARGETS", "IMPOSED_BY", "ESTABLISHED_BY"}
    assert {a.subject.entity_id for a in result.assertions} == {"fsd_id:EU.27.28:EU"}
    assert {a.validity.valid_from for a in result.assertions} == {
        datetime(2026, 7, 31, 7, tzinfo=UTC)
    }


def test_historical_ted_identity_country_title_and_publication_date():
    payload = b'''<TED_EXPORT DOC_ID="000503-2023"><DATE_PUB>20230102</DATE_PUB>
      <NO_DOC_OJS>2023/S 001-000503</NO_DOC_OJS>
      <CONTRACTING_BODY><ADDRESS_CONTRACTING_BODY><OFFICIALNAME>City</OFFICIALNAME>
      <COUNTRY VALUE="FR"/><POSTAL_CODE>75001</POSTAL_CODE><TOWN>Paris</TOWN>
      </ADDRESS_CONTRACTING_BODY></CONTRACTING_BODY>
      <TITLE><P>Survey services</P></TITLE></TED_EXPORT>'''
    raw = RawRecord(payload=payload, content_type="application/xml", fetched_at=NOW,
                    acquisition_context={"requested_notice_id": "503-2023"})
    result = TedAdapter().normalize(raw)
    assert result.errors == 0
    contract = next(a.object for a in result.assertions if a.relation == "BUYER_OF")
    assert contract.entity_id == "ted_notice_id:503-2023"
    assert contract.label == "Survey services"
    assert {a.validity.valid_from for a in result.assertions} == {
        datetime(2023, 1, 2, tzinfo=UTC)
    }
    assert any(a.relation == "HEADQUARTERED_IN" for a in result.assertions)

def test_invalid_payload_refreshes_without_losing_archived_evidence(tmp_path):
    archive = ArchiveStore(tmp_path / "archive")
    store = AcquisitionStore(archive, tmp_path / "progress")
    url = "https://example.test/export"
    with respx.mock:
        route = respx.get(url).mock(side_effect=[
            httpx.Response(200, content=b"invalid"), httpx.Response(200, content=b"corrected")
        ])
        with store.session("fsd", {}, "v1") as acquisition:
            raw = RawRecord(
                payload=fetch_bytes(url), content_type="application/xml", fetched_at=NOW
            )
            acquisition.invalidate(raw)
        with store.session("fsd", {}, "v1"):
            assert fetch_bytes(url) == b"corrected"
        assert route.call_count == 2
        import hashlib

        assert archive.get(hashlib.sha256(b"invalid").hexdigest()) == b"invalid"


def test_transparency_current_export_has_bounded_chunks_and_original_evidence():
    from pathlib import Path

    from lxml import etree

    from limes.sources.transparency_register import EXPORT_URL, TransparencyRegisterAdapter

    root = etree.parse(str(Path(__file__).parents[1] / "fixtures/ingest47/transparency.xml"))
    # Keep both independent source rows but force a one-row chunk for this test's
    # boundary by expanding to 251 source records with distinct authoritative IDs.
    row = root.xpath("//*[local-name()='interestRepresentative']")[0]
    result = root.xpath("//*[local-name()='resultList']")[0]
    result.clear()
    from copy import deepcopy

    for number in range(251):
        copied = deepcopy(row)
        copied.xpath(".//*[local-name()='identificationCode']")[0].text = f"source-{number}"
        result.append(copied)
    root.xpath("//*[local-name()='numberOfIR']")[0].text = "251"
    payload = etree.tostring(root)
    with respx.mock:
        respx.get(EXPORT_URL).respond(200, content=payload)
        adapter = TransparencyRegisterAdapter()
        records = list(adapter.fetch(None, None))
    assert len(records) == 3
    assert records[0].payload == payload and records[0].acquisition_context["archive_only"]
    assert [len(adapter.normalize(raw).entities) for raw in records[1:]] == [250, 1]

def test_changed_package_cannot_complete_with_equally_many_obsolete_receipts(tmp_path):
    store = AcquisitionStore(ArchiveStore(tmp_path / "archive"), tmp_path / "progress")
    with store.session("ted", {}, "v1") as acquisition:
        old = RawRecord(payload=b"old", content_type="text/plain", fetched_at=NOW,
                        acquisition_context={"unit": "package"})
        corrected = old.model_copy(update={"payload": b"corrected"})
        acquisition.acknowledge(old)
        acquisition.finish_unit("package", [acquisition.record_key(corrected)])
        assert not acquisition.unit_loaded("package")
        acquisition.acknowledge(corrected)
        acquisition.finish_unit("package", [acquisition.record_key(corrected)])
        assert acquisition.unit_loaded("package")
