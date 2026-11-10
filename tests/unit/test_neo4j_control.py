"""Physical dump requires a clean stop, and restart runs even when dumping fails."""

import importlib.util
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location(
    "neo4j_control", Path(__file__).resolve().parents[2] / "docker/neo4j_control.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_dump_failure_still_restarts_database(monkeypatch, tmp_path):
    db = module.Database()
    events = []
    monkeypatch.setattr(module, "Path", lambda _: tmp_path)
    monkeypatch.setattr(db, "stop", lambda: events.append("stop"))
    monkeypatch.setattr(db, "start", lambda: events.append("start"))
    monkeypatch.setattr(db, "ready", lambda: events.append("ready"))

    def dump(*args, **kwargs):
        events.append("dump")
        raise subprocess.CalledProcessError(1, args[0])

    monkeypatch.setattr(module.subprocess, "run", dump)
    with pytest.raises(subprocess.CalledProcessError):
        db.backup()
    assert events == ["stop", "dump", "start", "ready"]
    assert db.lock.acquire(blocking=False)


def test_unclean_stop_never_dumps(monkeypatch, tmp_path):
    db = module.Database()
    events = []
    monkeypatch.setattr(module, "Path", lambda _: tmp_path)

    def stop():
        raise subprocess.TimeoutExpired("neo4j", 180)

    monkeypatch.setattr(db, "stop", stop)
    monkeypatch.setattr(db, "start", lambda: events.append("start"))
    monkeypatch.setattr(db, "ready", lambda: events.append("ready"))
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **kw: events.append("dump"))
    with pytest.raises(subprocess.TimeoutExpired):
        db.backup()
    assert events == ["start", "ready"]


def test_stop_rejects_failed_exit(monkeypatch):
    db = module.Database()
    db.process = SimpleNamespace(pid=99999, poll=lambda: None, wait=lambda **kw: 42)
    monkeypatch.setattr(module.os, "killpg", lambda *a: None)
    with pytest.raises(RuntimeError, match="cleanly"):
        db.stop()


def test_concurrent_backup_refused():
    db = module.Database()
    db.lock.acquire()
    with pytest.raises(BlockingIOError):
        db.backup()


class ReadinessClock:
    def __init__(self):
        self.elapsed = 0.0
        self.stopping = False

    def is_set(self):
        return self.stopping

    def wait(self, seconds):
        self.elapsed += seconds


def test_cold_cli_startup_can_provision_and_authenticate_within_the_shared_deadline(monkeypatch):
    # A real cold cypher-shell probe took 34.51 seconds in the two-CPU cloud
    # executor. Simulate a 35-second launch; the old 15-second cap never let
    # a healthy database complete even one probe.
    clock = ReadinessClock()
    db = module.Database()
    db.process = SimpleNamespace(poll=lambda: None)
    db.stopping = clock
    monkeypatch.setattr(module.time, "monotonic", lambda: clock.elapsed)
    monkeypatch.setenv("LIMES_NEO4J_USER", "limes")
    monkeypatch.setenv("LIMES_NEO4J_PASSWORD", "fixture-password")
    users = []

    def shell(argv, **kwargs):
        budget = kwargs["timeout"]
        if budget < 35:
            clock.elapsed += budget
            raise subprocess.TimeoutExpired("cypher-shell", budget)
        clock.elapsed += 35
        users.append(argv[argv.index("-u") + 1])
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(module.subprocess, "run", shell)
    db.ready(provision=True)
    assert users == ["neo4j", "neo4j", "limes"]
    assert clock.elapsed == 105


def test_repeated_probe_timeouts_cannot_extend_the_overall_startup_deadline(monkeypatch):
    clock = ReadinessClock()
    db = module.Database()
    db.process = SimpleNamespace(poll=lambda: None)
    db.stopping = clock
    monkeypatch.setattr(module.time, "monotonic", lambda: clock.elapsed)
    monkeypatch.setenv("LIMES_NEO4J_USER", "limes")
    monkeypatch.setenv("LIMES_NEO4J_PASSWORD", "fixture-password")
    budgets = []

    def hanging_shell(argv, **kwargs):
        budgets.append(kwargs["timeout"])
        clock.elapsed += kwargs["timeout"]
        raise subprocess.TimeoutExpired("cypher-shell", kwargs["timeout"])

    monkeypatch.setattr(module.subprocess, "run", hanging_shell)
    with pytest.raises(RuntimeError, match="did not become ready"):
        db.ready()
    assert clock.elapsed == 360
    assert budgets[-1] < budgets[0]  # final probe receives only the remaining time


def test_shutdown_between_probes_does_not_start_more_cli_processes(monkeypatch):
    clock = ReadinessClock()
    db = module.Database()
    db.process = SimpleNamespace(poll=lambda: None)
    db.stopping = clock
    monkeypatch.setattr(module.time, "monotonic", lambda: clock.elapsed)
    monkeypatch.setenv("LIMES_NEO4J_USER", "limes")
    monkeypatch.setenv("LIMES_NEO4J_PASSWORD", "fixture-password")
    calls = []

    def stop_during_probe(argv, **kwargs):
        calls.append(argv)
        clock.stopping = True
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(module.subprocess, "run", stop_during_probe)
    with pytest.raises(RuntimeError, match="shutting down"):
        db.ready(provision=True)
    assert len(calls) == 1


def test_restart_reclaims_only_stale_browser_assets_before_launch(monkeypatch, tmp_path):
    stale = tmp_path / "decompressed-browser123"
    stale.mkdir()
    (stale / "asset.js").write_text("public browser asset")
    unrelated = tmp_path / "decompressed-browser-important"
    unrelated.mkdir()
    outside = tmp_path / "other-data"
    outside.mkdir()
    (tmp_path / "decompressed-browser456").symlink_to(outside, target_is_directory=True)
    db = module.Database()
    db.process = SimpleNamespace(poll=lambda: 0)
    monkeypatch.setattr(module, "Path", lambda _: tmp_path)
    launched = SimpleNamespace(poll=lambda: None)

    def launch(*args, **kwargs):
        assert not stale.exists()
        assert unrelated.is_dir()
        assert outside.is_dir()
        assert (tmp_path / "decompressed-browser456").is_symlink()
        return launched

    monkeypatch.setattr(module.subprocess, "Popen", launch)
    db.start()
    assert db.process is launched


def test_start_does_not_remove_an_active_database_browser_cache(monkeypatch, tmp_path):
    active = tmp_path / "decompressed-browser123"
    active.mkdir()
    db = module.Database()
    db.process = SimpleNamespace(poll=lambda: None)
    monkeypatch.setattr(module, "Path", lambda _: tmp_path)
    monkeypatch.setattr(
        module.subprocess, "Popen", lambda *a, **kw: pytest.fail("active process relaunched")
    )
    db.start()
    assert active.is_dir()


def test_browser_cache_cleanup_respects_directory_ownership(monkeypatch, tmp_path):
    foreign = tmp_path / "decompressed-browser123"
    foreign.mkdir()
    owner = foreign.stat().st_uid
    monkeypatch.setattr(module, "Path", lambda _: tmp_path)
    monkeypatch.setattr(module.os, "getuid", lambda: owner + 1)
    module.Database._clear_browser_cache()
    assert foreign.is_dir()
