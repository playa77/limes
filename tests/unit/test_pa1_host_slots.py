# tests/unit/test_pa1_host_slots.py | PA-1 | cross-process per-host netiquette (R5)
"""AC-5: concurrent scopes contending on one host serialize under the slot
cap; different hosts do not contending; the slot releases with the request."""

from __future__ import annotations

import threading
import time

import httpx
import pytest
import respx
from httpx import Response

from limes.errors import SourceFetchError
from limes.sources import base as source_base

URL_A = "https://host-a.test/data"
URL_B = "https://host-b.test/data"


def _slot_env(monkeypatch, tmp_path, cap=1, wait=0.5):
    monkeypatch.setenv("LIMES_HOST_SLOT_DIR", str(tmp_path / "host-slots"))
    monkeypatch.setenv("LIMES_HOST_CONCURRENCY_DEFAULT", str(cap))
    monkeypatch.setenv("LIMES_HOST_SLOT_WAIT_SECONDS", str(wait))


def test_two_contenders_on_one_host_serialize(tmp_path, monkeypatch):
    _slot_env(monkeypatch, tmp_path, cap=1, wait=0.5)
    order: list[str] = []
    release = threading.Event()
    acquired = threading.Event()

    def first() -> None:
        with source_base.host_slot("https://www.bundestag.de/x"):
            order.append("first-in")
            acquired.set()
            release.wait(10)
            order.append("first-out")

    def second() -> None:
        acquired.wait(10)
        with pytest.raises(SourceFetchError):
            with source_base.host_slot("https://www.bundestag.de/y"):
                order.append("second-in")

    t1, t2 = threading.Thread(target=first), threading.Thread(target=second)
    t1.start(); t2.start()  # noqa: E701 (confident two-statement lines)
    t2.join(timeout=10)
    assert "second-in" not in order  # bounded wait expired without the slot
    release.set()
    t1.join(timeout=10)
    # the freed slot is acquirable again
    with source_base.host_slot("https://www.bundestag.de/y"):
        assert True


def test_different_hosts_do_not_contend(tmp_path, monkeypatch):
    _slot_env(monkeypatch, tmp_path, cap=1, wait=0.5)
    with source_base.host_slot("https://host-a.test/x"):
        # same cap, different host: acquires immediately
        with source_base.host_slot("https://host-b.test/x"):
            assert True


def test_cap_two_allows_two_concurrent(tmp_path, monkeypatch):
    _slot_env(monkeypatch, tmp_path, cap=2, wait=0.5)
    scope1 = source_base.host_slot("https://host-c.test/x")
    scope2 = source_base.host_slot("https://host-c.test/y")
    with scope1, scope2:
        assert True


def test_overpass_hosts_share_one_cap(tmp_path, monkeypatch):
    _slot_env(monkeypatch, tmp_path, cap=1, wait=0.2)
    with source_base.host_slot("https://overpass-api.de/api/interpreter"):
        with pytest.raises(SourceFetchError):
            # a different overpass mirror maps to the same shared cap key
            with source_base.host_slot("https://overpass.kumi.systems/api/interpreter"):
                pass


def test_requests_honor_slots_and_release(tmp_path, monkeypatch):
    _slot_env(monkeypatch, tmp_path, cap=1, wait=5)
    monkeypatch.setattr("time.sleep", lambda _: None)
    results: list[str] = []
    errors: list[Exception] = []

    def handler(request: httpx.Request) -> Response:
        time.sleep(0.3)  # longer than the acquisition spacing
        return Response(200, content=b"ok")

    def hit(url: str) -> None:
        try:
            results.append(source_base.fetch_bytes(url))
        except Exception as exc:  # noqa: BLE001  (test surface)
            errors.append(exc)

    with respx.mock:
        respx.get("https://polite.test/").mock(side_effect=handler)
        threads = [threading.Thread(target=hit, args=("https://polite.test/",)) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
    assert not errors, errors
    assert results == [b"ok"] * 4
