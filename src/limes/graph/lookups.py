# src/limes/graph/lookups.py | v1.0.0 | introduced by WP-08
"""Cross-process reference-data reads per Technical Specification §8.16.

`postal_code_to_nuts` answers postal-code → NUTS correspondence from
`:PostalCode` nodes that a previous CLI invocation wrote (C-07, DD-20): the
correspondence is produced by one process and consumed by three others, so it
lives in the graph, never in module state or a derived file. The in-process
LRU cache is explicitly *not* that cross-process state — it only saves graph
round trips within one process. A miss returns `None`; the caller leaves the
field unassigned and counts it, never guessing and never blocking.
"""

from __future__ import annotations

from collections import OrderedDict

from limes.graph.driver import GraphDriver

_QUERY = """
MATCH (p:PostalCode {country_code: $cc, postal_code: $pc})
RETURN p.nuts_code AS nuts
"""

_CACHE_SIZE = 4096
_cache: OrderedDict[tuple[str, str], str | None] = OrderedDict()


def postal_code_to_nuts(
    driver: GraphDriver, country_code: str, postal_code: str
) -> str | None:
    """The NUTS code for a postal code, or `None` when the correspondence is
    not in the graph. Misses are cached too: a code known to be absent is not
    re-queried. The cache key is the code pair, not the driver — one driver
    per process (composition root), so a stale entry across databases cannot
    occur."""
    key = (country_code, postal_code)
    cached = _cache.get(key)
    if key in _cache:
        _cache.move_to_end(key)
        return cached

    rows = driver.read(_QUERY, {"cc": country_code, "pc": postal_code}, timeout_s=30)
    nuts: str | None = rows[0]["nuts"] if rows else None
    _cache[key] = nuts
    _cache.move_to_end(key)
    if len(_cache) > _CACHE_SIZE:
        _cache.popitem(last=False)
    return nuts


def clear_cache() -> None:
    """Drop the in-process cache; used by tests, never by production code."""
    _cache.clear()
