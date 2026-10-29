"""Current public source formats and independent failure/coverage expectations."""

from __future__ import annotations

import bz2
import csv
import io
import json
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
import respx
from lxml import etree

from limes.errors import LimesError, SourceFetchError, SourceParseError
from limes.pipeline.run import RunSpec
from limes.pipeline.window import resolve_window
from limes.sources.gdelt import GdeltAdapter
from limes.sources.gleif import GleifAdapter
from limes.sources.offeneregister import OffeneRegisterAdapter
from limes.sources.ted import SEARCH_URL, TedAdapter
from limes.sources.transparency_register import TransparencyRegisterAdapter
from limes.types import RawRecord, SourceRecord

FIXTURES = Path(__file__).parents[1] / "fixtures/ingest47"
NOW = datetime(2026, 10, 29, 12, tzinfo=UTC)


def source_record(name, kind="application/xml"):
    payload = (FIXTURES / name).read_bytes()
    if kind == "application/x-bzip2":
        payload = bz2.compress(payload)
    if kind == "application/zip":
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as archive:
            archive.writestr(name, payload)
        payload = buf.getvalue()
    return RawRecord(
        payload=payload,
        content_type=kind,
        source_url="https://example.test/" + name,
        fetched_at=NOW,
    )


def test_current_rr_financial_consolidation_not_ownership():
    record = source_record("gleif-rr.csv", "application/zip")
    result = GleifAdapter().normalize(record)
    assert result.errors == 0
    assert {a.relation for a in result.assertions} == {
        "DIRECTLY_CONSOLIDATED_BY",
        "ULTIMATELY_CONSOLIDATED_BY",
    }
    assert len(result.assertions) == 2
    source = list(csv.DictReader((FIXTURES / "gleif-rr.csv").open()))
    for assertion in result.assertions:
        row = source[assertion.provenance.evidence_row - 1]
        assert assertion.subject.entity_id == "lei:" + row["Relationship.StartNode.NodeID"]
        assert assertion.object.entity_id == "lei:" + row["Relationship.EndNode.NodeID"]
        assert assertion.validity.valid_from < NOW
        assert assertion.provenance.evidence_member == "gleif-rr.csv"
        assert assertion.provenance.ontology_version == "1.3.0"


def test_offene_actual_unwrapped_rows_use_individual_historical_vintage():
    record = source_record("offeneregister.jsonl", "application/x-bzip2")
    result = OffeneRegisterAdapter().normalize(record)
    assert result.errors == 0 and len(result.assertions) == 3
    companies = [
        json.loads(line) for line in (FIXTURES / "offeneregister.jsonl").read_text().splitlines()
    ]
    dates = {
        "german_register_number:" + row["company_number"]: datetime.fromisoformat(
            row["retrieved_at"].replace("Z", "+00:00")
        )
        for row in companies
    }
    for assertion in result.assertions:
        assert assertion.validity.recorded_at == dates[assertion.object.entity_id]
        assert assertion.validity.recorded_at.year == 2018
    row = companies[0]
    row.pop("retrieved_at")
    missing = record.model_copy(update={"payload": bz2.compress(json.dumps(row).encode())})
    with pytest.raises(SourceParseError, match="refusing a wall-clock vintage"):
        OffeneRegisterAdapter().normalize(missing)


def test_current_transparency_export_counts_and_missing_people_are_honest():
    record = source_record("transparency.xml")
    result = TransparencyRegisterAdapter().normalize(record)
    assert result.errors == 0 and len(result.entities) == 2
    assert len(result.assertions) == 14
    assert {a.relation for a in result.assertions} == {"LOBBIES_FOR"}
    assert {a.subject.entity_id for a in result.assertions} == {
        e.entity_id for e in result.entities
    }
    bad = record.model_copy(
        update={"payload": record.payload.replace(b">2</numberOfIR>", b">3</numberOfIR>")}
    )
    with pytest.raises(SourceParseError, match="incomplete export"):
        TransparencyRegisterAdapter().normalize(bad)


def test_ubl_contract_notice_never_creates_awards():
    result = TedAdapter().normalize(source_record("ted-contract.xml"))
    assert result.errors == 0 and len(result.entities) == 2
    assert {a.relation for a in result.assertions} == {
        "BUYER_OF",
        "HEADQUARTERED_IN",
        "LOCATED_IN",
        "ABOUT_TOPIC",
    }
    assert {a.object.label for a in result.assertions if a.relation == "ABOUT_TOPIC"} == {
        "30213200"
    }


def test_ubl_awards_join_winning_result_to_exact_lot_and_parties():
    record = source_record("ted-award.xml")
    result = TedAdapter().normalize(record)
    awards = [a for a in result.assertions if a.relation == "AWARDED_TO"]
    assert result.errors == 0 and len(awards) == 3
    assert {a.subject.entity_id for a in awards} == {"ted_notice_id:999999-2026#LOT-1"}
    assert {a.object.label for a in awards} == {
        "First Consortium Member",
        "Second Consortium Member",
        "Other Winner",
    }
    assert {a.validity.valid_from for a in awards} == {datetime(2023, 3, 22, 22, tzinfo=UTC)}
    # A losing result still references a tender; it must not create an award for LOT-0002.
    root = etree.fromstring(record.payload)
    for company in root.xpath("//*[local-name()='Company']"):
        if company.xpath(".//*[local-name()='ID' and text()='ORG-2']"):
            company.getparent().remove(company)
    broken = record.model_copy(update={"payload": etree.tostring(root)})
    assert TedAdapter().normalize(broken).errors > 0


def test_ted_iteration_covers_all_pages_and_rejects_truncated_results():
    payload = (FIXTURES / "ted-contract.xml").read_bytes()

    def page(number, token):
        return {
            "notices": [
                {
                    "publication-number": str(number),
                    "links": {"xml": {"MUL": f"https://ted.europa.eu/en/notice/{number}/xml"}},
                }
            ],
            "totalNoticeCount": 2,
            "iterationNextToken": token,
            "timedOut": False,
        }

    with respx.mock:
        search = respx.post(SEARCH_URL).mock(
            side_effect=[
                httpx.Response(200, json=page(1, "next")),
                httpx.Response(200, json=page(2, None)),
            ]
        )
        respx.get("https://ted.europa.eu/en/notice/1/xml").respond(200, content=payload)
        respx.get("https://ted.europa.eu/en/notice/2/xml").respond(200, content=payload)
        records = list(TedAdapter().fetch(None, None))
        assert len(records) == 2
        assert json.loads(search.calls[1].request.content)["iterationNextToken"] == "next"
        assert records[1].acquisition_context["search_page"] == 2
        search.mock(return_value=httpx.Response(200, json=page(1, None)))
        with pytest.raises(SourceFetchError, match="incomplete search"):
            list(TedAdapter().fetch(None, None))


def test_gdelt_initial_and_resume_keep_backlog_within_96_slots():
    from tests.unit.test_pipeline_window import _settings

    adapter = GdeltAdapter()
    since, until = resolve_window(
        RunSpec(source_id="gdelt", mode="ingest"), adapter, None, _settings(), now=NOW
    )
    assert since == NOW - timedelta(days=90)
    assert until == since + timedelta(hours=23, minutes=45)
    checkpoint = SourceRecord(
        source_id="gdelt", name="GDELT", kind="structured", trust_rank=0.5, last_success_at=until
    )
    next_since, next_until = resolve_window(
        RunSpec(source_id="gdelt", mode="ingest"), adapter, checkpoint, _settings(), now=NOW
    )
    assert next_since == until
    assert next_until == until + timedelta(hours=23, minutes=45)
    # One inclusive overlap slot; no gap and no leap over the remaining 89 days.
    assert next_until < NOW - timedelta(days=87)


def test_ingest_all_continues_then_fails_aggregate(monkeypatch, capsys):
    from limes.cli import ingest

    calls = []
    monkeypatch.setattr(ingest, "load_settings", lambda: None)
    monkeypatch.setattr(ingest, "configure_logging", lambda _: None)
    monkeypatch.setattr(ingest, "_ingestable_source_ids", lambda: ["a", "b", "c"])

    def run(settings, source, spec):
        calls.append(source)
        if source == "b":
            raise SourceFetchError("upstream unavailable")

    monkeypatch.setattr(ingest, "_ingest_source", run)
    with pytest.raises(LimesError, match="failed sources: b"):
        ingest.ingest_all()
    assert calls == ["a", "b", "c"]
    assert "upstream unavailable" in capsys.readouterr().err


def test_bulk_original_first_then_bounded_chunks_and_invalid_tail(monkeypatch):
    from limes.sources.bulk import bz2_jsonl_records, zip_csv_records

    monkeypatch.setattr("limes.sources.bulk.CHUNK_ROWS", 1)
    raw = source_record("gleif-rr.csv", "application/zip")
    records = list(zip_csv_records(raw.payload, raw.source_url, NOW))
    assert records[0].payload == raw.payload
    assert records[0].acquisition_context["archive_only"]
    assert len(records) == 4
    assert [r.acquisition_context["source_row_offset"] for r in records[1:]] == [0, 1, 2]
    assert all(r.acquisition_context["rows"] == 1 for r in records[1:])
    raw = source_record("offeneregister.jsonl", "application/x-bzip2")
    records = list(bz2_jsonl_records(raw.payload, raw.source_url, NOW))
    assert records[0].payload == raw.payload and len(records) == 3
    assert b"".join(bz2.decompress(r.payload) for r in records[1:]) == bz2.decompress(raw.payload)
    monkeypatch.setattr("limes.sources.bulk.MAX_LINE_BYTES", 8)
    it = bz2_jsonl_records(raw.payload, raw.source_url, NOW)
    assert next(it).payload == raw.payload  # archive retained even when normalization is unsafe
    with pytest.raises(SourceFetchError, match="row exceeds byte limit"):
        next(it)


def test_law_index_is_archived_without_creating_a_permanent_parse_error(monkeypatch):
    from limes.sources.gesetze_im_internet import GesetzeImInternetAdapter
    from tests.unit.test_gesetze_im_internet_adapter import MEMBER_WITH_TOPICS, _law_zip_bytes, _toc

    monkeypatch.setattr(
        "limes.sources.gesetze_im_internet.fetch_bytes",
        lambda url: _toc() if url.endswith("gii-toc.xml") else _law_zip_bytes(MEMBER_WITH_TOPICS),
    )
    adapter = GesetzeImInternetAdapter()
    records = list(adapter.fetch(None, None))
    assert records[0].acquisition_context["archive_only"]
    result = adapter.normalize(records[0])
    assert result.errors == 0 and not result.assertions and not result.entities


def test_eurlex_standalone_act_survives_absent_relations():
    from limes.sources.eurlex import EurlexAdapter

    payload = json.dumps(
        {
            "results": {
                "bindings": [
                    {
                        "celex": {"value": "32024R1689"},
                        "title": {"value": "Artificial Intelligence Act"},
                    }
                ]
            }
        }
    ).encode()
    result = EurlexAdapter().normalize(
        RawRecord(payload=payload, content_type="application/json", fetched_at=NOW)
    )
    assert not result.assertions
    assert result.entities[0].entity_id == "celex:32024R1689"
    assert result.entities[0].label == "Artificial Intelligence Act"


def test_eurlex_actual_cdm_response_and_canonical_predicates():
    from limes.sources.eurlex import EurlexAdapter, _build_query

    record = source_record("eurlex.json", "application/json")
    result = EurlexAdapter().normalize(record)
    assert len(result.assertions) == 1 and len(result.entities) == 1
    assert result.assertions[0].relation == "AMENDS"
    assert result.assertions[0].object.entity_id == "celex:11972B/AFI/DCL/07"
    query = _build_query(None, None)
    assert "cdm:resource_legal_id_celex" in query
    assert "cdm:work_date_document" in query
    assert "cdm:resource-legal-id-celex" not in query


def test_eurlex_pages_are_ordered_archived_and_repeated_data_fails(monkeypatch):
    from limes.sources.eurlex import EurlexAdapter

    monkeypatch.setattr("limes.sources.eurlex.PAGE_SIZE", 1)
    requests = []
    pages = [
        json.dumps({"results": {"bindings": [{"celex": {"value": code}}]}}).encode()
        for code in ["32024R1689", "32025R0001"]
    ]
    replies = iter(pages + [b'{"results":{"bindings":[]}}'])

    def fetch(url, **kwargs):
        requests.append(url)
        return next(replies)

    monkeypatch.setattr("limes.sources.eurlex.fetch_bytes", fetch)
    records = list(EurlexAdapter().fetch(None, None))
    assert len(records) == 3
    assert records[1].payload == pages[1]
    assert [r.acquisition_context["page"] for r in records] == [1, 2, 3]
    from urllib.parse import parse_qs, urlsplit

    assert "OFFSET 1" in parse_qs(urlsplit(requests[1]).query)["query"][0]
    # Whitespace variation is not a new data page.
    replies = iter([pages[0], json.dumps(json.loads(pages[0]), indent=2).encode()])
    with pytest.raises(SourceFetchError, match="repeated SPARQL page"):
        list(EurlexAdapter().fetch(None, None))


def test_ubl_iso3_country_preserves_existing_buyer_address_identity_and_lookup():
    import hashlib

    record = source_record("ted-contract.xml")
    root = etree.fromstring(record.payload)
    for node in root.xpath("//*[local-name()='CountrySubentityCode']"):
        node.getparent().remove(node)
    calls = []

    def lookup(country, postal):
        calls.append((country, postal))
        return "AT130"

    result = TedAdapter().normalize(
        record.model_copy(update={"payload": etree.tostring(root)}), postal_lookup=lookup
    )
    assert result.errors == 0
    buyers = {a.subject.entity_id for a in result.assertions if a.relation == "BUYER_OF"}
    assert buyers == {"ted_buyer_id:" + hashlib.sha256(b"AT|Flughafen Wien AG").hexdigest()}
    hq = [a.object.entity_id for a in result.assertions if a.relation == "HEADQUARTERED_IN"]
    assert set(hq) == {"coordinate_hash:" + hashlib.sha256(b"AT|1300|Wien-Flughafen").hexdigest()}
    assert calls == [("AT", "1300"), ("AT", "1300")]
