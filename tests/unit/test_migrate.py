# tests/unit/test_migrate.py | v1.0.0 | introduced by WP-31
"""Migration CLI unit tests per Doc 2 §8.14 and Doc 1 §9.6.

The version-routing logic (fresh / already-at-target / downgrade / additive
/ breaking) is exercised against a stub driver whose answers model the
graph's stamped versions — the routing is the code under test. The
fresh-database no-op and the already-at-target path against the real
container live in tests/integration/test_cli_migrate.py (G10).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from limes.cli.migrate import _migrate, _version_tuple
from limes.errors import LimesError


class _StubDriver:
    """A driver whose read answers model the stamped graph: node and edge
    max versions plus the affected counts of the target version."""

    def __init__(
        self,
        node_stamp: str | None = None,
        edge_stamp: str | None = None,
        affected: tuple[int, int] = (3, 2),
    ) -> None:
        self._node_stamp = node_stamp
        self._edge_stamp = edge_stamp
        self._affected = affected
        self.upgraded = False

    def read(self, cypher: str, params: dict, timeout_s: int) -> list[dict]:
        if "RETURN max(n.ontology_version) AS max_version" in cypher:
            return [{"max_version": self._node_stamp}]
        if "RETURN max(r.ontology_version) AS max_version" in cypher:
            return [{"max_version": self._edge_stamp}]
        if "count(n) AS affected" in cypher:
            return [{"affected": self._affected[0]}]
        if "count(r) AS affected" in cypher:
            return [{"affected": self._affected[1]}]
        return []

    def write_batch(self, statements: list[tuple[str, dict]]) -> None:
        pass


def _migrations_dir(tmp_path: Path, script: str, to_version: str) -> Path:
    """A tmp migrations directory with one migration for `to_version`,
    whose upgrade records the call on the driver."""
    migrations = tmp_path / "ontology" / "migrations"
    migrations.mkdir(parents=True)
    (migrations / f"{script}.py").write_text(
        f'TO_VERSION = "{to_version}"\n\ndef upgrade(driver):\n    driver.upgraded = True\n',
        encoding="utf-8",
    )
    return migrations


def test_version_tuple_parses_and_rejects():
    assert _version_tuple("1.0.0") == (1, 0, 0)
    assert _version_tuple("2.10.3") == (2, 10, 3)
    with pytest.raises(LimesError):
        _version_tuple("1.0")
    with pytest.raises(LimesError):
        _version_tuple("a.b.c")


def test_fresh_database_needs_no_migration(capsys):
    driver = _StubDriver(node_stamp=None, edge_stamp=None)
    _migrate(driver, Path("/x/ontology.yaml"), "1.0.0", "1.0.0")
    assert "nothing to migrate" in capsys.readouterr().out
    assert driver.upgraded is False


def test_already_at_target_is_a_no_op(capsys):
    driver = _StubDriver(node_stamp="1.0.0", edge_stamp="1.0.0")
    _migrate(driver, Path("/x/ontology.yaml"), "1.0.0", "1.0.0")
    assert "already at 1.0.0" in capsys.readouterr().out
    assert driver.upgraded is False


def test_downgrade_is_refused():
    # The artifact matches the requested version, but the graph is stamped
    # newer — the §4.3 direction, re-checked over both stamp surfaces.
    driver = _StubDriver(node_stamp="1.0.0", edge_stamp="1.0.0")
    with pytest.raises(LimesError, match="downgrade refused"):
        _migrate(driver, Path("/x/ontology.yaml"), "0.9.0", "0.9.0")


def test_additive_change_needs_no_migration(capsys):
    driver = _StubDriver(node_stamp="1.0.0", edge_stamp="1.0.0")
    _migrate(driver, Path("/x/ontology.yaml"), "1.1.0", "1.1.0")
    assert "additive change" in capsys.readouterr().out
    assert driver.upgraded is False


def test_breaking_change_runs_the_migration_for_the_target(tmp_path, capsys):
    migrations = _migrations_dir(tmp_path, "0002_breaking", "2.0.0")
    driver = _StubDriver(node_stamp="1.0.0", edge_stamp="1.0.0", affected=(5, 7))
    ontology_yaml = migrations.parent / "ontology.yaml"
    _migrate(driver, ontology_yaml, "2.0.0", "2.0.0")
    out = capsys.readouterr().out
    assert driver.upgraded is True
    assert "0002_breaking" in out
    assert "affected nodes 5 -> 5" in out  # the no-op stamp script reports before/after


def test_breaking_change_without_a_migration_fails_loudly(tmp_path):
    migrations = _migrations_dir(tmp_path, "0002_breaking", "2.0.0")
    driver = _StubDriver(node_stamp="1.0.0", edge_stamp="1.0.0")
    ontology_yaml = migrations.parent / "ontology.yaml"
    with pytest.raises(LimesError, match="no migration found"):
        _migrate(driver, ontology_yaml, "2.1.0", "2.1.0")


def test_artifact_version_mismatch_is_refused():
    driver = _StubDriver(node_stamp=None, edge_stamp=None)
    with pytest.raises(LimesError, match="not the requested"):
        _migrate(driver, Path("/x/ontology.yaml"), "1.0.0", "2.0.0")


def test_max_stamped_version_reads_both_surfaces():
    # An edge-only stamp must be seen even when no node carries one — the
    # CLI reads both surfaces where §4.3's guard reads nodes only.
    from limes.cli.migrate import _max_stamped_version

    driver = _StubDriver(node_stamp=None, edge_stamp="1.0.0")
    assert _max_stamped_version(driver) == "1.0.0"
    driver = _StubDriver(node_stamp="1.2.0", edge_stamp="1.0.0")
    assert _max_stamped_version(driver) == "1.2.0"
    driver = _StubDriver(node_stamp=None, edge_stamp=None)
    assert _max_stamped_version(driver) is None


def test_migrate_command_wires_the_typer_option():
    # The command's required option is the §8.14 surface: missing
    # --ontology-version is a usage error before any code runs.
    from typer.testing import CliRunner

    from limes.cli.main import app

    result = CliRunner().invoke(app, ["migrate"])
    assert result.exit_code != 0
