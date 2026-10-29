# tests/acceptance/test_ac02_ontology.py | v1.0.0 | introduced by WP-39
"""AC-02: the ontology loads, self-validates, and rejects each malformed
case in §5.1.

The committed artifact is loaded through the production loader and checked
for the full type/relation counts. Each §5.1 rejection rule is then
exercised against a crafted artifact derived from the committed one — the
only way to be sure a rule still rejects after an unrelated edit to the
real artifact.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from limes.errors import OntologyError
from limes.ontology.registry import load_ontology

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"


def test_ac02_committed_artifact_loads_with_full_counts():
    ontology = load_ontology(ONTOLOGY_PATH)
    assert len(ontology.entity_types) == 19
    assert len(ontology.relation_types) == 30
    assert ontology.version == "1.1.0"


def _mutate(mutations) -> dict:
    """The committed artifact as a mutable dict with `mutations` applied —
    each mutation targets exactly one §5.1 rule."""
    data = yaml.safe_load(ONTOLOGY_PATH.read_text(encoding="utf-8"))
    return mutations(data)


def _write_artifact(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "ontology.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_ac02_rejects_undeclared_supertype(tmp_path: Path):
    def mutate(data):
        data["entity_types"][0]["supertype"] = "NotAThing"
        return data

    with pytest.raises(OntologyError, match="undeclared supertype"):
        load_ontology(_write_artifact(tmp_path, _mutate(mutate)))


def test_ac02_rejects_identifying_key_absent_from_property_list(tmp_path: Path):
    def mutate(data):
        corporation = next(e for e in data["entity_types"] if e["name"] == "Corporation")
        corporation["properties"] = [p for p in corporation["properties"] if p["name"] != "lei"]
        return data

    with pytest.raises(OntologyError, match="identifying key 'lei' is absent"):
        load_ontology(_write_artifact(tmp_path, _mutate(mutate)))


def test_ac02_rejects_unique_property_that_is_not_an_identifying_key(tmp_path: Path):
    def mutate(data):
        person = next(e for e in data["entity_types"] if e["name"] == "Person")
        person["properties"].append(
            {"name": "not_a_key", "type": "string", "required": False, "unique": True}
        )
        return data

    with pytest.raises(OntologyError, match="marked unique but is not an identifying key"):
        load_ontology(_write_artifact(tmp_path, _mutate(mutate)))


def test_ac02_rejects_undeclared_type_in_domain_or_range(tmp_path: Path):
    def mutate(data):
        subsidiary = next(r for r in data["relation_types"] if r["name"] == "SUBSIDIARY_OF")
        subsidiary["domain"] = ["Corporation", "NotAThing"]
        return data

    with pytest.raises(OntologyError, match="undeclared type 'NotAThing'"):
        load_ontology(_write_artifact(tmp_path, _mutate(mutate)))


def test_ac02_rejects_duplicate_type_names(tmp_path: Path):
    def mutate(data):
        data["entity_types"].append(dict(data["entity_types"][0]))
        return data

    with pytest.raises(OntologyError, match="duplicate entity_type names"):
        load_ontology(_write_artifact(tmp_path, _mutate(mutate)))
