# tests/fixtures/embeddings.py | v1.0.0 | introduced by WP-25a
"""Deterministic fake embedder for tests exercising the §5.6
`label_embedding` merge stamp and the resolution candidate index.

The test container provisions the vector index with
`LIMES_EMBEDDING_DIMENSIONS` (1024) and cosine similarity, so the fake
emits normalized 1024-dimensional vectors. The vector is a pure function of
the label (`random.Random(label)`): two test runs agree on a label's
embedding, so a test can compute an entity's expected embedding before the
loader stamps it and construct a query vector with a controlled cosine
against it (`vector_with_cosines`).
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable

from limes.graph.embeddings import normalize_embedding

TEST_EMBEDDING_DIMENSIONS = 1024


def fake_embedder(
    dimensions: int = TEST_EMBEDDING_DIMENSIONS,
) -> Callable[[list[str]], list[list[float]]]:
    """An embedder whose output is deterministic per label and index-ready:
    exactly `dimensions` floats, L2-normalized."""

    def embed(texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            rng = random.Random(f"limes-test:{text}")
            vector = [rng.uniform(-1.0, 1.0) for _ in range(dimensions)]
            vectors.append(normalize_embedding(vector, dimensions))
        return vectors

    return embed


def expected_vector(label: str, dimensions: int = TEST_EMBEDDING_DIMENSIONS) -> list[float]:
    """The embedding `fake_embedder` produces for `label` — the value the
    loader stamps for an entity with that label."""
    return fake_embedder(dimensions)([label])[0]


def vector_with_cosines(
    targets: list[tuple[list[float], float]],
) -> list[float]:
    """A unit vector whose cosine with each target equals the requested
    value.

    With one target: a rotation of the target into a perpendicular plane
    (exact). With two: the exact construction in the targets' span — the
    second cosine is determined by the geometry
    `c2 = c1·g ± sqrt((1−c1²)(1−g²))` with `g = e1·e2`, and the sign is
    chosen so that |q| = 1 holds exactly. Used to place a mention embedding
    in a specific §8.8.3 band against known entity embeddings.
    """
    if len(targets) == 1:
        (e, c) = targets[0]
        assert len(e) == TEST_EMBEDDING_DIMENSIONS
        assert abs(c) <= 1.0
        rng = random.Random("limes-perp")
        perp = [rng.uniform(-1.0, 1.0) for _ in range(len(e))]
        dot = sum(a * b for a, b in zip(perp, e, strict=True))
        perp = [p - dot * ei for p, ei in zip(perp, e, strict=True)]
        perp = normalize_embedding(perp, len(e))
        q = [c * ei + math.sqrt(max(0.0, 1.0 - c * c)) * pi for ei, pi in zip(e, perp, strict=True)]
        return normalize_embedding(q, len(e))
    if len(targets) == 2:
        (e1, c1), (e2, _c2) = targets
        g = sum(a * b for a, b in zip(e1, e2, strict=True))
        assert abs(g) < 1.0 - 1e-9, "target embeddings must not be parallel"
        # |q| = c1^2 + a2^2 (1 - g^2) = 1  ->  a2 = ±sqrt((1-c1^2)/(1-g^2)).
        # The minus sign keeps the second cosine below the first, which is
        # the ordering the candidate list needs.
        a2 = -math.sqrt(max(0.0, (1.0 - c1 * c1) / (1.0 - g * g)))
        a1 = c1 - a2 * g
        q = [a1 * x + a2 * y for x, y in zip(e1, e2, strict=True)]
        return q  # unit norm by construction
    raise AssertionError("vector_with_cosines supports one or two targets")
