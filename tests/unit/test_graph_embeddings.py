# tests/unit/test_graph_embeddings.py | v1.0.0 | introduced by WP-25a
"""Unit tests for the §5.3/§5.6 embedding normalization contract (WP-25a).

The vector index declares cosine similarity; `normalize_embedding` is the
single place the write side of that contract is enforced. Wrong-dimension
and zero vectors fail loudly — an unnormalized or wrong-length embedding
would silently under-recall in `db.index.vector.queryNodes`, reproducing
the duplication trap the merge stamp exists to prevent.
"""

import math

import pytest

from limes.graph.embeddings import normalize_embedding


def test_normalize_scales_to_unit_norm():
    vector = normalize_embedding([3.0, 4.0])
    assert vector == pytest.approx([0.6, 0.8])
    norm = math.sqrt(sum(v * v for v in vector))
    assert norm == pytest.approx(1.0)


def test_normalize_is_idempotent():
    first = normalize_embedding([1.0, 2.0, 3.0])
    assert normalize_embedding(first) == pytest.approx(first)


def test_normalize_preserves_sign_and_relative_magnitudes():
    vector = normalize_embedding([-2.0, 1.0])
    assert vector[0] < 0.0
    assert abs(vector[0]) > abs(vector[1])


def test_normalize_rejects_wrong_dimension_when_declared():
    with pytest.raises(ValueError, match="dimension"):
        normalize_embedding([1.0, 2.0, 3.0], dimensions=4)


def test_normalize_accepts_any_length_without_declared_dimension():
    # The loader normalizes defensively without knowing
    # LIMES_EMBEDDING_DIMENSIONS; the dimension contract is enforced by the
    # embedder's caller (the composition wiring).
    assert len(normalize_embedding([1.0] * 7)) == 7


def test_normalize_rejects_zero_vector():
    with pytest.raises(ValueError, match="zero"):
        normalize_embedding([0.0, 0.0, 0.0])
