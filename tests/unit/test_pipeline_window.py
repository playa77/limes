# tests/unit/test_pipeline_window.py | v1.0.0 | introduced by WP-27
"""Window resolution tests per Doc 2 §8.6.2 (AC-42).

Pure function, injected clock — no graph, no network. The four routes: an
explicit `since` always wins; an incremental source with a last success
anchors there; a never-run incremental source starts at
`now − LIMES_BACKFILL_DAYS_UNSTRUCTURED`; a non-incremental source is a
full load.
"""

from datetime import UTC, datetime, timedelta

from limes.config import Settings
from limes.pipeline.run import RunSpec
from limes.pipeline.window import resolve_window
from limes.types import SourceRecord

NOW = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
LAST_SUCCESS = NOW - timedelta(days=3)


class _IncrementalAdapter:
    source_id = "test_incremental"
    name = "Test incremental"
    kind = "unstructured"
    trust_rank = 0.5
    supports_backfill = True
    supports_incremental = True

    def fetch(self, since, until):
        yield from ()

    def normalize(self, record):
        raise NotImplementedError


class _StaticAdapter:
    source_id = "test_static"
    name = "Test static"
    kind = "structured"
    trust_rank = 0.5
    supports_backfill = True
    supports_incremental = False

    def fetch(self, since, until):
        yield from ()

    def normalize(self, record):
        raise NotImplementedError


def _settings(**overrides) -> Settings:
    base = dict(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="limes",
        neo4j_password="pw",
        ontology_path="/tmp/ontology.yaml",
        feeds_config_path="/tmp/feeds.yaml",
        gold_set_path="/tmp/gold_set.jsonl",
        baseline_path="/tmp/baseline.json",
        archive_path="/tmp/archive",
        backfill_days_unstructured=90,
    )
    base.update(overrides)
    return Settings(**base)


def _spec(**overrides) -> RunSpec:
    base = dict(source_id="test_incremental", mode="ingest")
    base.update(overrides)
    return RunSpec(**base)


def test_explicit_since_always_wins():
    spec = _spec(since=NOW - timedelta(days=7), until=NOW)
    since, until = resolve_window(spec, _IncrementalAdapter(), None, _settings(), now=NOW)
    assert since == spec.since
    assert until == spec.until


def test_incremental_with_last_success_anchors_there():
    source = SourceRecord(
        source_id="test_incremental",
        name="Test incremental",
        kind="unstructured",
        trust_rank=0.5,
        last_success_at=LAST_SUCCESS,
        last_run_id="run-1",
    )
    since, until = resolve_window(
        _spec(),
        _IncrementalAdapter(),
        source,
        _settings(),
        now=NOW,
    )
    assert since == LAST_SUCCESS
    assert until is None


def test_never_run_incremental_starts_at_backfill_cutoff():
    since, until = resolve_window(
        _spec(),
        _IncrementalAdapter(),
        None,
        _settings(backfill_days_unstructured=90),
        now=NOW,
    )
    assert since == NOW - timedelta(days=90)
    assert until is None


def test_non_incremental_is_full_load():
    since, until = resolve_window(
        _spec(source_id="test_static"),
        _StaticAdapter(),
        SourceRecord(
            source_id="test_static",
            name="Test static",
            kind="structured",
            trust_rank=0.5,
        ),
        _settings(),
        now=NOW,
    )
    assert since is None
    assert until is None


def test_explicit_since_wins_even_on_static_source():
    # The explicit-since route precedes the incremental check: a full-load
    # source can still be windowed by hand.
    spec = _spec(source_id="test_static", since=NOW - timedelta(days=1))
    since, until = resolve_window(spec, _StaticAdapter(), None, _settings(), now=NOW)
    assert since == spec.since


def test_last_success_at_never_ignored_when_null():
    # A SourceRecord with last_success_at=None (never run, node exists)
    # must fall to the backfill cutoff, not to a full load.
    source = SourceRecord(
        source_id="test_incremental",
        name="Test incremental",
        kind="unstructured",
        trust_rank=0.5,
    )
    since, until = resolve_window(
        _spec(),
        _IncrementalAdapter(),
        source,
        _settings(backfill_days_unstructured=30),
        now=NOW,
    )
    assert since == NOW - timedelta(days=30)


def test_until_passes_through_unmodified():
    until = NOW + timedelta(hours=6)
    _, passed = resolve_window(
        _spec(until=until),
        _IncrementalAdapter(),
        None,
        _settings(),
        now=NOW,
    )
    assert passed == until
