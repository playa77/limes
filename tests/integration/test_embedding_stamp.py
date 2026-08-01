# tests/integration/test_embedding_stamp.py | v1.0.0 | introduced by WP-25a
"""Integration tests for the §5.6 `label_embedding` merge stamp and the
one-shot backfill (WP-25a).

Test-construction rule: every node in the graph is created by calling the
production path under test — `load` — never by direct Cypher. The fake
embedder is the seam the composition root would wire (WP-26); its vectors
are deterministic per label, so an expected embedding is computed before
the loader runs.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from limes.graph.driver import GraphDriver
from limes.graph.embeddings import normalize_embedding
from limes.graph.loader import load, stamp_missing_embeddings
from limes.graph.schema import provision
from limes.ontology.registry import load_ontology
from limes.types import Assertion, EntityEndpoint, Provenance, Validity
from tests.fixtures.embeddings import (
    TEST_EMBEDDING_DIMENSIONS,
    expected_vector,
    fake_embedder,
)
from tests.integration.conftest import Neo4jInstance

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"

NOW = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)
V_2020 = datetime(2020, 1, 1, tzinfo=UTC)


@pytest.fixture(scope="module")
def driver(neo4j_instance: Neo4jInstance) -> GraphDriver:
    d = GraphDriver(
        neo4j_instance.uri,
        neo4j_instance.user,
        neo4j_instance.password,
        neo4j_instance.database,
    )
    yield d
    d.close()


@pytest.fixture(scope="module")
def ontology():
    return load_ontology(ONTOLOGY_PATH)


@pytest.fixture(scope="module", autouse=True)
def _provisioned(driver: GraphDriver, ontology) -> None:
    provision(driver, ontology, embedding_dimensions=TEST_EMBEDDING_DIMENSIONS)


def endpoint(entity_id: str, label: str, key: tuple[str, str] | None = None) -> EntityEndpoint:
    return EntityEndpoint(
        entity_id=entity_id,
        type="Corporation",
        label=label,
        deterministic_key=key,
    )


def assertion(entity_id: str, label: str) -> Assertion:
    return Assertion(
        assertion_id=f"stamp-{entity_id}",
        subject=endpoint(entity_id, label),
        relation="SUBSIDIARY_OF",
        object=endpoint("stamp-parent-1", "Parent GmbH"),
        validity=Validity(valid_from=V_2020, recorded_at=NOW),
        provenance=Provenance(
            source_id="s1",
            source_trust=1.0,
            confidence=0.9,
            ontology_version="1.0.0",
        ),
    )


def _embedding_of(driver: GraphDriver, entity_id: str) -> list[float] | None:
    rows = driver.read(
        "MATCH (n:Entity {entity_id: $id}) RETURN n.label_embedding AS embedding",
        {"id": entity_id},
        10,
    )
    return rows[0]["embedding"] if rows else None


def test_load_stamps_label_embedding_on_create(driver: GraphDriver, ontology):
    load(
        driver,
        [assertion("stamp-ac08-1", "Volkswagen AG")],
        ontology,
        embedder=fake_embedder(),
    )
    embedding = _embedding_of(driver, "stamp-ac08-1")
    assert embedding is not None
    assert len(embedding) == TEST_EMBEDDING_DIMENSIONS
    norm = sum(v * v for v in embedding) ** 0.5
    assert norm == pytest.approx(1.0)
    assert embedding == pytest.approx(expected_vector("Volkswagen AG"))


def test_remerge_never_overwrites_embedding(driver: GraphDriver, ontology):
    entity_id = "stamp-ac09-1"
    load(
        driver,
        [assertion(entity_id, "Volkswagen AG")],
        ontology,
        embedder=fake_embedder(),
    )
    first = _embedding_of(driver, entity_id)

    load(
        driver,
        [assertion(entity_id, "VW AG")],
        ontology,
        embedder=fake_embedder(),
    )
    assert _embedding_of(driver, entity_id) == pytest.approx(first)
    rows = driver.read(
        "MATCH (n:Entity {entity_id: $id}) RETURN n.label AS label",
        {"id": entity_id},
        10,
    )
    assert rows[0]["label"] == "Volkswagen AG"


def test_load_does_not_reembed_existing_entities(driver: GraphDriver, ontology):
    entity_id = "stamp-noreembed-1"
    load(
        driver,
        [assertion(entity_id, "Bundesdruckerei GmbH")],
        ontology,
        embedder=fake_embedder(),
    )

    def exploding_embedder(texts):
        raise AssertionError(f"embedder must not be called for existing nodes: {texts}")

    result = load(
        driver,
        [assertion(entity_id, "Bundesdruckerei GmbH")],
        ontology,
        embedder=exploding_embedder,
    )
    assert result.nodes_created == 0
    assert result.written == 0


def test_load_without_embedder_writes_null(driver: GraphDriver, ontology):
    entity_id = "stamp-noembedder-1"
    load(driver, [assertion(entity_id, "Ohne Embedder AG")], ontology)
    assert _embedding_of(driver, entity_id) is None


def test_backfill_stamps_exactly_the_nulls(driver: GraphDriver, ontology):
    entity_id = "stamp-backfill-1"
    load(driver, [assertion(entity_id, "Nachzuegler GmbH")], ontology)
    assert _embedding_of(driver, entity_id) is None

    stamped = stamp_missing_embeddings(driver, fake_embedder(), batch_size=2)
    assert stamped >= 1
    assert _embedding_of(driver, entity_id) == pytest.approx(expected_vector("Nachzuegler GmbH"))

    again = stamp_missing_embeddings(driver, fake_embedder(), batch_size=2)
    assert again == 0


def test_backfill_leaves_stamped_nodes_untouched(driver: GraphDriver, ontology):
    entity_id = "stamp-backfill-mix-1"
    load(
        driver,
        [assertion(entity_id, "Schon Gestempelt GmbH")],
        ontology,
        embedder=fake_embedder(),
    )
    before = _embedding_of(driver, entity_id)

    count = stamp_missing_embeddings(driver, fake_embedder())
    assert _embedding_of(driver, entity_id) == pytest.approx(before)
    assert count >= 0


def test_load_rejects_embedder_with_wrong_vector_count(driver: GraphDriver, ontology):
    with pytest.raises(ValueError, match="vectors"):
        load(
            driver,
            [assertion("stamp-wrongcount-1", "Falsche Zaehlung GmbH")],
            ontology,
            embedder=lambda texts: [],
        )


def test_loader_normalizes_unnormalized_embedder_output(driver: GraphDriver, ontology):
    def unnormalized(texts):
        return [[3.0] * TEST_EMBEDDING_DIMENSIONS for _ in texts]

    entity_id = "stamp-unnormalized-1"
    load(driver, [assertion(entity_id, "Rohvektor GmbH")], ontology, embedder=unnormalized)
    embedding = _embedding_of(driver, entity_id)
    assert embedding is not None
    norm = sum(v * v for v in embedding) ** 0.5
    assert norm == pytest.approx(1.0)
    assert embedding == pytest.approx(normalize_embedding([3.0] * TEST_EMBEDDING_DIMENSIONS))
