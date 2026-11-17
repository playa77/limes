"""Current public source formats and independent failure/coverage expectations."""

from __future__ import annotations

import bz2
import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from lxml import etree

from limes.errors import LimesError, SourceFetchError, SourceParseError
from limes.sources.ted import TedAdapter
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

def test_current_transparency_export_counts_and_missing_people_are_honest():
    record = source_record("transparency.xml")
    result = TransparencyRegisterAdapter().normalize(record)
    # BE-59: the Köln-relocated organisation is kept; the Prague one is outside NRW.
    assert result.errors == 0 and len(result.entities) == 1
    assert len(result.assertions) == 8
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
