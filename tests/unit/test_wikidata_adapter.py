# tests/unit/test_wikidata_adapter.py | v1.0.0 | introduced by WP-18
"""Wikidata enrichment adapter tests per Technical Specification §8.5.2.

The adapter is enrichment-only: `enrich` resolves a label to one unambiguous
Wikidata item, returning None rather than guessing. HTTP is mocked with respx
against recorded wbsearchentities/wbsgetentities responses in
tests/fixtures/wikidata/; no live network. The tests assert on `enrich`'s
outputs — the match, the None misses — never on the mechanics that produce
them, and the request-parameter dictionaries below are the specification's
documented request surface, not state the adapter produces.
"""

from __future__ import annotations

import json

import pytest
import respx
from httpx import Response

from limes.errors import SourceParseError
from limes.sources.wikidata import ENTITIES_URL, SEARCH_URL, WikidataAdapter, WikidataMatch

FIXTURES = __import__("pathlib").Path(__file__).parents[1] / "fixtures" / "wikidata"

ADAPTER = WikidataAdapter()

SEARCH_PARAMS = {
    "action": "wbsearchentities",
    "search": "Mercedes-Benz Group",
    "language": "de",
    "format": "json",
    "type": "item",
    "limit": "10",
}
ENTITIES_PARAMS = {
    "action": "wbsgetentities",
    "ids": "Q283036",
    "props": "claims|labels",
    "languages": "de|en",
    "format": "json",
}


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_exact_label_match_with_matching_class_returns_match():
    with respx.mock:
        respx.get(SEARCH_URL, params=SEARCH_PARAMS).mock(
            return_value=Response(200, content=_fixture("search_mercedes.json"))
        )
        respx.get(ENTITIES_URL, params=ENTITIES_PARAMS).mock(
            return_value=Response(200, content=_fixture("entities_mercedes.json"))
        )
        match = ADAPTER.enrich("Corporation", "Mercedes-Benz Group")
    assert match == WikidataMatch(
        qid="Q283036",
        label="Mercedes-Benz Group",
        aliases=["Mercedes-Benz Group AG", "Daimler AG", "Daimler-Benz", "DaimlerChrysler"],
    )


def test_two_exact_label_matches_are_ambiguous_and_return_none():
    params = dict(SEARCH_PARAMS, search="European Union")
    with respx.mock:
        respx.get(SEARCH_URL, params=params).mock(
            return_value=Response(200, content=_fixture("search_ambiguous.json"))
        )
        match = ADAPTER.enrich("IGO", "European Union")
    assert match is None


def test_zero_results_return_none():
    with respx.mock:
        respx.get(SEARCH_URL, params=SEARCH_PARAMS).mock(
            return_value=Response(200, content=_fixture("search_empty.json"))
        )
        match = ADAPTER.enrich("Corporation", "Mercedes-Benz Group")
    assert match is None


def test_alias_only_match_returns_none():
    params = dict(SEARCH_PARAMS, search="Daimler")
    with respx.mock:
        respx.get(SEARCH_URL, params=params).mock(
            return_value=Response(200, content=_fixture("search_alias_only.json"))
        )
        match = ADAPTER.enrich("Corporation", "Daimler")
    assert match is None


def test_class_mismatch_returns_none():
    with respx.mock:
        respx.get(SEARCH_URL, params=SEARCH_PARAMS).mock(
            return_value=Response(200, content=_fixture("search_mercedes.json"))
        )
        respx.get(ENTITIES_URL, params=ENTITIES_PARAMS).mock(
            return_value=Response(200, content=_fixture("entities_p31_mismatch.json"))
        )
        match = ADAPTER.enrich("Corporation", "Mercedes-Benz Group")
    assert match is None


def test_unmapped_entity_type_skips_class_filter_without_second_request():
    with respx.mock:
        respx.get(SEARCH_URL, params=SEARCH_PARAMS).mock(
            return_value=Response(200, content=_fixture("search_mercedes.json"))
        )
        match = ADAPTER.enrich("LegalAct", "Mercedes-Benz Group")
        assert len(respx.calls) == 1
    assert match is not None
    assert match.qid == "Q283036"
    assert match.label == "Mercedes-Benz Group"


def test_non_json_search_response_raises_source_parse_error():
    with respx.mock:
        respx.get(SEARCH_URL, params=SEARCH_PARAMS).mock(
            return_value=Response(200, content=b"not json")
        )
        with pytest.raises(SourceParseError):
            ADAPTER.enrich("Corporation", "Mercedes-Benz Group")


def test_search_response_without_search_key_raises_source_parse_error():
    with respx.mock:
        respx.get(SEARCH_URL, params=SEARCH_PARAMS).mock(
            return_value=Response(200, json={"searchinfo": {"totalhits": 0}})
        )
        with pytest.raises(SourceParseError):
            ADAPTER.enrich("Corporation", "Mercedes-Benz Group")


def test_fetch_raises_not_implemented_error():
    with pytest.raises(NotImplementedError):
        list(ADAPTER.fetch(None, None))


def test_normalize_raises_not_implemented_error():
    with pytest.raises(NotImplementedError):
        ADAPTER.normalize(None)


def test_matches_are_serializable_and_validate():
    match = WikidataMatch(qid="Q283036", label="Mercedes-Benz Group")
    assert json.loads(match.model_dump_json()) == {
        "qid": "Q283036",
        "label": "Mercedes-Benz Group",
        "aliases": [],
    }
