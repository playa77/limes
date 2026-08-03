# tests/unit/test_composition.py | v1.0.0 | introduced by WP-26
"""Composition-root unit tests per Doc 2 §8.15.

The construction paths are covered by the integration suite
(test_composition_root.py); these tests pin the embedder wiring (D-26):
the dimension-checked, normalized callable the loader stamps node
embeddings with, and its length-mismatch guard.
"""

from pathlib import Path

import pytest

from limes.composition import embedder_for
from limes.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]


def _settings(**overrides) -> Settings:
    base = dict(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="u",
        neo4j_password="p",
        ontology_path=REPO_ROOT / "ontology" / "ontology.yaml",
        feeds_config_path=REPO_ROOT / "ontology" / "feeds.yaml",
        gold_set_path=REPO_ROOT / "gold_set" / "gold_set.jsonl",
        baseline_path=REPO_ROOT / "gold_set" / "baseline.json",
        archive_path=REPO_ROOT / "data" / "archive",
        embedding_model="test/embed",
        embedding_dimensions=4,
    )
    base.update(overrides)
    return Settings(**base)


class FakeClient:
    def __init__(self, vectors) -> None:
        self.vectors = vectors

    def embed(self, texts: list[str], model_id: str) -> list[list[float]]:
        return self.vectors


def test_embedder_for_without_client_is_none():
    assert embedder_for(_settings(), None) is None


def test_embedder_normalizes_and_dimension_checks():
    embedder = embedder_for(_settings(), FakeClient([[3.0, 0.0, 0.0, 0.0]]))
    assert embedder(["alpha"]) == [[1.0, 0.0, 0.0, 0.0]]


def test_embedder_rejects_wrong_vector_count():
    # One vector for two labels is a programming error on the client side;
    # the wiring must fail loudly rather than silently drop an embedding.
    embedder = embedder_for(_settings(), FakeClient([[1.0, 0.0, 0.0, 0.0]]))
    with pytest.raises(ValueError, match="embedder returned 1 vectors for 2 labels"):
        embedder(["alpha", "beta"])
