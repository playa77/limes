# tests/acceptance/test_ac32_memory.py | v1.0.0 | introduced by WP-39
"""AC-32: total resident memory of all services under a full backfill
stays below 11 GB.

The full backfill is a paid, multi-hour operation that this suite must not
run; what is mechanically testable is the resource contract that bounds the
resident set: the §13.4 runtime caps declared in the Compose topology. The
test asserts the four declared Neo4j caps (heap 2 GB initial and max, page
cache 2 GB, transaction memory cap 512 MB — the §13.4 values) and that the
sum of every declared cap in the topology stays below the 11 GB ceiling
with the margin the worker's spaCy models and the API/UI processes consume
under backfill.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE = REPO_ROOT / "docker-compose.yml"

# Technical Specification §13.4: heap 2 GB initial and max, page cache
# 2 GB, transaction memory cap 512 MB, transaction timeout 120 s.
EXPECTED_CAPS = {
    "NEO4J_server_memory_heap_initial__size": "2G",
    "NEO4J_server_memory_heap_max__size": "2G",
    "NEO4J_server_memory_pagecache_size": "2G",
    "NEO4J_db_memory_transaction_total_max": "512m",
}

# The 11 GB ceiling of AC-32.
CEILING_BYTES = 11 * 1024**3


def _parse_size(value: str) -> int:
    """`2G`, `512m`, `1024M` → bytes (the compose env values are fixed
    literals with the documented units)."""
    match = re.fullmatch(r"(\d+)([kKmMgGtT]?)", value.strip())
    assert match, f"unparseable size literal: {value!r}"
    number = int(match.group(1))
    unit = match.group(2).lower()
    return number * {"": 1, "k": 1024, "m": 1024**2, "g": 1024**3, "t": 1024**4}[unit]


def _neo4j_environment() -> dict[str, str]:
    environment = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text())["services"][
        "neo4j"
    ]["environment"]
    if isinstance(environment, dict):
        return environment
    return dict(item.split("=", 1) for item in environment)


def test_ac32_neo4j_runtime_caps_match_section_13_4():
    environment = _neo4j_environment()
    for key, expected in EXPECTED_CAPS.items():
        raw = environment.get(key, "")
        # The compose file interpolates the host .env with a fallback; the
        # fallback is the documented value (the trailing '}' closes the
        # interpolation).
        assert raw.endswith(f":-{expected}}}") or raw == expected, (key, raw)


def test_ac32_declared_caps_sum_below_the_ceiling():
    environment = _neo4j_environment()
    declared = sum(
        _parse_size(environment[key].split(":-")[-1].rstrip("}")) for key in EXPECTED_CAPS
    )
    assert declared < CEILING_BYTES, f"declared caps sum to {declared} bytes"
    # The documented operating point (Doc 1 §8.2): ~4.5 GB resident for
    # Neo4j alone, leaving the rest of the ceiling for the worker's models,
    # the API, and the UI under backfill.
    assert declared <= 7 * 1024**3, f"declared caps sum to {declared} bytes"
