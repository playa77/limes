# tests/unit/test_cli_commands.py | v1.0.0 | introduced by WP-40
"""Unit tests for the CLI command bodies per Doc 2 §8.14.

The integration suite drives the commands in-process through the CliRunner
or across a real subprocess, which covers their happy paths but not every
branch: the subprocess invocations (backup, reextract, `python -m
limes.cli.main`) are invisible to the coverage tracer, and the failure
branches never fire against a working stack. These tests exercise the
command bodies with the composition root and the process boundary stubbed —
settings, context, and `_compose`/`_wait_reachable` are the seams, exactly
as the integration tests stub the network.
"""

from __future__ import annotations

import runpy
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from limes.cli import backup as backup_module
from limes.cli import ingest as ingest_module
from limes.cli import main as main_module
from limes.cli import reextract as reextract_module
from limes.config import Settings
from limes.errors import LimesError

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"

runner = CliRunner()


def _settings(**overrides: Any) -> Settings:
    base = dict(
        neo4j_uri="bolt://test:7687",
        neo4j_user="u",
        neo4j_password="p",
        ontology_path=ONTOLOGY_PATH,
        feeds_config_path=REPO_ROOT / "ontology" / "feeds.yaml",
        gold_set_path=REPO_ROOT / "gold_set" / "gold_set.jsonl",
        baseline_path=REPO_ROOT / "gold_set" / "baseline.json",
        archive_path=Path("/tmp/archive"),
    )
    base.update(overrides)
    return Settings(**base)


# --------------------------------------------------------------------------
# main.py — timestamp parsing and the entry point
# --------------------------------------------------------------------------


def test_parse_iso_datetime_naive_value_is_assumed_utc():
    parsed = main_module.parse_iso_datetime("2026-07-15T08:30:00", "--since")
    assert parsed == datetime(2026, 7, 15, 8, 30, tzinfo=UTC)


def test_parse_iso_datetime_rejects_garbage():
    with pytest.raises(LimesError, match="not an ISO-8601 timestamp"):
        main_module.parse_iso_datetime("not-a-date", "--since")


def test_main_entry_point_runs_the_app(capsys):
    # `python -m limes.cli.main` executes the module as __main__; runpy does
    # that in-process so the tracer sees the entry-point lines (the real
    # subprocess invocation in the integration suite is invisible to it).
    with pytest.raises(SystemExit):
        runpy.run_module("limes.cli.main", run_name="__main__")
    # Typer derives the program name from sys.argv (pytest here) and prints
    # the help to stderr.
    assert "Usage:" in capsys.readouterr().err


# --------------------------------------------------------------------------
# ingest.py — the ingest-all sequence body
# --------------------------------------------------------------------------


def test_ingest_all_runs_every_ingestable_source_in_sequence(
    monkeypatch: pytest.MonkeyPatch, capsys
):
    settings = _settings()
    calls: list[str] = []
    monkeypatch.setattr(ingest_module, "load_settings", lambda: settings)
    monkeypatch.setattr(ingest_module, "configure_logging", lambda settings: None)
    monkeypatch.setattr(ingest_module, "_ingestable_source_ids", lambda: ["gisco_nuts", "gleif"])

    def fake_ingest(settings, source_id, spec):
        calls.append(source_id)

    monkeypatch.setattr(ingest_module, "_ingest_source", fake_ingest)
    ingest_module.ingest_all()
    assert calls == ["gisco_nuts", "gleif"]
    out = capsys.readouterr().out
    assert "ingest-all: gisco_nuts" in out
    assert "ingest-all: gleif" in out
    assert "ingest-all: complete" in out


# --------------------------------------------------------------------------
# reextract.py — the command body and one-source run
# --------------------------------------------------------------------------


def test_reextract_source_copies_the_prompt_version_into_settings(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = _settings(extraction_prompt_version="1.0.0")
    seen: dict[str, Any] = {}
    monkeypatch.setattr(reextract_module, "load_settings", lambda: settings)
    monkeypatch.setattr(reextract_module, "configure_logging", lambda settings: None)
    monkeypatch.setattr(reextract_module, "_reextract_sources", lambda explicit: ["feeds"])

    def fake_build(settings, needs_inference, budget_eur=None):
        seen["prompt_version"] = settings.extraction_prompt_version
        seen["needs_inference"] = needs_inference
        seen["budget"] = budget_eur
        return SimpleNamespace(driver=SimpleNamespace(close=lambda: None))

    record = SimpleNamespace(
        records_fetched=1,
        assertions_written=2,
        assertions_skipped=0,
        errors=0,
        cost_eur=Decimal("0.0100"),
    )
    monkeypatch.setattr("limes.composition.build_run_context", fake_build)
    monkeypatch.setattr("limes.cli.main.adapter_kind", lambda source_id: "unstructured")
    monkeypatch.setattr(
        "limes.cli.main.run_with_lock",
        lambda ctx, source_id, spec: record,
    )
    reextract_module.reextract_source(prompt_version="2.0.0", budget=1.5)
    # The cache key includes the prompt version (D-39): the run must see the
    # requested version, not the configured one.
    assert seen["prompt_version"] == "2.0.0"
    assert seen["needs_inference"] is True
    assert seen["budget"] == Decimal("1.5")


def test_reextract_one_runs_with_the_explicit_source_and_envelope(
    monkeypatch: pytest.MonkeyPatch, capsys
):
    settings = _settings()
    seen: dict[str, Any] = {}

    def fake_build(settings, needs_inference, budget_eur=None):
        seen["source"] = None
        return SimpleNamespace(driver=SimpleNamespace(close=lambda: None))

    record = SimpleNamespace(
        records_fetched=3,
        assertions_written=1,
        assertions_skipped=1,
        errors=0,
        cost_eur=Decimal("0.0200"),
    )
    monkeypatch.setattr("limes.composition.build_run_context", fake_build)
    monkeypatch.setattr("limes.cli.main.adapter_kind", lambda source_id: "structured")

    def fake_run_with_lock(ctx, source_id, spec):
        seen["source"] = source_id
        seen["mode"] = spec.mode
        return record

    monkeypatch.setattr("limes.cli.main.run_with_lock", fake_run_with_lock)
    reextract_module._reextract_one(settings, "gisco_nuts", Decimal("2.00"))
    assert seen["source"] == "gisco_nuts"
    assert seen["mode"] == "reextract"
    out = capsys.readouterr().out
    assert "reextract gisco_nuts: 3 records" in out
    assert "cost EUR 0.0200" in out


# --------------------------------------------------------------------------
# backup.py — the lifecycle, the compose seam, reachability polling
# --------------------------------------------------------------------------


def test_backup_stops_dumps_and_restarts(monkeypatch: pytest.MonkeyPatch, capsys):
    settings = _settings()
    monkeypatch.setattr(backup_module, "load_settings", lambda: settings)
    monkeypatch.setattr(backup_module, "configure_logging", lambda settings: None)
    ctx = SimpleNamespace(driver=SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(
        "limes.composition.build_run_context", lambda settings, needs_inference: ctx
    )
    compose_calls: list[list[str]] = []
    monkeypatch.setattr(backup_module, "_compose", lambda args: compose_calls.append(args))
    monkeypatch.setattr(backup_module, "_wait_reachable", lambda driver, timeout_s: None)

    backup_module.backup()
    # stop → offline dump → start, in that order (§13.6), then verify.
    assert [c[0] for c in compose_calls] == ["stop", "run", "start"]
    out = capsys.readouterr().out
    assert "backup: complete (limes-" in out


def test_compose_failure_raises_limes_error(monkeypatch: pytest.MonkeyPatch):
    import subprocess as subprocess_module

    def fake_run(args, capture_output, text, check):
        return SimpleNamespace(returncode=1, stderr="container exploded", stdout="")

    monkeypatch.setattr(subprocess_module, "run", fake_run)
    with pytest.raises(LimesError, match="docker compose stop neo4j failed"):
        backup_module._compose(["stop", "neo4j"])


def test_compose_success_logs_the_step(monkeypatch: pytest.MonkeyPatch, capfd):
    import subprocess as subprocess_module

    def fake_run(args, capture_output, text, check):
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(subprocess_module, "run", fake_run)
    backup_module._compose(["stop", "neo4j"])
    # The default structlog renderer writes to stdout, command as a kv-pair.
    captured = capfd.readouterr()
    assert "docker compose step completed" in captured.out
    assert "command='stop neo4j'" in captured.out


def test_wait_reachable_returns_when_the_database_answers(monkeypatch: pytest.MonkeyPatch):
    driver = SimpleNamespace(read=lambda cypher, params, timeout_s: [{"ok": 1}])
    backup_module._wait_reachable(driver, 10)


def test_wait_reachable_survives_transient_failures(monkeypatch: pytest.MonkeyPatch):
    attempts = {"n": 0}

    def read(cypher, params, timeout_s):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("not ready yet")
        return [{"ok": 1}]

    monkeypatch.setattr(backup_module.time, "sleep", lambda seconds: None)
    backup_module._wait_reachable(SimpleNamespace(read=read), 10)
    assert attempts["n"] == 3


def test_wait_reachable_gives_up_after_the_timeout(monkeypatch: pytest.MonkeyPatch):
    driver = SimpleNamespace(
        read=lambda cypher, params, timeout_s: (_ for _ in ()).throw(RuntimeError("down"))
    )
    # A non-positive timeout means the deadline is already past: the poll
    # loop never runs and the refusal fires immediately.
    with pytest.raises(LimesError, match="did not become reachable"):
        backup_module._wait_reachable(driver, -1)
