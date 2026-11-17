"""Qualified official fixtures and shared BE-56 acquisition/identity regressions."""

import gzip
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from limes.archive.store import ArchiveStore
from limes.errors import SourceFetchError, SourceParseError
from limes.graph.loader import validate_entity_properties
from limes.ontology.registry import load_ontology
from limes.ontology.validator import validate_assertions
from limes.public_offices.acquisition import Acquisition
from limes.public_offices.catalogue import BY_CODE
from limes.public_offices.models import Member, Snapshot
from limes.public_offices.parsing import parse_page
from limes.public_offices.resolution import matching_aliases, resolve_identities
from limes.sources.public_offices import PublicOfficesAdapter
from limes.types import RawRecord

FIXTURES = Path(__file__).parents[1] / "fixtures" / "public_offices"
NOW = datetime(2026, 11, 7, 18, tzinfo=UTC)
# Dated fixture sets, not legal seat quotas or live population claims.
EXPECTED = {
    "bt": 136,
    "nw": 195,
    "br": 13,
}


def fixture_payloads(scope):
    manifest = json.loads((FIXTURES / f"{scope}.json").read_text())
    pages = (
        manifest["pages"] + manifest.get("term_evidence", []) + manifest.get("profile_evidence", [])
    )
    result = {}
    for page in pages:
        raw = gzip.decompress((FIXTURES / page["file"]).read_bytes())
        assert hashlib.sha256(raw).hexdigest() == page["sha256"]
        result[page["url"]] = (raw, page["sha256"], page["retrieved_at"])
    return result


@pytest.mark.parametrize("scope", EXPECTED)
def test_every_qualified_official_mapping_archives_and_normalizes(scope):
    pages = fixture_payloads(scope)
    snapshot = Acquisition._collect(
        BY_CODE[scope], lambda url, fresh: pages[url], False, NOW.isoformat()
    )
    assert len(snapshot.members) == EXPECTED[scope]
    assert set(snapshot.expected_ids) == {m.external_id for m in snapshot.members}
    assert (snapshot.term is not None) == (scope != "br")
    snapshot.consistent = True
    raw = RawRecord(
        payload=snapshot.model_dump_json().encode(),
        content_type="application/json",
        source_url=BY_CODE[scope].url,
        fetched_at=NOW,
    )
    adapter = PublicOfficesAdapter(BY_CODE[scope])
    normalized = adapter.normalize(raw)
    ontology = load_ontology(Path("ontology/ontology.yaml"))
    accepted, rejected = validate_assertions(normalized.assertions, ontology)
    assert not rejected
    assert accepted
    validate_entity_properties(normalized.entities, ontology)
    assert not any(e.type == "PoliticalParty" for e in normalized.entities)
    assert all(a.provenance.validity_basis == "roster_observation" for a in accepted)
    members = [
        e
        for e in normalized.entities
        if e.type == "RosterMembership" and e.properties["is_current"]
    ]
    assert len(members) == EXPECTED[scope]
    assert all(e.properties["evidence_hash"] for e in members)
    assert normalized.model_dump() == adapter.normalize(raw).model_dump()
    if scope == "br":
        assert Counter(m.role for m in snapshot.members) == {"regular": 6, "deputy": 7}
        assert {m.land for m in snapshot.members} == {"Nordrhein-Westfalen"}
        conflict = next(m for m in snapshot.members if "Dorothee Feller" in m.name)
        assert conflict.service_start == datetime(2022, 6, 30, tzinfo=UTC)
        assert not conflict.conflicts
        assert normalized.errors == sum(bool(m.conflicts) for m in snapshot.members)
    if scope == "bt":
        # Selected at the source by the roster's Bundesland facet (BE-59); the
        # Bundestag-wide departure table never adds non-NRW former members.
        assert {m.land for m in snapshot.members} == {"Nordrhein-Westfalen"}
        assert "official_land_filter" in snapshot.check_basis
        assert any(m.name == "Bas, Bärbel" for m in snapshot.members)
        assert not snapshot.historical_members


class CursorDriver:
    def __init__(self):
        self.cursor = None
        self.failure = None
        self.successful_run = None
        self.active_run = "attempt-1"

    def read(self, *args):
        return [
            {
                "cursor": self.cursor,
                "successful_run": self.successful_run,
                "active_run": self.active_run,
            }
        ]

    def write_batch(self, statements):
        for _query, params in statements:
            if "cursor" in params:
                self.cursor = params["cursor"]
            if "failure" in params:
                self.failure = params["failure"]
        return SimpleNamespace(properties_set=1)


def nw_fetcher(transform=lambda roster_calls, raw: raw):
    """Landtag NRW roster plus its archived term evidence; counts roster reads."""
    pages = fixture_payloads("nw")
    roster_url = BY_CODE["nw"].url
    roster_calls = []

    def fetch(url):
        if url != roster_url:
            return pages[url][0]
        roster_calls.append(url)
        return transform(len(roster_calls), pages[roster_url][0])

    return fetch, roster_calls


@pytest.mark.parametrize("failure", ["changed", "empty", "overflow", "count"])
def test_incomplete_or_changing_snapshot_never_emits_complete_record(
    tmp_path, monkeypatch, failure
):
    driver = CursorDriver()
    archive = ArchiveStore(tmp_path / "archive")

    def transform(call, original):
        if failure == "empty":
            return b"<html><main>No directory</main></html>"
        if failure == "overflow":
            return b"x" * 11
        if failure == "count":
            return original.replace(
                b"</main>", "<p>196 Abgeordnete für diese Auswahl</p></main>".encode()
            )
        if call == 2:
            return original.replace(b"Achtermeyer", b"Changed")
        return original

    fetch, _ = nw_fetcher(transform)
    if failure == "overflow":
        monkeypatch.setattr("limes.public_offices.acquisition.MAX_PAGE_BYTES", 10)
    with pytest.raises((SourceFetchError, SourceParseError)):
        Acquisition(driver, archive, fetch).acquire(BY_CODE["nw"])
    assert driver.failure
    assert driver.cursor
    assert driver.successful_run is None
    assert list((tmp_path / "archive").glob("*/*/*"))


def test_resume_reuses_archived_pages_but_rechecks_and_success_starts_fresh(tmp_path):
    driver = CursorDriver()
    archive = ArchiveStore(tmp_path / "archive")

    def transform(call, original):
        if call == 2:
            raise SourceFetchError("consistency recheck transport failed")
        return original

    fetch, calls = nw_fetcher(transform)
    acquisition = Acquisition(driver, archive, fetch)
    with pytest.raises(SourceFetchError):
        acquisition.acquire(BY_CODE["nw"])
    driver.active_run = "attempt-2"
    snapshot = acquisition.acquire(BY_CODE["nw"])
    assert snapshot.consistent
    assert len(calls) == 3
    assert all(p["retrieved_at"] for p in snapshot.pages)
    driver.successful_run = "attempt-2"
    driver.active_run = "attempt-3"
    acquisition.acquire(BY_CODE["nw"])
    assert len(calls) == 5


def test_verified_dip_key_reuses_existing_person_without_name_merging():
    snapshot = Snapshot(
        scope="bt",
        observed_at=NOW,
        term="21",
        consistent=True,
        members=[
            Member(
                external_id="web:42",
                name="Dr. Müller, Ada",
                profile_url="https://example.org/42",
                locator="/row/1",
                bundestag_id="42",
            )
        ],
        expected_ids=["web:42"],
        pages=[],
    )
    adapter = PublicOfficesAdapter(BY_CODE["bt"])
    raw = RawRecord(
        payload=snapshot.model_dump_json().encode(), content_type="application/json", fetched_at=NOW
    )
    normalized = adapter.normalize(raw)
    driver = SimpleNamespace(read=lambda *args: [{"id": "legacy-person", "label": "Ada Müller"}])
    resolve_identities(driver, normalized)
    membership = next(e for e in normalized.entities if e.type == "RosterMembership")
    assert membership.properties["person_id"] == "legacy-person"
    assert "Ada Müller" in matching_aliases("Dr. Müller, Ada")
    assert "Ada Mueller" in matching_aliases("Dr. Müller, Ada")
    assert not any(a.subject.entity_id == "bundestag_id:42" for a in normalized.assertions)


def test_changed_markup_and_incomplete_compound_office_key_fail_closed():
    with pytest.raises(SourceParseError):
        parse_page("nw", b"<html><main>New layout</main></html>", BY_CODE["nw"].url)
    from limes.resolution.keys import deterministic_key
    from limes.types import Mention

    ontology = load_ontology(Path("ontology/ontology.yaml"))
    assert (
        deterministic_key(
            Mention(surface="Member", type="Office", deterministic_key=("body_id", "BT")), ontology
        )
        is None
    )


def test_operator_identity_review_is_bounded_and_only_accepted_by_its_command():
    from uuid import uuid4

    from pydantic import ValidationError

    from limes.operations.models import JobRequest

    review = {
        "request_id": "decision-1",
        "external_id": "official:bt:web-42",
        "person_id": "existing-person",
        "evidence_hash": "a" * 64,
        "note": "Reviewed official identity evidence",
    }
    job = JobRequest(
        request_id=uuid4(), command="public-offices-identify", identity_reviews=[review]
    )
    assert json.loads(job.argv()[-1]) == [review]
    with pytest.raises(ValidationError):
        JobRequest(
            request_id=uuid4(), command="ingest", source="gleif", identity_reviews=[review]
        )
    with pytest.raises(ValidationError):
        JobRequest(
            request_id=uuid4(), command="public-offices-identify", identity_reviews=[review] * 101
        )
