# desktop/tests/contract/test_no_ontology_literals.py | v0.1.0 | AC-DC-4 guard
"""AC-DC-4: no ontology type/relation literals in the desktop client.

The desktop client is schema-driven: it must never hold an entity type
name, a relation name, or a Cypher clause fragment as a string literal —
those come from the ontology artifact via the API. Mirrors the UI guard
in tests/integration/test_ui.py (G2) over desktop/src/limes_desktop/.
"""

from __future__ import annotations

import ast
from pathlib import Path

from limes.ontology.registry import load_ontology

REPO_ROOT = Path(__file__).resolve().parents[3]
CLIENT_ROOT = REPO_ROOT / "desktop" / "src" / "limes_desktop"
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"

CYIPHER_KEYWORDS = (
    "MATCH",
    "RETURN",
    "MERGE",
    "CREATE",
    "WHERE",
    "LIMIT",
    "UNWIND",
    "WITH",
    "DETACH",
    "SET",
    "REMOVE",
    "LOAD",
)


def test_no_ontology_literals() -> None:
    ontology = load_ontology(ONTOLOGY_PATH)
    names = set(ontology.entity_types) | set(ontology.relation_types)
    py_files = list(CLIENT_ROOT.rglob("*.py"))
    assert py_files, f"no client sources found under {CLIENT_ROOT}"
    for py_file in py_files:
        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert node.value not in names, f"{py_file.name}: literal {node.value!r}"
                assert not any(keyword in node.value for keyword in CYIPHER_KEYWORDS), (
                    f"{py_file.name}: literal {node.value!r} contains a Cypher keyword"
                )
