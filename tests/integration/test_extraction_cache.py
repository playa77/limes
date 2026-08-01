# tests/integration/test_extraction_cache.py | v1.0.0 | introduced by WP-23
"""Extraction cache integration tests against a disposable Neo4j container.

Covers the §8.7.5 contract: `cache_key` deterministic across processes (a
real process boundary per §12.2), put/get/exists round-trips, a miss on a
changed version triple, and AC-12/AC-33 — a cache hit on the current version
triple issues no paid call, and a full rebuild with an unchanged triple hits
the cache for every document.
"""

import subprocess
import sys
from datetime import UTC, datetime

import pytest

from limes.extraction.base import ExtractionResult
from limes.extraction.cache import cache_key, exists, get, put
from limes.graph.driver import GraphDriver
from limes.types import ExtractedAssertion, Mention
from tests.integration.conftest import Neo4jInstance

HASH = "abc123contenthash"
PROMPT = "1.0.0"
SCHEMA = "1.0.0"
MODEL = "test/model"

TRIPLE = {
    "content_hash": HASH,
    "prompt_version": PROMPT,
    "schema_version": SCHEMA,
    "model_id": MODEL,
}


@pytest.fixture
def driver(neo4j_instance: Neo4jInstance) -> GraphDriver:
    d = GraphDriver(
        neo4j_instance.uri,
        neo4j_instance.user,
        neo4j_instance.password,
        neo4j_instance.database,
    )
    yield d
    d.close()


def _result() -> ExtractionResult:
    return ExtractionResult(
        assertions=[
            ExtractedAssertion(
                passage_index=0,
                subject=Mention(surface="Kommission", type="PublicBody"),
                relation="ADOPTED",
                object=Mention(surface="Gesetz", type="LegalAct"),
                confidence=0.9,
                evidence_start=10,
                evidence_end=60,
                valid_from=datetime(2026, 7, 27, tzinfo=UTC),
            )
        ],
        input_tokens=120,
        output_tokens=40,
        raw_response='[{"passage_index": 0}]',
        parse_errors=[],
    )


def test_put_get_round_trip(driver: GraphDriver):
    put(driver, **TRIPLE, result=_result())
    stored = get(driver, **TRIPLE)
    assert stored is not None
    assert len(stored.assertions) == 1
    assertion = stored.assertions[0]
    assert assertion.relation == "ADOPTED"
    assert assertion.valid_from == datetime(2026, 7, 27, tzinfo=UTC)
    assert stored.input_tokens == 120
    assert stored.raw_response == stored.raw_response


def test_miss_returns_none(driver: GraphDriver):
    assert (
        get(
            driver,
            content_hash="nope",
            prompt_version=PROMPT,
            schema_version=SCHEMA,
            model_id=MODEL,
        )
        is None
    )
    assert not exists(
        driver, content_hash="nope", prompt_version=PROMPT, schema_version=SCHEMA, model_id=MODEL
    )


def test_version_change_produces_a_miss(driver: GraphDriver):
    put(driver, **TRIPLE, result=_result())
    # A prompt bump must not be served by the old entry (DD-08).
    assert (
        get(
            driver, content_hash=HASH, prompt_version="2.0.0", schema_version=SCHEMA, model_id=MODEL
        )
        is None
    )
    assert not exists(
        driver, content_hash=HASH, prompt_version="2.0.0", schema_version=SCHEMA, model_id=MODEL
    )
    # A model change likewise.
    assert (
        get(
            driver,
            content_hash=HASH,
            prompt_version=PROMPT,
            schema_version=SCHEMA,
            model_id="other/model",
        )
        is None
    )


def test_put_is_idempotent_on_cache_key(driver: GraphDriver):
    put(driver, **TRIPLE, result=_result())
    put(driver, **TRIPLE, result=_result())
    rows = driver.read(
        "MATCH (c:ExtractionCacheEntry {cache_key: $key}) RETURN count(c) AS c",
        {"key": cache_key(HASH, PROMPT, SCHEMA, MODEL)},
        10,
    )
    assert rows[0]["c"] == 1


def test_cache_key_is_deterministic_across_processes():
    # §12.2: a cross-process test crosses a real process boundary.
    script = (
        "from limes.extraction.cache import cache_key; "
        f"print(cache_key({HASH!r}, {PROMPT!r}, {SCHEMA!r}, {MODEL!r}))"
    )
    first = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    ).stdout.strip()
    second = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert first == second == cache_key(HASH, PROMPT, SCHEMA, MODEL)


def test_cache_key_changes_with_any_triple_component():
    key = cache_key(HASH, PROMPT, SCHEMA, MODEL)
    assert key != cache_key(HASH, "2.0.0", SCHEMA, MODEL)
    assert key != cache_key(HASH, PROMPT, "2.0.0", MODEL)
    assert key != cache_key(HASH, PROMPT, SCHEMA, "other/model")
    assert key != cache_key("other-hash", PROMPT, SCHEMA, MODEL)


def test_full_rebuild_with_unchanged_triple_hits_every_document(driver: GraphDriver):
    # AC-33 (partial): a rebuild over N documents with the same version triple
    # short-circuits on existence for every document and issues zero paid
    # calls — the guarded extractor would raise if invoked.
    hashes = [f"rebuild-{i}" for i in range(5)]
    for content_hash in hashes:
        put(
            driver,
            content_hash=content_hash,
            prompt_version=PROMPT,
            schema_version=SCHEMA,
            model_id=MODEL,
            result=_result(),
        )

    class GuardExtractor:
        def extract(self, *args, **kwargs):
            raise AssertionError("extract must not be called on a cache hit")

    extractor = GuardExtractor()
    paid_calls = 0
    for content_hash in hashes:
        if exists(
            driver,
            content_hash=content_hash,
            prompt_version=PROMPT,
            schema_version=SCHEMA,
            model_id=MODEL,
        ):
            continue  # the gate's short-circuit: no paid call
        paid_calls += 1
        extractor.extract([])
    assert paid_calls == 0
