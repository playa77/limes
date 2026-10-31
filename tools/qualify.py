#!/usr/bin/env python3
"""Run one complete disposable candidate; retain fail-closed, source-bound evidence.

No production endpoint or paid model is used. Run with the canonical venv.
Reports deliberately make no production, model-quality or platform claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATHS = (
    "src", "desktop/src", "tests", "desktop/tests", "tools", "ontology", "docker",
    "gold_set", "reference_questions", "pyproject.toml", "uv.lock", ".github",
    "docker-compose.yml", ".dockerignore", "docs/runtime-contract.json", "Makefile",
)
TOOL_LINT_PATHS = (
    "tools/build_context.py", "tools/deploy.py", "tools/init_config.py",
    "tools/generate_runtime_docs.py", "tools/smoke_test.py", "tools/qualify.py",
    "docker/neo4j_control.py",
)
SUITES = {
    "unit": ["tests/unit"],
    "desktop": ["desktop/tests/unit", "desktop/tests/contract"],
    # Building three images while the suite's shared graph is running can exhaust
    # constrained executor storage and corrupt that disposable graph's logs.
    "integration": ["tests/integration", "--ignore=tests/integration/test_runtime_stack.py"],
    "acceptance": ["tests/acceptance"],
    "desktop-integration": ["desktop/tests/integration"],
    "runtime-stack": ["tests/integration/test_runtime_stack.py"],
}


def fingerprint(root: Path) -> dict[str, str]:
    paths = subprocess.check_output(
        ["git", "ls-files", "-co", "--exclude-standard", "-z", "--", *SOURCE_PATHS], cwd=root
    ).decode().split("\0")
    return {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in sorted(set(paths) - {""})
    }


def junit_result(path: Path) -> dict[str, int]:
    """Read leaf suites only, avoiding double-counting aggregate attributes."""
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    suites = [suite for suite in suites if suite.find("testsuite") is None]
    totals = {key: sum(int(s.get(key, "0")) for s in suites)
              for key in ("tests", "failures", "errors", "skipped")}
    if (totals["tests"] <= totals["skipped"] or totals["failures"] or totals["errors"]):
        raise ValueError(f"JUnit does not establish a passing suite: {totals}")
    return totals


def write_report(path: Path, report: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n")
    temporary.replace(path)


def execute(command: list[str], log: Path, timeout: int, env: dict[str, str]) -> int:
    with log.open("w") as output:
        process = subprocess.Popen(
            command, cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            return process.wait(timeout=timeout)
        except BaseException:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new directory under work/")
    parser.add_argument("--timeout", type=int, default=2400, help="per-check seconds")
    args = parser.parse_args()
    directory = args.output.resolve()
    if not directory.is_relative_to(ROOT / "work") or args.timeout <= 0:
        parser.error("output must be under work/ and timeout must be positive")
    # An old successful report can never survive a rerun or interrupted attempt.
    directory.mkdir(parents=True, exist_ok=False)
    before = fingerprint(ROOT)
    digest = hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest()
    (directory / "source.json").write_text(json.dumps(before, indent=2) + "\n")
    report = {
        "status": "running", "started_at": datetime.now(UTC).isoformat(),
        "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT)
        .decode().strip(), "source_sha256": digest, "checks": [],
        "scope": "offline and disposable fixtures; no production or paid-quality claim",
    }
    path = directory / "report.json"
    write_report(path, report)
    python = str(ROOT / "venv/bin/python")
    checks = [
        ("baseline", [python, "tools/check_git_baseline.py"]),
        ("lint", [str(ROOT / "venv/bin/ruff"), "check", "src", "tests", "desktop/src",
                  "desktop/tests"]),
        ("tools-lint", [str(ROOT / "venv/bin/ruff"), "check", *TOOL_LINT_PATHS]),
        ("types", [str(ROOT / "venv/bin/mypy")]),
        ("docs", [python, "tools/check_docs.py", "docs/"]),
        ("generated", [python, "tools/generate_runtime_docs.py", "--check"]),
        ("guards", [python, "tools/smoke_test.py", "--guards-only"]),
        ("whitespace", ["git", "diff", "--check"]),
    ]
    checks += [(name, [python, "-m", "pytest", *paths, "-q", "--tb=short",
                       f"--junitxml={directory / (name + '.xml')}"])
               for name, paths in SUITES.items()]
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "QTWEBENGINE_CHROMIUM_FLAGS": "--no-sandbox --disable-gpu",
           "BUILDX_CONFIG": str(ROOT / "work/be45/buildx")}
    started = time.monotonic()
    try:
        if env.get("LIMES_TEST_NEO4J_URI"):
            raise RuntimeError("qualification requires fixture-owned disposable Neo4j")
        for name, command in checks:
            item = {"name": name, "command": command, "status": "running"}
            report["checks"].append(item)
            write_report(path, report)
            tick = time.monotonic()
            print(f"Running {name}; log: {directory / (name + '.log')}", flush=True)
            code = execute(command, directory / (name + ".log"), args.timeout, env)
            item.update(returncode=code, duration_seconds=round(time.monotonic() - tick, 3))
            if code:
                item["status"] = "failed"
                raise RuntimeError(f"{name} exited {code}")
            if name in SUITES:
                item["junit"] = junit_result(directory / (name + ".xml"))
            item["status"] = "passed"
            write_report(path, report)
        if fingerprint(ROOT) != before:
            raise RuntimeError("candidate source changed during qualification")
        report["status"] = "passed"
    except BaseException as exc:
        report["status"] = "failed"
        if report["checks"] and report["checks"][-1]["status"] == "running":
            report["checks"][-1]["status"] = "failed"
        report["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        report["duration_seconds"] = round(time.monotonic() - started, 3)
        report["finished_at"] = datetime.now(UTC).isoformat()
        write_report(path, report)
    print(f"Qualification {report['status']}: {path}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
