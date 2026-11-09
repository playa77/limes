# desktop/tests/contract/test_no_ontology_literals.py | v1.1.0 | AC-DC-4 guard
"""AC-DC-4: no ontology type/relation literals in the desktop client.

The desktop client is schema-driven: it must never hold an entity type
name, a relation name, or a Cypher clause fragment as a string literal —
those come from the ontology artifact via the API. The Python launcher is
scanned through its AST; the web client's TypeScript sources are scanned
with a string-literal tokenizer over quotes/backticks (comments excluded),
so both halves of the DC-17 client are guarded by one ontology-derived
name set.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from limes.ontology.registry import load_ontology

REPO_ROOT = Path(__file__).resolve().parents[3]
CLIENT_ROOT = REPO_ROOT / "desktop" / "src" / "limes_desktop"
WEB_SRC_ROOT = REPO_ROOT / "desktop" / "web" / "src"
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"

CYPHER_KEYWORDS = (
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

_STRING_RE = re.compile(
    r"(?s)"  # span-related, not needed; backticks may cover lines
    r'"(?:[^"\\\n]|\\.)*"'  # "..."
    r"|'(?:[^'\\\n]|\\.)*'"  # '...'
    r"|`(?:[^`\\]|\\.)*`"  # `...`
)


def _ontology_names() -> set[str]:
    ontology = load_ontology(ONTOLOGY_PATH)
    return set(ontology.entity_types) | set(ontology.relation_types)


def test_no_ontology_literals_in_python_launcher() -> None:
    names = _ontology_names()
    py_files = list(CLIENT_ROOT.rglob("*.py"))
    assert py_files, f"no client sources found under {CLIENT_ROOT}"
    for py_file in py_files:
        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert node.value not in names, f"{py_file.name}: literal {node.value!r}"
                assert not any(keyword in node.value for keyword in CYPHER_KEYWORDS), (
                    f"{py_file.name}: literal {node.value!r} contains a Cypher keyword"
                )


def test_no_ontology_literals_in_web_client() -> None:
    names = _ontology_names()
    web_files = sorted(WEB_SRC_ROOT.rglob("*.ts")) + sorted(WEB_SRC_ROOT.rglob("*.tsx"))
    assert web_files, f"no web sources found under {WEB_SRC_ROOT}"
    for web_file in web_files:
        text = web_file.read_text()
        for match in _STRING_RE.finditer(text):
            literal = match.group(0)
            inner = literal[1:-1]
            clean = inner.replace("\\\"", '"').replace("\\'", "'").replace("\\`", "`")
            assert clean not in names, f"{web_file.name}: literal {clean!r}"
            keywords = [keyword for keyword in CYPHER_KEYWORDS if keyword in clean]
            assert not keywords, f"{web_file.name}: literal {clean!r} holds {keywords}"
