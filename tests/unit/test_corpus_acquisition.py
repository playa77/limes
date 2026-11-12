"""Recovery and real corpus shapes; network is always mocked in tests."""

import io
import tarfile
from datetime import UTC, datetime

import httpx
import pytest
import respx

from limes.archive.store import ArchiveStore
from limes.errors import SourceFetchError, SourceRunBudgetExceeded
from limes.sources.acquisition import AcquisitionStore
from limes.sources.base import fetch_bytes, now_utc, source_run_scope
from limes.sources.fsd import FsdAdapter
from limes.sources.ted import SEARCH_URL, TedAdapter
from limes.sources.ted_bulk import fetch_packages, package_urls
from limes.types import RawRecord

NOW = datetime(2026, 11, 10, tzinfo=UTC)


def _tar(*members):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, payload in members:
            member = tarfile.TarInfo(name)
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))
    return output.getvalue()


def test_scoped_backfill_uses_72_monthly_packages_without_notice_or_search_requests():
    with respx.mock:
        urls = list(package_urls(datetime(2020, 1, 1, tzinfo=UTC),
                                 datetime(2025, 12, 31, tzinfo=UTC)))
    assert len(urls) == 72
    assert urls[0] == "https://ted.europa.eu/packages/monthly/2020-1"
    assert urls[-1] == "https://ted.europa.eu/packages/monthly/2025-12"


def test_daily_discovery_uses_one_search_and_one_package_for_all_notices(tmp_path):
    archive = ArchiveStore(tmp_path / "archive")
    store = AcquisitionStore(archive, tmp_path / "progress")
    url = "https://ted.europa.eu/packages/daily/202600001"
    payload = _tar(("edition/00000001_2026.xml", b"<notice/>"),
                   ("edition/00000002_2026.xml", b"<notice id='2'/>"))
    with respx.mock:
        search = respx.post(SEARCH_URL).respond(200, json={
            "totalNoticeCount": 2, "notices": [{"ojs-number": "1/2026"}]
        })
        download = respx.get(url).respond(200, content=payload)
        with store.session("ted", {}, "v1") as acquisition:
            records = list(fetch_packages(datetime(2026, 1, 2, tzinfo=UTC),
                                          datetime(2026, 1, 2, tzinfo=UTC)))
            assert len(records) == 2
            assert search.call_count == download.call_count == 1
            digest = records[0].acquisition_context["source_archive_hash"]
            assert archive.get(digest) == payload
            assert [r.acquisition_context["requested_notice_id"] for r in records] == [
                "1-2026", "2-2026"
            ]
            replayed = list(fetch_packages(datetime(2026, 1, 2, tzinfo=UTC),
                                            datetime(2026, 1, 2, tzinfo=UTC)))
            assert replayed == records  # original payloads AND response observation timestamps
            for raw in records:
                acquisition.acknowledge(raw)
            acquisition.finish_unit(url, [acquisition.record_key(raw) for raw in records])
        # A completed package is skipped without even decompressing it on restart.
        with store.session("ted", {}, "v1"):
            assert list(fetch_packages(datetime(2026, 1, 2, tzinfo=UTC),
                                       datetime(2026, 1, 2, tzinfo=UTC))) == []
        assert search.call_count == download.call_count == 1


def test_historical_monthly_package_contains_nested_daily_archives():
    payload = _tar(("2020-01-04.tar.gz", _tar(("20200104_001/000036_2020.xml", b"<notice/>"))))
    with respx.mock:
        respx.get("https://ted.europa.eu/packages/monthly/2020-1").respond(200, content=payload)
        records = list(fetch_packages(datetime(2020, 1, 1, tzinfo=UTC),
                                      datetime(2020, 1, 31, tzinfo=UTC)))
    assert len(records) == 1
    assert records[0].acquisition_context["source_member"] == (
        "2020-01-04.tar.gz!/20200104_001/000036_2020.xml"
    )


@pytest.mark.parametrize("payload", [
    _tar(("../00000001_2026.xml", b"<x/>")),
    _tar(("00000001_2026.xml", b"<x/>"), ("00000001_2026.xml", b"<x/>")),
    _tar(("readme.txt", b"not a corpus")),
    b"<html>blocked</html>",
    _tar(("00000001_2026.xml", b"<x/>"))[:-8],
])
def test_invalid_or_truncated_package_never_certifies_completion(payload):
    with respx.mock:
        respx.get("https://ted.europa.eu/packages/monthly/2020-1").respond(200, content=payload)
        with pytest.raises(SourceFetchError):
            list(fetch_packages(datetime(2020, 1, 1, tzinfo=UTC),
                                datetime(2020, 1, 31, tzinfo=UTC)))


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


def test_eurlex_can_cross_the_previous_40_page_ceiling(monkeypatch):
    import json

    from limes.sources import eurlex

    monkeypatch.setattr(eurlex, "PAGE_SIZE", 1)
    count = 0

    def response(url, **kwargs):
        nonlocal count
        count += 1
        return json.dumps({"results": {"bindings": [{"celex": {"value": str(count)}}]
                                      if count <= 45 else []}}).encode()

    monkeypatch.setattr(eurlex, "fetch_bytes", response)
    assert len(list(eurlex.EurlexAdapter().fetch(None, None))) == 46
    assert count == 46


def test_dip_can_cross_100_pages_and_retains_distinct_terminal_page(monkeypatch):
    import json

    from limes.sources import bundestag_dip

    count = 0

    def response(url, **kwargs):
        nonlocal count
        count += 1
        return json.dumps({"documents": [{"id": str(count)}],
                           "cursor": str(min(count, 104))}).encode()

    monkeypatch.setattr(bundestag_dip, "fetch_bytes", response)
    assert len(list(bundestag_dip.BundestagDipAdapter().fetch(None, None))) == 105
    assert count == 105


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


def test_gdelt_explicit_multiday_window_requires_and_uses_durable_context(tmp_path, monkeypatch):
    from datetime import timedelta

    from limes.sources import gdelt

    calls = []
    monkeypatch.setattr(gdelt, "fetch_bytes", lambda url, **kwargs: (calls.append(url) or b"zip"))
    store = AcquisitionStore(ArchiveStore(tmp_path / "archive"), tmp_path / "progress")
    with store.session("gdelt", {}, "v1"):
        records = list(gdelt.GdeltAdapter().fetch(NOW, NOW + timedelta(days=1)))
    assert len(records) == len(calls) == 97


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


def test_empty_historical_search_uses_monthly_archive_and_filters_publication_dates():
    url = "https://ted.europa.eu/packages/monthly/2020-1"
    payload = _tar(("20200104_001/000036_2020.xml",
                    b"<TED_EXPORT><DATE_PUB>20200104</DATE_PUB></TED_EXPORT>"),
                   ("20200105_002/000037_2020.xml",
                    b"<TED_EXPORT><DATE_PUB>20200105</DATE_PUB></TED_EXPORT>"))
    with respx.mock:
        search = respx.post(SEARCH_URL).respond(200, json={
            "totalNoticeCount": 0, "notices": []})
        archive = respx.get(url).respond(200, content=payload)
        records = list(fetch_packages(datetime(2020, 1, 4, tzinfo=UTC),
                                      datetime(2020, 1, 4, tzinfo=UTC)))
    assert search.call_count == archive.call_count == 1
    assert len(records) == 1
    assert records[0].acquisition_context["requested_notice_id"] == "36-2020"


def test_empty_historical_weekend_is_checked_against_nonempty_archive():
    payload = _tar(("20200104_001/000036_2020.xml",
                    b"<TED_EXPORT><DATE_PUB>20200104</DATE_PUB></TED_EXPORT>"))
    with respx.mock:
        respx.post(SEARCH_URL).respond(200, json={"totalNoticeCount": 0, "notices": []})
        respx.get("https://ted.europa.eu/packages/monthly/2020-1").respond(200, content=payload)
        assert list(fetch_packages(datetime(2020, 1, 8, tzinfo=UTC),
                                   datetime(2020, 1, 8, tzinfo=UTC))) == []


def test_pre_scope_ted_package_request_is_rejected_before_network():
    with respx.mock as network, pytest.raises(SourceFetchError, match="2020"):
        list(package_urls(datetime(2019, 12, 1, tzinfo=UTC), NOW))
    assert not network.calls
