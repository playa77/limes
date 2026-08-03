# tests/acceptance/test_ac39_lookups.py | v1.0.0 | introduced by WP-39
"""AC-39: a value written as a `LookupRow` by one CLI invocation is
readable by `postal_code_to_nuts` in a separate operating-system process;
a miss returns `None` without raising.

The `:PostalCode` node is written through the production ingestion path —
`execute_run` over the recorded GISCO fixture (Trace 1) — and read from a
fresh OS process via `subprocess` (Doc 2 §12.2 rule 2).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from limes.graph.driver import GraphDriver
from limes.graph.lookups import clear_cache, postal_code_to_nuts
from tests.acceptance.conftest import acceptance_settings, gisco_fixture_records
from tests.fixtures.graph_data import wipe_graph
from tests.integration.conftest import Neo4jInstance

REPO_ROOT = Path(__file__).resolve().parents[2]

# A correspondence present in the recorded GISCO fixture (and its miss).
PRESENT = ("FI", "15701")
ABSENT = ("DE", "99999")


def test_ac39_lookup_is_readable_from_a_separate_process(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Trace 1 writes the correspondence; a fresh process reads it back and
    a miss returns None without raising."""
    from limes.composition import build_run_context
    from limes.pipeline.run import RunSpec, execute_run
    from limes.sources.gisco_nuts import GiscoNutsAdapter

    wipe_graph(neo4j_instance)
    records = gisco_fixture_records()
    monkeypatch.setattr(GiscoNutsAdapter, "fetch", lambda self, s, u: iter(records))

    ctx = build_run_context(acceptance_settings(neo4j_instance, tmp_path), needs_inference=False)
    try:
        record = execute_run(RunSpec(source_id="gisco_nuts", mode="ingest"), ctx)
        assert record.assertions_written > 0, "the GISCO run must write content"
    finally:
        ctx.driver.close()

    # The postal correspondence landed in the graph: the reader in this
    # process confirms before the subprocess does the cross-process read.
    from limes.graph.lookups import postal_code_to_nuts

    clear_cache()
    driver = GraphDriver(
        neo4j_instance.uri,
        neo4j_instance.user,
        neo4j_instance.password,
        neo4j_instance.database,
    )
    try:
        assert postal_code_to_nuts(driver, *PRESENT) is not None
    finally:
        driver.close()
        clear_cache()

    script = (
        "import os\n"
        "from limes.graph.driver import GraphDriver\n"
        "from limes.graph.lookups import postal_code_to_nuts\n"
        "d = GraphDriver(os.environ['URI'], os.environ['USER'], "
        "os.environ['PASSWORD'], os.environ['DB'])\n"
        "nuts = postal_code_to_nuts(d, 'FI', '15701')\n"
        "assert nuts is not None, 'the written correspondence must be readable'\n"
        "assert postal_code_to_nuts(d, 'DE', '99999') is None, 'a miss must return None'\n"
        "print('CROSS-PROCESS OK')\n"
    )
    env = {
        **os.environ,
        "URI": neo4j_instance.uri,
        "USER": neo4j_instance.user,
        "PASSWORD": neo4j_instance.password,
        "DB": neo4j_instance.database,
        "PYTHONPATH": str(REPO_ROOT / "src"),
    }
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "CROSS-PROCESS OK" in result.stdout


def test_ac39_miss_returns_none_without_raising(
    neo4j_instance: Neo4jInstance,
):
    clear_cache()
    driver = GraphDriver(
        neo4j_instance.uri,
        neo4j_instance.user,
        neo4j_instance.password,
        neo4j_instance.database,
    )
    try:
        assert postal_code_to_nuts(driver, *ABSENT) is None
        assert postal_code_to_nuts(driver, "XX", "00000") is None
    finally:
        driver.close()
        clear_cache()
