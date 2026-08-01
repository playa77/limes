# tests/unit/test_loader_logic.py | v1.0.0 | introduced by WP-07
"""Loader partition and property-building logic (no database).

The graph-touching behavior is covered by `tests/integration/test_loader.py`;
these tests pin the pure parts: rejection partitioning (AC-10), deterministic
key guarding, and the §5.6 metadata property map.
"""

from datetime import UTC, datetime

from limes.graph.loader import (
    _distinct_endpoints,
    _key_property,
    _partition,
    _relationship_properties,
)
from limes.ontology.registry import load_ontology
from limes.types import Assertion, EntityEndpoint, Provenance, Validity

ONTOLOGY = load_ontology(__import__("pathlib").Path("ontology/ontology.yaml"))

NOW = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)


def _endpoint(
    entity_id: str,
    type_: str = "Corporation",
    key: tuple[str, str] | None = None,
) -> EntityEndpoint:
    return EntityEndpoint(
        entity_id=entity_id,
        type=type_,
        label=f"Entity {entity_id}",
        deterministic_key=key,
        aliases=[f"alias-{entity_id}"],
    )


def _assertion(
    assertion_id: str,
    subject: EntityEndpoint,
    relation: str,
    object_: EntityEndpoint,
    valid_to: datetime | None = None,
) -> Assertion:
    return Assertion(
        assertion_id=assertion_id,
        subject=subject,
        relation=relation,
        object=object_,
        validity=Validity(valid_from=NOW, valid_to=valid_to, recorded_at=NOW),
        provenance=Provenance(
            source_id="s1",
            source_trust=1.0,
            confidence=0.9,
            ontology_version="1.0.0",
        ),
    )


def test_partition_accepts_valid_assertion():
    a = _assertion("a1", _endpoint("e1"), "SUBSIDIARY_OF", _endpoint("e2"))
    valid, rejected = _partition([a], ONTOLOGY)
    assert valid == [a]
    assert rejected == []


def test_partition_rejects_unidentified_endpoint_as_endpoint_unidentified():
    a = _assertion("a1", _endpoint(""), "SUBSIDIARY_OF", _endpoint("e2"))
    valid, rejected = _partition([a], ONTOLOGY)
    assert valid == []
    assert len(rejected) == 1
    assert rejected[0].reason == "ENDPOINT_UNIDENTIFIED"
    assert rejected[0].assertion_index == 0


def test_partition_reuses_ontology_validator_rejections():
    a = _assertion("a1", _endpoint("e1"), "NOT_A_RELATION", _endpoint("e2"))
    valid, rejected = _partition([a], ONTOLOGY)
    assert valid == []
    assert rejected[0].reason == "UNKNOWN_RELATION"


def test_partition_keeps_original_indices():
    bad = _assertion("bad", _endpoint(""), "SUBSIDIARY_OF", _endpoint("e2"))
    good = _assertion("good", _endpoint("e3"), "SUBSIDIARY_OF", _endpoint("e4"))
    valid, rejected = _partition([bad, good], ONTOLOGY)
    assert rejected[0].assertion_index == 0
    assert valid == [good]


def test_key_property_only_for_declared_identifying_keys():
    corp = _endpoint("e1", "Corporation", key=("lei", "549300ABC"))
    assert _key_property(corp, ONTOLOGY) == "lei"
    person = _endpoint("e2", "Person", key=("lei", "549300ABC"))
    assert _key_property(person, ONTOLOGY) is None
    empty_value = _endpoint("e3", "Corporation", key=("lei", ""))
    assert _key_property(empty_value, ONTOLOGY) is None


def test_relationship_properties_include_full_metadata():
    a = _assertion(
        "a1",
        _endpoint("e1"),
        "SUBSIDIARY_OF",
        _endpoint("e2"),
        valid_to=datetime(2026, 12, 31, tzinfo=UTC),
    )
    props = _relationship_properties(a, temporal=True)
    for key in (
        "assertion_id",
        "valid_from",
        "valid_to",
        "recorded_at",
        "retracted_at",
        "source_id",
        "source_trust",
        "confidence",
        "ontology_version",
    ):
        assert key in props
    assert props["valid_to"] == datetime(2026, 12, 31, tzinfo=UTC)


def test_non_temporal_relationship_never_carries_valid_to():
    a = _assertion("a1", _endpoint("e1", "LegalAct"), "AMENDS", _endpoint("e2", "LegalAct"))
    props = _relationship_properties(a, temporal=False)
    assert "valid_to" not in props


def test_distinct_endpoints_deduplicates_across_assertions():
    a1 = _assertion("a1", _endpoint("e1"), "SUBSIDIARY_OF", _endpoint("e2"))
    a2 = _assertion("a2", _endpoint("e2"), "SUBSIDIARY_OF", _endpoint("e3"))
    endpoints = _distinct_endpoints([a1, a2], [])
    assert [e.entity_id for e in endpoints] == ["e1", "e2", "e3"]
