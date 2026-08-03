# tests/unit/test_graph_driver.py | v1.0.0 | introduced by WP-04
"""GraphDriver unit tests per Doc 2 §8.3.

The read/explain behavior against a live server is covered by the
integration suite; these tests pin the write-error surface: a persistent
`GraphWriteError` from the session is re-raised unchanged — the driver never
wraps its own error in itself.
"""

from contextlib import contextmanager

import pytest

from limes.errors import GraphWriteError
from limes.graph.driver import GraphDriver


class FailingSession:
    """A session whose write execution fails persistently."""

    def execute_write(self, fn, statements):
        raise GraphWriteError("graph write failed: boom")


class FakeRawDriver:
    def __init__(self) -> None:
        self._session = FailingSession()

    @contextmanager
    def session(self, **kwargs):
        yield self._session

    def close(self) -> None:
        pass


def test_write_batch_reraises_graph_write_errors_unchanged():
    driver = GraphDriver("bolt://localhost:7687", "u", "p", "neo4j")
    driver._driver = FakeRawDriver()
    with pytest.raises(GraphWriteError, match="graph write failed: boom"):
        driver.write_batch([("RETURN 1", {})])
