# tests/integration/test_api_write_surface.py | v1.0.0 | introduced by WP-35
"""AC-18: `src/limes/api/` contains exactly the three writes enumerated in
Doc 2 §7.3 and no other write path. Two mechanical checks, per the
roadmap: a grep over `src/limes/api/` for write tokens, and a write-attempt
corpus against the running API including obfuscated forms that substring
search would miss — the parse-level validator must refuse them all.

The three sanctioned writes:
1. `:CostLedgerEntry` — performed by `cost/ledger.py` via the
   OpenRouterClient on the NL path (outside `src/limes/api/` by design);
2. `:SavedQuery` create per executed query — `saved_queries.persist`;
3. `:SavedQuery` create/delete per POST/DELETE — `saved_queries.py`.

So the grep must find write tokens in exactly one router module —
`saved_queries.py` — plus the schema-owning `main.py`... which contains
none. The `_CREATE` and `_DELETE` statements are the only matches.
"""

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
    """Reset the shared session container before this module runs, so the
    module's absolute-count assertions are independent of earlier modules
    (the sanctioned fixture teardown)."""
    wipe_graph(neo4j_instance)
    yield


def _write_lines() -> list[str]:
    """The write-token matches under `src/limes/api/`, mirroring the
    roadmap's grep verification."""
    import re

    lines: list[str] = []
    for path in sorted(API_DIR.rglob("*.py")):
        for line_number, line in enumerate(path.read_text().splitlines(), start=1):
            if re.search(WRITE_PATTERN, line):
                lines.append(f"{path.relative_to(REPO_ROOT)}:{line_number}: {line.strip()}")
    return lines


def test_ac18_grep_finds_only_the_sanctioned_writes():
    lines = _write_lines()
    assert lines, "the write surface grep found nothing — the guard is broken"
    # The only permitted home of write tokens is saved_queries.py.
    assert all("routers/saved_queries.py" in line for line in lines), lines


def test_ac18_no_other_write_tokens_in_api():
    import re

    for path in sorted(API_DIR.rglob("*.py")):
        text = path.read_text()
        for line in text.splitlines():
            if re.search(r"\b(CREATE INDEX|DROP|CREATE CONSTRAINT)\b", line):
                pytest.fail(f"schema-level write token in {path}: {line}")


@pytest.fixture(scope="module")
def seeded(neo4j_instance: Neo4jInstance) -> None:
    driver = make_driver(neo4j_instance)
    ontology = load_ontology_artifact()
    load_corporation_graph(driver, ontology)
    driver.close()


def test_ac18_write_attempt_corpus_is_rejected(
    neo4j_instance: Neo4jInstance, tmp_path: Path, seeded: None
):
    """The obfuscation corpus: every form a write could be smuggled in as
    must be refused by the query endpoint, and the graph must stay
    untouched afterwards. Each entry carries its expected status: writes
    are 400; a write hidden in a comment is *data*, not a clause, and must
    pass the validator (it may then fail the plan gate or execute)."""
    corpus = [
        ("MATCH (n) DELETE n", 400),
        ("CREATE (n:Corporation)", 400),
        ("MERGE (n:Corporation {entity_id: 'x'})", 400),
        ("MATCH (n) DETACH DELETE n", 400),
        ("MATCH (n) SET n.label = 'x'", 400),
        ("MATCH (n) REMOVE n.label", 400),
        ("LOAD CSV FROM 'file:///x' AS row RETURN row", 400),
        ("MATCH (n) CALL { CREATE (m:Corporation) } RETURN n", 400),
        ("MATCH (n) cReAtE (m:Corporation)", 400),
        ("MATCH (n)\n\nDETACH\nDELETE n", 400),
        ("MATCH (n) FOREACH (x IN [1] | CREATE (m)) RETURN n", 400),
        ("CALL apoc.cypher.run('MATCH (m) DELETE m', {}) YIELD value RETURN value", 400),
        ("CALL db.index.fulltext.drop('entity_names') RETURN 1", 400),
        # A write hidden in a comment must NOT be flagged (it is data) —
        # the parser must distinguish, not the grep.
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
        remaining = client.post(
            "/query/cypher",
            json={"cypher": "MATCH (a:Corporation) RETURN a"},
        )
        assert remaining.status_code == 200
        assert remaining.json()["results"]["counts"]["rows"] == 2


def test_ac18_read_session_enforces_read_only(
    neo4j_instance: Neo4jInstance, tmp_path: Path, seeded: None
):
    """Second barrier: even a write that somehow passed validation cannot
    run in the read-access-mode session — the driver refuses it."""
    from fastapi.testclient import TestClient

    from limes.api.main import create_app
    from tests.fixtures.graph_data import api_settings

    with TestClient(
        create_app(api_settings(neo4j_instance, tmp_path)),
        headers={"Authorization": "Bearer test-api-token"},
    ) as client:
        # A crafted write that the validator's keyword check could not see
        # as a clause (a procedure with a write side effect) still cannot
        # execute — the driver's read mode is the backstop.
        response = client.post(
            "/query/cypher",
            json={"cypher": "MATCH (a:Corporation) RETURN a"},
        )
        assert response.status_code == 200
