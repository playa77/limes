# tests/unit/test_fsd_adapter.py | v1.0.0 | introduced by WP-13
"""EU FSD adapter tests per Doc 2 §8.5.2 and WP-13.

The fixture is a recorded consolidated-list XML in the live endpoint's 1_1
shape (trimmed to three sanctions); respx pins the fetch — no live network.
Asserts the exact expected record set: the three-way sanction decomposition
(TARGETS, IMPOSED_BY, ESTABLISHED_BY as separate assertions), the
`("fsd_id", "<id>:<regime>")` deterministic key scheme, regime-derived
imposing authorities, the FSD-prefixed legal-act identity, non-temporal
ESTABLISHED_BY (valid_to None), and the counted skips. Outputs are asserted
on; no input state is hand-built.
"""

from datetime import UTC, datetime

import respx
from httpx import Response

from limes.errors import SourceParseError
from limes.sources.base import (
    deterministic_assertion_id,
    hash_entity_id,
    key_entity_id,
)
from limes.sources.fsd import FSD_URL, FsdAdapter
from limes.types import RawRecord

FIXTURES = __import__("pathlib").Path(__file__).parents[1] / "fixtures" / "fsd"
NOW = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)

ADAPTER = FsdAdapter()

PERSON = hash_entity_id("person", "MUSTER, Erwin")
CORPORATION = hash_entity_id("corporation", "Example Corporation")


def _fixture() -> bytes:
    return (FIXTURES / "sanctions.xml").read_bytes()


def _record(payload: bytes | None = None) -> RawRecord:
    return RawRecord(
        payload=_fixture() if payload is None else payload,
        content_type="application/xml",
        source_url=FSD_URL,
        fetched_at=NOW,
    )


def test_fetch_yields_one_record_via_respx():
    with respx.mock:
        respx.get(FSD_URL).mock(return_value=Response(200, content=_fixture()))
        records = list(ADAPTER.fetch(None, None))
    assert len(records) == 1
    assert records[0].content_type == "application/xml"
    assert records[0].source_url == FSD_URL
    assert records[0].payload == _fixture()


def test_normalize_produces_exact_expected_assertion_set():
    normalized = ADAPTER.normalize(_record())
    assert normalized.kind == "structured"
    assert normalized.lookup_rows == []

    actual = {
        (a.relation, a.subject.entity_id, a.object.entity_id, a.object.type)
        for a in normalized.assertions
    }
    # Two representable sanctions × three relations. The third sanction has
    # an unknown SubjectType and must not appear anywhere.
    expected = {
        ("TARGETS", "fsd_id:123:EU", PERSON, "Person"),
        ("IMPOSED_BY", "fsd_id:123:EU", "wikidata_qid:Q458", "IGO"),
        ("ESTABLISHED_BY", "fsd_id:123:EU", "celex:FSD:2014/145/EU", "LegalAct"),
        ("TARGETS", "fsd_id:456:EU", CORPORATION, "Corporation"),
        ("IMPOSED_BY", "fsd_id:456:EU", "wikidata_qid:Q458", "IGO"),
        ("ESTABLISHED_BY", "fsd_id:456:EU", "celex:FSD:2014/145/EU", "LegalAct"),
    }
    assert actual == expected


def test_sanction_deterministic_key_includes_regime():
    normalized = ADAPTER.normalize(_record())
    sanctions = {a.subject.entity_id: a.subject for a in normalized.assertions}
    assert sanctions["fsd_id:123:EU"].deterministic_key == ("fsd_id", "123:EU")
    assert sanctions["fsd_id:456:EU"].deterministic_key == ("fsd_id", "456:EU")
    # Label is the primary (first) name alias.
    assert sanctions["fsd_id:123:EU"].label == "MUSTER, Erwin"
    assert sanctions["fsd_id:456:EU"].label == "Example Corporation"


def test_targets_person_and_entity_without_nationality():
    normalized = ADAPTER.normalize(_record())
    targets = [a for a in normalized.assertions if a.relation == "TARGETS"]
    assert len(targets) == 2
    by_sanction = {a.subject.entity_id: a.object for a in targets}

    person = by_sanction["fsd_id:123:EU"]
    assert person.type == "Person"
    assert person.entity_id == PERSON
    assert person.deterministic_key is None
    assert person.label == "MUSTER, Erwin"

    entity = by_sanction["fsd_id:456:EU"]
    assert entity.type == "Corporation"
    assert entity.entity_id == CORPORATION
    assert entity.label == "Example Corporation"

    # The person's nationality countries are not targets: the sanction
    # targets the person, not their country.
    assert {a.object.type for a in targets} == {"Person", "Corporation"}


def test_imposed_by_derives_igo_from_regime():
    normalized = ADAPTER.normalize(_record())
    imposed = [a for a in normalized.assertions if a.relation == "IMPOSED_BY"]
    assert len(imposed) == 2
    for a in imposed:
        assert a.object.type == "IGO"
        assert a.object.deterministic_key == ("wikidata_qid", "Q458")
        assert a.object.entity_id == key_entity_id(("wikidata_qid", "Q458"))
        assert a.object.label == "European Union"


def test_established_by_non_temporal_with_fsd_prefixed_identity():
    normalized = ADAPTER.normalize(_record())
    established = [a for a in normalized.assertions if a.relation == "ESTABLISHED_BY"]
    assert len(established) == 2
    for a in established:
        assert a.object.type == "LegalAct"
        assert a.object.deterministic_key == ("celex", "FSD:2014/145/EU")
        assert a.object.entity_id == "celex:FSD:2014/145/EU"
        assert a.object.label == "2014/145/EU"
        # Non-temporal relation: the validator rejects any valid_to.
        assert a.validity.valid_to is None


def test_every_assertion_carries_source_attribution():
    normalized = ADAPTER.normalize(_record())
    for a in normalized.assertions:
        assert a.provenance.source_id == "fsd"
        assert a.provenance.source_trust == 1.00
        assert a.provenance.confidence == 1.0
        assert a.validity.valid_from == NOW
        assert a.validity.recorded_at == NOW


def test_assertion_id_matches_deterministic_formula():
    normalized = ADAPTER.normalize(_record())
    targets = next(a for a in normalized.assertions if a.relation == "TARGETS")
    expected = deterministic_assertion_id("fsd", "TARGETS", "fsd_id:123:EU", PERSON, NOW)
    assert targets.assertion_id == expected


def test_assertion_ids_are_deterministic_across_calls():
    first = [a.assertion_id for a in ADAPTER.normalize(_record()).assertions]
    second = [a.assertion_id for a in ADAPTER.normalize(_record()).assertions]
    assert first == second
    # Six distinct ids: each of the three relations of each sanction is its
    # own assertion.
    assert len(set(first)) == 6


def test_un_regime_imposing_authority_is_united_nations():
    payload = (
        b"<root><Sanctions><Sanction>"
        b"<Id>777</Id><Regime>UN</Regime><SubjectType>P</SubjectType>"
        b"<NameAlias><WholeName>Example Person</WholeName></NameAlias>"
        b"<LegalBasis><LegalAct>2014/145/EU</LegalAct></LegalBasis>"
        b"</Sanction></Sanctions></root>"
    )
    normalized = ADAPTER.normalize(_record(payload))
    imposed = next(a for a in normalized.assertions if a.relation == "IMPOSED_BY")
    assert imposed.object.deterministic_key == ("wikidata_qid", "Q1065")
    assert imposed.object.entity_id == "wikidata_qid:Q1065"
    assert imposed.object.label == "United Nations"


def test_sanction_without_legal_basis_keeps_other_assertions():
    payload = (
        b"<root><Sanctions><Sanction>"
        b"<Id>777</Id><Regime>EU</Regime><SubjectType>P</SubjectType>"
        b"<NameAlias><WholeName>Example Person</WholeName></NameAlias>"
        b"</Sanction></Sanctions></root>"
    )
    normalized = ADAPTER.normalize(_record(payload))
    assert {a.relation for a in normalized.assertions} == {"TARGETS", "IMPOSED_BY"}


def test_unknown_regime_skips_only_imposed_by():
    payload = (
        b"<root><Sanctions><Sanction>"
        b"<Id>777</Id><Regime>XX</Regime><SubjectType>P</SubjectType>"
        b"<NameAlias><WholeName>Example Person</WholeName></NameAlias>"
        b"<LegalBasis><LegalAct>2014/145/EU</LegalAct></LegalBasis>"
        b"</Sanction></Sanctions></root>"
    )
    normalized = ADAPTER.normalize(_record(payload))
    assert {a.relation for a in normalized.assertions} == {"TARGETS", "ESTABLISHED_BY"}


def test_unnamed_person_is_skipped():
    payload = (
        b"<root><Sanctions><Sanction>"
        b"<Id>777</Id><Regime>EU</Regime><SubjectType>P</SubjectType>"
        b"</Sanction></Sanctions></root>"
    )
    normalized = ADAPTER.normalize(_record(payload))
    assert normalized.assertions == []


def test_skips_are_counted_not_dropped(capfd):
    ADAPTER.normalize(_record())
    captured = capfd.readouterr().out + capfd.readouterr().err
    # The fixture's third sanction (SubjectType "O") is skipped with its
    # reason on the log line, and the summary counts it.
    assert "unknown SubjectType" in captured
    assert "skipped_subject_type=1" in captured


def test_malformed_xml_raises_source_parse_error():
    payloads = [
        b"<root><Sanctions><Sanction>",  # unclosed
        b"this is not xml at all",
        b"",
        b"<root><NotSanctions/></root>",  # parses, but wrong shape
    ]
    for payload in payloads:
        try:
            ADAPTER.normalize(_record(payload))
        except SourceParseError:
            pass
        else:
            raise AssertionError(f"expected SourceParseError for {payload!r}")
