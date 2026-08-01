# src/limes/graph/embeddings.py | v1.0.0 | introduced by WP-25a
"""Embedding vector normalization per Technical Specification §5.3, §5.6.

The `entity_label_embedding` vector index declares cosine similarity; the
scores `db.index.vector.queryNodes` returns are only meaningful when the
indexed vectors are comparable on that metric. `normalize_embedding` is the
single place the write-side contract is enforced: unit L2 norm so the cosine
score is valid regardless of the embedder's conventions (the amendment
authorized by the WP-25 seam conflict resolution — the merge stamp owns
`label_embedding`, and it normalizes what it stamps).

The dimension check is optional because the loader does not know the declared
dimension (`LIMES_EMBEDDING_DIMENSIONS` lives in Settings, which the loader
never sees); the embedder's caller — the composition root wiring, WP-26 — is
where the dimension contract is enforced. The loader calls this function
without dimensions, defensively normalizing whatever the embedder returns.
"""

from __future__ import annotations

import math


def normalize_embedding(vector: list[float], dimensions: int | None = None) -> list[float]:
    """Return `vector` scaled to unit L2 norm.

    Raises `ValueError` when `dimensions` is given and the vector length
    differs — a wrong-dimension vector would be silently unindexable — and
    for a zero vector, which cannot be normalized and indicates a broken
    embedder rather than a legitimate embedding.
    """
    if dimensions is not None and len(vector) != dimensions:
        raise ValueError(
            f"embedding dimension {len(vector)} does not match declared dimension {dimensions}"
        )
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0.0:
        raise ValueError("cannot normalize a zero embedding vector")
    return [v / norm for v in vector]
