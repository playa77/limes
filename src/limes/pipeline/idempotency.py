# src/limes/pipeline/idempotency.py | v1.0.0 | introduced by WP-24
"""Content-hash deduplication per Technical Specification §8.6.3, DD-06.

`is_already_extracted` is the zero-cost short-circuit in front of every paid
extraction call: a document whose content hash is already in the extraction
cache under the current version triple is not extracted again. The check is
the gate's first step, before any spaCy model is loaded (§8.6.3).
"""

from __future__ import annotations

import structlog

from limes.extraction.cache import exists
from limes.graph.driver import GraphDriver

logger = structlog.get_logger(__name__)


def is_already_extracted(
    driver: GraphDriver,
    content_hash: str,
    prompt_version: str,
    schema_version: str,
    model_id: str,
) -> bool:
    """True when the document's content hash is cached under the current
    version triple. A hit means the document was extracted before under an
    identical prompt, schema, and model — re-extraction would be a paid
    no-op, so the gate short-circuits (AC-12)."""
    hit = exists(driver, content_hash, prompt_version, schema_version, model_id)
    if hit:
        logger.info(
            "document already extracted; cache hit",
            content_hash=content_hash,
            prompt_version=prompt_version,
            schema_version=schema_version,
            model_id=model_id,
        )
    return hit
