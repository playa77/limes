# src/limes/coverage/report.py | v1.0.0 | introduced by WP-34
"""The coverage report per Technical Specification §8.11: attached to every
query result. It answers the two questions a result raises — which sources
contributed these edges, and how fresh is each contributing source — with
graph-wide per-relation counts that the UI renders as-is (AC-23).

The report reads only: relation counts, distinct contributing `source_id`s
from the edges themselves (never from `:Source` — a source that wrote edges
but never closed a run would otherwise vanish), and the contributing
sources' `:Source.last_success_at` refresh stamps.
"""

from __future__ import annotations

from datetime import datetime

from limes.api.models import CoverageReport, native_datetime
from limes.graph.driver import GraphDriver

_RELATION_COUNTS = """
MATCH ()-[r]->()
WHERE type(r) IN $types
RETURN type(r) AS relation, count(*) AS count
"""

_CONTRIBUTING_SOURCES = """
MATCH ()-[r]->()
WHERE type(r) IN $types
RETURN DISTINCT r.source_id AS source_id
"""

_SOURCE_REFRESH = """
MATCH (s:Source)
WHERE s.source_id IN $ids
RETURN s.source_id AS source_id, s.last_success_at AS last_success_at
"""


def report_for_relations(driver: GraphDriver, relation_types: list[str]) -> CoverageReport:
    """The coverage report for a set of relation types. Empty input yields
    an empty report — a query involving no relationships has no coverage to
    claim."""
    if not relation_types:
        return CoverageReport()

    counts: dict[str, int] = {}
    for row in driver.read(_RELATION_COUNTS, {"types": relation_types}, 30):
        counts[str(row["relation"])] = int(row["count"])
    sources = [
        str(row["source_id"])
        for row in driver.read(_CONTRIBUTING_SOURCES, {"types": relation_types}, 30)
    ]
    refresh: dict[str, datetime | None] = {}
    if sources:
        for row in driver.read(_SOURCE_REFRESH, {"ids": sources}, 30):
            last = native_datetime(row["last_success_at"])
            refresh[str(row["source_id"])] = last if last is not None else None
    return CoverageReport(
        relation_counts=counts,
        contributing_sources=sources,
        source_refresh=refresh,
    )
