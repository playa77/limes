# tests/unit/test_gleif_adapter.py | v2.0.0 | introduced by WP-11, NRW API rewrite BE-59
"""GLEIF LEI API adapter: NRW selection at the source, cursor paging, mapping.

Recorded public API pages (tests/fixtures/gleif_api) — no live network.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from limes.errors import SourceFetchError
from limes.ontology.registry import load_ontology
from limes.ontology.validator import validate_assertions
from limes.sources import gleif
from limes.sources.gleif import GleifAdapter, first_page_url
from limes.types import RawRecord

FIXTURES = Path(__file__).parents[1] / "fixtures" / "gleif_api"
NOW = datetime(2026, 11, 17, 12, tzinfo=UTC)
ADAPTER = GleifAdapter()


def _record(name: str, payload: bytes | None = None) -> RawRecord:
    return RawRecord(
        payload=payload if payload is not None else (FIXTURES / name).read_bytes(),
        content_type=gleif.CONTENT_TYPE,
        source_url=first_page_url(),
        fetched_at=NOW,
    )


def test_first_page_selects_nrw_server_side_with_cursor_paging():
    query = parse_qs(urlsplit(first_page_url()).query)
    assert query["filter[entity.addresses.region]"] == ["DE-NW"]
    assert query["page[cursor]"] == ["*"]
    assert query["page[size]"] == [str(gleif.PAGE_SIZE)]


def test_fetch_follows_checked_cursor_links_until_exhausted(monkeypatch):
    page = json.loads((FIXTURES / "page.json").read_text())
    last = {**page, "links": {"first": page["links"]["first"]}}
    requested = []

    def fetch(url, **kwargs):
        requested.append(url)
        return json.dumps(page if len(requested) == 1 else last).encode()

    monkeypatch.setattr(gleif, "fetch_bytes", fetch)
    records = list(ADAPTER.fetch(None, None))
    assert len(records) == 2
    assert requested == [first_page_url(), page["links"]["next"]]


def test_foreign_or_unfiltered_next_link_stops_acquisition(monkeypatch):
    page = json.loads((FIXTURES / "page.json").read_text())
    page["links"]["next"] = "https://api.gleif.org/api/v1/lei-records?page%5Bcursor%5D=x"
    monkeypatch.setattr(gleif, "fetch_bytes", lambda url, **kw: json.dumps(page).encode())
    with pytest.raises(SourceFetchError, match="pagination link"):
        list(ADAPTER.fetch(None, None))


def test_nrw_entities_get_headquarters_and_nuts3_region():
    result = ADAPTER.normalize(_record("page.json"))
    ontology = load_ontology(Path("ontology/ontology.yaml"))
    accepted, rejected = validate_assertions(result.assertions, ontology)
    assert not rejected
    hq = [a for a in accepted if a.relation == "HEADQUARTERED_IN"]
    assert {a.subject.entity_id for a in hq} == {
        "lei:159500N9IYX6ABSWOK68",
        "lei:159504GH0R1IAC3U3A87",
        "lei:15950GF4PVT0ITS3D568",
        "lei:15950GH83CN3BLYT7L96",
        "lei:15950MY52GYS1N4YKD15",
    }
    labels = {a.subject.entity_id: a.subject.label for a in hq}
    assert labels["lei:159504GH0R1IAC3U3A87"] == "Verbraucherschutzstiftung in NRW"
    regions = {a.object.entity_id for a in accepted if a.relation == "LOCATED_IN"}
    assert regions and all(r.startswith("nuts_code:DEA") for r in regions)
    # Reporting exceptions are not parents.
    assert not [a for a in accepted if a.relation.endswith("CONSOLIDATED_BY")]
    assert all(a.provenance.source_url == first_page_url() for a in accepted)
    assert result.model_dump() == ADAPTER.normalize(_record("page.json")).model_dump()


def test_lei_parents_become_consolidation_edges_observed_now():
    result = ADAPTER.normalize(_record("page_with_parents.json"))
    edges = {
        (a.subject.entity_id, a.relation, a.object.entity_id)
        for a in result.assertions
        if a.relation.endswith("CONSOLIDATED_BY")
    }
    assert edges == {
        ("lei:213800128CEQCC37AF74", "DIRECTLY_CONSOLIDATED_BY", "lei:5493000C8J3C3SZYS040"),
        ("lei:213800128CEQCC37AF74", "ULTIMATELY_CONSOLIDATED_BY", "lei:5299001BUUGXAREGE533"),
        ("lei:2138001EMROZHYY91387", "DIRECTLY_CONSOLIDATED_BY", "lei:969500NWL0UGSFMZK421"),
        ("lei:2138001EMROZHYY91387", "ULTIMATELY_CONSOLIDATED_BY", "lei:F5WCUMTUM4RKZ1MAIE39"),
    }
    parent = next(a.object for a in result.assertions if a.relation.endswith("CONSOLIDATED_BY"))
    assert parent.label == parent.deterministic_key[1]  # labelled by its LEI until it loads
    assert all(
        a.validity.valid_from == NOW for a in result.assertions
    )  # snapshot observation, no invented relationship period


def test_inactive_and_malformed_rows_are_counted_not_loaded():
    page = json.loads((FIXTURES / "page.json").read_text())
    page["data"][0]["attributes"]["entity"]["status"] = "INACTIVE"
    page["data"][1]["id"] = "not-a-lei"
    page["data"][2]["attributes"]["entity"]["headquartersAddress"] = {}
    page["data"][2]["relationships"] = {}
    result = ADAPTER.normalize(_record("page.json", json.dumps(page).encode()))
    subjects = {a.subject.entity_id for a in result.assertions}
    assert "lei:159500N9IYX6ABSWOK68" not in subjects
    assert result.errors == 1
    assert [e.entity_id for e in result.entities] == ["lei:15950GF4PVT0ITS3D568"]
