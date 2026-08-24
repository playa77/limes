# tests/integration/test_loader.py | v1.0.0 | introduced by WP-07
"""Graph loader integration tests per Doc 2 §12.2 (AC-05…AC-10).

Test-construction rule: no test pre-creates endpoint nodes or relationships
by direct Cypher. All graph state is produced by calling `load` — the
production path under test. `provision` (WP-04) runs first only because the
real composition root would provision before any load.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from limes.graph.driver import GraphDriver
from limes.graph.loader import load, retract
from limes.graph.schema import provision
from limes.ontology.registry import load_ontology
from limes.types import Assertion, EntityEndpoint, LookupRow, Provenance, Validity
from tests.integration.conftest import Neo4jInstance

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"

NOW = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)
V_2020 = datetime(2020, 1, 1, tzinfo=UTC)
V_2022 = datetime(2022, 1, 1, tzinfo=UTC)


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
    provision(driver, ontology, embedding_dimensions=1024)


def endpoint(
    entity_id: str,
    type_: str = "Corporation",
    label: str = None,
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
    source_id: str = "s1",
    valid_from: datetime = V_2020,
    valid_to: datetime | None = None,
    trust: float = 1.0,
    ontology_version: str = "1.0.0",
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
            ontology_version=ontology_version,
            evidence_document_id="doc-1",
            evidence_start=10,
            evidence_end=40,
        ),
    )


def test_load_materializes_nodes_with_labels_and_keys(driver: GraphDriver, ontology):
    result = load(
        driver,
        [
            assertion(
                "ac08-1",
                endpoint("ac08-parent", key=("lei", "LEI-AC08")),
                "SUBSIDIARY_OF",
                endpoint("ac08-child"),
            )
        ],
        ontology,
    )
    assert result.written == 1
    assert result.nodes_created == 2

    rows = driver.read(
        "MATCH (n:Entity {entity_id: $id}) RETURN labels(n) AS labels, n",
        {"id": "ac08-parent"},
        10,
    )
    assert set(rows[0]["labels"]) == {"Entity", "Agent", "Corporation"}
    assert rows[0]["n"]["label"] == "Entity ac08-parent"
    assert rows[0]["n"]["lei"] == "LEI-AC08"
    assert rows[0]["n"]["ontology_version"] == "1.0.0"


def test_load_materializes_standalone_entities(driver: GraphDriver, ontology):
    result = load(
        driver,
        [],
        ontology,
        standalone_entities=[endpoint("ac08-standalone", type_="Country", key=("iso2", "DE"))],
    )
    assert result.nodes_created == 1
    rows = driver.read(
        "MATCH (n:Entity {entity_id: 'ac08-standalone'}) "
        "RETURN labels(n) AS labels, n.iso2 AS iso2",
        {},
        10,
    )
    assert set(rows[0]["labels"]) == {"Entity", "Place", "Country"}
    assert rows[0]["iso2"] == "DE"


def test_relationship_carries_complete_metadata(driver: GraphDriver, ontology):
    load(
        driver,
        [assertion("ac07-1", endpoint("ac07-a"), "SUBSIDIARY_OF", endpoint("ac07-b"))],
        ontology,
    )
    rows = driver.read(
        "MATCH (:Entity {entity_id: 'ac07-a'})-[r:SUBSIDIARY_OF]->(:Entity {entity_id: 'ac07-b'}) "
        "RETURN r",
        {},
        10,
    )
    assert len(rows) == 1
    r = rows[0]["r"]
    for prop in (
        "assertion_id",
        "valid_from",
        "recorded_at",
        "source_id",
        "source_trust",
        "confidence",
        "extractor_model",
        "prompt_version",
        "schema_version",
        "ontology_version",
        "evidence_document_id",
        "evidence_start",
        "evidence_end",
    ):
        assert r[prop] is not None, prop
    # An open interval carries no valid_to until closure; retracted_at is
    # null until retraction. Both must stay absent/null by design.
    assert "valid_to" not in r
    assert r["retracted_at"] is None
    assert r["assertion_id"] == "ac07-1"


def test_identical_reload_writes_nothing_and_reports_skips(driver: GraphDriver, ontology):
    assertion_id = "ac05-1"
    load(
        driver,
        [assertion(assertion_id, endpoint("ac05-a"), "SUBSIDIARY_OF", endpoint("ac05-b"))],
        ontology,
    )

    second = load(
        driver,
        [assertion(assertion_id, endpoint("ac05-a"), "SUBSIDIARY_OF", endpoint("ac05-b"))],
        ontology,
    )
    assert second.nodes_created == 0
    assert second.written == 0
    assert second.skipped == 1
    assert second.nodes_matched == 2

    rows = driver.read(
        "MATCH (:Entity {entity_id: 'ac05-a'})-[r:SUBSIDIARY_OF]->(:Entity {entity_id: 'ac05-b'}) "
        "RETURN count(r) AS c",
        {},
        10,
    )
    assert rows[0]["c"] == 1


def test_lower_trust_rematch_never_overwrites(driver: GraphDriver, ontology):
    load(
        driver,
        [
            assertion(
                "ac09-1",
                endpoint("ac09-x", label="Original Label"),
                "SUBSIDIARY_OF",
                endpoint("ac09-y"),
            )
        ],
        ontology,
    )

    second = load(
        driver,
        [
            assertion(
                "ac09-2",
                endpoint("ac09-x", label="Degraded Label"),
                "SUBSIDIARY_OF",
                endpoint("ac09-y"),
                trust=0.3,
                ontology_version="0.9.0",
            )
        ],
        ontology,
    )
    assert second.nodes_created == 0

    rows = driver.read(
        "MATCH (n:Entity {entity_id: 'ac09-x'}) RETURN n.label AS label, n.ontology_version AS v",
        {},
        10,
    )
    assert rows[0]["label"] == "Original Label"
    assert rows[0]["v"] == "1.0.0"


def test_interval_closure_within_source(driver: GraphDriver, ontology):
    load(
        driver,
        [
            assertion(
                "ac06-1", endpoint("ac06-a"), "SUBSIDIARY_OF", endpoint("ac06-b"), valid_from=V_2020
            )
        ],
        ontology,
    )
    second = load(
        driver,
        [
            assertion(
                "ac06-2", endpoint("ac06-a"), "SUBSIDIARY_OF", endpoint("ac06-b"), valid_from=V_2022
            )
        ],
        ontology,
    )
    assert second.closed_intervals == 1

    rows = driver.read(
        "MATCH (:Entity {entity_id: 'ac06-a'})-[r:SUBSIDIARY_OF]->(:Entity {entity_id: 'ac06-b'}) "
        "RETURN r.assertion_id AS aid, r.valid_from AS vf, r.valid_to AS vt ORDER BY r.valid_from",
        {},
        10,
    )
    assert rows[0]["aid"] == "ac06-1"
    assert rows[0]["vt"] == V_2022
    assert rows[1]["aid"] == "ac06-2"
    assert rows[1]["vt"] is None


def test_interval_never_closed_across_sources(driver: GraphDriver, ontology):
    load(
        driver,
        [
            assertion(
                "ac06-3",
                endpoint("ac06-c"),
                "SUBSIDIARY_OF",
                endpoint("ac06-d"),
                valid_from=V_2020,
                source_id="s1",
            )
        ],
        ontology,
    )
    load(
        driver,
        [
            assertion(
                "ac06-4",
                endpoint("ac06-c"),
                "SUBSIDIARY_OF",
                endpoint("ac06-d"),
                valid_from=V_2022,
                source_id="s2",
            )
        ],
        ontology,
    )

    rows = driver.read(
        "MATCH (:Entity {entity_id: 'ac06-c'})-[r:SUBSIDIARY_OF]->(:Entity {entity_id: 'ac06-d'}) "
        "WHERE r.assertion_id = 'ac06-3' RETURN r.valid_to AS vt",
        {},
        10,
    )
    assert rows[0]["vt"] is None  # s2 must not close s1's interval


def test_endpoint_unidentified_is_rejected_and_never_written(driver: GraphDriver, ontology):
    result = load(
        driver, [assertion("ac10-1", endpoint(""), "SUBSIDIARY_OF", endpoint("ac10-b"))], ontology
    )
    assert result.rejected == 1
    assert result.written == 0
    assert result.nodes_created == 0

    rows = driver.read("MATCH (n:Entity {entity_id: 'ac10-b'}) RETURN count(n) AS c", {}, 10)
    assert rows[0]["c"] == 0


def test_lookup_rows_materialize_postal_code_nodes(driver: GraphDriver, ontology):
    result = load(
        driver,
        [],
        ontology,
        lookup_rows=[
            LookupRow(
                kind="postal_code",
                key={"country_code": "DE", "postal_code": "10115"},
                value={"nuts_code": "DE300"},
            )
        ],
    )
    assert result.lookup_rows_written == 1
    rows = driver.read(
        "MATCH (p:PostalCode {country_code: 'DE', postal_code: '10115'}) "
        "RETURN p.nuts_code AS nuts, p.source_id AS src",
        {},
        10,
    )
    assert rows[0]["nuts"] == "DE300"
    assert rows[0]["src"] == "gisco_nuts"


def test_lookup_rows_are_batched_across_transactions(driver: GraphDriver, ontology, monkeypatch):
    """The WP-28 conflict repair: a lookup list larger than `BATCH_SIZE` may
    not ride in one transaction — the live GISCO postcode payload (~300k
    rows) timed out a single transaction (DECISIONS.md, 2026-08-02). The spy
    counts postal statements per committed transaction through the
    documented `GraphDriver._driver` seam; no transaction may carry more
    than `BATCH_SIZE` of them, and more than one transaction must be used."""
    from limes.graph.loader import BATCH_SIZE

    postal_per_tx: list[int] = []

    class SpyTx:
        def __init__(self, real):
            self._real = real
            self._postal = 0

        def run(self, cypher, **params):
            if "PostalCode" in cypher:
                self._postal += 1
            return self._real.run(cypher, **params)

        def commit(self):
            postal_per_tx.append(self._postal)
            return self._real.commit()

        def rollback(self):
            return self._real.rollback()

    class SpySession:
        def __init__(self, real):
            self._real = real

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return self._real.__exit__(*exc)

        def begin_transaction(self):
            return SpyTx(self._real.begin_transaction())

        def __getattr__(self, name):
            return getattr(self._real, name)

    class SpyDriver:
        def __init__(self, real):
            self._real = real

        def session(self, **kwargs):
            return SpySession(self._real.session(**kwargs))

    monkeypatch.setattr(driver, "_driver", SpyDriver(driver._driver))

    rows = [
        LookupRow(
            kind="postal_code",
            key={"country_code": "DE", "postal_code": str(90000 + i)},
            value={"nuts_code": "DE300"},
        )
        for i in range(BATCH_SIZE * 2 + 1)
    ]
    result = load(driver, [], ontology, lookup_rows=rows)
    assert result.lookup_rows_written == len(rows)
    assert len(postal_per_tx) > 1
    assert max(postal_per_tx) <= BATCH_SIZE
    assert sum(postal_per_tx) == len(rows)

    count = driver.read(
        "MATCH (p:PostalCode) "
        "WHERE p.postal_code >= '90000' AND p.postal_code < '91001' "
        "RETURN count(p) AS c",
        {},
        30,
    )
    assert count[0]["c"] == len(rows)


def test_non_temporal_relation_never_gets_valid_to(driver: GraphDriver, ontology):
    load(
        driver,
        [assertion("nt-1", endpoint("nt-a", "LegalAct"), "AMENDS", endpoint("nt-b", "LegalAct"))],
        ontology,
    )
    rows = driver.read(
        "MATCH (:Entity {entity_id: 'nt-a'})-[r:AMENDS]->(:Entity {entity_id: 'nt-b'}) "
        "RETURN r.valid_to AS vt, r.recorded_at AS rec",
        {},
        10,
    )
    assert rows[0]["vt"] is None
    assert rows[0]["rec"] is not None


def test_retract_sets_retracted_at(driver: GraphDriver, ontology):
    load(
        driver,
        [assertion("ret-1", endpoint("ret-a"), "SUBSIDIARY_OF", endpoint("ret-b"))],
        ontology,
    )
    count = retract(driver, ["ret-1"], datetime(2026, 8, 2, tzinfo=UTC))
    assert count == 1

    rows = driver.read(
        "MATCH (:Entity {entity_id: 'ret-a'})-[r:SUBSIDIARY_OF]->(:Entity {entity_id: 'ret-b'}) "
        "RETURN r.retracted_at AS rt",
        {},
        10,
    )
    assert rows[0]["rt"] == datetime(2026, 8, 2, tzinfo=UTC)

    again = retract(driver, ["ret-1"], datetime(2026, 8, 3, tzinfo=UTC))
    assert again == 0
