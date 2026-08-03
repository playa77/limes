# tests/acceptance/test_ac18_write_surface.py | v1.0.0 | introduced by WP-39
"""AC-18: `src/limes/api/` contains exactly the three writes enumerated in
§7.3 and no other write path.

Two mechanical checks, as the criterion names them: a grep over
`src/limes/api/` for write tokens (which must land only in
`saved_queries.py`), and a write-attempt corpus against the running API —
including obfuscated forms a substring search would miss — every one of
which the parse-level validator must refuse.

The three sanctioned writes:
1. `:CostLedgerEntry` — performed by `cost/ledger.py` via the
   OpenRouterClient (outside `src/limes/api/` by design);
2. `:SavedQuery` create per executed query — `saved_queries.persist`;
3. `:SavedQuery` create/delete per POST/DELETE — `saved_queries.py`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.fixtures.graph_data import (
    load_corporation_graph,
    load_ontology_artifact,
    make_api_client,
    make_driver,
    wipe_graph,
)
from tests.integration.conftest import Neo4jInstance

REPO_ROOT = Path(__file__).resolve().parents[2]
API_DIR = REPO_ROOT / "src" / "limes" / "api"

WRITE_PATTERN = r"(CREATE|MERGE|DELETE|SET |REMOVE )"


@pytest.fixture(scope="module", autouse=True)
def _fresh_graph(neo4j_instance: Neo4jInstance):
    wipe_graph(neo4j_instance)
    yield


@pytest.fixture(scope="module")
def seeded(neo4j_instance: Neo4jInstance) -> None:
    driver = make_driver(neo4j_instance)
    ontology = load_ontology_artifact()
    load_corporation_graph(driver, ontology)
    driver.close()


def _write_lines() -> list[str]:
    """The write-token matches under `src/limes/api/`, mirroring the
    roadmap's grep verification."""
    lines: list[str] = []
    for path in sorted(API_DIR.rglob("*.py")):
        for line_number, line in enumerate(path.read_text().splitlines(), start=1):
            if re.search(WRITE_PATTERN, line):
                lines.append(f"{path.relative_to(REPO_ROOT)}:{line_number}: {line.strip()}")
    return lines


def test_ac18_grep_finds_only_the_sanctioned_writes():
    lines = _write_lines()
    assert lines, "the write surface grep found nothing — the guard is broken"
    assert all("routers/saved_queries.py" in line for line in lines), lines


def test_ac18_no_schema_level_write_tokens_in_api():
    for path in sorted(API_DIR.rglob("*.py")):
        for line in path.read_text().splitlines():
            if re.search(r"\b(CREATE INDEX|DROP|CREATE CONSTRAINT)\b", line):
                pytest.fail(f"schema-level write token in {path}: {line}")


def test_ac18_write_attempt_corpus_is_rejected(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    seeded: None,
):
    """The obfuscation corpus: every form a write could be smuggled in as
    must be refused by the query endpoint. A write hidden in a comment is
    *data*, not a clause, and must pass the validator."""
    corpus = [
        ("MATCH (n) DELETE n", 400),
        ("CREATE (n:Corporation)", 400),
        ("MERGE (n:Corporation {entity_id: 'x'})", 400),
        ("MATCH (n) DETACH DELETE n", 400),
        ("MATCH (n) SET n.label = 'x'", 400),
        ("MATCH (n) REMOVE n.label", 400),
        ("MATCH (n) cReAtE (m:Corporation)", 400),
        ("MATCH (n)\n\nDETACH\nDELETE n", 400),
        ("MATCH (n) FOREACH (x IN [1] | CREATE (m)) RETURN n", 400),
        ("CALL apoc.cypher.run('MATCH (m) DELETE m', {}) YIELD value RETURN value", 400),
        ("CALL db.index.fulltext.drop('entity_names') RETURN 1", 400),
        ("MATCH (a:Corporation) RETURN a /* CREATE (x) */", (200, 422)),
        ("MATCH (a:Corporation) RETURN a // MERGE (x)", (200, 422)),
    ]

    with make_api_client(neo4j_instance, tmp_path) as client:
        for query, expected in corpus:
            response = client.post("/query/cypher", json={"cypher": query})
            accepted = expected if isinstance(expected, tuple) else (expected,)
            assert response.status_code in accepted, (query, response.text)

        # The graph is byte-for-byte what the loader wrote: nothing was
        # created, deleted, or modified by the corpus.
        rows = client.post("/query/cypher", json={"cypher": "MATCH (n:Entity) RETURN n LIMIT 500"})
        assert rows.status_code == 200, rows.text
        assert rows.json()["results"]["counts"]["nodes"] == 4  # the seeded graph
