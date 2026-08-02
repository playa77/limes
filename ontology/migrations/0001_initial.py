# ontology/migrations/0001_initial.py | v1.0.0 | introduced by WP-31
"""Migration 0001 — the initial version; a no-op that establishes the pattern.

Migrations are numbered, run in order, and each rewrites the version stamp
(`ontology_version`) on the nodes and edges a breaking ontology change
affects. `limes migrate --ontology-version <v>` (src/limes/cli/migrate.py)
loads the script whose `TO_VERSION` equals the target version and calls its
`upgrade(driver)`. `TO_VERSION` is the ontology version the migration
brings the graph *to*.

For 1.0.0 — the initial artifact — there is nothing to rewrite: every
stamp the loader wrote is already 1.0.0. A future breaking migration
(e.g. a relation split, a type removal) rewrites stamps here, in one
transaction, and bumps `TO_VERSION` accordingly.
"""

from __future__ import annotations

from limes.graph.driver import GraphDriver

# The ontology version this migration migrates the graph to (Doc 1 §9.6).
TO_VERSION = "1.0.0"


def upgrade(driver: GraphDriver) -> None:
    """No-op for the initial version.

    The loader stamps every node and relationship it writes with the
    loaded ontology's version, so a graph that only ever saw 1.0.0 has
    nothing to rewrite. A future migration rewrites `ontology_version` on
    the affected labels and relationship types here.
    """
    return None
