"""BE-59 Wikidata NRW organisation source: source-side selection and typing."""

import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from limes.errors import SourceParseError
from limes.ontology.registry import load_ontology
from limes.ontology.validator import validate_assertions
from limes.sources import wikidata_nrw
from limes.sources.wikidata_nrw import WikidataNrwAdapter
from limes.types import RawRecord

FIXTURE = Path(__file__).parents[1] / "fixtures" / "wikidata_nrw" / "organisations.json"
NOW = datetime(2026, 11, 17, 12, tzinfo=UTC)


def record(payload: bytes | None = None) -> RawRecord:
    return RawRecord(
        payload=payload if payload is not None else FIXTURE.read_bytes(),
        content_type=wikidata_nrw.CONTENT_TYPE,
        source_url=wikidata_nrw.SPARQL_URL,
        fetched_at=NOW,
    )


def test_query_selects_nrw_headquarters_at_the_source(monkeypatch):
    requested = []

    def fetch(url, **kwargs):
        requested.append((url, kwargs))
        return FIXTURE.read_bytes()

    monkeypatch.setattr(wikidata_nrw, "fetch_bytes", fetch)
    records = list(WikidataNrwAdapter().fetch(None, None))
    assert len(records) == 1 and len(requested) == 1
    query = parse_qs(urlsplit(requested[0][0]).query)["query"][0]
    assert "wdt:P131* wd:Q1198" in query  # Nordrhein-Westfalen, server-side
    assert f"LIMIT {wikidata_nrw.MAX_ROWS + 1}" in query


def test_items_are_typed_once_and_companies_reuse_gleif_identity():
    result = WikidataNrwAdapter().normalize(record())
    ontology = load_ontology(Path("ontology/ontology.yaml"))
    accepted, rejected = validate_assertions(result.assertions, ontology)
    assert not rejected and len(accepted) == 3
    subjects = {a.subject.label: a.subject for a in result.assertions}
    assert subjects["Rheinische Beispiel AG"].deterministic_key == ("lei", "529900T8BM49AURSDO55")
    assert subjects["Rheinische Beispiel AG"].entity_id == "lei:529900T8BM49AURSDO55"
    # Listed under a nonprofit and a company class: one Corporation, never two nodes.
    werkstatt = subjects["Ruhr Werkstatt gGmbH"]
    assert werkstatt.type == "Corporation"
    assert werkstatt.deterministic_key == ("wikidata_qid", "Q100002")
    verein = subjects["Turnverein Beispielstadt 1888 e.V."]
    assert verein.type == "InterestGroup" and verein.deterministic_key is None
    assert "Q100003" in verein.aliases
    # No HQ coordinates: the organisation is still emitted, without a location.
    assert [e.label for e in result.entities] == ["Stiftung Westfälisches Beispiel"]
    assert result.errors == 0
    assert result.model_dump() == WikidataNrwAdapter().normalize(record()).model_dump()


def test_row_bound_and_malformed_payload_fail_loudly(monkeypatch):
    monkeypatch.setattr(wikidata_nrw, "MAX_ROWS", 2)
    with pytest.raises(SourceParseError, match="row bound"):
        WikidataNrwAdapter().normalize(record())
    with pytest.raises(SourceParseError):
        WikidataNrwAdapter().normalize(record(json.dumps({"results": {}}).encode()))
