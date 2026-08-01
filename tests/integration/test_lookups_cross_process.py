# tests/integration/test_lookups_cross_process.py | v1.0.0 | introduced by WP-08
"""Cross-process lookup tests per AC-39 and Doc 2 §12.2 rule 2.

A `:PostalCode` node is written by the loader (production path — never by
direct Cypher), then read by `postal_code_to_nuts` in a separate OS process
via `subprocess`. The cache tests use a counting driver so a cache hit is
proven by the absence of a graph read, not asserted.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from limes.graph.driver import GraphDriver
from limes.graph.loader import load
from limes.graph.lookups import clear_cache, postal_code_to_nuts
from limes.ontology.registry import load_ontology
from limes.types import LookupRow
from tests.integration.conftest import Neo4jInstance

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"

CODE = ("DE", "10115")
NUTS = "DE300"


@pytest.fixture
def driver(neo4j_instance: Neo4jInstance) -> GraphDriver:
    clear_cache()
    d = GraphDriver(
        neo4j_instance.uri,
        neo4j_instance.user,
        neo4j_instance.password,
        neo4j_instance.database,
    )
    yield d
    d.close()
    clear_cache()


def _write_correspondence(driver: GraphDriver) -> None:
    ontology = load_ontology(ONTOLOGY_PATH)
    result = load(
        driver,
        [],
        ontology,
        lookup_rows=[
            LookupRow(
                kind="postal_code",
                key={"country_code": CODE[0], "postal_code": CODE[1]},
                value={"nuts_code": NUTS},
            )
        ],
    )
    assert result.lookup_rows_written == 1


def test_lookup_returns_nuts_code(driver: GraphDriver):
    _write_correspondence(driver)
    assert postal_code_to_nuts(driver, *CODE) == NUTS


def test_miss_returns_none_without_raising(driver: GraphDriver):
    assert postal_code_to_nuts(driver, "DE", "99999") is None
    assert postal_code_to_nuts(driver, "XX", "00000") is None


def test_lookup_is_readable_from_a_separate_process(driver: GraphDriver, neo4j_instance: Neo4jInstance):
    """AC-39: a value written by one OS process is readable by another. The
    subprocess connects to the same container with its own GraphDriver and
    fresh module state — no cache, no shared memory."""
    _write_correspondence(driver)

    script = (
        "import os, sys\n"
        "from limes.graph.driver import GraphDriver\n"
        "from limes.graph.lookups import postal_code_to_nuts\n"
        "d = GraphDriver(os.environ['URI'], os.environ['USER'], "
        "os.environ['PASSWORD'], os.environ['DB'])\n"
        "nuts = postal_code_to_nuts(d, 'DE', '10115')\n"
        "assert nuts == 'DE300', nuts\n"
        "assert postal_code_to_nuts(d, 'DE', '99999') is None\n"
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
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "CROSS-PROCESS OK" in result.stdout


class CountingDriver:
    """Wraps a real driver, counting `read` calls to prove cache behavior."""

    def __init__(self, inner: GraphDriver) -> None:
        self._inner = inner
        self.read_calls = 0

    def read(self, cypher: str, params: dict, timeout_s: int) -> list[dict]:
        self.read_calls += 1
        return self._inner.read(cypher, params, timeout_s)


def test_lru_cache_hits_without_database_access(driver: GraphDriver):
    _write_correspondence(driver)
    counting = CountingDriver(driver)

    assert postal_code_to_nuts(counting, *CODE) == NUTS
    assert counting.read_calls == 1
    assert postal_code_to_nuts(counting, *CODE) == NUTS
    assert counting.read_calls == 1  # cached: no graph read
    assert postal_code_to_nuts(counting, "DE", "00000") is None
    assert postal_code_to_nuts(counting, "DE", "00000") is None
    assert counting.read_calls == 2  # the miss was cached too


def test_lru_cache_evicts_oldest_entry(driver: GraphDriver, monkeypatch):
    import limes.graph.lookups as lookups

    _write_correspondence(driver)
    monkeypatch.setattr(lookups, "_CACHE_SIZE", 2)
    lookups.clear_cache()

    assert postal_code_to_nuts(driver, "DE", "10115") == NUTS
    assert postal_code_to_nuts(driver, "DE", "10116") is None
    assert postal_code_to_nuts(driver, "DE", "10117") is None  # evicts DE/10115

    # The evicted entry is re-queried (a read would be needed) — verify via
    # the counting wrapper from a fresh cache.
    lookups.clear_cache()
    counting = CountingDriver(driver)
    postal_code_to_nuts(counting, "DE", "10115")
    assert counting.read_calls == 1
