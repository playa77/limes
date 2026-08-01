# src/limes/extraction/cache.py | v1.0.0 | introduced by WP-23
"""The extraction cache per Technical Specification §8.7.5, §5.8, DD-08.

Stores extraction results as `:ExtractionCacheEntry` nodes keyed by
`cache_key = SHA-256(content_hash | prompt_version | schema_version |
model_id)`. The version triple is part of the key, so a prompt, schema, or
model change invalidates nothing automatically — the next ingest re-extracts
only new content (Doc 1 §9.4). A hit costs nothing and is what makes a full
rebuild from the archive free while the triple is unchanged (AC-12, AC-33).

The cache is the sole writer of `:ExtractionCacheEntry` (§15.2). `exists` is
the zero-cost short-circuit the gate calls (WP-24 `idempotency.py`); `get`
deserializes for the pipeline run; `put` writes the serialized
`ExtractionResult`. The cache key is a pure function of its inputs, so it is
deterministic across processes — the test crosses a real process boundary to
prove it.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import structlog

from limes.extraction.base import ExtractionResult
from limes.graph.driver import GraphDriver

logger = structlog.get_logger(__name__)

_CACHE_READ = """
MATCH (c:ExtractionCacheEntry {cache_key: $cache_key})
RETURN c.result_json AS result_json
"""

_CACHE_EXISTS = """
MATCH (c:ExtractionCacheEntry {cache_key: $cache_key})
RETURN count(c) > 0 AS exists
"""

_CACHE_WRITE = """
MERGE (c:ExtractionCacheEntry {cache_key: $cache_key})
SET c.content_hash = $content_hash,
    c.prompt_version = $prompt_version,
    c.schema_version = $schema_version,
    c.model_id = $model_id,
    c.result_json = $result_json,
    c.created_at = $created_at
"""


def cache_key(content_hash: str, prompt_version: str, schema_version: str, model_id: str) -> str:
    """The cache key: SHA-256 over the four key components joined with a
    separator. Pure and deterministic — the same inputs in any process yield
    the same key, which is what makes the cache serve across CLI invocations
    (C-07)."""
    material = "|".join([content_hash, prompt_version, schema_version, model_id])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def get(
    driver: GraphDriver,
    content_hash: str,
    prompt_version: str,
    schema_version: str,
    model_id: str,
) -> ExtractionResult | None:
    """The stored `ExtractionResult` for a key, or None on a miss. A miss is
    not an error — it is the normal first-ingest path."""
    rows = driver.read(
        _CACHE_READ,
        {"cache_key": cache_key(content_hash, prompt_version, schema_version, model_id)},
        timeout_s=30,
    )
    if not rows or not rows[0].get("result_json"):
        return None
    try:
        return ExtractionResult.model_validate_json(str(rows[0]["result_json"]))
    except ValueError as exc:
        logger.warning(
            "extraction cache entry unparsable; treated as a miss",
            content_hash=content_hash,
            reason=str(exc),
        )
        return None


def put(
    driver: GraphDriver,
    content_hash: str,
    prompt_version: str,
    schema_version: str,
    model_id: str,
    result: ExtractionResult,
) -> None:
    """Store a result under the key. `MERGE` on the unique `cache_key`
    (constraint from §5.3) makes a retried transaction idempotent — a
    re-extract with an unchanged triple overwrites nothing new."""
    key = cache_key(content_hash, prompt_version, schema_version, model_id)
    driver.write_batch(
        [
            (
                _CACHE_WRITE,
                {
                    "cache_key": key,
                    "content_hash": content_hash,
                    "prompt_version": prompt_version,
                    "schema_version": schema_version,
                    "model_id": model_id,
                    "result_json": result.model_dump_json(),
                    "created_at": datetime.now(UTC),
                },
            )
        ]
    )
    logger.info(
        "extraction cache written",
        content_hash=content_hash,
        prompt_version=prompt_version,
        schema_version=schema_version,
        model_id=model_id,
        assertions=len(result.assertions),
    )


def exists(
    driver: GraphDriver,
    content_hash: str,
    prompt_version: str,
    schema_version: str,
    model_id: str,
) -> bool:
    """True when an entry exists under the key — the zero-cost short-circuit:
    existence is checked without deserializing the stored result."""
    rows = driver.read(
        _CACHE_EXISTS,
        {"cache_key": cache_key(content_hash, prompt_version, schema_version, model_id)},
        timeout_s=30,
    )
    return bool(rows) and bool(rows[0].get("exists"))
