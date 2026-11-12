"""Source-time scope must not become a fact-time or source-removal policy."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import respx

from limes.archive.store import ArchiveStore
from limes.data_scope import DATA_SCOPE_VERSION, DATA_START
from limes.errors import SourceFetchError
from limes.sources.acquisition import AcquisitionStore
from limes.sources.ted import SEARCH_URL, TedAdapter

NOW = datetime(2026, 11, 12, tzinfo=UTC)


def test_scope_journals_preserve_but_do_not_replay_legacy_evidence(tmp_path):
    archive = ArchiveStore(tmp_path / "archive")
    root = tmp_path / "acquisition"
    legacy = root / hashlib.sha256(b"ted").hexdigest()
    legacy.mkdir(parents=True)
    old_journal = legacy / "progress.sqlite3"
    old_journal.write_bytes(b"retained pre-policy evidence")
    store = AcquisitionStore(archive, root)
    with store.session("ted", {}, "v1") as session:
        assert session.directory.parent.name == DATA_SCOPE_VERSION
        assert session.window(DATA_START, NOW) == (DATA_START, NOW)
        session.save_response("old", b"old response")
        with session.db:
            session.db.execute("UPDATE responses SET fetched_at=? WHERE key='old'",
                               ("2019-12-31T23:59:59+00:00",))
        # Refuse old cached observations before reading their archived payload.
        original_get = archive.get
        archive.get = Mock(side_effect=AssertionError("old archive must not be read"))
        with pytest.raises(SourceFetchError, match="precedes 2020"):
            session.response("old")
        archive.get.assert_not_called()
        archive.get = original_get
    assert old_journal.read_bytes() == b"retained pre-policy evidence"


def test_ted_out_of_scope_search_hit_is_rejected_before_notice_download():
    with respx.mock as transport:
        respx.post(SEARCH_URL).respond(200, json={
            "totalNoticeCount": 1,
            "notices": [{"publication-number": "12-2019",
                         "links": {"xml": {"MUL": "https://ted.europa.eu/old.xml"}}}],
        })
        with pytest.raises(SourceFetchError, match="pre-2020"):
            list(TedAdapter().fetch_individual(None, None))
        assert len(transport.calls) == 1


def test_news_replay_preserves_original_acquisition_and_internal_old_publication(
    monkeypatch,
):
    from limes.cli.news import reextract
    from limes.sources.news import NewsAdapter

    metadata = json.dumps({"published": "2018-06-01T00:00:00+00:00"})
    rows = [
        {"id": "old-acquisition", "metadata": metadata,
         "observed_at": datetime(2019, 12, 31, tzinfo=UTC)},
        {"id": "current-snapshot", "metadata": metadata, "observed_at": NOW},
        {"id": "unknown-acquisition", "metadata": metadata, "observed_at": None},
    ]
    adapter = NewsAdapter()
    archive = SimpleNamespace(get=Mock(return_value=b"eligible current snapshot"))
    driver = SimpleNamespace(read=Mock(return_value=rows), close=Mock())
    ctx = SimpleNamespace(driver=driver, registry=SimpleNamespace(get=lambda _: adapter),
                          archive=archive)
    # Configuration is an I/O boundary too: this replay unit test must not
    # read operator settings or require environment configuration on CI.
    monkeypatch.setattr("limes.cli.news.load_settings", Mock())
    monkeypatch.setattr("limes.composition.build_run_context", lambda *a, **kw: ctx)
    monkeypatch.setattr("limes.cli.main.run_with_lock", lambda *a: SimpleNamespace(
        errors=0, records_fetched=len(adapter.replay_records)))
    reextract("case", "2.0.0", "")
    archive.get.assert_called_once_with("current-snapshot")
    assert len(adapter.replay_records) == 1
    raw = adapter.replay_records[0]
    assert raw.fetched_at == NOW  # original saved observation, not today's re-extraction time
    assert raw.acquisition_context["published"].startswith("2018")


def test_sources_keep_complete_registry_and_require_scoped_completeness():
    from limes.api.routers.sources import sources
    from limes.sources.registry import build_default_registry

    contract = json.loads((Path(__file__).parents[2] / "docs/runtime-contract.json").read_text())
    assert contract["source_acquisition_start"] == DATA_START.date().isoformat()
    assert contract["all_sources_required"] is True
    state = {"source_id": "ted", "last_success_at": NOW, "last_run_id": "legacy",
             "corpus_complete": True}
    driver = SimpleNamespace(read=lambda *a: [state])
    first = {row.source_id: row for row in sources(driver)}
    assert set(first) == set(build_default_registry().source_ids())
    assert "offeneregister" in first and not first["ted"].corpus_complete
    assert all(row.source_evidence_start == "2020-01-01" for row in first.values())
    state["data_scope_version"] = DATA_SCOPE_VERSION
    second = {row.source_id: row for row in sources(driver)}
    assert second["ted"].corpus_complete


def test_osm_reacquires_current_snapshot_without_reading_pre_scope_cache(tmp_path):
    from limes.sources.osm_acquisition import AcquisitionState, OsmAcquisition, PartitionEntry

    archive = ArchiveStore(tmp_path / "archive")
    cursor = tmp_path / "cursor"
    store = OsmAcquisition(archive, cursor)
    old_date = datetime(2019, 12, 31, tzinfo=UTC)
    old_state = AcquisitionState(plan_hash="a" * 64, started_at=old_date,
                                partitions={"0": PartitionEntry(
                                    content_hash="b" * 64, fetched_at=old_date)})
    with store.locked():
        store.write(old_state)
        original = (cursor / "active.json").read_bytes()
        archive.get = Mock(side_effect=AssertionError("old payload must not be read"))
        fresh = store.read("a" * 64)
    assert fresh.acquisition_id != old_state.acquisition_id and fresh.partitions == {}
    assert (cursor / f"pre-2020-{old_state.acquisition_id}.json").read_bytes() == original
    archive.get.assert_not_called()
