# tests/integration/test_cli_lock.py | v1.0.0 | introduced by WP-28
"""Advisory lock tests (Doc 2 §8.14, §5.8 `:AdvisoryLock`).

G3: a second acquire on the same source fails while the lock is held; a
stale lock is reclaimed with a warning; release clears the node. The
cross-process test proves the refusal is honored across a real process
boundary — a second CLI invocation fails at the lock check, before any
fetch, so no network is involved.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from limes.cli.main import acquire_lock, reclaim_stale_lock, release_lock
from limes.errors import LimesError
from tests.integration.conftest import Neo4jInstance

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"


@pytest.fixture
def graph(neo4j_instance: Neo4jInstance):
    from limes.graph.driver import GraphDriver

    driver = GraphDriver(
        neo4j_instance.uri,
        neo4j_instance.user,
        neo4j_instance.password,
        neo4j_instance.database,
    )
    driver.write_batch([("MATCH (n) DETACH DELETE n", {})])
    yield driver
    driver.close()


def _lock_rows(graph) -> list[dict]:
    return graph.read(
        "MATCH (l:AdvisoryLock {source_id: 'gisco_nuts'}) "
        "RETURN l.run_id AS run_id, l.acquired_at AS acquired_at",
        {},
        30,
    )


def test_second_acquire_refuses_while_held(graph):
    acquire_lock(graph, "gisco_nuts", "run-1")
    with pytest.raises(LimesError, match="advisory lock held"):
        acquire_lock(graph, "gisco_nuts", "run-2")
    rows = _lock_rows(graph)
    assert len(rows) == 1
    assert rows[0]["run_id"] == "run-1"


def test_release_clears_the_lock(graph):
    acquire_lock(graph, "gisco_nuts", "run-1")
    release_lock(graph, "gisco_nuts")
    assert _lock_rows(graph) == []
    # Release is idempotent: a missing lock is a no-op.
    release_lock(graph, "gisco_nuts")


def test_stale_lock_is_reclaimed_with_warning(graph):
    acquire_lock(graph, "gisco_nuts", "run-1")
    # A run_timeout of zero makes any held lock stale — the production
    # function's own parameter, not an aged fixture.
    reclaim_stale_lock(graph, "gisco_nuts", run_timeout=0)
    assert _lock_rows(graph) == []
    # The reclaimed lock is gone, so a fresh acquire succeeds.
    acquire_lock(graph, "gisco_nuts", "run-2")
    assert len(_lock_rows(graph)) == 1


def test_fresh_lock_is_not_reclaimed(graph):
    acquire_lock(graph, "gisco_nuts", "run-1")
    reclaim_stale_lock(graph, "gisco_nuts", run_timeout=4 * 3600)
    assert len(_lock_rows(graph)) == 1


def test_lock_refusal_crosses_a_real_process_boundary(
    neo4j_instance: Neo4jInstance, graph, tmp_path
):
    # G3 (subprocess): the holding lock is created in this process; a fresh
    # CLI invocation on the same source fails at the lock check with exit 1
    # and never reaches the adapter's fetch — no network is involved, and
    # the refusal is proven across a real process boundary.
    acquire_lock(graph, "gisco_nuts", "holder-run")

    env = {
        **os.environ,
        "LIMES_NEO4J_URI": neo4j_instance.uri,
        "LIMES_NEO4J_USER": neo4j_instance.user,
        "LIMES_NEO4J_PASSWORD": neo4j_instance.password,
        "LIMES_NEO4J_DATABASE": neo4j_instance.database,
        "LIMES_ONTOLOGY_PATH": str(ONTOLOGY_PATH),
        "LIMES_FEEDS_CONFIG_PATH": str(REPO_ROOT / "ontology" / "feeds.yaml"),
        "LIMES_GOLD_SET_PATH": str(tmp_path / "gold_set.jsonl"),
        "LIMES_BASELINE_PATH": str(tmp_path / "baseline.json"),
        "LIMES_ARCHIVE_PATH": str(tmp_path / "archive"),
    }
    result = subprocess.run(
        [sys.executable, "-m", "limes.cli.main", "ingest", "--source", "gisco_nuts"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
        timeout=120,
    )
    assert result.returncode == 1
    assert "advisory lock held" in result.stderr
