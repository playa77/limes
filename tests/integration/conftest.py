# tests/integration/conftest.py | v1.0.0 | introduced by WP-04
"""Disposable Neo4j container lifecycle for integration tests.

Starts one Community Edition container per test session via the docker CLI,
waits until the bolt port accepts connections, and tears the container down
afterward. Integration tests must never require a pre-provisioned database:
`provision()` (WP-04) creates the schema on every context build, and the
loader tests (WP-07) assert against an empty graph.

The image tag defaults to the Neo4j 2026.x Community line per C-01 and can be
overridden with LIMES_TEST_NEO4J_IMAGE. Set LIMES_TEST_NEO4J_URI to point at
an already-running container instead of starting one.
"""

from __future__ import annotations

import os
import socket
import subprocess
import time
from dataclasses import dataclass

import pytest
from neo4j import GraphDatabase

IMAGE = os.environ.get("LIMES_TEST_NEO4J_IMAGE", "neo4j:2026.06-community")
PASSWORD = "limes-test-password"
ADMIN_USER = "neo4j"  # Neo4j 2026.x only accepts the default admin name at first boot
USER = "limes"
DB = "neo4j"

FIXED_URI = os.environ.get("LIMES_TEST_NEO4J_URI", "")


@dataclass(frozen=True)
class Neo4jInstance:
    uri: str
    user: str
    password: str
    database: str
    container_id: str | None = None


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_ready(uri: str, user: str, timeout_s: int = 240) -> None:
    deadline = time.monotonic() + timeout_s
    driver = GraphDatabase.driver(uri, auth=(user, PASSWORD))
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


def _create_test_user(uri: str) -> None:
    """Create the `limes` test user with the admin credentials.

    C-01: Community Edition grants identical privileges to every user, so the
    test user mirrors production (a non-admin named `limes`) without any
    privilege separation to exercise."""
    driver = GraphDatabase.driver(uri, auth=(ADMIN_USER, PASSWORD))
    try:
        with driver.session() as session:
            session.run(
                "CREATE USER $user SET PASSWORD $password CHANGE NOT REQUIRED",
                user=USER,
                password=PASSWORD,
            ).consume()
    except Exception as exc:
        if "already exists" not in str(exc):
            raise
    finally:
        driver.close()


@pytest.fixture(scope="session")
def neo4j_instance() -> Neo4jInstance:
    if FIXED_URI:
        _wait_ready(FIXED_URI, USER)
        return Neo4jInstance(uri=FIXED_URI, user=USER, password=PASSWORD, database=DB)

    port = _free_port()
    uri = f"bolt://127.0.0.1:{port}"
    container_id = subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "-p",
            f"{port}:7687",
            "-e",
            f"NEO4J_AUTH={ADMIN_USER}/{PASSWORD}",
            "-e",
            "NEO4J_server_memory_heap_initial__size=512m",
            "-e",
            "NEO4J_server_memory_heap_max__size=512m",
            "-e",
            "NEO4J_server_memory_pagecache_size=512m",
            "--name",
            f"limes-test-neo4j-{port}",
            IMAGE,
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    try:
        _wait_ready(uri, ADMIN_USER)
        _create_test_user(uri)
        return Neo4jInstance(
            uri=uri,
            user=USER,
            password=PASSWORD,
            database=DB,
            container_id=container_id,
        )
    except Exception:
        subprocess.run(["docker", "rm", "-f", container_id], capture_output=True)
        raise


@pytest.fixture(scope="session", autouse=True)
def _teardown(neo4j_instance: Neo4jInstance) -> None:
    yield
    if neo4j_instance.container_id:
        subprocess.run(
            ["docker", "rm", "-f", neo4j_instance.container_id],
            capture_output=True,
            check=False,
        )
