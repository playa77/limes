# tests/unit/test_api_builder.py | v1.0.0 | introduced by WP-32/WP-35
"""Builder unit tests per Doc 2 §6 and the roadmap: the schema projection
is rendered from the ontology at runtime (NG-08 — never authored), and the
spec → Cypher translation rejects every invalid spec precisely (AC-24)
before any query text is produced, parameterizes all filter values and
temporal instants, and composes the §5.7 temporal fragments."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from limes.api.builder import (
    BuilderSpecRejected,
    project_for_builder,
    translate_spec,
)
from limes.api.models import BuilderHop, BuilderSpec
from limes.config import Settings
from limes.ontology.model import EntityTypeSpec, Ontology, PropertySpec, RelationTypeSpec
from limes.ontology.registry import load_ontology

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY = load_ontology(REPO_ROOT / "ontology" / "ontology.yaml")

SETTINGS = Settings(
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="u",
    neo4j_password="p",
    ontology_path=REPO_ROOT / "ontology" / "ontology.yaml",
    feeds_config_path=REPO_ROOT / "ontology" / "feeds.yaml",
    gold_set_path=REPO_ROOT / "gold_set" / "gold_set.jsonl",
    baseline_path=REPO_ROOT / "gold_set" / "baseline.json",
    archive_path=REPO_ROOT / "data" / "archive",
)


def spec(**overrides) -> BuilderSpec:
    base: dict = {"start_type": "Corporation", "start_filters": {}, "hops": []}
    base.update(overrides)
    return BuilderSpec(**base)


def test_projection_is_rendered_from_the_ontology():
    projection = project_for_builder(ONTOLOGY)
    assert projection["version"] == ONTOLOGY.version
    names = {entry["name"] for entry in projection["entity_types"]}
    assert names == set(ONTOLOGY.entity_types)
    relations = {entry["name"] for entry in projection["relation_types"]}
    assert relations == set(ONTOLOGY.relation_types)
    directorship = next(
        entry for entry in projection["relation_types"] if entry["name"] == "DIRECTOR_OF"
    )
    assert directorship["domain"] == ["Person"]
    assert directorship["range"] == ["Corporation"]
    assert directorship["temporal"] is True


def test_translate_simple_spec():
    cypher, params = translate_spec(spec(), ONTOLOGY, SETTINGS)
    assert cypher.startswith("MATCH (n0:Corporation)")
    assert cypher.endswith(f"RETURN * LIMIT {SETTINGS.query_default_limit}")
    assert params == {}


def test_translate_spec_with_hop_and_filters_parameterizes_values():
    s = spec(
        start_filters={"lei": "LEI-ALPHA"},
        hops=[
            BuilderHop(
                relation="SUBSIDIARY_OF",
                direction="out",
                target_type="Corporation",
                filters={"legal_form": "GmbH"},
            )
        ],
    )
    cypher, params = translate_spec(s, ONTOLOGY, SETTINGS)
    assert "MATCH (n0:Corporation {lei: $n0_lei})" in cypher
    assert "-[:SUBSIDIARY_OF]->(n1:Corporation {legal_form: $n1_legal_form})" in cypher
    assert params == {"n0_lei": "LEI-ALPHA", "n1_legal_form": "GmbH"}


def test_translate_spec_with_inbound_hop():
    s = spec(
        hops=[
            BuilderHop(
                relation="DIRECTOR_OF",
                direction="in",
                target_type="Person",
            )
        ]
    )
    cypher, _ = translate_spec(s, ONTOLOGY, SETTINGS)
    assert "(n0:Corporation) <-[:DIRECTOR_OF]-(n1:Person)" in cypher


def test_translate_spec_current_qualifier():
    s = spec(
        hops=[
            BuilderHop(
                relation="SUBSIDIARY_OF",
                direction="out",
                target_type="Corporation",
                temporal_qualifier="current",
            )
        ]
    )
    cypher, _ = translate_spec(s, ONTOLOGY, SETTINGS)
    assert "WHERE r0.valid_to IS NULL" in cypher


def test_translate_spec_as_of_qualifier_uses_temporal_fragments():
    instant = datetime(2024, 6, 1, tzinfo=UTC)
    s = spec(
        hops=[
            BuilderHop(
                relation="SUBSIDIARY_OF",
                direction="out",
                target_type="Corporation",
                temporal_qualifier="as_of",
                temporal_instant=instant,
            )
        ]
    )
    cypher, params = translate_spec(s, ONTOLOGY, SETTINGS)
    assert "r0.valid_from <= $r0_valid_as_of" in cypher
    assert params["r0_valid_as_of"] == instant


def test_translate_spec_as_believed_qualifier():
    instant = datetime(2024, 6, 1, tzinfo=UTC)
    s = spec(
        hops=[
            BuilderHop(
                relation="SUBSIDIARY_OF",
                direction="out",
                target_type="Corporation",
                temporal_qualifier="as_believed",
                temporal_instant=instant,
            )
        ]
    )
    cypher, params = translate_spec(s, ONTOLOGY, SETTINGS)
    assert "r0.recorded_at <= $r0_believed_as_of" in cypher
    assert params["r0_believed_as_of"] == instant


def test_ac24_invalid_specs_are_rejected_precisely():
    cases = [
        (spec(start_type="NotAType"), "unknown start type"),
        (
            spec(
                hops=[
                    BuilderHop(
                        relation="DIRECTOR_OF",
                        direction="out",
                        target_type="Corporation",
                    )
                ]
            ),
            "does not admit 'Corporation' as subject",
        ),
        (
            spec(
                hops=[
                    BuilderHop(
                        relation="SUBSIDIARY_OF",
                        direction="in",
                        target_type="Person",
                    )
                ]
            ),
            "does not admit 'Person' as subject",
        ),
        (
            spec(
                hops=[
                    BuilderHop(
                        relation="NotARelation",
                        direction="out",
                        target_type="Corporation",
                    )
                ]
            ),
            "unknown relation",
        ),
        (
            spec(
                hops=[
                    BuilderHop(
                        relation="CITES",
                        direction="out",
                        target_type="LegalAct",
                        temporal_qualifier="current",
                    )
                ]
            ),
            "non-temporal",
        ),
        (
            spec(
                hops=[
                    BuilderHop(
                        relation="SUBSIDIARY_OF",
                        direction="out",
                        target_type="Corporation",
                        temporal_qualifier="as_of",
                    )
                ]
            ),
            "needs temporal_instant",
        ),
        (
            spec(start_filters={"not a property": 1}),
            "not a valid Cypher identifier",
        ),
    ]
    for invalid, message in cases:
        with pytest.raises(BuilderSpecRejected, match=message):
            translate_spec(invalid, ONTOLOGY, SETTINGS)


def test_supertype_relations_permitted():
    # OWNS_STAKE_IN's domain is the Agent supertype; a spec starting from
    # Person (an Agent) is admitted.
    s = spec(
        start_type="Person",
        hops=[
            BuilderHop(
                relation="OWNS_STAKE_IN",
                direction="out",
                target_type="Corporation",
            )
        ],
    )
    cypher, _ = translate_spec(s, ONTOLOGY, SETTINGS)
    assert "-[:OWNS_STAKE_IN]->" in cypher


def chained_ontology() -> Ontology:
    # Org is a concrete type with no declared properties; Corporation's
    # supertype chain runs through it, so a domain walk must pass through a
    # concrete type.
    return Ontology(
        version="9.9.9",
        supertypes=["Agent"],
        entity_types={
            "Org": EntityTypeSpec(name="Org", supertype="Agent", identifying_keys=[]),
            "Corporation": EntityTypeSpec(
                name="Corporation",
                supertype="Org",
                identifying_keys=[],
                properties=[PropertySpec(name="label", type="string", required=True)],
            ),
        },
        relation_types={
            "OWNS": RelationTypeSpec(name="OWNS", domain=["Agent"], range=["Corporation"]),
        },
    )


def test_filters_on_a_start_type_without_properties_are_rejected():
    # A filter can only target a declared property; a type with none makes
    # any filter a mismatch.
    s = spec(start_type="Org", start_filters={"x": 1})
    with pytest.raises(BuilderSpecRejected, match="match no declared property"):
        translate_spec(s, chained_ontology(), SETTINGS)


def test_filters_on_a_hop_type_without_properties_are_rejected():
    s = spec(
        hops=[BuilderHop(relation="OWNS", direction="out", target_type="Org", filters={"x": 1})]
    )
    with pytest.raises(
        BuilderSpecRejected, match="hop 1: filters for 'Org' match no declared property"
    ):
        translate_spec(s, chained_ontology(), SETTINGS)


def test_as_believed_qualifier_without_instant_is_rejected():
    s = spec(
        hops=[
            BuilderHop(
                relation="OWNS",
                direction="out",
                target_type="Corporation",
                temporal_qualifier="as_believed",
            )
        ]
    )
    with pytest.raises(BuilderSpecRejected, match="needs temporal_instant"):
        translate_spec(s, chained_ontology(), SETTINGS)


def test_object_side_rejection_walks_the_supertype_chain():
    # The subject side is admitted via its supertype chain (Corporation ->
    # Org -> Agent); the object side is not, and the rejection names the
    # object — the walk through the concrete supertype is what decides.
    s = spec(
        start_type="Corporation",
        hops=[BuilderHop(relation="OWNS", direction="out", target_type="Org")],
    )
    with pytest.raises(BuilderSpecRejected, match="does not admit 'Org' as object"):
        translate_spec(s, chained_ontology(), SETTINGS)
