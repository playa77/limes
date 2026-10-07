#!/usr/bin/env python3
"""Static guards and disposable three-service smoke; never operator data or paid calls.

G1: API-only loopback publication, internal database/control (docs checker).
G2: retired Dash absent (docs checker).
G3: spaCy worker-only, non-root services, no host-control privilege.
G4: operational Make targets use HTTP without budget gates.
Run with the canonical venv; --guards-only creates no containers.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    "up down bootstrap-db ingest ingest-all backfill reextract select-models "
    "evaluate migrate backup stamp-embeddings"
).split()


def guards() -> None:
    subprocess.run([sys.executable, "tools/check_docs.py", "docs/"], cwd=ROOT, check=True)
    topology = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    for name, service in topology["services"].items():
        if service.get("user") != "7474:7474" or service.get("cap_drop") != ["ALL"]:
            raise RuntimeError(f"{name} must be non-root and drop capabilities")
        if any("docker.sock" in str(volume) for volume in service.get("volumes", [])):
            raise RuntimeError(f"{name} holds host Docker control")
    api = (ROOT / "docker/api.Dockerfile").read_text()
    worker = (ROOT / "docker/worker.Dockerfile").read_text()
    if "--prune de-core-news-md" not in api or "--prune en-core-web-md" not in api:
        raise RuntimeError("API must exclude spaCy model wheels")
    if "--prune" in worker or '"limes.operations.worker"' not in worker:
        raise RuntimeError("worker must include spaCy models and run the durable daemon")
    help_text = subprocess.run(
        ["make", "help"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout
    for target in TARGETS:
        if target not in help_text:
            raise RuntimeError(f"Make target missing: {target}")
    for target, arguments in (("backfill", ["SOURCE=feeds", "DAYS=7"]), ("backup", [])):
        command = subprocess.run(
            ["make", "-n", target, *arguments], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout
        if "remote run" not in command or "compose exec" in command or "BUDGET" in command:
            raise RuntimeError(f"{target} must use bounded HTTP operations without budget gates")
    print("G1–G4: topology, privilege, packaging and operational targets passed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guards-only", action="store_true", help="no containers or network")
    args = parser.parse_args()
    guards()
    if args.guards_only:
        return 0
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/integration/test_runtime_stack.py",
            "tests/integration/test_cli_backup.py",
            "-q",
        ],
        cwd=ROOT,
        timeout=1800,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
