# tests/integration/test_cli_backup.py | v1.0.1 | inspect backups in the Docker volume
"""Backup tests per Doc 2 §13.6 and Doc 1 §8.5.

G4: `limes backup` stops the database, dumps offline to the archive with
a timestamped filename, restarts, and verifies reachability — a real
`docker compose` lifecycle against a disposable container. The test's
compose file is the harness (the production compose is WP-37's): one neo4j
service from the same image the suite uses, with a named archive volume
mounted at `/data/archive` — the mount point the backup command's
constants declare.

The whole lifecycle runs as one subprocess CLI invocation (the command is
process-boundary code); the test then verifies the archive artifact and a
reachable database through a fresh driver.
"""

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from neo4j import GraphDatabase

from tests.integration.conftest import IMAGE, PASSWORD

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"

BACKUP_RECONNECT_TIMEOUT_SECONDS = 240


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_ready(uri: str, timeout_s: int = 240) -> None:
    deadline = time.monotonic() + timeout_s
    driver = GraphDatabase.driver(uri, auth=("neo4j", PASSWORD))
    try:
        while time.monotonic() < deadline:
            try:
                driver.verify_connectivity()
                return
            except Exception:
                time.sleep(2)
    finally:
        driver.close()
    raise RuntimeError(f"Neo4j did not become reachable at {uri} within {timeout_s}s")


@pytest.fixture
def backup_env(tmp_path: Path) -> dict[str, str]:
    """A compose root with a neo4j service and the archive mounted at the
    container path the backup command writes to.

    The CLI resolves `ontology/feeds.yaml` relative to its working
    directory (the adapter's default path — the registry takes no
    settings), so the compose root mirrors the production layout: the
    repo's feed configuration lives next to the compose file."""
    ontology_dir = tmp_path / "ontology"
    ontology_dir.mkdir()
    shutil.copy(REPO_ROOT / "ontology" / "feeds.yaml", ontology_dir / "feeds.yaml")
    archive = tmp_path / "archive"
    archive.mkdir()
    port = _free_port()
    compose = tmp_path / "docker-compose.yml"
    compose.write_text(
        f"""services:
  neo4j:
    image: {IMAGE}
    environment:
      - NEO4J_AUTH=neo4j/{PASSWORD}
      - NEO4J_server_memory_heap_initial__size=512m
      - NEO4J_server_memory_heap_max__size=512m
      - NEO4J_server_memory_pagecache_size=512m
    ports:
      - "{port}:7687"
    volumes:
      - limes-backup-test-data:/data
      - limes-backup-test-archive:/data/archive
volumes:
  limes-backup-test-data:
  limes-backup-test-archive:
""",
        encoding="utf-8",
    )
    uri = f"bolt://127.0.0.1:{port}"
    env = {
        **os.environ,
        "LIMES_NEO4J_URI": uri,
        "LIMES_NEO4J_USER": "neo4j",
        "LIMES_NEO4J_PASSWORD": PASSWORD,
        "LIMES_NEO4J_DATABASE": "neo4j",
        "LIMES_ONTOLOGY_PATH": str(ONTOLOGY_PATH),
        "LIMES_FEEDS_CONFIG_PATH": str(REPO_ROOT / "ontology" / "feeds.yaml"),
        "LIMES_GOLD_SET_PATH": str(tmp_path / "gold_set.jsonl"),
        "LIMES_BASELINE_PATH": str(tmp_path / "baseline.json"),
        "LIMES_ARCHIVE_PATH": str(archive),
    }
    return {"compose_root": str(tmp_path), "archive": str(archive), "uri": uri, "env": env}


def test_backup_stops_dumps_and_restarts(backup_env: dict[str, str]):
    compose_root = backup_env["compose_root"]
    uri = backup_env["uri"]
    env = backup_env["env"]

    subprocess.run(
        ["docker", "compose", "up", "-d"],
        check=True,
        capture_output=True,
        text=True,
        cwd=compose_root,
        timeout=300,
    )
    try:
        _wait_ready(uri)

        # The command runs as one subprocess CLI invocation from the compose
        # root — the backup lifecycle (stop → dump → start → verify) is the
        # process-boundary code under test.
        result = subprocess.run(
            [sys.executable, "-m", "limes.cli.main", "backup"],
            capture_output=True,
            text=True,
            cwd=compose_root,
            env=env,
            timeout=600,
        )
        assert result.returncode == 0, result.stderr

        # Inspect the production-style named volume through Docker. Neo4j
        # owns it and may set directory mode 0700; the host's UID and /tmp
        # namespace need not match the daemon's. Keep the count/size guards.
        inspection = subprocess.run(
            [
                "docker", "compose", "run", "--rm", "--no-deps",
                "--entrypoint", "sh", "neo4j", "-c",
                "find /data/archive -maxdepth 1 -type f -name 'limes-*.dump' "
                "-printf '%f %s\\n'",
            ],
            check=True, capture_output=True, text=True, cwd=compose_root, timeout=60,
        )
        dumps = inspection.stdout.strip().splitlines()
        assert len(dumps) == 1, inspection.stdout
        name, size = dumps[0].split()
        assert name.startswith("limes-") and name.endswith(".dump")
        assert int(size) > 0

        driver = GraphDatabase.driver(uri, auth=("neo4j", PASSWORD))
        try:
            driver.verify_connectivity()
        finally:
            driver.close()
    finally:
        subprocess.run(
            ["docker", "compose", "down", "-v", "--remove-orphans"],
            check=False,
            capture_output=True,
            text=True,
            cwd=compose_root,
            timeout=300,
        )
