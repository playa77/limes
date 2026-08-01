# src/limes/resolution/blocking.py | v1.0.0 | introduced by WP-25
"""Embedding and candidate retrieval per Technical Specification §8.8.2.

`embed` turns mention text into vectors: the surface plus the inferred type
plus one contextual qualifier, embedded through the OpenRouter client with a
permanent cache keyed by text and model, and L2-normalized — the same
contract the §5.6 merge stamp honors, because the §5.3 index declares cosine
and a query vector and an indexed vector must be comparable on that metric
(the dimension contract of WP-25a).

`candidates` queries the vector index for the nearest entities of a type
and returns them with their cosine scores. The resolver is read-only against
the index: the index is populated by the loader's merge stamp and the one-shot
backfill (WP-25a), never by this module (Doc 2 §8.8.3).

The pre-filter count `k` exceeds the limit so the type filter has room: the
index query itself cannot filter by label, so `k = limit * 5` rows are
retrieved and the label predicate narrows them. A small graph spends a cheap
round trip; a large one stays proportional.
"""

from __future__ import annotations

from limes.errors import ExtractionError
from limes.extraction.openrouter_client import OpenRouterClient
from limes.graph.driver import GraphDriver
from limes.graph.embeddings import normalize_embedding

# The vector index created by §5.3 provisioning; its name is fixed by the
# schema module's DDL.
ENTITY_EMBEDDING_INDEX = "entity_label_embedding"

# How many raw nearest neighbors the index query retrieves before the type
# filter narrows them: `limit` results are returned after filtering, so the
# pre-filter count must leave room for other types in the neighborhood.
FILTER_FACTOR = 5

# (model_id, text) -> normalized embedding. "Permanent" per §8.8.2 in the
# sense that matters: it lives for the process, so a mention embedded once
# is never embedded again within one run. Cross-process persistence would
# need a node type §15.2 does not register, so it is deliberately absent.
_EMBED_CACHE: dict[tuple[str, str], list[float]] = {}

CANDIDATES_QUERY = """
CALL db.index.vector.queryNodes($index, $k, $query_vector) YIELD node, score
WHERE node:{entity_type} AND node.entity_id IS NOT NULL
RETURN node.entity_id AS entity_id, node.label AS label, score
ORDER BY score DESC
LIMIT $limit
""".strip()


def embed(
    texts: list[str],
    client: OpenRouterClient,
    model_id: str,
    dimensions: int | None = None,
) -> list[list[float]]:
    """Embed `texts` through the client, cached per (model, text) and
    L2-normalized.

    `dimensions`, when given, verifies the provider's vectors against the
    declared `LIMES_EMBEDDING_DIMENSIONS` — a mismatch would make the index
    query fail obscurely at best and silently drop candidates at worst. A
    zero vector or a wrong response length raises `ExtractionError`.
    """
    missing: list[tuple[int, str]] = [
        (index, text) for index, text in enumerate(texts) if (model_id, text) not in _EMBED_CACHE
    ]
    if missing:
        vectors = client.embed([text for _, text in missing], model_id)
        if len(vectors) != len(missing):
            raise ExtractionError(
                f"embedding call returned {len(vectors)} vectors for {len(missing)} texts"
            )
        for (_, text), vector in zip(missing, vectors, strict=True):
            try:
                _EMBED_CACHE[(model_id, text)] = normalize_embedding(vector, dimensions)
            except ValueError as exc:
                raise ExtractionError(f"embedding call returned an unusable vector: {exc}") from exc
    return [_EMBED_CACHE[(model_id, text)] for text in texts]


def candidates(
    driver: GraphDriver,
    embedding: list[float],
    entity_type: str,
    limit: int,
) -> list[dict[str, str | float]]:
    """The nearest `limit` entities of `entity_type` by cosine similarity,
    as `{"entity_id", "label", "score"}` dicts sorted by score descending,
    with `score` in cosine space.

    `entity_type` is a concrete ontology type — the mention's validated
    type, which the extractor already bounded against the ontology — and is
    interpolated into the label predicate; the label segment is never built
    from source data. An empty index yields an empty list, which the caller
    routes to minting.

    The engine's cosine index reports `(1 + cosine) / 2` — its cosine
    distance is defined as the half-angle `(1 - cos) / 2` — so the raw score
    is converted back to cosine space here. The §8.8.3 thresholds are
    cosines; an unconverted score would auto-link at a true cosine of only
    0.86. The conversion is linear, so the candidate ordering is unchanged.
    """
    rows = driver.read(
        CANDIDATES_QUERY.format(entity_type=entity_type),
        {
            "index": ENTITY_EMBEDDING_INDEX,
            "k": max(limit * FILTER_FACTOR, limit + 1),
            "query_vector": embedding,
            "limit": limit,
        },
        60,
    )
    return [
        {
            "entity_id": str(row["entity_id"]),
            "label": str(row["label"]),
            "score": 2.0 * float(row["score"]) - 1.0,
        }
        for row in rows
        if row.get("entity_id") is not None
    ]
