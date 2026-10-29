# tests/acceptance/test_ac05_09_loader.py | v1.0.0 | introduced by WP-39
"""AC-05…AC-10: the loader's bitemporal merge semantics, exercised against
the disposable container through the production paths only.

AC-05 runs the full pipeline twice over the identical GISCO fixture window
— `execute_run`, Trace 1 — so the zero-new-writes claim covers the whole
path, not just `load`. AC-06…AC-10 call `load` directly, which is itself
the production writer under test; no test pre-creates a node or
relationship by direct Cypher (Doc 2 §12.2 rule 1).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from limes.composition import build_run_context
from limes.graph.driver import GraphDriver
from limes.graph.loader import load
from limes.graph.schema import provision
from limes.ontology.registry import load_ontology
from limes.pipeline.run import RunSpec, execute_run
from limes.types import EntityEndpoint, Provenance, Validity
from tests.acceptance.conftest import acceptance_settings, gisco_fixture_records
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


@pytest.fixture(autouse=True)
def _isolated_graph(driver: GraphDriver):
    driver.write_batch([("MATCH (n) DETACH DELETE n", {})])
    yield


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
    source_id: str = "s1",
    valid_from: datetime = V_2020,
    valid_to: datetime | None = None,
    trust: float = 1.0,
):
    from limes.types import Assertion

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


def _relation_rows(driver: GraphDriver, relation: str) -> list[dict]:
    return driver.read(f"MATCH ()-[r:{relation}]->() RETURN r", {}, 30)


def test_ac05_identical_ingest_writes_zero_new(
    neo4j_instance: Neo4jInstance, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """AC-05: re-running an ingest over an identical window writes zero new
    relationships and zero new nodes, and reports the skip count."""
    from limes.sources.gisco_nuts import GiscoNutsAdapter

    records = gisco_fixture_records()
    monkeypatch.setattr(GiscoNutsAdapter, "fetch", lambda self, since, until: iter(records))
    ctx = build_run_context(acceptance_settings(neo4j_instance, tmp_path), needs_inference=False)
    try:
        first = execute_run(RunSpec(source_id="gisco_nuts", mode="ingest"), ctx)
        assert first.assertions_written > 0, "the first run must write assertions"

        before_nodes = ctx.driver.read("MATCH (n:Entity) RETURN count(n) AS c", {}, 30)[0]["c"]
        before_rels = ctx.driver.read("MATCH ()-[r]->() RETURN count(r) AS c", {}, 30)[0]["c"]

        second = execute_run(RunSpec(source_id="gisco_nuts", mode="ingest"), ctx)

        assert second.assertions_written == 0
        assert second.nodes_created == 0
        assert second.assertions_skipped == first.assertions_written, (
            "every previously written assertion must be reported as skipped"
        )
        after_nodes = ctx.driver.read("MATCH (n:Entity) RETURN count(n) AS c", {}, 30)[0]["c"]
        after_rels = ctx.driver.read("MATCH ()-[r]->() RETURN count(r) AS c", {}, 30)[0]["c"]
        assert after_nodes == before_nodes
        assert after_rels == before_rels
    finally:
        ctx.driver.close()


def test_ac06_interval_closure_within_source_only(driver: GraphDriver, ontology):
    """AC-06: the loader closes a superseded interval for a later assertion
    from the same source, and never across sources."""
    subject = endpoint("closure-sub", "Corporation", "Closure Subject")
    object_ = endpoint("closure-obj", "Corporation", "Closure Object")

    load(
        driver,
        [
            assertion("cl-1", subject, "SUBSIDIARY_OF", object_, source_id="s1", valid_from=V_2020),
            assertion("cl-2", subject, "SUBSIDIARY_OF", object_, source_id="s1", valid_from=V_2022),
        ],
        ontology,
    )
    rows = driver.read(
        "MATCH ()-[r:SUBSIDIARY_OF]->() RETURN r.valid_from AS vf, r.valid_to AS vt "
        "ORDER BY r.valid_from",
        {},
        30,
    )
    assert len(rows) == 2
    assert rows[0]["vf"].to_native() == V_2020
    assert rows[0]["vt"].to_native() == V_2022  # closed within the source

    # A third assertion for the same pair from a different source must not
    # close anything, and the other source's interval stays open.
    other = endpoint("closure-other", "Corporation", "Closure Other")
    load(
        driver,
        [
            assertion(
                "cl-3",
                other,
                "SUBSIDIARY_OF",
                object_,
                source_id="s2",
                valid_from=datetime(2023, 1, 1, tzinfo=UTC),
            )
        ],
        ontology,
    )
    rows = driver.read(
        "MATCH (a)-[r:SUBSIDIARY_OF]->(b) "
        "RETURN a.entity_id AS a, r.assertion_id AS aid, r.source_id AS src, r.valid_to AS vt "
        "ORDER BY r.valid_from",
        {},
        30,
    )
    sub_rows = {row["aid"]: row for row in rows if row["a"] == "closure-sub"}
    assert sub_rows["cl-1"]["vt"].to_native() == V_2022  # closed once, not again
    assert sub_rows["cl-2"]["vt"] is None  # the current interval stays open
    other_rows = {row["aid"]: row for row in rows if row["a"] == "closure-other"}
    assert other_rows["cl-3"]["vt"] is None  # s2's interval stays open
    assert all(row["src"] == "s1" for row in sub_rows.values())  # s2 never touched s1


def test_ac07_graph_wide_audit_returns_zero_rows(
    neo4j_instance: Neo4jInstance, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """AC-07: every relationship carries complete non-null assertion
    metadata and every ontology-typed node carries its ontology version;
    the graph-wide audit returns zero rows."""
    from limes.sources.gisco_nuts import GiscoNutsAdapter
    from limes.sources.gleif import GleifAdapter

    monkeypatch.setattr(GiscoNutsAdapter, "fetch", lambda self, s, u: iter(gisco_fixture_records()))
    from tests.acceptance.conftest import gleif_fixture_records

    monkeypatch.setattr(GleifAdapter, "fetch", lambda self, s, u: iter(gleif_fixture_records()))
    ctx = build_run_context(acceptance_settings(neo4j_instance, tmp_path), needs_inference=False)
    try:
        execute_run(RunSpec(source_id="gisco_nuts", mode="ingest"), ctx)
        execute_run(RunSpec(source_id="gleif", mode="ingest"), ctx)

        bad_relations = ctx.driver.read(
            "MATCH ()-[r]->() WHERE r.assertion_id IS NULL OR r.valid_from IS NULL "
            "OR r.recorded_at IS NULL OR r.source_id IS NULL OR r.source_trust IS NULL "
            "OR r.confidence IS NULL OR r.ontology_version IS NULL "
            "RETURN count(r) AS bad",
            {},
            30,
        )[0]["bad"]
        assert bad_relations == 0

        bad_nodes = ctx.driver.read(
            "MATCH (n:Entity) WHERE n.ontology_version IS NULL OR n.label IS NULL "
            "RETURN count(n) AS bad",
            {},
            30,
        )[0]["bad"]
        assert bad_nodes == 0

        # A spot check that an ontology-typed node carries type, supertype,
        # and Entity labels — the labeling contract of §5.2.
        rows = ctx.driver.read("MATCH (n:Corporation) RETURN labels(n) AS labels LIMIT 1", {}, 30)
        assert rows
        labels = set(rows[0]["labels"])
        assert {"Corporation", "Agent", "Entity"} <= labels
    finally:
        ctx.driver.close()


def test_ac08_loading_materializes_endpoints_and_standalone_entities(driver: GraphDriver, ontology):
    """AC-08: loading into an empty graph materializes endpoint nodes with
    labels, deterministic keys, and ontology version; standalone entities
    are materialized identically. Nothing here pre-creates nodes."""
    subject = endpoint("mat-a", "Corporation", "Materialized A", key=("lei", "LEI-MAT-A"))
    object_ = endpoint("mat-b", "Corporation", "Materialized B", key=("lei", "LEI-MAT-B"))
    standalone = endpoint("mat-solo", "Country", "Materialized Solo", key=("iso2", "DE"))

    result = load(
        driver,
        [assertion("mat-1", subject, "SUBSIDIARY_OF", object_, source_id="s1")],
        ontology,
        standalone_entities=[standalone],
    )

    assert result.nodes_created == 3
    rows = driver.read(
        "MATCH (n:Entity) WHERE n.entity_id IN $ids "
        "RETURN n.entity_id AS id, labels(n) AS labels, n.lei AS lei, n.iso2 AS iso2, "
        "n.ontology_version AS ov",
        {"ids": [subject.entity_id, object_.entity_id, standalone.entity_id]},
        30,
    )
    by_id = {row["id"]: row for row in rows}
    assert set(by_id) == {subject.entity_id, object_.entity_id, standalone.entity_id}
    for row in by_id.values():
        assert row["ov"] == "1.1.0"
    assert by_id[subject.entity_id]["lei"] == "LEI-MAT-A"
    assert by_id[standalone.entity_id]["iso2"] == "DE"
    assert "Entity" in by_id[standalone.entity_id]["labels"]


def test_ac09_lower_trust_remerge_does_not_overwrite(driver: GraphDriver, ontology):
    """AC-09: re-merging from a lower-trust source does not overwrite label,
    deterministic key, or original ontology version; a second identical
    load reports `nodes_created = 0`."""
    subject = endpoint("keep-a", "Corporation", "Keep A", key=("lei", "LEI-KEEP-A"))
    object_ = endpoint("keep-b", "Corporation", "Keep B", key=("lei", "LEI-KEEP-B"))
    first = load(
        driver,
        [assertion("keep-1", subject, "SUBSIDIARY_OF", object_, source_id="s1", trust=1.0)],
        ontology,
    )
    assert first.nodes_created == 2

    # The lower-trust source names the same identity with a different
    # surface — a re-merge must not touch the canonical label or the key.
    remerge = endpoint("keep-a", "Corporation", "Renamed A", key=("lei", "LEI-KEEP-A"))
    second = load(
        driver,
        [
            assertion(
                "keep-2",
                remerge,
                "SUBSIDIARY_OF",
                object_,
                source_id="s2",
                trust=0.5,
                valid_from=V_2022,
            )
        ],
        ontology,
    )
    assert second.nodes_created == 0
    assert second.written == 1  # the new assertion itself is a new row

    rows = driver.read(
        "MATCH (n:Corporation {entity_id: $id}) RETURN n.label AS label, n.lei AS lei, "
        "n.ontology_version AS ov",
        {"id": "keep-a"},
        30,
    )
    assert rows[0]["label"] == "Keep A"  # the canonical label survived
    assert rows[0]["lei"] == "LEI-KEEP-A"
    assert rows[0]["ov"] == "1.1.0"

    identical = load(
        driver,
        [
            assertion(
                "keep-2",
                remerge,
                "SUBSIDIARY_OF",
                object_,
                source_id="s2",
                trust=0.5,
                valid_from=V_2022,
            ),
        ],
        ontology,
    )
    assert identical.nodes_created == 0
    assert identical.written == 0
    assert identical.skipped == 1


def test_ac10_endpoint_without_entity_id_is_rejected(driver: GraphDriver, ontology):
    """AC-10: an assertion whose endpoint lacks an `entity_id` is rejected
    as `ENDPOINT_UNIDENTIFIED`, counted, never written."""
    subject = endpoint("ok-a", "Corporation", "Ok A")
    unnamed = endpoint("", "Corporation", "Unnamed")
    result = load(
        driver,
        [
            assertion("an-1", subject, "SUBSIDIARY_OF", unnamed, source_id="s1"),
            assertion(
                "an-2",
                subject,
                "SUBSIDIARY_OF",
                endpoint("ok-b", "Corporation", "Ok B"),
                source_id="s1",
            ),
        ],
        ontology,
    )
    assert result.rejected == 1
    assert result.written == 1  # only the identified assertion landed

    rows = _relation_rows(driver, "SUBSIDIARY_OF")
    assert len(rows) == 1
    assert rows[0]["r"]["assertion_id"] == "an-2"
