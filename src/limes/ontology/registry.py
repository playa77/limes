# src/limes/ontology/registry.py | v1.0.0 | introduced by WP-03
"""Ontology loading and self-validation per Technical Specification §5.1.

`load_ontology` reads the YAML artifact, validates it against
`ontology.schema.json` (structural), then self-validates it (semantic). The
self-validation rejections from §5.1: a relation naming an undeclared type in
domain or range; an entity naming an undeclared supertype; duplicate names;
an identifying key absent from the property list; a property marked unique
that is not an identifying key.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema  # type: ignore[import-untyped]
import structlog
import yaml  # type: ignore[import-untyped]

from limes.errors import OntologyError
from limes.ontology.model import EntityTypeSpec, Ontology, RelationTypeSpec, VocabularySpec

logger = structlog.get_logger(__name__)

_SCHEMA_PATH = Path(__file__).resolve().parents[3] / "ontology" / "ontology.schema.json"


class OntologyValidator:
    """Runs the §5.1 self-validation rules; exposes the rejection reasons."""

    def __init__(self, ontology: Ontology) -> None:
        self.ontology = ontology
        self.errors: list[str] = []

    def _fail(self, reason: str) -> None:
        self.errors.append(reason)

    def run(self) -> None:
        # Domains and ranges may legitimately name supertypes (e.g. the
        # domain of OWNS_STAKE_IN is Agent, Doc 2 §5.4), so "undeclared"
        # means a name that is neither an entity type nor a supertype.
        known = set(self.ontology.entity_types) | set(self.ontology.supertypes)

        for type_name, spec in self.ontology.entity_types.items():
            if spec.supertype is not None and spec.supertype not in self.ontology.supertypes:
                self._fail(
                    f"entity type '{type_name}' names undeclared supertype '{spec.supertype}'"
                )
            prop_names = {p.name for p in spec.properties}
            for key in spec.identifying_keys:
                if key not in prop_names:
                    self._fail(
                        f"entity type '{type_name}' identifying key '{key}' "
                        f"is absent from its property list"
                    )
            for prop in spec.properties:
                if prop.unique and prop.name not in spec.identifying_keys:
                    self._fail(
                        f"entity type '{type_name}' property '{prop.name}' is "
                        f"marked unique but is not an identifying key"
                    )

        for rel_name, rel in self.ontology.relation_types.items():
            for declared_type in rel.domain + rel.range:
                if declared_type not in known:
                    self._fail(
                        f"relation '{rel_name}' names undeclared type "
                        f"'{declared_type}' in domain or range"
                    )


def load_ontology(path: Path) -> Ontology:
    """Read, structurally validate, and self-validate the ontology artifact.

    Raises `OntologyError` naming the first problem when the file is missing,
    unparsable, fails its JSON Schema, or fails self-validation.
    """
    if not path.is_file():
        raise OntologyError(f"ontology artifact not found: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise OntologyError(f"ontology artifact is not valid YAML: {path}: {exc}") from exc

    schema_path = path.parent / "ontology.schema.json"
    if not schema_path.is_file():
        schema_path = _SCHEMA_PATH
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.validate(raw, schema)
    except (jsonschema.ValidationError, jsonschema.SchemaError, json.JSONDecodeError) as exc:
        raise OntologyError(f"ontology artifact fails its JSON Schema: {exc}") from exc

    for section, entries in (
        ("entity_types", raw["entity_types"]),
        ("relation_types", raw["relation_types"]),
    ):
        names = [e["name"] for e in entries]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            raise OntologyError(
                f"ontology self-validation failed: duplicate {section[:-1]} "
                f"names: {', '.join(dupes)}"
            )

    ontology = Ontology(
        version=raw["version"],
        supertypes=raw["supertypes"],
        entity_types={e["name"]: EntityTypeSpec(**e) for e in raw["entity_types"]},
        relation_types={r["name"]: RelationTypeSpec(**r) for r in raw["relation_types"]},
        vocabularies=[VocabularySpec(**v) for v in raw["vocabularies"]],
    )

    validator = OntologyValidator(ontology)
    validator.run()
    if validator.errors:
        raise OntologyError("ontology self-validation failed: " + "; ".join(validator.errors[:5]))

    logger.info(
        "ontology loaded",
        version=ontology.version,
        entity_types=len(ontology.entity_types),
        relation_types=len(ontology.relation_types),
    )
    return ontology
