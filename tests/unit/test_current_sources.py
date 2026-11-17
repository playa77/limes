"""Current public source formats and independent failure/coverage expectations."""

from __future__ import annotations

import bz2
import csv
import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import respx
from lxml import etree

from limes.errors import LimesError, SourceFetchError, SourceParseError
from limes.sources.gleif import GleifAdapter
from limes.sources.ted import SEARCH_URL, TedAdapter
from limes.sources.transparency_register import TransparencyRegisterAdapter
from limes.types import RawRecord

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
        assert assertion.provenance.ontology_version == "1.4.0"

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
        records = list(TedAdapter().fetch_individual(None, None))
        assert len(records) == 2
        assert json.loads(search.calls[1].request.content)["iterationNextToken"] == "next"
        assert records[1].acquisition_context["search_page"] == 2
        search.mock(return_value=httpx.Response(200, json=page(1, None)))
        with pytest.raises(SourceFetchError, match="incomplete search"):
            list(TedAdapter().fetch_individual(None, None))

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
    from limes.sources.bulk import zip_csv_records

    monkeypatch.setattr("limes.sources.bulk.CHUNK_ROWS", 1)
    raw = source_record("gleif-rr.csv", "application/zip")
    records = list(zip_csv_records(raw.payload, raw.source_url, NOW))
    assert records[0].payload == raw.payload
    assert records[0].acquisition_context["archive_only"]
    assert len(records) == 4
    assert [r.acquisition_context["source_row_offset"] for r in records[1:]] == [0, 1, 2]
    assert all(r.acquisition_context["rows"] == 1 for r in records[1:])

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
