# src/limes/ontology/model.py | v1.0.0 | introduced by WP-03
"""Ontology data model per Technical Specification §5.1 and §8.2.

`Ontology` exposes the three operations the consumers need: `labels_for`
(loader node labeling), `permits` (loader and validator domain/range checks),
and `serialize_for_prompt` (NL-to-Cypher generation, A-04 token budget).
The classes mirror the YAML artifact; `load_ontology` (registry.py) converts
the artifact's list forms into the dict-keyed model.
"""

from __future__ import annotations

from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

PROMPT_TOKEN_WARN_THRESHOLD = 3000

SUPERTYPES = ("Agent", "Place", "Artifact")
ROOT_LABEL = "Entity"


class PropertySpec(BaseModel):
    """One declared property of an entity type."""

    name: str
    type: str
    required: bool = False
    unique: bool = False


class EntityTypeSpec(BaseModel):
    """One concrete entity type: its supertype, identifying keys, and
    properties."""

    name: str
    supertype: str | None = None
    identifying_keys: list[str]
    properties: list[PropertySpec] = Field(default_factory=list)


class RelationTypeSpec(BaseModel):
    """One relation: declared domain and range types, and whether it is
    temporal. Non-temporal relations are immutable statements of record and
    never have `valid_to` set (Doc 2 §5.1)."""

    name: str
    domain: list[str]
    range: list[str]
    temporal: bool = True


class VocabularySpec(BaseModel):
    """A controlled vocabulary attached to an entity type."""

    name: str
    applies_to: str


class Ontology(BaseModel):
    """The loaded, self-validated ontology artifact."""

    version: str
    supertypes: list[str]
    entity_types: dict[str, EntityTypeSpec]
    relation_types: dict[str, RelationTypeSpec]
    vocabularies: list[VocabularySpec] = Field(default_factory=list)

    def labels_for(self, type_name: str) -> list[str]:
        """The Neo4j label set for a type: [type, supertype, "Entity"], with
        supertypes resolved transitively. The label segment is always built
        from this method, never from source data (Doc 2 §5.6)."""
        labels = [type_name]
        current = self.entity_types[type_name].supertype
        seen = set(labels)
        while current is not None and current not in seen:
            labels.append(current)
            seen.add(current)
            current = self.entity_types[current].supertype if current in self.entity_types else None
        labels.append(ROOT_LABEL)
        return labels

    def permits(self, relation: str, subject_type: str, object_type: str) -> bool:
        """True when the relation's declared domain admits the subject type
        (or its supertype) and its range admits the object type (or its
        supertype)."""

        def admits(declared: list[str], actual: str) -> bool:
            if actual in declared:
                return True
            sup = self.entity_types[actual].supertype
            while sup is not None:
                if sup in declared:
                    return True
                sup = self.entity_types[sup].supertype if sup in self.entity_types else None
            return False

        spec = self.relation_types[relation]
        return admits(spec.domain, subject_type) and admits(spec.range, object_type)

    def serialize_for_prompt(self) -> str:
        """Compact text representation of the ontology for the NL-to-Cypher
        prompt. Logs an approximate token estimate at every call and warns
        when it exceeds the A-04 budget (3,000 tokens)."""
        lines: list[str] = [f"Ontology version {self.version}"]
        for relation_spec in self.relation_types.values():
            lines.append(
                f"RELATION {relation_spec.name}: "
                f"{', '.join(relation_spec.domain)} -> "
                f"{', '.join(relation_spec.range)}"
                + ("" if relation_spec.temporal else " [non-temporal]")
            )
        for entity_spec in self.entity_types.values():
            keys = ", ".join(entity_spec.identifying_keys)
            props = ", ".join(f"{p.name}:{p.type}" for p in entity_spec.properties)
            lines.append(
                f"ENTITY {entity_spec.name}"
                + (f" ({entity_spec.supertype})" if entity_spec.supertype else "")
                + f"; keys: {keys}; properties: {props}"
            )
        serialized = "\n".join(lines)

        tokens = max(1, len(serialized) // 4)
        if tokens > PROMPT_TOKEN_WARN_THRESHOLD:
            logger.warning(
                "serialized ontology exceeds prompt token budget",
                estimate_tokens=tokens,
                threshold=PROMPT_TOKEN_WARN_THRESHOLD,
            )
        else:
            logger.info("serialized ontology token estimate", estimate_tokens=tokens)
        return serialized

    def to_prompt_dict(self) -> dict[str, Any]:
        """Serializable projection used by the NL-to-Cypher prompt."""
        return {
            "version": self.version,
            "relations": [
                {
                    "name": r.name,
                    "domain": r.domain,
                    "range": r.range,
                    "temporal": r.temporal,
                }
                for r in self.relation_types.values()
            ],
            "entities": [
                {
                    "name": e.name,
                    "supertype": e.supertype,
                    "identifying_keys": e.identifying_keys,
                }
                for e in self.entity_types.values()
            ],
        }
