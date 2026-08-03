# tests/unit/test_api_models.py | v1.0.0 | introduced by WP-32
"""API response model unit tests per Doc 2 §6.

`GraphResult.from_rows` is the one conversion from raw driver output to the
response shape. These tests pin the recognition and deduplication rules
with driver-typed values (Node/Relationship/Path): dict projections, nested
paths and lists, the assertion-dict skip, and the concrete-type derivation
for multi-label nodes.
"""

from datetime import UTC, datetime
from pathlib import Path as FilePath

import pytest
from neo4j.graph import Node, Relationship
from neo4j.graph import Path as Neo4jPath

from limes.api.models import GraphResult, native_datetime
from limes.ontology.model import EntityTypeSpec, Ontology
from limes.ontology.registry import load_ontology

REPO_ROOT = FilePath(__file__).resolve().parents[2]
ONTOLOGY = load_ontology(REPO_ROOT / "ontology" / "ontology.yaml")


def _node(element_id: str, labels=("Corporation",), **properties) -> Node:
    return Node(
        graph=None,
        element_id=element_id,
        id_=int(element_id[1:]),
        n_labels=labels,
        properties=properties,
    )


def _rel(element_id: str, start: Node, end: Node, **properties) -> Relationship:
    rel = Relationship(
        graph=None, element_id=element_id, id_=int(element_id[1:]), properties=properties
    )
    rel._start_node = start  # the driver hydrates these; tests wire them
    rel._end_node = end
    return rel


def test_dict_node_projection_is_collected():
    rows = [
        {
            "n": {
                "entity_id": "e1",
                "label": "Alpha",
                "lei": "X1",
                "ontology_version": "1.0.0",
                "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            }
        }
    ]
    result = GraphResult.from_rows(rows, ONTOLOGY)
    assert len(result.nodes) == 1
    node = result.nodes[0]
    # A dict projection has no labels: the concrete type is the root.
    assert node.type == "Entity"
    assert node.label == "Alpha"
    assert node.properties == {"lei": "X1"}
    assert node.ontology_version == "1.0.0"
    assert result.counts["rows"] == 1


def test_dict_without_entity_id_is_ignored():
    result = GraphResult.from_rows([{"n": {"label": "Alpha"}}], ONTOLOGY)
    assert result.nodes == []
    assert result.edges == []


def test_dict_hiding_its_entity_id_key_is_refused():
    # `collect` recognizes a dict by membership *and* by its `get` result; a
    # dict whose membership test hides the key but whose value is present
    # reaches the add_node guard, which then refuses it.
    class HidingDict(dict):
        def __contains__(self, key):
            return False if key == "entity_id" else super().__contains__(key)

    hidden = HidingDict(entity_id="e1", label="Alpha")
    result = GraphResult.from_rows([{"n": hidden}], ONTOLOGY)
    assert result.nodes == []
    assert result.edges == []


def test_dict_node_deduplicated_by_entity_id():
    rows = [
        {"n": {"entity_id": "e1", "label": "Alpha"}},
        {"m": {"entity_id": "e1", "label": "Alpha again"}},
    ]
    result = GraphResult.from_rows(rows, ONTOLOGY)
    assert len(result.nodes) == 1
    # First occurrence wins.
    assert result.nodes[0].label == "Alpha"


def test_driver_node_deduplicated_by_entity_id():
    n1 = _node("n1", entity_id="e1", label="Alpha")
    n2 = _node("n2", entity_id="e1", label="Beta")
    result = GraphResult.from_rows([{"a": n1}, {"b": n2}], ONTOLOGY)
    assert len(result.nodes) == 1


def test_relationship_deduplicated_by_element_id():
    n1 = _node("n1", entity_id="e1", label="Alpha")
    n2 = _node("n2", entity_id="e2", label="Beta")
    rel = _rel("r1", n1, n2, source_id="s1")
    result = GraphResult.from_rows([{"a": rel}, {"b": rel}], ONTOLOGY)
    assert len(result.edges) == 1
    assert result.edges[0].subject_id == "e1"
    assert result.edges[0].object_id == "e2"
    assert result.edges[0].source_id == "s1"


def test_path_is_flattened_into_nodes_and_edges():
    n1 = _node("n1", entity_id="e1", label="Alpha")
    n2 = _node("n2", entity_id="e2", label="Beta")
    rel = _rel("r1", n1, n2, assertion_id="a1")
    path = Neo4jPath(n1, rel)
    result = GraphResult.from_rows([{"p": path}], ONTOLOGY)
    assert {node.entity_id for node in result.nodes} == {"e1", "e2"}
    assert len(result.edges) == 1


def test_assertion_dict_is_not_treated_as_a_node():
    rows = [{"r": {"assertion_id": "a1", "relation": "SUBSIDIARY_OF"}}]
    result = GraphResult.from_rows(rows, ONTOLOGY)
    assert result.nodes == []
    assert result.edges == []


def test_nested_lists_are_collected_recursively():
    n1 = _node("n1", entity_id="e1", label="Alpha")
    rows = [{"nested": [[{"entity_id": "e1", "label": "Alpha"}], n1]}]
    result = GraphResult.from_rows(rows, ONTOLOGY)
    assert len(result.nodes) == 1


def test_multi_label_node_gets_the_most_specific_type():
    chained = Ontology(
        version="9.9.9",
        supertypes=["Agent"],
        entity_types={
            "Org": EntityTypeSpec(name="Org", supertype="Agent", identifying_keys=[]),
            "Corporation": EntityTypeSpec(name="Corporation", supertype="Org", identifying_keys=[]),
        },
        relation_types={},
    )
    node = _node("n1", labels=("Corporation", "Org"), entity_id="e1", label="Alpha")
    result = GraphResult.from_rows([{"n": node}], chained)
    assert result.nodes[0].type == "Corporation"


def test_native_datetime_rejects_unexpected_to_native_results():
    class FakeTime:
        def to_native(self):
            return "2026-01-01"

    with pytest.raises(TypeError, match="unexpected time value"):
        native_datetime(FakeTime())


def test_native_datetime_rejects_plain_non_time_values():
    # A value that is neither None, nor datetime, nor driver-time-shaped is
    # a malformed shape and must not silently become null in a response.
    with pytest.raises(TypeError, match="unexpected time value"):
        native_datetime("2026-01-01")
