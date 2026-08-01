# tests/unit/test_resolution_blocking.py | v1.0.0 | introduced by WP-25
"""Blocking tests per Doc 2 §8.8.2: the permanent per-process embed cache
keyed by (model, text), L2 normalization with the dimension contract, and
the vector-index candidate query shape (WP-25).
"""

import pytest

from limes.errors import ExtractionError
from limes.resolution import blocking

DIMS = 4


class StubEmbedClient:
    """A client whose `embed` records calls and returns canned vectors."""

    def __init__(self, vectors_by_text: dict[str, list[float]]) -> None:
        self.vectors_by_text = vectors_by_text
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str], model_id: str) -> list[list[float]]:
        self.calls.append(texts)
        return [self.vectors_by_text[text] for text in texts]


class StubDriver:
    """A driver whose `read` returns canned rows; the query text is captured
    so the test can assert the type predicate."""

    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.last_query = ""
        self.read_calls = 0

    def read(self, cypher: str, params: dict, timeout_s: int) -> list[dict]:
        self.read_calls += 1
        self.last_query = cypher
        return self.rows


def test_embed_caches_per_model_and_text():
    vectors = {
        "Volkswagen AG (Corporation)": [1.0, 2.0, 3.0, 4.0],
        "Anders (Person)": [4.0, 3.0, 2.0, 1.0],
    }
    client = StubEmbedClient(vectors)
    first = blocking.embed(list(vectors), client, "m-1", DIMS)
    second = blocking.embed(list(vectors), client, "m-1", DIMS)
    blocking.embed(list(vectors), client, "m-2", DIMS)  # different model, new call
    assert first == second
    assert client.calls == [list(vectors), list(vectors)]  # m1 hit, m2 miss


def test_embed_normalizes_and_checks_dimensions():
    client = StubEmbedClient({"x": [1.0, 0.0, 0.0, 0.0]})
    (vector,) = blocking.embed(["x"], client, "m-dims", DIMS)
    assert vector == [1.0, 0.0, 0.0, 0.0]
    # The dimension contract is enforced on the first embedding of a
    # (model, text) pair; a cached pair is already validated.
    bad = StubEmbedClient({"y": [1.0, 0.0, 0.0, 0.0, 0.0]})
    with pytest.raises(ExtractionError, match="dimension"):
        blocking.embed(["y"], bad, "m-dims", DIMS)


def test_embed_rejects_zero_vector():
    client = StubEmbedClient({"x": [0.0, 0.0, 0.0, 0.0]})
    with pytest.raises(ExtractionError, match="unusable"):
        blocking.embed(["x"], client, "m-zero", DIMS)


class ShortStubClient:
    """Returns one vector regardless of the request size."""

    def __init__(self, vector: list[float]) -> None:
        self.vector = vector

    def embed(self, texts: list[str], model_id: str) -> list[list[float]]:
        return [self.vector]


def test_embed_rejects_wrong_vector_count():
    client = ShortStubClient([1.0, 0.0, 0.0, 0.0])
    with pytest.raises(ExtractionError, match="vectors"):
        blocking.embed(["x", "y"], client, "m-count", DIMS)


def test_candidates_parses_rows_and_filters_type():
    # The stub returns raw engine scores; the engine reports (1 + cosine)/2,
    # so candidates() converts back to cosine space.
    driver = StubDriver(
        [
            {"entity_id": "lei:X", "label": "Volkswagen AG", "score": 0.975},
            {"entity_id": "lei:Y", "label": "VW AG", "score": 0.94},
        ]
    )
    result = blocking.candidates(driver, [1.0, 0.0, 0.0, 0.0], "Corporation", 10)
    assert result[0]["entity_id"] == "lei:X"
    assert result[0]["score"] == pytest.approx(0.95)
    assert result[1]["entity_id"] == "lei:Y"
    assert result[1]["score"] == pytest.approx(0.88)
    assert "node:Corporation" in driver.last_query
    assert driver.read_calls == 1


def test_candidates_handles_empty_index():
    driver = StubDriver([])
    assert blocking.candidates(driver, [1.0, 0.0, 0.0, 0.0], "Person", 10) == []
