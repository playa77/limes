# tests/unit/test_neo4j_fixture.py | v1.0.0 | shared fixture cleanup on success and failure
from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.integration import conftest as fixtures


def _mock_docker(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    commands: list[list[str]] = []

    def run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(stdout="test-container\n", returncode=0)

    monkeypatch.setattr(fixtures.subprocess, "run", run)
    monkeypatch.setattr(fixtures, "FIXED_URI", "")
    monkeypatch.setattr(fixtures, "_wait_ready", lambda *args: None)
    monkeypatch.setattr(fixtures, "_create_test_user", lambda *args: None)
    return commands


def test_fixture_removes_container_and_volumes_on_teardown(monkeypatch: pytest.MonkeyPatch):
    commands = _mock_docker(monkeypatch)
    lifecycle = fixtures.neo4j_instance.__wrapped__()
    assert next(lifecycle).container_id == "test-container"
    lifecycle.close()
    assert commands[-1] == ["docker", "rm", "-fv", "test-container"]


def test_fixture_removes_container_when_startup_fails(monkeypatch: pytest.MonkeyPatch):
    commands = _mock_docker(monkeypatch)

    def fail(*args):
        raise RuntimeError("startup failed")

    monkeypatch.setattr(fixtures, "_wait_ready", fail)
    with pytest.raises(RuntimeError, match="startup failed"):
        next(fixtures.neo4j_instance.__wrapped__())
    assert commands[-1] == ["docker", "rm", "-fv", "test-container"]


def test_fixture_preserves_externally_supplied_database(monkeypatch: pytest.MonkeyPatch):
    commands = _mock_docker(monkeypatch)
    monkeypatch.setattr(fixtures, "FIXED_URI", "bolt://provided.test:7687")
    lifecycle = fixtures.neo4j_instance.__wrapped__()
    assert next(lifecycle).container_id is None
    lifecycle.close()
    assert commands == []
