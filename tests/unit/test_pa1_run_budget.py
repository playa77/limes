# tests/unit/test_pa1_run_budget.py | PA-1 | per-source run and transport budgets (R3)
"""AC-3: a degraded source aborts inside its budget; endpoint rotation does not
reset the consecutive-transport-failure counter; success resets it; the budget
error is a `SourceFetchError` subclass so the abort-and-durable-close path of
`_execute_run` is preserved; per-source override keys are honored."""

from __future__ import annotations

import time
from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
import respx
from httpx import Response

from limes.errors import SourceFetchError, SourceRunBudgetExceeded
from limes.pipeline.run import RunSpec, execute_run
from limes.sources import base as source_base
from limes.sources.base import fetch_bytes

URL = "https://upstream.invalid/data"
MIRROR = "https://mirror.invalid/data"


def _persistent_500(request: httpx.Request) -> Response:
    return Response(500, content=b"down")


def test_transport_budget_aborts_across_endpoint_rotation(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _: None)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> Response:
        calls["n"] += 1
        if "mirror" in str(request.url):
            return Response(503, content=b"mirror down")
        return Response(500, content=b"down")

    with respx.mock:
        respx.get(URL).mock(side_effect=handler)
        respx.get(MIRROR).mock(side_effect=handler)
        with source_base.source_run_scope(
            deadline=time.monotonic() + 600, transport_attempts=5
        ):
            # one call holds at most HTTP_MAX_ATTEMPTS (4) failures; the run
            # budget spans calls and endpoint rotation inside both of them
            with pytest.raises(SourceFetchError):
                source_base._fetch("GET", URL, fallback_urls=(MIRROR,))
            with pytest.raises(SourceRunBudgetExceeded):
                source_base._fetch("GET", URL, fallback_urls=(MIRROR,))
            observed = source_base.run_consecutive_failures()
    # 5 consecutive failed attempts counted, endpoint rotation never resets
    assert observed == 5
    assert calls["n"] == 5


def test_success_resets_the_transport_counter(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _: None)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> Response:
        calls["n"] += 1
        return Response(503, content=b"busy") if calls["n"] == 1 else Response(200, content=b"ok")

    with respx.mock:
        respx.get(URL).mock(side_effect=handler)
        with source_base.source_run_scope(
            deadline=time.monotonic() + 600, transport_attempts=2
        ):
            assert fetch_bytes(URL) == b"ok"  # 1 failure then success: counter reset
            assert fetch_bytes(URL) == b"ok"  # would exceed a stale counter of 2
        assert source_base.run_consecutive_failures() == 0


def test_no_scope_means_no_budget(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _: None)

    def handler(request: httpx.Request) -> Response:
        return Response(200, content=b"ok")

    with respx.mock:
        respx.get(URL).mock(side_effect=handler)
        assert fetch_bytes(URL) == b"ok"


def test_budget_error_is_a_source_fetch_error():
    assert issubclass(SourceRunBudgetExceeded, SourceFetchError)


def test_per_source_override_key(monkeypatch):
    from limes.pipeline.run import _source_budget

    settings = SimpleNamespace(
        source_run_budget_seconds=1800, source_transport_budget_attempts=8
    )
    assert _source_budget(settings, "ted") == (1800, 8)
    monkeypatch.setenv("LIMES_SOURCE_BUDGET_GLEIF_SECONDS", "60")
    assert _source_budget(settings, "gleif") == (60, 8)


def test_wall_clock_budget_aborts_a_slow_stream(tmp_path):
    from limes.errors import SourceParseError
    from tests.unit.test_pipeline_run import FakeAdapter, FakeDriver, _ctx, _raw_record

    def _raise_parse(record):
        raise SourceParseError("unparseable but counted, never fatal")

    class SlowBrokenAdapter(FakeAdapter):
        def fetch(self, since, until):
            for _ in range(6):
                time.sleep(0.5)
                yield _raw_record()

    driver = FakeDriver()
    ctx = _ctx(tmp_path, driver, SlowBrokenAdapter(normalize=_raise_parse),
               source_run_budget_seconds=1)
    with pytest.raises(SourceRunBudgetExceeded):
        execute_run(RunSpec(source_id="test", mode="ingest"), ctx)
    closures = [params for _, params in driver.writes if "finished_at" in params]
    assert len(closures) == 1  # durable record closed despite the abort
    assert closures[0]["errors"] >= 1
    # checkpoint untouched: no success statement in any write
    assert not any("last_success_at" in params for _, params in driver.writes)