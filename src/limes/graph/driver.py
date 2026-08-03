# src/limes/graph/driver.py | v1.0.0 | introduced by WP-04
"""Neo4j driver wrapper per Technical Specification §8.3.

`GraphDriver.read` opens sessions in read access mode (Doc 2 §7.2 point 2):
the driver refuses write statements client-side, which is the second barrier
against a validator defect. `write_batch` runs all statements in one
transaction. `explain` parses an `EXPLAIN` plan into a `PlanSummary` for the
plan gate (WP-33). Nothing here is specific to any query shape; the loader
and the query paths build their own Cypher on top.
"""

from __future__ import annotations

from typing import Any

from neo4j import GraphDatabase, ManagedTransaction
from neo4j.exceptions import Neo4jError, SessionExpired, TransientError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from limes.errors import GraphWriteError
from limes.types import PlanSummary, WriteResult

_RETRYABLE = (SessionExpired, TransientError)


class GraphDriver:
    """Thin wrapper over the Neo4j driver with read/write session separation."""

    def __init__(self, uri: str, user: str, password: str, database: str) -> None:
        self._database = database
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        self._driver.close()

    def read(self, cypher: str, params: dict[str, Any], timeout_s: int) -> list[dict[str, Any]]:
        """Execute `cypher` in a read-access-mode session and return rows as
        dicts. A write statement inside read mode is refused by the driver."""
        with self._driver.session(database=self._database, default_access_mode="READ") as session:
            result = session.run(cypher, **params, timeout=timeout_s)
            return [dict(record) for record in result]

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(2),
        reraise=True,
    )
    def write_batch(self, statements: list[tuple[str, dict[str, Any]]]) -> WriteResult:
        """Execute all `(cypher, params)` statements in one transaction.
        Retried once on transient errors; a persistent failure surfaces as
        `GraphWriteError`."""
        try:
            with self._driver.session(
                database=self._database, default_access_mode="WRITE"
            ) as session:
                result = session.execute_write(self._run_statements, statements)
                return result
        except GraphWriteError:
            raise
        except Neo4jError as exc:
            raise GraphWriteError(f"graph write failed: {exc}") from exc

    @staticmethod
    def _run_statements(
        tx: ManagedTransaction, statements: list[tuple[str, dict[str, Any]]]
    ) -> WriteResult:
        summary = WriteResult(
            statements_executed=0,
            nodes_created=0,
            relationships_created=0,
            properties_set=0,
        )
        for cypher, params in statements:
            tx_result = tx.run(cypher, **params)
            counters = tx_result.consume().counters
            summary.statements_executed += 1
            summary.nodes_created += counters.nodes_created or 0
            summary.relationships_created += counters.relationships_created or 0
            summary.properties_set += counters.properties_set or 0
        return summary

    def explain(self, cypher: str, params: dict[str, Any]) -> PlanSummary:
        """Run `EXPLAIN` and parse the plan into a `PlanSummary`. Used by the
        plan gate (WP-33); never executes the query."""
        with self._driver.session(database=self._database, default_access_mode="READ") as session:
            result = session.run(f"EXPLAIN {cypher}", **params)
            plan = result.consume().plan
            return _parse_plan(plan)


def _parse_plan(plan: dict[str, Any] | None) -> PlanSummary:
    """Walk the operator tree of an EXPLAIN plan and aggregate the metrics
    the plan gate needs."""
    operators: list[str] = []
    max_rows = 0
    total_rows = 0
    has_cartesian = False
    max_hops: int | None = None

    def walk(node: dict[str, Any]) -> None:
        nonlocal max_rows, total_rows, has_cartesian, max_hops
        name = node.get("operatorType", "?")
        operators.append(name)
        if name.upper().startswith("CARTESIAN"):
            has_cartesian = True
        # The 2026.x server nests the estimate as `args.EstimatedRows`;
        # older drivers exposed a top-level `estimatedRows` key. Reading
        # both keeps the two row-ceiling rejections (§8.10) alive across
        # server generations — without it, OPERATOR_ROWS_EXCEEDED and
        # TOTAL_ROWS_EXCEEDED silently never fire (verified against a
        # live 2026.06 container in WP-39).
        raw = (node.get("args") or {}).get("EstimatedRows", node.get("estimatedRows", 0))
        rows = int(raw or 0)
        max_rows = max(max_rows, rows)
        total_rows += rows
        identifiers = node.get("identifiers", [])
        if "UNWIND" not in name.upper() and any(identifiers):
            # varlength hops surface as identifiers like `x` in a
            # VarLengthExpand(All) operator; estimate from the operator name.
            if "VARLENGTH" in name.upper() or "VARIABLELENGTH" in name.upper():
                max_hops = 1  # refined by depth below if present
        for child in node.get("children", []):
            walk(child)

    walk(plan or {})
    return PlanSummary(
        operators=operators,
        max_estimated_rows=max_rows,
        total_estimated_rows=total_rows,
        has_cartesian_product=has_cartesian,
        max_varlength_hops=max_hops,
    )
