# tests/acceptance/test_ac01_config.py | v1.0.0 | introduced by WP-39
"""AC-01: startup fails with a named key when any required configuration
is absent, and when the ontology artifact is older than the version
stamped in the graph.

The missing-key half runs in a real subprocess with its working directory
pointed away from the repository — the repository's own `.env` would
otherwise supply the value and mask the defect. The downgrade-guard half
runs against the disposable container: a graph stamped by the loader
(production path) with a newer artifact version, then provisioning with
the older committed artifact must refuse.

The module wipes the shared container before and after: the stamped
`99.0.0` version would trip every later module's `provision`.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from limes.errors import OntologyError
from limes.graph.driver import GraphDriver
from limes.graph.loader import load
from limes.graph.schema import provision
from limes.ontology.registry import load_ontology
from tests.fixtures.graph_data import assertion, endpoint, wipe_graph
from tests.integration.conftest import Neo4jInstance

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"

REQUIRED_KEYS = (
    "LIMES_NEO4J_URI",
    "LIMES_NEO4J_USER",
    "LIMES_NEO4J_PASSWORD",
    "LIMES_ONTOLOGY_PATH",
    "LIMES_FEEDS_CONFIG_PATH",
    "LIMES_GOLD_SET_PATH",
    "LIMES_BASELINE_PATH",
    "LIMES_ARCHIVE_PATH",
)


@pytest.fixture(scope="module", autouse=True)
def _clean_container(neo4j_instance: Neo4jInstance):
    """The stamped 99.0.0 artifact version must not outlive this module —
    `provision`'s downgrade guard would refuse every later module."""
    yield
    wipe_graph(neo4j_instance)


def test_ac01_missing_configuration_key_names_it_in_a_clean_process(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
):
    """Startup (`load_settings`) in a fresh OS process whose environment
    lacks one required key must fail naming that key. The cwd is a temp
    directory so the repository's `.env` cannot fill the gap."""
    env = dict(os.environ)
    for key in REQUIRED_KEYS:
        env.pop(key, None)
    # `neo4j_uri` has no default and is in the required set — an absent
    # value must fail startup naming it. (A defaulted key like
    # `neo4j_database` would silently satisfy the load.)
    env.pop("LIMES_NEO4J_URI", None)
    env["PYTHONPATH"] = str(REPO_ROOT / "src")

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from limes.config import load_settings; load_settings()",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode != 0, "startup succeeded with a required key absent"
    assert "neo4j_uri" in result.stderr, result.stderr


def test_ac01_empty_required_key_names_it(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """The empty-value form of AC-01: a key present but blank is the same
    failure, naming the key."""
    from limes.config import load_settings
    from limes.errors import ConfigurationError

    monkeypatch.chdir(tmp_path)  # no legacy/split file can fill the empty required key
    for key in REQUIRED_KEYS:
        monkeypatch.setenv(key, "set")
    monkeypatch.setenv("LIMES_NEO4J_USER", "")
    with pytest.raises(ConfigurationError, match="neo4j_user"):
        load_settings()


def test_ac01_older_ontology_artifact_is_refused(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
):
    """A graph stamped by the loader with a newer ontology version must
    make provisioning with the older committed artifact fail — the startup
    guard of §4.3, exercised through the production writer."""
    driver = GraphDriver(
        neo4j_instance.uri,
        neo4j_instance.user,
        neo4j_instance.password,
        neo4j_instance.database,
    )
    try:
        wipe_graph(neo4j_instance)
        committed = load_ontology(ONTOLOGY_PATH)
        provision(driver, committed, embedding_dimensions=1024)

        newer = committed.model_copy(update={"version": "99.0.0"})
        subject = endpoint("downgrade-a", "Corporation", "Downgrade A")
        object_ = endpoint("downgrade-b", "Corporation", "Downgrade B")
        stamped = assertion(
            "downgrade-1",
            subject,
            "SUBSIDIARY_OF",
            object_,
            source_id="s-downgrade",
        )
        stamped.provenance.ontology_version = "99.0.0"
        load(driver, [stamped], newer)

        with pytest.raises(OntologyError, match="older than the version"):
            provision(driver, committed, embedding_dimensions=1024)
    finally:
        driver.close()
        wipe_graph(neo4j_instance)
