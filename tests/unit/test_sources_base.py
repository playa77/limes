# tests/unit/test_sources_base.py | v1.0.0 | introduced by WP-10
"""Shared source-layer helpers tests (src/limes/sources/base.py).

`fetch_bytes` / `fetch_bytes_post` are exercised through respx against the
§11 retry policy: transient statuses and connection errors retry with
exponential backoff (the sleeps are suppressed in-test; the retry logic
still runs), a persistent failure surfaces as `SourceFetchError` naming the
attempt count, and a permanent 4xx never retries. The identity helpers are
asserted against the documented schemes: `key:value` for deterministic keys,
the short SHA-256 digest for name-hashed identities, the full SHA-256 over
the pipe-joined assertion material, and the SHA-256 payload hash.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import httpx
import pytest
import respx
from httpx import Response

from limes.errors import SourceFetchError
from limes.sources.base import (
    HTTP_MAX_ATTEMPTS,
    RETRYABLE_STATUSES,
    deterministic_assertion_id,
    fetch_bytes,
    fetch_bytes_post,
    hash_entity_id,
    key_entity_id,
    payload_hash,
)

URL = "https://example.invalid/data"


def _assert_fetch_failure(exc: SourceFetchError, attempts: int) -> None:
    assert f"after {attempts} attempts" in str(exc)
    assert URL in str(exc)


def test_fetch_bytes_succeeds_after_transient_statuses(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _: None)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return Response(503, content=b"busy")
        return Response(200, content=b"ok")

    with respx.mock:
        respx.get(URL).mock(side_effect=handler)
        assert fetch_bytes(URL) == b"ok"
    assert calls["n"] == 3


def test_fetch_bytes_post_succeeds_after_throttling(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _: None)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return Response(429, content=b"slow down")
        return Response(200, content=b"done")

    with respx.mock:
        respx.post(URL).mock(side_effect=handler)
        assert fetch_bytes_post(URL, {"q": "x"}) == b"done"
    assert calls["n"] == 3


def test_fetch_bytes_exhausts_retries_on_persistent_5xx(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _: None)
    with respx.mock:
        respx.get(URL).mock(return_value=Response(502, content=b"gateway error"))
        with pytest.raises(SourceFetchError) as exc_info:
            fetch_bytes(URL)
    _assert_fetch_failure(exc_info.value, HTTP_MAX_ATTEMPTS)


def test_fetch_bytes_raises_source_fetch_error_on_connection_error(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _: None)
    with respx.mock:
        respx.get(URL).mock(side_effect=httpx.ConnectError("connection refused"))
        with pytest.raises(SourceFetchError) as exc_info:
            fetch_bytes(URL)
    _assert_fetch_failure(exc_info.value, HTTP_MAX_ATTEMPTS)


def test_fetch_bytes_does_not_retry_permanent_4xx():
    with respx.mock:
        route = respx.get(URL).mock(return_value=Response(404, content=b"gone"))
        with pytest.raises(SourceFetchError) as exc_info:
            fetch_bytes(URL)
    assert len(route.calls) == 1
    assert "HTTP 404" in str(exc_info.value)


def test_retryable_statuses_are_only_429_and_5xx():
    assert RETRYABLE_STATUSES == {429, 500, 502, 503, 504}
    for status in (400, 401, 403, 404):
        assert status not in RETRYABLE_STATUSES


def test_key_entity_id_is_the_documented_scheme():
    assert key_entity_id(("lei", "5493000TEST000000001")) == "lei:5493000TEST000000001"
    assert key_entity_id(("bundestag_id", "11004755")) == "bundestag_id:11004755"


def test_hash_entity_id_is_short_digest_in_typed_namespace():
    person_id = hash_entity_id("person", "Mustermann, Max")
    assert person_id.startswith("person:")
    assert len(person_id) - len("person:") == 32
    assert person_id == hash_entity_id("person", "Mustermann, Max")
    # A different namespace over the same parts must not collide.
    assert hash_entity_id("corporation", "Mustermann, Max") != person_id


def test_deterministic_assertion_id_material_and_stability():
    since = datetime(2026, 1, 1, tzinfo=UTC)
    first = deterministic_assertion_id("ted", "AWARDED_TO", "a", "b", since)
    second = deterministic_assertion_id("ted", "AWARDED_TO", "a", "b", since)
    assert first == second
    expected = hashlib.sha256(
        "|".join(["ted", "AWARDED_TO", "a", "b", since.isoformat(), ""]).encode("utf-8")
    ).hexdigest()
    assert first == expected
    # A different validity interval is a different assertion.
    assert first != deterministic_assertion_id("ted", "AWARDED_TO", "a", "b", since.replace(day=2))


def test_deterministic_assertion_id_includes_valid_to_when_present():
    since = datetime(2026, 1, 1, tzinfo=UTC)
    until = datetime(2026, 6, 30, tzinfo=UTC)
    assert deterministic_assertion_id(
        "offeneregister", "DIRECTOR_OF", "p", "c", since, until
    ) != deterministic_assertion_id("offeneregister", "DIRECTOR_OF", "p", "c", since)


def test_payload_hash_is_sha256_of_bytes():
    assert payload_hash(b"payload") == hashlib.sha256(b"payload").hexdigest()


def test_bounded_fetch_decodes_gzip_once_and_enforces_decoded_limit():
    import gzip

    logical = b'{"revision":"bounded original JSON"}'
    encoded = gzip.compress(logical)
    with respx.mock:
        respx.get(URL).mock(
            return_value=Response(200, content=encoded, headers={"Content-Encoding": "gzip"})
        )
        assert fetch_bytes(URL, max_bytes=len(logical)) == logical
        with pytest.raises(SourceFetchError, match="byte limit"):
            fetch_bytes(URL, max_bytes=len(logical) - 1)


@pytest.mark.parametrize("status", [429, 503])
def test_retry_after_minimum_is_honored(status, monkeypatch):
    delays = []
    monkeypatch.setattr("time.sleep", delays.append)
    with respx.mock:
        route = respx.get(URL).mock(side_effect=[
            Response(status, headers={"Retry-After": "75"}), Response(200, content=b"ok")
        ])
        assert fetch_bytes(URL) == b"ok"
    assert route.call_count == 2
    assert delays == [75]


def test_excessive_cooldown_fails_without_retrying_early(monkeypatch):
    delays = []
    monkeypatch.setattr("time.sleep", delays.append)
    with respx.mock:
        route = respx.get(URL).mock(return_value=Response(429, headers={"Retry-After": "3600"}))
        with pytest.raises(SourceFetchError, match="retry later"):
            fetch_bytes(URL)
    assert route.call_count == 1
    assert delays == []


def test_retry_after_http_date_and_invalid_values():
    from datetime import timedelta
    from email.utils import format_datetime

    from limes.sources.base import _retry_after_seconds

    future = format_datetime(datetime.now(UTC) + timedelta(seconds=90), usegmt=True)
    delay = _retry_after_seconds(future)
    assert delay is not None and 88 <= delay <= 90
    for value in (None, "invalid", "NaN", "inf"):
        assert _retry_after_seconds(value) is None
