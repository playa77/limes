"""Upstream positional expectations are independent of the adapter field list."""

import hashlib
import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
import respx
from httpx import Response

from limes.errors import SourceFetchError, SourceParseError
from limes.sources import gdelt
from limes.types import RawRecord

SAMPLE = Path(__file__).parents[1] / "fixtures/gdelt/upstream.tsv"


def export(data=None, name="20261027183000.export.CSV"):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, SAMPLE.read_bytes() if data is None else data)
    return stream.getvalue()


def raw(data):
    return RawRecord(
        payload=data,
        content_type="application/zip",
        source_url="https://data.gdeltproject.org/gdeltv2/20261027183000.export.CSV.zip",
        fetched_at=datetime(2026, 10, 28, tzinfo=UTC),
    )


def test_real_upstream_positions_and_row_evidence():
    payload = export()
    normalized = gdelt.GdeltAdapter().normalize(raw(payload))
    rows = [line.split("\t") for line in SAMPLE.read_text().splitlines()]
    assert len(rows) == 3 and all(len(r) == 61 for r in rows)
    assert normalized.document is None
    for a in normalized.assertions:
        p = a.provenance
        r = rows[p.evidence_row - 1]
        assert p.source_event_id == r[0]
        assert p.report_url == r[60]
        assert p.source_recorded_at == datetime.strptime(r[59], "%Y%m%d%H%M%S").replace(tzinfo=UTC)
        assert p.evidence_document_id == hashlib.sha256(payload).hexdigest()
        assert p.evidence_member == "20261027183000.export.CSV"
        assert p.article_text_available is False
        assert p.evidence_channel == "coded"
        assert a.validity.valid_from == datetime.strptime(r[1], "%Y%m%d").replace(tzinfo=UTC)
        assert a.validity.recorded_at == raw(payload).fetched_at


@pytest.mark.parametrize("country,iso", [("GM", "DE"), ("UK", "GB"), ("CH", "CN"), ("SZ", "CH")])
def test_fips_is_converted_instead_of_assumed_iso(country, iso):
    endpoint = gdelt._action_location({"ActionGeo_Type": "1", "ActionGeo_CountryCode": country})
    assert endpoint.deterministic_key == ("iso2", iso)


@pytest.mark.parametrize("geo_type", ["2", "3", "4", "5"])
def test_all_coordinate_geography_types(geo_type):
    assert (
        gdelt._action_location(
            {
                "ActionGeo_Type": geo_type,
                "ActionGeo_FullName": "Berlin",
                "ActionGeo_Lat": "52.52",
                "ActionGeo_Long": "13.405",
            }
        ).type
        == "Location"
    )


@pytest.mark.parametrize("lat,lon", [("nan", "1"), ("91", "0"), ("1", "181"), ("inf", "0")])
def test_invalid_coordinates_are_not_loaded(lat, lon):
    assert (
        gdelt._action_location(
            {
                "ActionGeo_Type": "4",
                "ActionGeo_FullName": "bad",
                "ActionGeo_Lat": lat,
                "ActionGeo_Long": lon,
            }
        )
        is None
    )


@pytest.mark.parametrize("second,microsecond,minute", [(0, 0, 30), (1, 0, 45), (0, 1, 45)])
def test_fractional_since_never_includes_an_earlier_slot(second, microsecond, minute):
    since = datetime(2026, 10, 27, 15, 30, second, microsecond, tzinfo=UTC)
    assert gdelt._first_slot(since, None) == datetime(2026, 10, 27, 15, minute, tzinfo=UTC)


def test_official_url_and_bounded_fetch():
    slot = datetime(2026, 10, 27, 18, 30, tzinfo=UTC)
    with respx.mock:
        route = respx.get("https://data.gdeltproject.org/gdeltv2/20261027183000.export.CSV.zip")
        route.mock(return_value=Response(200, content=export()))
        assert len(list(gdelt.GdeltAdapter().fetch(slot, slot))) == 1
        with pytest.raises(SourceFetchError, match="96 slots"):
            list(gdelt.GdeltAdapter().fetch(slot.replace(day=1), slot))
        assert route.call_count == 1


def test_bounded_stream_and_zip(monkeypatch):
    slot = datetime(2026, 10, 27, 18, 30, tzinfo=UTC)
    monkeypatch.setattr(gdelt, "MAX_COMPRESSED_BYTES", 10)
    with respx.mock:
        respx.get(gdelt.FILE_URL_TEMPLATE.format(slot=slot)).mock(
            return_value=Response(200, content=b"x" * 11)
        )
        with pytest.raises(SourceFetchError, match="byte limit"):
            list(gdelt.GdeltAdapter().fetch(slot, slot))
    with pytest.raises(SourceParseError, match="compressed"):
        gdelt.GdeltAdapter().normalize(raw(export()))
    monkeypatch.setattr(gdelt, "MAX_COMPRESSED_BYTES", 100000)
    monkeypatch.setattr(gdelt, "MAX_EXPANDED_BYTES", 10)
    with pytest.raises(SourceParseError, match="expanded"):
        gdelt.GdeltAdapter().normalize(raw(export()))


@pytest.mark.parametrize(
    "data,name",
    [
        (b"x\ty", "20261027183000.export.CSV"),
        (b"x", "../escape"),
        (b"\xff", "20261027183000.export.CSV"),
    ],
)
def test_schema_drift_and_unsafe_members_fail_closed(data, name):
    with pytest.raises(SourceParseError):
        gdelt.GdeltAdapter().normalize(raw(export(data, name)))


def test_duplicate_members_and_corrupt_zip_rejected():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("20261027183000.export.CSV", SAMPLE.read_bytes())
        archive.writestr("other", b"x")
    for data in (stream.getvalue(), b"not a zip", export()[:-10]):
        with pytest.raises(SourceParseError):
            gdelt.GdeltAdapter().normalize(raw(data))


def test_row_limit_prevents_unbounded_normalization(monkeypatch):
    monkeypatch.setattr(gdelt, "MAX_ROWS", 2)
    with pytest.raises(SourceParseError, match="row 3"):
        gdelt.GdeltAdapter().normalize(raw(export()))


def test_separate_reports_for_same_event_do_not_collapse():
    first = SAMPLE.read_bytes().splitlines()[0].split(b"\t")
    second = first.copy()
    second[60] = b"https://example.org/independent-report-version"
    normalized = gdelt.GdeltAdapter().normalize(
        raw(export(b"\t".join(first) + b"\n" + b"\t".join(second) + b"\n"))
    )
    by_row = {
        i: [a for a in normalized.assertions if a.provenance.evidence_row == i] for i in (1, 2)
    }
    assert by_row[1] and by_row[2]
    assert {a.assertion_id for a in by_row[1]}.isdisjoint(a.assertion_id for a in by_row[2])
    assert {a.provenance.report_url for a in by_row[1]} == {first[60].decode()}
    assert {a.provenance.report_url for a in by_row[2]} == {second[60].decode()}


def test_offset_window_formats_utc_slots_and_accepts_naive_utc():
    since = datetime.fromisoformat("2026-10-27T19:30:01+01:00")
    until = datetime(2026, 10, 27, 18, 45)
    with respx.mock:
        route = respx.get("https://data.gdeltproject.org/gdeltv2/20261027184500.export.CSV.zip")
        route.mock(return_value=Response(200, content=export()))
        records = list(gdelt.GdeltAdapter().fetch(since, until))
        assert len(records) == 1 and route.call_count == 1
