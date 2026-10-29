"""Qualification must reject false-green evidence and bind uncommitted source."""
import subprocess

import pytest

from tools.qualify import fingerprint, junit_result


@pytest.mark.parametrize("xml", [
    '<testsuites/>',
    '<testsuite tests="1" failures="1"/>',
    '<testsuite tests="1" errors="1"/>',
    '<testsuite tests="1" skipped="1"/>',
])
def test_unusable_junit_is_rejected(tmp_path, xml):
    path = tmp_path / "result.xml"
    path.write_text(xml)
    with pytest.raises(ValueError):
        junit_result(path)


def test_junit_aggregate_is_not_counted_twice(tmp_path):
    path = tmp_path / "result.xml"
    path.write_text('<testsuites tests="2"><testsuite tests="2"/></testsuites>')
    assert junit_result(path) == {"tests": 2, "failures": 0, "errors": 0, "skipped": 0}


def test_fingerprint_includes_untracked_source_and_detects_changes(tmp_path):
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    source = tmp_path / "src"
    source.mkdir()
    path = source / "candidate.py"
    path.write_text("first")
    before = fingerprint(tmp_path)
    assert "src/candidate.py" in before
    path.write_text("changed")
    assert fingerprint(tmp_path) != before


def test_failed_check_leaves_failed_report_and_stops(tmp_path, monkeypatch):
    import json

    from tools import qualify

    monkeypatch.setattr(qualify, "ROOT", tmp_path)
    monkeypatch.setattr(qualify, "fingerprint", lambda root: {})
    monkeypatch.setattr(qualify.subprocess, "check_output", lambda *a, **kw: b"revision")
    calls = []

    def fail(command, log, timeout, env):
        calls.append(command)
        return 1

    monkeypatch.setattr(qualify, "execute", fail)
    output = tmp_path / "work/candidate"
    monkeypatch.setattr("sys.argv", ["qualify", "--output", str(output)])
    assert qualify.main() == 1
    report = json.loads((output / "report.json").read_text())
    assert report["status"] == "failed"
    assert len(calls) == 1
    # Reusing an evidence directory cannot silently retain a prior green report.
    with pytest.raises(FileExistsError):
        qualify.main()


def test_successful_commands_cannot_qualify_changed_source(tmp_path, monkeypatch):
    import json

    from tools import qualify

    monkeypatch.setattr(qualify, "ROOT", tmp_path)
    fingerprints = iter([{"source": "before"}, {"source": "after"}])
    monkeypatch.setattr(qualify, "fingerprint", lambda root: next(fingerprints))
    monkeypatch.setattr(qualify.subprocess, "check_output", lambda *a, **kw: b"revision")
    monkeypatch.setattr(qualify, "execute", lambda *a: 0)
    monkeypatch.setattr(qualify, "junit_result", lambda path: {"tests": 1})
    monkeypatch.delenv("LIMES_TEST_NEO4J_URI", raising=False)
    output = tmp_path / "work/candidate"
    monkeypatch.setattr("sys.argv", ["qualify", "--output", str(output)])
    assert qualify.main() == 1
    report = json.loads((output / "report.json").read_text())
    assert report["status"] == "failed"
    assert "source changed" in report["error"]
