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
