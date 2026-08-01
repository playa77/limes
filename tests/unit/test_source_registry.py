# tests/unit/test_source_registry.py | v1.0.0 | introduced by WP-09
"""Source registry tests per Doc 2 §8.5.1.

`get` on an unknown source raises `SourceFetchError` naming both the unknown
and the registered ones (AC-38); `build_default_registry` is the authoritative
source set — after the phase it holds the eleven phase-2 adapters from the
source table (§8.5.2), and no other module constructs a registry.
"""

import pytest

from limes.errors import SourceFetchError
from limes.sources.base import SourceAdapter
from limes.sources.registry import SourceRegistry, build_default_registry


class _DummyAdapter:
    source_id = "dummy"
    name = "Dummy"
    kind = "structured"
    trust_rank = 1.0
    supports_backfill = True
    supports_incremental = True

    def fetch(self, since, until):
        return iter(())

    def normalize(self, record):
        raise NotImplementedError


def test_register_and_get_roundtrip():
    registry = SourceRegistry()
    registry.register(_DummyAdapter())
    assert isinstance(registry.get("dummy"), SourceAdapter)
    assert registry.trust_rank("dummy") == 1.0


def test_duplicate_registration_fails_fast():
    registry = SourceRegistry()
    registry.register(_DummyAdapter())
    with pytest.raises(ValueError, match="already registered"):
        registry.register(_DummyAdapter())


def test_get_unknown_source_names_both_unknown_and_registered():
    registry = SourceRegistry()
    registry.register(_DummyAdapter())
    with pytest.raises(SourceFetchError) as excinfo:
        registry.get("nope")
    message = str(excinfo.value)
    assert "nope" in message
    assert "dummy" in message


def test_get_unknown_source_on_empty_registry():
    registry = SourceRegistry()
    with pytest.raises(SourceFetchError) as excinfo:
        registry.get("anything")
    assert "(none)" in str(excinfo.value)


def test_trust_rank_unknown_source_raises():
    registry = SourceRegistry()
    with pytest.raises(SourceFetchError):
        registry.trust_rank("missing")


def test_source_ids_sorted():
    registry = SourceRegistry()
    registry.register(_DummyAdapter())

    class AlphaAdapter(_DummyAdapter):
        source_id = "alpha"

    registry.register(AlphaAdapter())
    assert registry.source_ids() == ["alpha", "dummy"]


def test_build_default_registry_contains_phase_two_sources():
    registry = build_default_registry()
    expected = {
        "bundestag_dip",
        "eurlex",
        "fsd",
        "gesetze_im_internet",
        "gisco_nuts",
        "gleif",
        "offeneregister",
        "osm",
        "ted",
        "transparency_register",
        "wikidata",
    }
    assert set(registry.source_ids()) == expected


def test_build_default_registry_trust_ranks_match_source_table():
    registry = build_default_registry()
    assert registry.trust_rank("gisco_nuts") == 1.00
    assert registry.trust_rank("gleif") == 1.00
    assert registry.trust_rank("wikidata") == 0.90
    assert registry.trust_rank("osm") == 0.75
    assert registry.trust_rank("offeneregister") == 0.30


def test_registry_get_is_the_only_public_construction_path():
    # Import-time self-registration is rejected (§8.5.1): importing every
    # adapter module must not register anything anywhere.
    import importlib

    for module_name in (
        "limes.sources.gisco_nuts",
        "limes.sources.gleif",
        "limes.sources.eurlex",
        "limes.sources.fsd",
        "limes.sources.ted",
        "limes.sources.transparency_register",
        "limes.sources.bundestag_dip",
        "limes.sources.gesetze_im_internet",
        "limes.sources.wikidata",
        "limes.sources.osm",
        "limes.sources.offeneregister",
    ):
        module = importlib.import_module(module_name)
        for attribute_name in dir(module):
            if isinstance(getattr(module, attribute_name), SourceRegistry):
                pytest.fail(f"{module_name} self-registers at import time")
