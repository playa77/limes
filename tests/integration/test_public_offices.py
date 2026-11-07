"""BE-56 persistence, source-owned migration, replay, time and authenticated API."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from limes.archive.store import ArchiveStore
from limes.cli.migrate import _load_migration_module, _migrate
from limes.graph.loader import load
from limes.pipeline.run import RunSpec, execute_run
from limes.public_offices.catalogue import BY_CODE
from limes.public_offices.models import Member, Snapshot
from limes.resolution.resolve import RunContext
from limes.sources.bundestag_dip import _office, _period_start
from limes.sources.public_offices import PublicOfficesAdapter
from limes.sources.registry import SourceRegistry
from limes.types import RawRecord
from tests.fixtures.graph_data import (
    ONTOLOGY_PATH,
    api_settings,
    assertion,
    endpoint,
    load_ontology_artifact,
    make_api_client,
    provisioned_driver,
)

T1 = datetime(2026, 11, 1, tzinfo=UTC)
T2 = datetime(2026, 11, 2, tzinfo=UTC)
T3 = datetime(2026, 11, 3, tzinfo=UTC)


@pytest.fixture
def graph(neo4j_instance):
    driver = provisioned_driver(neo4j_instance)
    driver.write_batch([("MATCH (n) DETACH DELETE n", {})])
    yield driver
    driver.close()


def ingest(graph, neo4j_instance, tmp_path, monkeypatch, members, observed=T1, scope="bt"):
    archive = ArchiveStore(tmp_path / "archive")
    evidence = archive.put(
        "public_offices_" + scope, b'[{"official":"fixture"}]', "application/json"
    )
    rows = [
        m.model_copy(update={"evidence_hash": evidence, "evidence_url": BY_CODE[scope].url})
        for m in members
    ]
    snapshot = Snapshot(
        scope=scope,
        observed_at=observed,
        members=rows,
        consistent=True,
        term="21" if scope == "bt" else None,
        expected_ids=[m.external_id for m in rows],
        expected_count=len(rows),
        check_basis="official_set_and_count",
        pages=[{"sha256": evidence, "url": BY_CODE[scope].url}],
    )
    raw = RawRecord(
        payload=snapshot.model_dump_json().encode(),
        content_type="application/json",
        fetched_at=observed,
        source_url=BY_CODE[scope].url,
    )
    adapter = PublicOfficesAdapter(BY_CODE[scope])
    monkeypatch.setattr(adapter, "fetch", lambda *args: iter([raw]))
    registry = SourceRegistry()
    registry.register(adapter)
    ctx = RunContext(
        settings=api_settings(neo4j_instance, tmp_path),
        driver=graph,
        ontology=load_ontology_artifact(),
        registry=registry,
        archive=archive,
    )
    return execute_run(RunSpec(source_id=adapter.source_id, mode="ingest"), ctx), evidence


def member(ident="web-42", name="Ada Müller", **fields):
    return Member(
        external_id=ident,
        name=name,
        profile_url="https://official.test/" + ident,
        locator="/row/1",
        **fields,
    )


def test_dip_migration_replay_preserves_ids_other_sources_and_rollback(
    graph,
    neo4j_instance,
    tmp_path,
    monkeypatch,
):
    ontology = load_ontology_artifact()
    person = endpoint("old-canonical", "Person", "Ada Müller", ("bundestag_id", "42"))
    office = _office(21, _period_start(21)).model_copy(
        update={"deterministic_key": ("body_id", "BT"), "properties": {}}
    )
    party = endpoint("legacy-party", "PoliticalParty", "CDU/CSU")
    load(
        graph,
        [
            assertion("old-party", person, "MEMBER_OF", party, source_id="bundestag_dip"),
            assertion("old-office", person, "HOLDS_OFFICE", office, source_id="bundestag_dip"),
            assertion("old-body", office, "OFFICE_AT", party, source_id="bundestag_dip"),
            assertion("other", person, "MEMBER_OF", party, source_id="other-source"),
        ],
        ontology,
    )
    _migrate(graph, ONTOLOGY_PATH, "1.4.0", "1.4.0")
    _migrate(graph, ONTOLOGY_PATH, "1.4.0", "1.4.0")
    old = graph.read(
        "MATCH ()-[r]->() WHERE r.assertion_id IN $ids "
        "RETURN r.assertion_id AS id, r.retracted_at AS retracted",
        {"ids": ["old-party", "old-office", "old-body", "other"]},
        30,
    )
    assert {r["id"] for r in old if r["retracted"] is None} == {"other"}
    row = member(bundestag_id="42", group="CDU/CSU")
    first, evidence = ingest(graph, neo4j_instance, tmp_path, monkeypatch, [row])
    second, _ = ingest(graph, neo4j_instance, tmp_path, monkeypatch, [row])
    assert first.errors == second.errors == 0
    assert second.assertions_written == 0
    assert graph.read("MATCH (p:Person) RETURN count(p) AS n", {}, 30)[0]["n"] == 1
    assert graph.read("MATCH (o:Office) RETURN count(o) AS n", {}, 30)[0]["n"] == 1
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.get("/public-offices", params={"scope": "bt"})
        assert response.status_code == 200
        body = response.json()
        assert body["members"][0]["person_id"] == "old-canonical"
        assert body["members"][0]["group_label"] == "CDU/CSU"
        assert body["members"][0]["party_label"] is None
        assert body["scopes"][0]["status"] == "reconciled"
        assert body["members"][0]["evidence_hash"] == evidence
        assert client.get("/public-offices", params={"scope": "unknown"}).status_code == 422
        assert client.get("/public-offices", params={"limit": 1001}).status_code == 422
    migration = _load_migration_module(Path("ontology/migrations/0002_public_offices.py"))
    migration.rollback(graph)
    assert (
        graph.read(
            "MATCH ()-[r]->() WHERE r.assertion_id='old-party' RETURN r.retracted_at AS at", {}, 30
        )[0]["at"]
        is None
    )


def test_current_asof_belief_replacement_reentry_and_missing_scopes(
    graph,
    neo4j_instance,
    tmp_path,
    monkeypatch,
):
    row = member(bundestag_id="42")
    ingest(graph, neo4j_instance, tmp_path, monkeypatch, [row], T1)
    first_recorded = graph.read("MATCH (s:RosterSnapshot) RETURN s.created_at AS at", {}, 30)[0][
        "at"
    ]
    ingest(
        graph,
        neo4j_instance,
        tmp_path,
        monkeypatch,
        [member("web-43", "Ada Müller", bundestag_id="43")],
        T2,
    )
    ingest(
        graph,
        neo4j_instance,
        tmp_path,
        monkeypatch,
        [member(bundestag_id="42", service_start=T3)],
        T3,
    )
    with make_api_client(neo4j_instance, tmp_path) as client:
        current = client.get("/public-offices").json()
        assert len(current["scopes"]) == 21
        assert sum(s["status"] == "missing" for s in current["scopes"]) == 20
        assert current["members"][0]["service_start"].startswith("2026-11-03")
        historical = client.get(
            "/public-offices", params={"scope": "bt", "as_of": T2.isoformat()}
        ).json()
        assert historical["members"][0]["person_id"] == "bundestag_id:43"
        belief = client.get(
            "/public-offices", params={"scope": "bt", "believed": first_recorded.iso_format()}
        ).json()
        assert belief["members"][0]["person_id"] == "bundestag_id:42"
        assert belief["members"][0]["service_start"] is None
        assert client.get("/public-offices", params={"as_of": "2026-01-01"}).status_code == 422
    holds = graph.read(
        "MATCH (:Person {entity_id:'bundestag_id:42'})-[r:HOLDS_OFFICE]->() "
        "RETURN r.valid_from AS start, r.valid_to AS end",
        {},
        30,
    )
    assert len(holds) == 2
    assert all(r["end"] is None for r in holds)  # No invented exit or filled service gap.


def test_conflicting_official_roles_are_retained_but_do_not_advance_checkpoint(
    graph,
    neo4j_instance,
    tmp_path,
    monkeypatch,
):
    row = member(
        role="deputy",
        land="Berlin",
        profile_member_class="regular",
        conflicts=["Official directory/profile roles disagree"],
    )
    record, _ = ingest(graph, neo4j_instance, tmp_path, monkeypatch, [row], scope="br")
    assert record.errors == 1
    source = graph.read(
        "MATCH (s:Source {source_id:'public_offices_br'}) RETURN s.last_success_at AS success",
        {},
        30,
    )[0]
    assert source["success"] is None
    with make_api_client(neo4j_instance, tmp_path) as client:
        data = client.get("/public-offices", params={"scope": "br"}).json()
    assert data["scopes"][0]["status"] == "failed"
    assert data["scopes"][0]["failed_rows"] == 1
    assert data["members"][0]["role"] == "deputy"
    assert data["members"][0]["profile_member_class"] == "regular"


def test_company_person_name_only_candidate_stays_unresolved_and_scoped_ids_do_not_collide(
    graph,
    neo4j_instance,
    tmp_path,
    monkeypatch,
):
    ontology = load_ontology_artifact()
    existing = endpoint("company-officer", "Person", "Ada Müller")
    corporation = endpoint("company", "Corporation", "Company")
    load(graph, [assertion("director", existing, "DIRECTOR_OF", corporation)], ontology)
    ingest(graph, neo4j_instance, tmp_path, monkeypatch, [member()], scope="bt")
    ingest(graph, neo4j_instance, tmp_path, monkeypatch, [member()], scope="be")
    with make_api_client(neo4j_instance, tmp_path) as client:
        data = client.get("/public-offices").json()
    bt = next(s for s in data["scopes"] if s["scope"] == "bt")
    assert bt["unresolved"] == 1
    assert bt["status"] == "partial"
    people = {m["person_id"] for m in data["members"]}
    assert len(people) == 2
    assert "company-officer" not in people
    assert graph.read("MATCH (p:Person) RETURN count(p) AS n", {}, 30)[0]["n"] == 3


def test_reviewed_identity_is_audited_replayable_and_belief_sensitive(
    graph,
    neo4j_instance,
    tmp_path,
    monkeypatch,
):
    from limes.errors import GraphWriteError
    from limes.graph.loader import review_person_identity
    from limes.public_offices.models import IdentityReview

    ontology = load_ontology_artifact()
    existing = endpoint("company-officer", "Person", "Ada Müller")
    corporation = endpoint("company", "Corporation", "Company")
    load(graph, [assertion("director", existing, "DIRECTOR_OF", corporation)], ontology)
    _, evidence = ingest(graph, neo4j_instance, tmp_path, monkeypatch, [member()])
    before = datetime.now(UTC)
    review = IdentityReview(
        request_id="review-1",
        external_id="official:bt:web-42",
        person_id="company-officer",
        evidence_hash=evidence,
        note="Reviewed official professional identity evidence",
    )
    review_person_identity(graph, review)
    review_person_identity(graph, review)
    with pytest.raises(GraphWriteError, match="different decision"):
        review_person_identity(graph, review.model_copy(update={"note": "changed request"}))
    assert graph.read("MATCH (r:PersonIdentityReview) RETURN count(r) AS n", {}, 30)[0]["n"] == 1
    with make_api_client(neo4j_instance, tmp_path) as client:
        current = client.get("/public-offices", params={"scope": "bt"}).json()
        historical = client.get(
            "/public-offices", params={"scope": "bt", "believed": before.isoformat()}
        ).json()
    assert current["members"][0]["person_id"] == "company-officer"
    assert current["members"][0]["identity_status"] == "operator_reviewed"
    assert current["scopes"][0]["unresolved"] == 0
    assert historical["members"][0]["person_id"] != "company-officer"
    ingest(graph, neo4j_instance, tmp_path, monkeypatch, [member()])
    with make_api_client(neo4j_instance, tmp_path) as client:
        replay = client.get("/public-offices", params={"scope": "bt"}).json()
        historical = client.get(
            "/public-offices", params={"scope": "bt", "believed": before.isoformat()}
        ).json()
    assert len(replay["members"]) == 1
    assert replay["members"][0]["person_id"] == "company-officer"
    assert len(historical["members"]) == 1
    assert historical["members"][0]["person_id"] != "company-officer"


def test_successful_replay_qualifies_snapshot_first_recorded_by_failed_run(
    graph,
    neo4j_instance,
    tmp_path,
    monkeypatch,
):
    original = PublicOfficesAdapter.normalize
    first_attempt = True

    def normalize(adapter, raw):
        nonlocal first_attempt
        result = original(adapter, raw)
        if first_attempt:
            result.errors = 1
            first_attempt = False
        return result

    monkeypatch.setattr(PublicOfficesAdapter, "normalize", normalize)
    first, _ = ingest(graph, neo4j_instance, tmp_path, monkeypatch, [member(bundestag_id="42")])
    assert first.errors == 1
    before_replay = datetime.now(UTC)
    second, _ = ingest(graph, neo4j_instance, tmp_path, monkeypatch, [member(bundestag_id="42")])
    assert second.errors == 0
    assert second.assertions_written == 0
    assert graph.read("MATCH (s:RosterSnapshot) RETURN count(s) AS n", {}, 30)[0]["n"] == 1
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.get("/public-offices", params={"scope": "bt", "include_members": False})
    with make_api_client(neo4j_instance, tmp_path) as client:
        historical = client.get(
            "/public-offices",
            params={"scope": "bt", "believed": before_replay.isoformat()},
        )
    assert historical.json()["scopes"][0]["status"] == "failed"
    assert response.status_code == 200
    assert response.json()["scopes"][0]["status"] == "reconciled"
    assert response.json()["members"] == []
    assert not response.json()["truncated"]
