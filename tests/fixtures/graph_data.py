# tests/fixtures/graph_data.py | v1.0.0 | introduced by WP-32
"""Shared graph-building helpers for the API/query integration tests.

Test-construction rule (Doc 2 §12.2): no test may hand-build the state the
code under test is supposed to produce. All graph state here is produced by
calling the production path — `graph/loader.py::load` — exactly as the
loader's own tests do. The helpers return the ids and labels the tests
assert against.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from limes.config import Settings
from limes.graph.driver import GraphDriver
from limes.graph.loader import load
from limes.graph.schema import provision
from limes.ontology.model import Ontology
from limes.ontology.registry import load_ontology
from limes.types import Assertion, EntityEndpoint, Provenance, Validity
from tests.integration.conftest import Neo4jInstance

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"

NOW = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)
V_2020 = datetime(2020, 1, 1, tzinfo=UTC)


def load_ontology_artifact() -> Ontology:
    return load_ontology(ONTOLOGY_PATH)


def make_driver(neo4j_instance: Neo4jInstance) -> GraphDriver:
    return GraphDriver(
        neo4j_instance.uri,
        neo4j_instance.user,
        neo4j_instance.password,
        neo4j_instance.database,
    )


def provisioned_driver(neo4j_instance: Neo4jInstance) -> GraphDriver:
    driver = make_driver(neo4j_instance)
    provision(driver, load_ontology_artifact(), embedding_dimensions=1024)
    return driver


def api_settings(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    **overrides: Any,
) -> Settings:
    base: dict[str, Any] = {
        "neo4j_uri": neo4j_instance.uri,
        "neo4j_user": neo4j_instance.user,
        "neo4j_password": neo4j_instance.password,
        "neo4j_database": neo4j_instance.database,
        "ontology_path": ONTOLOGY_PATH,
        "feeds_config_path": REPO_ROOT / "ontology" / "feeds.yaml",
        "gold_set_path": tmp_path / "gold_set.jsonl",
        "baseline_path": tmp_path / "baseline.json",
        "archive_path": tmp_path / "archive",
        "openrouter_api_key": "sk-test",
        "openrouter_base_url": "https://openrouter.test/api/v1",
        "nl2cypher_model": "test/nl2cypher",
        "embedding_model": "test/embed",
        "http_timeout_seconds": 10,
    }
    base.update(overrides)
    return Settings(**base)


def endpoint(
    entity_id: str,
    type_: str = "Corporation",
    label: str | None = None,
    key: tuple[str, str] | None = None,
) -> EntityEndpoint:
    return EntityEndpoint(
        entity_id=entity_id,
        type=type_,
        label=label or f"Entity {entity_id}",
        deterministic_key=key,
        aliases=[f"alias-{entity_id}"],
    )


def assertion(
    assertion_id: str,
    subject: EntityEndpoint,
    relation: str,
    object_: EntityEndpoint,
    *,
    source_id: str = "test-source",
    valid_from: datetime = V_2020,
    valid_to: datetime | None = None,
    trust: float = 0.9,
) -> Assertion:
    return Assertion(
        assertion_id=assertion_id,
        subject=subject,
        relation=relation,
        object=object_,
        validity=Validity(valid_from=valid_from, valid_to=valid_to, recorded_at=NOW),
        provenance=Provenance(
            source_id=source_id,
            source_trust=trust,
            confidence=0.9,
            extractor_model="test-model",
            prompt_version="1.0.0",
            schema_version="1.0.0",
            ontology_version="1.0.0",
        ),
    )


def load_corporation_graph(driver: GraphDriver, ontology: Ontology) -> dict[str, str]:
    """Load a small deterministic graph — two corporations, a location, a
    person, and three relationships — via the production path. Returns the
    entity ids by role."""
    alpha = endpoint("corp-alpha", "Corporation", "Alpha Industries", key=("lei", "LEI-ALPHA"))
    beta = endpoint("corp-beta", "Corporation", "Beta GmbH", key=("lei", "LEI-BETA"))
    hq = endpoint("hq-berlin", "Location", "Berlin HQ", key=("geonames_id", "GN-1"))
    boss = endpoint("person-ada", "Person", "Ada Lovelace")

    assertions = [
        assertion("a1", alpha, "SUBSIDIARY_OF", beta, source_id="test-source"),
        assertion("a2", alpha, "HEADQUARTERED_IN", hq, source_id="test-source"),
        assertion("a3", boss, "DIRECTOR_OF", alpha, source_id="test-source"),
    ]
    load(driver, assertions, ontology, standalone_entities=[])
    return {
        "alpha": alpha.entity_id,
        "beta": beta.entity_id,
        "hq": hq.entity_id,
        "boss": boss.entity_id,
    }


def load_closed_interval_graph(driver: GraphDriver, ontology: Ontology) -> dict[str, str]:
    """Load a corporation pair with a superseded SUBSIDIARY_OF interval —
    the state the temporal-filter tests need. Its own entity and assertion
    ids, so it is independent of `load_corporation_graph` in any order."""
    alpha = endpoint("ci-alpha", "Corporation", "Interval Alpha")
    beta = endpoint("ci-beta", "Corporation", "Interval Beta")
    load(
        driver,
        [
            assertion(
                "ci-1",
                alpha,
                "SUBSIDIARY_OF",
                beta,
                valid_from=datetime(2018, 1, 1, tzinfo=UTC),
                valid_to=datetime(2020, 6, 1, tzinfo=UTC),
            ),
            assertion(
                "ci-2",
                alpha,
                "SUBSIDIARY_OF",
                beta,
                valid_from=datetime(2020, 6, 1, tzinfo=UTC),
            ),
        ],
        ontology,
    )
    return {"alpha": alpha.entity_id, "beta": beta.entity_id}


def make_api_client(neo4j_instance: Neo4jInstance, tmp_path: Path, **overrides: Any):
    """A FastAPI `TestClient` for the real application with settings
    pointing at the disposable test database. Context-managed: entering it
    runs the startup handler (settings, ontology, driver, provision,
    reachability)."""
    from fastapi.testclient import TestClient

    from limes.api.main import create_app

    settings = api_settings(neo4j_instance, tmp_path, **overrides)
    return TestClient(create_app(settings))


def wipe_graph(neo4j_instance: Neo4jInstance) -> None:
    """The sanctioned fixture-teardown exception to the delete ban (the
    pattern of the CLI tests' `graph` fixture): reset the shared session
    container so module fixtures stay order-independent and the loader
    tests' fresh-graph premises hold."""
    driver = make_driver(neo4j_instance)
    try:
        driver.write_batch([("MATCH (n) DETACH DELETE n", {})])
    finally:
        driver.close()
