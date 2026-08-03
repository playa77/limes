# tests/acceptance/test_ac42_window.py | v1.0.0 | introduced by WP-39
"""AC-42: window resolution returns a full load for a non-incremental
adapter and a `last_success_at`-anchored window for an incremental one
that has run before.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from limes.config import Settings
from limes.pipeline.run import RunSpec
from limes.pipeline.window import resolve_window
from limes.types import SourceRecord

REPO_ROOT = Path(__file__).resolve().parents[2]

LAST_SUCCESS = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
NOW = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
CUTOFF = NOW - timedelta(days=90)


def _settings() -> Settings:
    return Settings(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="limes",
        neo4j_password="pw",
        ontology_path=REPO_ROOT / "ontology" / "ontology.yaml",
        feeds_config_path=REPO_ROOT / "ontology" / "feeds.yaml",
        gold_set_path=REPO_ROOT / "gold_set" / "gold_set.jsonl",
        baseline_path=REPO_ROOT / "gold_set" / "baseline.json",
        archive_path=REPO_ROOT / "archive",
        openrouter_api_key="sk-test",
        backfill_days_unstructured=90,
    )


class _Adapter:
    """A minimal adapter stub for the window function's inputs."""

    def __init__(self, supports_incremental: bool) -> None:
        self.supports_incremental = supports_incremental
        self.kind: Literal["structured", "unstructured"] = "unstructured"


def _source(last_success_at: datetime | None) -> SourceRecord:
    return SourceRecord(
        source_id="feeds",
        name="Curated Feeds",
        kind="unstructured",
        trust_rank=0.6,
        last_success_at=last_success_at,
        last_run_id=None,
    )


def test_ac42_non_incremental_adapter_is_a_full_load():
    spec = RunSpec(source_id="gisco_nuts", mode="ingest")
    since, until = resolve_window(spec, _Adapter(False), None, _settings(), now=NOW)
    assert since is None and until is None  # a full load


def test_ac42_incremental_adapter_anchors_on_last_success_at():
    spec = RunSpec(source_id="feeds", mode="ingest")
    since, until = resolve_window(spec, _Adapter(True), _source(LAST_SUCCESS), _settings(), now=NOW)
    assert since == LAST_SUCCESS
    assert until is None


def test_ac42_incremental_adapter_without_history_uses_backfill_cutoff():
    spec = RunSpec(source_id="feeds", mode="ingest")
    since, until = resolve_window(spec, _Adapter(True), _source(None), _settings(), now=NOW)
    assert since == CUTOFF
    assert until is None


def test_ac42_explicit_since_always_wins():
    explicit = datetime(2024, 1, 1, tzinfo=UTC)
    spec = RunSpec(source_id="gisco_nuts", mode="ingest", since=explicit)
    since, until = resolve_window(spec, _Adapter(False), None, _settings(), now=NOW)
    assert since == explicit  # even for a non-incremental adapter
