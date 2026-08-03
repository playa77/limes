# tests/unit/test_eurlex_adapter.py | v1.0.0 | introduced by WP-12
"""EUR-Lex adapter tests per Doc 2 §8.5.2 and the WP-12 work package.

The Cellar SPARQL response is a recorded fixture (plausible CELEX numbers,
2024-2025 adoption dates, four bindings: a full row, an amends row, an
applies_to row, and a row without CELEX) pinned with respx — no live network.
Asserts the exact expected record set: deterministic keys (`celex`,
`wikidata_qid`, the multi-key Topic identity), the closed author mapping,
source attribution, non-temporal relations without `valid_to`, window
honoring via the adoption-date FILTER in the query text, and skip counting
for rows without a CELEX.
"""

import json
from datetime import UTC, datetime

import respx
from httpx import Response

from limes.errors import SourceParseError
from limes.sources.eurlex import AUTHOR_QIDS, SPARQL_URL, EurlexAdapter
from limes.types import RawRecord

FIXTURES = __import__("pathlib").Path(__file__).parents[1] / "fixtures" / "eurlex"
NOW = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)

ADAPTER = EurlexAdapter()


def _record(payload: bytes) -> RawRecord:
    return RawRecord(
        payload=payload, content_type="application/json", source_url=SPARQL_URL, fetched_at=NOW
    )


def _fixture() -> bytes:
    return (FIXTURES / "sparql_results.json").read_bytes()


def test_fetch_yields_one_record_and_honors_window():
    since = datetime(2024, 1, 1, tzinfo=UTC)
    until = datetime(2025, 12, 31, tzinfo=UTC)
    with respx.mock:
        route = respx.get(url__regex=r"^https://publications\.europa\.eu/webapi/rdf/sparql\?")
        route.mock(return_value=Response(200, content=_fixture()))
        records = list(ADAPTER.fetch(since, until))
        query = route.calls[0].request.url.params["query"]

    assert len(records) == 1
    record = records[0]
    assert record.content_type == "application/json"
    assert record.source_url == SPARQL_URL
    assert record.fetched_at.tzinfo is not None
    # The window is compiled into the query text as an adoption-date FILTER.
    assert "FILTER" in query
    assert '?date >= "2024-01-01"^^xsd:date' in query
    assert '?date <= "2025-12-31"^^xsd:date' in query


def test_fetch_without_window_sends_no_date_filter():
    with respx.mock:
        route = respx.get(url__regex=r"^https://publications\.europa\.eu/webapi/rdf/sparql\?")
        route.mock(return_value=Response(200, content=_fixture()))
        records = list(ADAPTER.fetch(None, None))
        query = route.calls[0].request.url.params["query"]

    assert len(records) == 1
    assert "FILTER" not in query


def test_normalize_produces_expected_assertions():
    normalized = ADAPTER.normalize(_record(_fixture()))

    assert normalized.kind == "structured"
    assert normalized.entities == []
    assert normalized.lookup_rows == []

    expected = {
        ("ADOPTED", "wikidata_qid:Q8889", "celex:32024R1234", "2024-05-21T00:00:00+00:00"),
        ("ABOUT_TOPIC", "celex:32024R1234", "topic:EuroVoc:2421", "2024-05-21T00:00:00+00:00"),
        ("CITES", "celex:32024R1234", "celex:32024R9999", "2024-05-21T00:00:00+00:00"),
        ("ADOPTED", "wikidata_qid:Q8897", "celex:32025L0001", "2025-03-10T00:00:00+00:00"),
        ("AMENDS", "celex:32025L0001", "celex:32019L0001", "2025-03-10T00:00:00+00:00"),
        ("APPLIES_TO", "celex:32025R0002", "topic:EuroVoc:1631", "2025-01-22T00:00:00+00:00"),
    }
    got = {
        (a.relation, a.subject.entity_id, a.object.entity_id, a.validity.valid_from.isoformat())
        for a in normalized.assertions
    }
    assert got == expected

    by_triple = {
        (a.relation, a.subject.entity_id, a.object.entity_id): a for a in normalized.assertions
    }

    # ADOPTED endpoints: IGO from the closed author mapping, LegalAct by CELEX.
    adopted_ep = by_triple[("ADOPTED", "wikidata_qid:Q8889", "celex:32024R1234")]
    assert adopted_ep.subject.type == "IGO"
    assert adopted_ep.subject.label == "European Parliament"
    assert adopted_ep.subject.deterministic_key == ("wikidata_qid", "Q8889")
    assert adopted_ep.object.type == "LegalAct"
    assert adopted_ep.object.label.startswith("Regulation (EU) 2024/1234")
    assert adopted_ep.object.deterministic_key == ("celex", "32024R1234")
    assert adopted_ep.validity.valid_from == datetime(2024, 5, 21, tzinfo=UTC)

    # Multi-key Topic identity: vocabulary in the entity_id, code as the
    # deterministic key, code as label (the row carries no label).
    topic = by_triple[("ABOUT_TOPIC", "celex:32024R1234", "topic:EuroVoc:2421")].object
    assert topic.type == "Topic"
    assert topic.label == "2421"
    assert topic.deterministic_key == ("code", "2421")
    applies_topic = by_triple[("APPLIES_TO", "celex:32025R0002", "topic:EuroVoc:1631")].object
    assert applies_topic.entity_id == "topic:EuroVoc:1631"

    # Non-temporal relations never carry valid_to; the temporal ones in this
    # fixture carry none either (no end date exists in the source).
    for relation in ("AMENDS", "REPEALS", "CITES"):
        for assertion in by_triple:
            if assertion[0] == relation:
                assert by_triple[assertion].validity.valid_to is None

    # Source attribution and belief time on every assertion.
    for assertion in normalized.assertions:
        assert assertion.provenance.source_id == "eurlex"
        assert assertion.provenance.source_trust == 1.00
        assert assertion.provenance.confidence == 1.0
        assert assertion.validity.recorded_at == NOW


def test_assertion_ids_are_deterministic_across_calls():
    record = _record(_fixture())
    first = [a.assertion_id for a in ADAPTER.normalize(record).assertions]
    second = [a.assertion_id for a in ADAPTER.normalize(record).assertions]
    assert first == second
    assert len(set(first)) == len(first)


def test_malformed_json_raises_source_parse_error():
    try:
        ADAPTER.normalize(_record(b"not json at all"))
    except SourceParseError:
        pass
    else:
        raise AssertionError("expected SourceParseError")


def test_payload_without_results_bindings_raises_source_parse_error():
    payload = json.dumps({"head": {"vars": ["celex"]}}).encode()
    try:
        ADAPTER.normalize(_record(payload))
    except SourceParseError:
        pass
    else:
        raise AssertionError("expected SourceParseError")


def test_rows_without_celex_are_skipped_and_counted():
    from structlog.testing import capture_logs

    with capture_logs() as logs:
        normalized = ADAPTER.normalize(_record(_fixture()))

    # The binding without a CELEX produced nothing and was counted, not
    # dropped: one summary line carrying bindings, assertions, and reasons.
    # The applies_to row carries no author, so its ADOPTED skip is counted too.
    summary = [log for log in logs if log["event"] == "eurlex: normalized"][0]
    assert summary["bindings"] == 4
    assert summary["assertions"] == len(normalized.assertions)
    assert summary["skipped"] == {"missing_celex": 1, "missing_author": 1}


def test_unknown_author_skips_only_adopted_and_is_counted():
    from structlog.testing import capture_logs

    payload = json.dumps(
        {
            "results": {
                "bindings": [
                    {
                        "celex": {"type": "literal", "value": "32025R0003"},
                        "date": {"type": "literal", "value": "2025-02-01"},
                        "author": {"type": "literal", "value": "European Commission"},
                        "topic_code": {"type": "literal", "value": "1234"},
                        "topic_voc": {"type": "literal", "value": "EuroVoc"},
                    }
                ]
            }
        }
    ).encode()

    with capture_logs() as logs:
        normalized = ADAPTER.normalize(_record(payload))

    # Unknown author: no ADOPTED, but the rest of the row still normalizes.
    assert len(normalized.assertions) == 1
    assert normalized.assertions[0].relation == "ABOUT_TOPIC"
    # No title: the CELEX stands in as the LegalAct label.
    assert normalized.assertions[0].subject.label == "32025R0003"
    summary = [log for log in logs if log["event"] == "eurlex: normalized"][0]
    assert summary["skipped"] == {"unknown_author": 1}
    assert "European Commission" not in AUTHOR_QIDS


def test_non_object_payload_raises_source_parse_error():
    try:
        ADAPTER.normalize(_record(b"[1, 2, 3]"))
    except SourceParseError:
        pass
    else:
        raise AssertionError("expected SourceParseError")


def test_malformed_binding_is_skipped_and_counted():
    from structlog.testing import capture_logs

    payload = json.dumps(
        {
            "results": {
                "bindings": [
                    "not a binding",
                    {"celex": {"type": "literal", "value": "32025R0009"}},
                ]
            }
        }
    ).encode()

    with capture_logs() as logs:
        normalized = ADAPTER.normalize(_record(payload))

    assert len(normalized.assertions) == 0  # the malformed binding produced nothing
    summary = [log for log in logs if log["event"] == "eurlex: normalized"][0]
    assert summary["skipped"] == {"malformed_binding": 1, "missing_author": 1}


def test_incomplete_topic_or_applies_to_is_skipped_and_counted():
    from structlog.testing import capture_logs

    payload = json.dumps(
        {
            "results": {
                "bindings": [
                    {
                        "celex": {"type": "literal", "value": "32025R0010"},
                        "topic_code": {"type": "literal", "value": "2421"},
                        "applies_to_voc": {"type": "literal", "value": "EuroVoc"},
                    }
                ]
            }
        }
    ).encode()

    with capture_logs() as logs:
        normalized = ADAPTER.normalize(_record(payload))

    assert normalized.assertions == []
    summary = [log for log in logs if log["event"] == "eurlex: normalized"][0]
    assert summary["skipped"] == {
        "missing_author": 1,
        "incomplete_topic": 1,
        "incomplete_applies_to": 1,
    }


def test_list_binding_produces_one_assertion_per_target():
    payload = json.dumps(
        {
            "results": {
                "bindings": [
                    {
                        "celex": {"type": "literal", "value": "32025R0011"},
                        "amends_celex": [
                            {"type": "literal", "value": "32019L0001"},
                            {"type": "literal", "value": "32019L0002"},
                        ],
                    }
                ]
            }
        }
    ).encode()

    normalized = ADAPTER.normalize(_record(payload))
    amends = [a for a in normalized.assertions if a.relation == "AMENDS"]
    assert {a.object.entity_id for a in amends} == {"celex:32019L0001", "celex:32019L0002"}


def test_row_without_date_falls_back_to_fetched_at():
    payload = json.dumps(
        {
            "results": {
                "bindings": [
                    {
                        "celex": {"type": "literal", "value": "32025R0012"},
                        "author": {"type": "literal", "value": "European Parliament"},
                    }
                ]
            }
        }
    ).encode()

    normalized = ADAPTER.normalize(_record(payload))
    assert len(normalized.assertions) == 1
    assert normalized.assertions[0].validity.valid_from == NOW


def test_unparseable_date_falls_back_and_is_counted():
    from structlog.testing import capture_logs

    payload = json.dumps(
        {
            "results": {
                "bindings": [
                    {
                        "celex": {"type": "literal", "value": "32025R0013"},
                        "date": {"type": "literal", "value": "not-a-date"},
                        "author": {"type": "literal", "value": "European Parliament"},
                    }
                ]
            }
        }
    ).encode()

    with capture_logs() as logs:
        normalized = ADAPTER.normalize(_record(payload))

    adopted = next(a for a in normalized.assertions if a.relation == "ADOPTED")
    assert adopted.validity.valid_from == NOW
    summary = [log for log in logs if log["event"] == "eurlex: normalized"][0]
    assert summary["skipped"] == {"unparseable_date": 1}
