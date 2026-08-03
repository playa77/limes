# tests/unit/test_loader_logic.py | v1.0.0 | introduced by WP-07
"""Loader partition and property-building logic (no database).

The graph-touching behavior is covered by `tests/integration/test_loader.py`;
these tests pin the pure parts: rejection partitioning (AC-10), deterministic
key guarding, and the §5.6 metadata property map. The batch-transaction
failure surface (embedder contract violations, unknown lookup kinds, graph
write errors) is exercised through `load` and `stamp_missing_embeddings` with
a fake raw driver — the `GraphDriver._driver` seam the loader's transactions
run on.
"""

from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from neo4j.exceptions import Neo4jError

from limes.errors import GraphWriteError
from limes.graph.loader import (
    _distinct_endpoints,
    _key_property,
    _partition,
    _relationship_properties,
    load,
    retract,
    stamp_missing_embeddings,
)
from limes.ontology.registry import load_ontology
from limes.types import Assertion, EntityEndpoint, LookupRow, Provenance, Validity

ONTOLOGY = load_ontology(__import__("pathlib").Path("ontology/ontology.yaml"))

NOW = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)


def _endpoint(
    entity_id: str,
    type_: str = "Corporation",
    key: tuple[str, str] | None = None,
) -> EntityEndpoint:
    return EntityEndpoint(
        entity_id=entity_id,
        type=type_,
        label=f"Entity {entity_id}",
        deterministic_key=key,
        aliases=[f"alias-{entity_id}"],
    )


def _assertion(
    assertion_id: str,
    subject: EntityEndpoint,
    relation: str,
    object_: EntityEndpoint,
    valid_to: datetime | None = None,
) -> Assertion:
    return Assertion(
        assertion_id=assertion_id,
        subject=subject,
        relation=relation,
        object=object_,
        validity=Validity(valid_from=NOW, valid_to=valid_to, recorded_at=NOW),
        provenance=Provenance(
            source_id="s1",
            source_trust=1.0,
            confidence=0.9,
            ontology_version="1.0.0",
        ),
    )


def test_partition_accepts_valid_assertion():
    a = _assertion("a1", _endpoint("e1"), "SUBSIDIARY_OF", _endpoint("e2"))
    valid, rejected = _partition([a], ONTOLOGY)
    assert valid == [a]
    assert rejected == []


def test_partition_rejects_unidentified_endpoint_as_endpoint_unidentified():
    a = _assertion("a1", _endpoint(""), "SUBSIDIARY_OF", _endpoint("e2"))
    valid, rejected = _partition([a], ONTOLOGY)
    assert valid == []
    assert len(rejected) == 1
    assert rejected[0].reason == "ENDPOINT_UNIDENTIFIED"
    assert rejected[0].assertion_index == 0


def test_partition_reuses_ontology_validator_rejections():
    a = _assertion("a1", _endpoint("e1"), "NOT_A_RELATION", _endpoint("e2"))
    valid, rejected = _partition([a], ONTOLOGY)
    assert valid == []
    assert rejected[0].reason == "UNKNOWN_RELATION"


def test_partition_keeps_original_indices():
    bad = _assertion("bad", _endpoint(""), "SUBSIDIARY_OF", _endpoint("e2"))
    good = _assertion("good", _endpoint("e3"), "SUBSIDIARY_OF", _endpoint("e4"))
    valid, rejected = _partition([bad, good], ONTOLOGY)
    assert rejected[0].assertion_index == 0
    assert valid == [good]


def test_key_property_only_for_declared_identifying_keys():
    corp = _endpoint("e1", "Corporation", key=("lei", "549300ABC"))
    assert _key_property(corp, ONTOLOGY) == "lei"
    person = _endpoint("e2", "Person", key=("lei", "549300ABC"))
    assert _key_property(person, ONTOLOGY) is None
    empty_value = _endpoint("e3", "Corporation", key=("lei", ""))
    assert _key_property(empty_value, ONTOLOGY) is None


def test_relationship_properties_include_full_metadata():
    a = _assertion(
        "a1",
        _endpoint("e1"),
        "SUBSIDIARY_OF",
        _endpoint("e2"),
        valid_to=datetime(2026, 12, 31, tzinfo=UTC),
    )
    props = _relationship_properties(a, temporal=True)
    for key in (
        "assertion_id",
        "valid_from",
        "valid_to",
        "recorded_at",
        "retracted_at",
        "source_id",
        "source_trust",
        "confidence",
        "ontology_version",
    ):
        assert key in props
    assert props["valid_to"] == datetime(2026, 12, 31, tzinfo=UTC)


def test_non_temporal_relationship_never_carries_valid_to():
    a = _assertion("a1", _endpoint("e1", "LegalAct"), "AMENDS", _endpoint("e2", "LegalAct"))
    props = _relationship_properties(a, temporal=False)
    assert "valid_to" not in props


def test_distinct_endpoints_deduplicates_across_assertions():
    a1 = _assertion("a1", _endpoint("e1"), "SUBSIDIARY_OF", _endpoint("e2"))
    a2 = _assertion("a2", _endpoint("e2"), "SUBSIDIARY_OF", _endpoint("e3"))
    endpoints = _distinct_endpoints([a1, a2], [])
    assert [e.entity_id for e in endpoints] == ["e1", "e2", "e3"]


class FakeCounters:
    nodes_created = 0
    relationships_created = 0
    properties_set = 0


class FakeResult:
    """A driver result: iterable of records with a `consume`able summary."""

    def __init__(self, records=None) -> None:
        self._records = records or []

    def __iter__(self):
        return iter(self._records)

    def consume(self) -> SimpleNamespace:
        return SimpleNamespace(counters=FakeCounters())


class FakeTx:
    """One transaction on the fake raw driver; `fail_on_run` arms the graph
    write error the loader's except branch turns into `GraphWriteError`."""

    def __init__(self, fail_on_run: bool = False) -> None:
        self.ran: list[str] = []
        self.fail_on_run = fail_on_run
        self.rollback_called = False
        self.commit_called = False

    def run(self, cypher: str, **params):
        if self.fail_on_run:
            raise Neo4jError("statement rejected")
        self.ran.append(cypher)
        return FakeResult()

    def commit(self) -> None:
        self.commit_called = True

    def rollback(self) -> None:
        self.rollback_called = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeSession:
    def __init__(self, fail_on_run: bool = False) -> None:
        self.tx = FakeTx(fail_on_run=fail_on_run)

    def begin_transaction(self) -> FakeTx:
        return self.tx


class FakeRawDriver:
    """The `driver._driver` seam the loader's transactions run on: `session`
    returns a context manager over a FakeSession."""

    def __init__(self, fail_on_run: bool = False) -> None:
        self._session = FakeSession(fail_on_run=fail_on_run)
        self.session_opens = 0

    @contextmanager
    def session(self, **kwargs):
        self.session_opens += 1
        yield self._session


class FakeDriver:
    """A GraphDriver-shaped fake: `read` serves canned rows, `write_batch`
    records, and `_driver` carries the raw transaction seam."""

    def __init__(self, rows=None, fail_on_run: bool = False) -> None:
        self.rows = rows or []
        self.writes: list[tuple[str, dict]] = []
        self._driver = FakeRawDriver(fail_on_run=fail_on_run)

    def read(self, cypher: str, params: dict, timeout_s: int) -> list[dict]:
        return self.rows

    def write_batch(self, statements: list[tuple[str, dict]]):
        self.writes.extend(statements)


def test_stamp_missing_embeddings_raises_on_vector_count_mismatch():
    driver = FakeDriver(
        [{"entity_id": "e1", "label": "Alpha"}, {"entity_id": "e2", "label": "Beta"}]
    )
    with pytest.raises(ValueError, match="embedder returned 1 vectors for 2 labels"):
        stamp_missing_embeddings(driver, lambda labels: [[1.0, 0.0]])


def test_stamp_missing_embeddings_stops_after_a_short_page():
    pages = [
        [{"entity_id": f"e{i}", "label": f"L{i}"} for i in range(2)],
        [{"entity_id": "e9", "label": "L9"}],
    ]

    class PageDriver(FakeDriver):
        def read(self, cypher: str, params: dict, timeout_s: int) -> list[dict]:
            return pages.pop(0) if pages else []

    driver = PageDriver()
    stamped = stamp_missing_embeddings(
        driver, lambda labels: [[1.0, 0.0]] * len(labels), batch_size=2
    )
    assert stamped == 3
    # The short last page terminated the loop instead of starting a third.
    assert len(driver.writes) == 3


def test_retract_surfaces_graph_write_errors():
    driver = FakeDriver(fail_on_run=True)
    with pytest.raises(GraphWriteError, match="retraction failed"):
        retract(driver, ["a1"], NOW)


def test_load_skips_lookup_rows_without_a_declared_source():
    # A lookup kind the source table does not attribute (only postal_code
    # exists) is counted out with a warning, never written.
    bogus = LookupRow.model_construct(kind="no_such_kind", key={"x": "y"}, value={"z": "w"})
    driver = FakeDriver()
    result = load(driver, [], ONTOLOGY, lookup_rows=[bogus])
    assert result.lookup_rows_written == 0
    assert result.rejected == 0
    assert driver._driver._session.tx.commit_called


def test_load_surfaces_graph_write_errors_with_rollback():
    driver = FakeDriver(fail_on_run=True)
    assertion = _assertion("a1", _endpoint("e1"), "SUBSIDIARY_OF", _endpoint("e2"))
    with pytest.raises(GraphWriteError, match="graph load failed"):
        load(driver, [assertion], ONTOLOGY)
    assert driver._driver._session.tx.rollback_called
    assert not driver._driver._session.tx.commit_called
