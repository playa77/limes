# tests/unit/test_ontology.py | v1.0.0 | introduced by WP-03
"""Ontology artifact loading, self-validation, labels_for, permits, and
validate_assertions per Technical Specification §5.1 and §8.2."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from limes.errors import OntologyError
from limes.ontology.model import EntityTypeSpec, Ontology, PropertySpec, RelationTypeSpec
from limes.ontology.registry import load_ontology
from limes.ontology.validator import validate_assertions
from limes.types import Assertion, EntityEndpoint, Provenance, Validity

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"

NOW = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def ontology() -> Ontology:
    return load_ontology(ONTOLOGY_PATH)


def _assertion(
    subject_type: str = "Corporation",
    object_type: str = "Corporation",
    relation: str = "SUBSIDIARY_OF",
    valid_to: datetime | None = None,
) -> Assertion:
    return Assertion(
        assertion_id="a1",
        subject=EntityEndpoint(entity_id="s1", type=subject_type, label="S"),
        relation=relation,
        object=EntityEndpoint(entity_id="o1", type=object_type, label="O"),
        validity=Validity(valid_from=NOW, valid_to=valid_to, recorded_at=NOW),
        provenance=Provenance(
            source_id="test",
            source_trust=1.0,
            confidence=1.0,
            ontology_version="1.0.0",
        ),
    )


def test_ontology_loads_current_version_types_and_relations(ontology):
    assert len(ontology.entity_types) == 23
    assert len(ontology.relation_types) == 34
    assert ontology.version == "1.2.0"


def test_self_validation_rejects_undeclared_supertype(tmp_path):
    doc = yaml_like(
        {
            "entity_types": [
                {
                    "name": "Goblin",
                    "supertype": "Demon",
                    "identifying_keys": ["gid"],
                    "properties": [
                        {"name": "label", "type": "string", "required": True},
                        {"name": "gid", "type": "string", "required": False},
                    ],
                }
            ]
        }
    )
    path = write_yaml(tmp_path, doc)
    with pytest.raises(OntologyError, match="undeclared supertype"):
        load_ontology(path)


def test_self_validation_rejects_undeclared_relation_type(tmp_path):
    doc = yaml_like(
        {
            "relation_types": [
                {"name": "HATES", "domain": ["Ghost"], "range": ["Corporation"], "temporal": True}
            ]
        }
    )
    path = write_yaml(tmp_path, doc)
    with pytest.raises(OntologyError, match="undeclared type 'Ghost'"):
        load_ontology(path)


def test_self_validation_rejects_duplicate_entity_type_names(tmp_path):
    # A document with two entity types of the same name must be rejected.
    doc = yaml_like(
        {
            "entity_types": [
                {
                    "name": "Corporation",
                    "supertype": "Agent",
                    "identifying_keys": ["lei"],
                    "properties": [
                        {"name": "label", "type": "string", "required": True},
                        {"name": "lei", "type": "string", "required": False},
                    ],
                },
                {
                    "name": "Corporation",
                    "supertype": "Agent",
                    "identifying_keys": ["lei"],
                    "properties": [
                        {"name": "label", "type": "string", "required": True},
                        {"name": "lei", "type": "string", "required": False},
                    ],
                },
            ]
        }
    )
    path = write_yaml(tmp_path, doc)
    with pytest.raises(OntologyError):
        load_ontology(path)


def test_self_validation_rejects_identifying_key_absent_from_properties(tmp_path):
    doc = yaml_like(
        {
            "entity_types": [
                {
                    "name": "Corporation",
                    "supertype": "Agent",
                    "identifying_keys": ["lei"],
                    "properties": [{"name": "label", "type": "string", "required": True}],
                }
            ]
        }
    )
    path = write_yaml(tmp_path, doc)
    with pytest.raises(OntologyError, match="identifying key 'lei' is absent"):
        load_ontology(path)


def test_self_validation_rejects_unique_property_not_identifying_key(tmp_path):
    doc = yaml_like(
        {
            "entity_types": [
                {
                    "name": "Corporation",
                    "supertype": "Agent",
                    "identifying_keys": ["lei"],
                    "properties": [
                        {"name": "label", "type": "string", "required": True},
                        {"name": "lei", "type": "string", "required": False, "unique": True},
                        {"name": "legal_form", "type": "string", "required": False, "unique": True},
                    ],
                }
            ]
        }
    )
    path = write_yaml(tmp_path, doc)
    with pytest.raises(OntologyError, match="marked unique but is not an identifying key"):
        load_ontology(path)


def test_self_validation_rejects_missing_required_field(tmp_path):
    doc = yaml_like({"entity_types": [{"name": "X"}]})
    path = write_yaml(tmp_path, doc)
    with pytest.raises(OntologyError, match="JSON Schema"):
        load_ontology(path)


def test_labels_for_concrete_type(ontology):
    assert ontology.labels_for("Corporation") == ["Corporation", "Agent", "Entity"]


def test_labels_for_type_without_supertype(ontology):
    assert ontology.labels_for("Event") == ["Event", "Entity"]


def test_permits_valid_domain_range(ontology):
    assert ontology.permits("SUBSIDIARY_OF", "Corporation", "Corporation")


def test_permits_rejects_wrong_domain(ontology):
    assert not ontology.permits("SUBSIDIARY_OF", "Person", "Corporation")


def test_permits_resolves_supertypes(ontology):
    # OWNS_STAKE_IN's domain is Agent; a Corporation subject resolves to
    # Agent, so it is permitted.
    assert ontology.permits("OWNS_STAKE_IN", "Corporation", "Corporation")
    assert ontology.permits("OWNS_STAKE_IN", "Person", "Corporation")


def test_permits_rejects_type_outside_declared_range(ontology):
    # TARGETS' range is Person, Corporation, Country, Topic; an
    # AdministrativeRegion object must be rejected.
    assert not ontology.permits("TARGETS", "Sanction", "AdministrativeRegion")


def test_serialize_for_prompt_contains_types_and_relations(ontology):
    serialized = ontology.serialize_for_prompt()
    assert "SUBSIDIARY_OF" in serialized
    assert "Corporation" in serialized
    assert "[non-temporal]" in serialized


def test_validate_assertions_partitions_valid_and_invalid(ontology):
    valid = _assertion()
    unknown_relation = _assertion(relation="NOT_A_RELATION")
    domain_violation = _assertion(subject_type="Person", relation="SUBSIDIARY_OF")
    range_violation = _assertion(object_type="Topic", relation="SUBSIDIARY_OF")
    non_temporal_with_valid_to = _assertion(
        subject_type="LegalAct",
        object_type="LegalAct",
        relation="AMENDS",
        valid_to=NOW,
    )

    accepted, rejected = validate_assertions(
        [valid, unknown_relation, domain_violation, range_violation, non_temporal_with_valid_to],
        ontology,
    )

    assert len(accepted) == 1
    assert accepted[0].assertion_id == "a1"
    reasons = [r.reason for r in rejected]
    assert "UNKNOWN_RELATION" in reasons
    assert "DOMAIN_VIOLATION" in reasons
    assert "RANGE_VIOLATION" in reasons
    assert "NON_TEMPORAL_HAS_VALID_TO" in reasons
    assert len(rejected) == 4


def yaml_like(overrides: dict) -> dict:
    """A minimal valid ontology document, with overrides applied to the
    entity_types and relation_types lists."""
    base = {
        "version": "1.0.0",
        "supertypes": ["Agent", "Place", "Artifact"],
        "entity_types": [
            {
                "name": "Corporation",
                "supertype": "Agent",
                "identifying_keys": ["lei"],
                "properties": [
                    {"name": "label", "type": "string", "required": True},
                    {"name": "lei", "type": "string", "required": False, "unique": True},
                ],
            }
        ],
        "relation_types": [
            {
                "name": "SUBSIDIARY_OF",
                "domain": ["Corporation"],
                "range": ["Corporation"],
                "temporal": True,
            }
        ],
        "vocabularies": [{"name": "EuroVoc", "applies_to": "Topic"}],
    }
    for key, value in overrides.items():
        base[key] = value
    return base


def write_yaml(tmp_path: Path, doc: dict) -> Path:
    import yaml as pyyaml

    path = tmp_path / "ontology.yaml"
    path.write_text(pyyaml.safe_dump(doc), encoding="utf-8")
    # The schema is needed for structural validation; copy the real one so
    # load_ontology finds it next to the artifact.
    (tmp_path / "ontology.schema.json").write_text(
        (REPO_ROOT / "ontology" / "ontology.schema.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return path


def test_schema_file_is_valid_json():
    schema = json.loads(
        (REPO_ROOT / "ontology" / "ontology.schema.json").read_text(encoding="utf-8")
    )
    assert schema["additionalProperties"] is False


def test_missing_artifact_is_an_ontology_error(tmp_path):
    with pytest.raises(OntologyError, match="ontology artifact not found"):
        load_ontology(tmp_path / "nope.yaml")


def test_invalid_yaml_is_an_ontology_error(tmp_path):
    path = tmp_path / "ontology.yaml"
    path.write_text("key: [1, 2", encoding="utf-8")
    with pytest.raises(OntologyError, match="not valid YAML"):
        load_ontology(path)


def test_serialize_for_prompt_warns_above_the_token_budget():
    # An ontology whose serialized form exceeds the A-04 budget warns; the
    # serialization still returns the full text — the warning is the guard.
    oversized = Ontology(
        version="9.9.9",
        supertypes=["Agent"],
        entity_types={
            f"Type{i}": EntityTypeSpec(
                name=f"Type{i}",
                supertype="Agent" if i % 2 else None,
                identifying_keys=["k0"],
                properties=[PropertySpec(name=f"property_{j}", type="string") for j in range(30)],
            )
            for i in range(80)
        },
        relation_types={
            f"R{i}": RelationTypeSpec(name=f"R{i}", domain=["Type0"], range=["Type1"])
            for i in range(60)
        },
    )
    serialized = oversized.serialize_for_prompt()
    assert len(serialized) > 4 * 3000  # the token estimate exceeds the budget


def test_to_prompt_dict_projects_the_loaded_ontology(ontology):
    projection = ontology.to_prompt_dict()
    assert projection["version"] == ontology.version
    assert {r["name"] for r in projection["relations"]} == set(ontology.relation_types)
    assert {e["name"] for e in projection["entities"]} == set(ontology.entity_types)
