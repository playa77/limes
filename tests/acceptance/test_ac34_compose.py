# tests/acceptance/test_ac34_compose.py | v1.0.0 | introduced by WP-39
"""AC-34: the base Compose file publishes no ports; the database port is
unpublished in both files.

Static assertion over the two committed Compose files — the same check
the WP-38 smoke test performs against the rendered config, expressed as a
mechanical test. The Neo4j port (7687) appears in neither file except as
the `LIMES_NEO4J_URI` value.
"""

from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE = REPO_ROOT / "docker-compose.yml"
OVERRIDE = REPO_ROOT / "docker-compose.override.yml"

NEO4J_BOLT_PORT = "7687"


def _load(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict) and "services" in data, path
    return data


def test_ac34_base_compose_publishes_only_api_on_loopback():
    services = _load(COMPOSE)["services"]
    assert "ui" not in services
    assert services["api"]["ports"] == ["127.0.0.1:8000:8000"]
    assert not services["neo4j"].get("ports")
    assert not services["worker"].get("ports")


def test_ac34_database_port_unpublished_in_both_files():
    for path in (COMPOSE, OVERRIDE):
        data = _load(path)
        text = path.read_text(encoding="utf-8")
        for name, service in data["services"].items():
            for port in service.get("ports", []):
                published = str(port)
                assert NEO4J_BOLT_PORT not in published, (
                    f"{path}: service {name} publishes the Neo4j port: {published}"
                )
        # The bolt port may appear nowhere in either file but the
        # LIMES_NEO4J_URI value.
        for line_number, line in enumerate(text.splitlines(), start=1):
            if NEO4J_BOLT_PORT in line and "LIMES_NEO4J_URI" not in line:
                raise AssertionError(f"{path}:{line_number}: stray Neo4j port: {line.strip()}")


def test_ac34_override_adds_no_publication():
    override = _load(OVERRIDE)
    assert "ui" not in override["services"]
    assert all(not service.get("ports") for service in override["services"].values())
