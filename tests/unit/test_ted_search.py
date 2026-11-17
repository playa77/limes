"""BE-59 TED acquisition: NRW result notices via the Search API, field mapping."""

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
import respx
from httpx import Response

from limes.errors import SourceFetchError, SourceParseError
from limes.ontology.registry import load_ontology
from limes.ontology.validator import validate_assertions
from limes.sources import ted_search
from limes.sources.ted import TedAdapter
from limes.sources.ted_search import SEARCH_URL, month_windows, nrw_query
from limes.types import RawRecord

FIXTURES = Path(__file__).parents[1] / "fixtures" / "ted_search"
NOW = datetime(2026, 11, 17, 12, tzinfo=UTC)


def page(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def record(document: dict) -> RawRecord:
    return RawRecord(payload=json.dumps(document).encode(), content_type="application/json",
                     source_url=SEARCH_URL, fetched_at=NOW)


def test_query_selects_nrw_result_notices_server_side():
    query = nrw_query(date(2024, 1, 1), date(2024, 1, 31))
    assert query.startswith("place-of-performance IN (DEA) AND notice-type IN (can-standard")
    assert query.endswith("PD >= 20240101 AND PD <= 20240131")
    assert list(month_windows(date(2020, 1, 15), date(2020, 3, 2))) == [
        (date(2020, 1, 15), date(2020, 1, 31)),
        (date(2020, 2, 1), date(2020, 2, 29)),
        (date(2020, 3, 1), date(2020, 3, 2)),
    ]


def test_fetch_pages_one_month_and_rejects_truncation(monkeypatch):
    monkeypatch.setattr(ted_search, "now_utc", lambda: NOW)
    first = page("results_2020.json")
    first["totalNoticeCount"] = 4
    second = {"notices": [dict(first["notices"][0], **{"publication-number": "999-2020"})],
              "totalNoticeCount": 4}
    with respx.mock:
        search = respx.post(SEARCH_URL).mock(side_effect=[
            Response(200, json=first), Response(200, json=second)])
        records = list(TedAdapter().fetch(datetime(2020, 3, 1, tzinfo=UTC),
                                          datetime(2020, 3, 2, tzinfo=UTC)))
        assert len(records) == 2 and len(search.calls) == 2
        sent = json.loads(search.calls[1].request.content)
        assert sent["iterationNextToken"] == first["iterationNextToken"]
        assert "place-of-performance IN (DEA)" in sent["query"]
        assert records[1].acquisition_context["search_page"] == 2
    second["totalNoticeCount"] = first["totalNoticeCount"] = 5
    with respx.mock:
        respx.post(SEARCH_URL).mock(side_effect=[
            Response(200, json=first), Response(200, json={**second, "notices": []})])
        with pytest.raises(SourceFetchError, match="incomplete search"):
            list(TedAdapter().fetch(datetime(2020, 3, 1, tzinfo=UTC),
                                    datetime(2020, 3, 2, tzinfo=UTC)))


def test_pre_scope_publication_and_timeouts_fail_closed():
    document = {"notices": [{"publication-number": "12-2019"}], "totalNoticeCount": 1}
    with respx.mock:
        respx.post(SEARCH_URL).respond(200, json=document)
        with pytest.raises(SourceFetchError, match="pre-2020"):
            list(TedAdapter().fetch(None, datetime(2020, 1, 2, tzinfo=UTC)))
    with pytest.raises(SourceFetchError, match="timed out"):
        TedAdapter().normalize(record({"notices": [], "timedOut": True}))
    with pytest.raises(SourceParseError):
        TedAdapter().normalize(record({"results": []}))


def test_eforms_page_maps_buyers_winners_topics_and_nrw_regions():
    result = TedAdapter().normalize(record(page("results_2025.json")))
    ontology = load_ontology(Path("ontology/ontology.yaml"))
    accepted, rejected = validate_assertions(result.assertions, ontology)
    assert not rejected and accepted
    awarded = [a for a in accepted if a.relation == "AWARDED_TO"]
    assert [(a.subject.entity_id, a.object.label) for a in awarded] == [
        ("ted_notice_id:350520-2025", "Bosch Sicherheitssysteme")]
    # A VAT number is not an LEI: the winner keeps the shared name-digest identity.
    assert awarded[0].object.deterministic_key is None
    buyers = {a.subject.label: a.subject for a in accepted if a.relation == "BUYER_OF"}
    dortmund = buyers["Bau- und Liegenschaftsbetrieb NRW Dortmund"]
    digest = hashlib.sha256(b"DE|Bau- und Liegenschaftsbetrieb NRW Dortmund").hexdigest()
    assert dortmund.entity_id == f"ted_buyer_id:{digest}"  # ISO2 digest, as the XML path
    regions = {a.object.entity_id for a in accepted if a.relation == "LOCATED_IN"}
    assert regions == {"nuts_code:DEA52"}  # the Frankfurt (60327) buyer gets no NRW region
    assert any(a.relation == "ABOUT_TOPIC" and a.object.entity_id.startswith("topic:CPV:")
               for a in accepted)
    assert {a.provenance.evidence_member for a in accepted} == {"350505-2025", "350520-2025"}


def test_legacy_page_keeps_contracts_and_buyers_without_inventing_winners():
    result = TedAdapter().normalize(record(page("results_2020.json")))
    assert not [a for a in result.assertions if a.relation == "AWARDED_TO"]
    contracts = {a.object.entity_id for a in result.assertions if a.relation == "BUYER_OF"}
    assert contracts == {"ted_notice_id:100828-2020", "ted_notice_id:100835-2020",
                         "ted_notice_id:100836-2020"}
    published = {a.validity.valid_from for a in result.assertions}
    assert published == {datetime(2020, 3, 2, tzinfo=UTC)}
    assert result == TedAdapter().normalize(record(page("results_2020.json")))
