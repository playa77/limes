# src/limes/sources/registry.py | v1.0.0 | introduced by WP-09
"""Source registry per Technical Specification §8.5.1.

`build_default_registry` is the authoritative list of live sources — the only
place the ingestable source set is defined. Adding an adapter means adding one
import and one `register()` call here and nowhere else; import-time
self-registration is rejected because it makes the live source set answerable
only by listing a directory. Each adapter work package (WP-10…WP-21) adds
exactly one line here.

`get` on an unknown identifier raises `SourceFetchError` naming both the
unknown source and the registered ones (AC-38), so a misspelled source id in a
CLI invocation fails with the full menu, not with a bare error.
"""

from __future__ import annotations

import structlog

from limes.errors import SourceFetchError
from limes.sources.base import SourceAdapter

logger = structlog.get_logger(__name__)


class SourceRegistry:
    """A mutable set of adapters, keyed by `source_id`."""

    def __init__(self) -> None:
        self._adapters: dict[str, SourceAdapter] = {}

    def register(self, adapter: SourceAdapter) -> None:
        """Register an adapter. A duplicate `source_id` is a programming
        error, not a runtime condition, and fails fast."""
        if adapter.source_id in self._adapters:
            raise ValueError(f"source already registered: {adapter.source_id}")
        self._adapters[adapter.source_id] = adapter
        logger.info("source registered", source_id=adapter.source_id, name=adapter.name)

    def get(self, source_id: str) -> SourceAdapter:
        """The adapter for `source_id`, or `SourceFetchError` naming both the
        unknown source and the registered ones (AC-38)."""
        adapter = self._adapters.get(source_id)
        if adapter is None:
            registered = ", ".join(sorted(self._adapters)) or "(none)"
            raise SourceFetchError(
                f"unknown source '{source_id}'; registered sources: {registered}"
            )
        return adapter

    def source_ids(self) -> list[str]:
        """All registered source ids, sorted for stable output."""
        return sorted(self._adapters)

    def trust_rank(self, source_id: str) -> float:
        """The trust rank of a registered source (Doc 1 §5.8). Unknown
        sources raise like `get`."""
        return self.get(source_id).trust_rank


def build_default_registry() -> SourceRegistry:
    """The authoritative list of live sources (Doc 2 §8.5.1).

    The only place the ingestable source set is defined. One line per
    adapter; enrichment-only sources (Wikidata) are registered for the
    resolver but never run through `execute_run` — their `fetch` raises
    `NotImplementedError` (§8.5.2), and the CLI's `ingest-all` skips them.
    """
    registry = SourceRegistry()

    from limes.sources.bundestag_dip import BundestagDipAdapter

    registry.register(BundestagDipAdapter())

    from limes.sources.eurlex import EurlexAdapter

    registry.register(EurlexAdapter())

    from limes.sources.feeds import FeedsAdapter

    registry.register(FeedsAdapter())

    from limes.sources.fsd import FsdAdapter

    registry.register(FsdAdapter())

    from limes.sources.gdelt import GdeltAdapter

    registry.register(GdeltAdapter())

    from limes.sources.gesetze_im_internet import GesetzeImInternetAdapter

    registry.register(GesetzeImInternetAdapter())

    from limes.sources.gisco_nuts import GiscoNutsAdapter

    registry.register(GiscoNutsAdapter())

    from limes.sources.gleif import GleifAdapter

    registry.register(GleifAdapter())

    from limes.sources.offeneregister import OffeneRegisterAdapter

    registry.register(OffeneRegisterAdapter())

    from limes.sources.osm import OsmAdapter

    registry.register(OsmAdapter())

    from limes.sources.ted import TedAdapter

    registry.register(TedAdapter())

    from limes.sources.transparency_register import TransparencyRegisterAdapter

    registry.register(TransparencyRegisterAdapter())

    # Enrichment-only: exposes enrich() for the resolver; never ingestable.
    from limes.sources.wikidata import WikidataAdapter

    registry.register(WikidataAdapter())

    return registry
