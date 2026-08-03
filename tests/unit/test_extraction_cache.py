# tests/unit/test_extraction_cache.py | v1.0.0 | introduced by WP-23
"""Extraction cache unit tests per Doc 2 §8.7.5.

The graph-touching behavior is covered by tests/integration/test_extraction_cache.py;
these tests pin the pure parts with a driver stub: the deterministic key,
the miss path, and the guard that turns an unparsable stored result into a
miss — a poisoned cache entry must never fail an ingest.
"""

from limes.extraction.base import ExtractionResult
from limes.extraction.cache import cache_key, exists, get, put


class FakeDriver:
    """Serves canned rows for reads and records writes."""

    def __init__(self, rows=None) -> None:
        self.rows = rows or []
        self.writes: list[tuple[str, dict]] = []

    def read(self, cypher: str, params: dict, timeout_s: int) -> list[dict]:
        return self.rows

    def write_batch(self, statements: list[tuple[str, dict]]) -> None:
        self.writes.extend(statements)


def _result() -> ExtractionResult:
    return ExtractionResult(
        assertions=[], input_tokens=1, output_tokens=1, raw_response="", parse_errors=[]
    )


def test_cache_key_is_deterministic():
    first = cache_key("hash", "1.0.0", "1.0.0", "model")
    second = cache_key("hash", "1.0.0", "1.0.0", "model")
    assert first == second
    assert cache_key("hash", "1.0.0", "1.0.0", "model") != cache_key(
        "hash", "1.0.0", "1.0.0", "other"
    )


def test_get_miss_is_not_an_error():
    assert get(FakeDriver(), "hash", "1.0.0", "1.0.0", "model") is None


def test_put_writes_the_serialized_result():
    driver = FakeDriver()
    result = _result()
    put(driver, "hash", "1.0.0", "1.0.0", "model", result)
    assert len(driver.writes) == 1
    assert driver.writes[0][1]["result_json"] == result.model_dump_json()


def test_exists_reads_the_existence_row():
    assert exists(FakeDriver([{"exists": True}]), "hash", "1.0.0", "1.0.0", "model") is True
    assert exists(FakeDriver([{"exists": False}]), "hash", "1.0.0", "1.0.0", "model") is False
    assert exists(FakeDriver([]), "hash", "1.0.0", "1.0.0", "model") is False


def test_unparsable_cached_result_is_treated_as_a_miss(capsys):
    driver = FakeDriver([{"result_json": "{not json"}])
    assert get(driver, "hash", "1.0.0", "1.0.0", "model") is None
    captured = capsys.readouterr()
    assert "unparsable" in captured.out + captured.err
