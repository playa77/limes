# tests/unit/conftest.py | v1.0.0 | offline API startup for unit tests
"""Unit tests must not wait for a real database during application startup."""
import pytest
from neo4j.exceptions import ServiceUnavailable

from limes.api import main as api_main


@pytest.fixture(autouse=True)
def offline_api_startup(monkeypatch):
    def unavailable(*args, **kwargs):
        raise ServiceUnavailable("unit test database is mocked")

    monkeypatch.setattr(api_main, "provision", unavailable)
