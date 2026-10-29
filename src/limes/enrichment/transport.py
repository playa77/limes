"""Pinned replaceable Yahoo transport, preserving original quoteSummary bytes.

The narrow private YfData.get seam is pinned with yfinance; public DataFrame
accessors lose raw field/row evidence and can swallow errors as empty tables.
Never archive cookie/crumb/consent responses or credential-bearing URLs.
"""

from __future__ import annotations

import time
from tempfile import TemporaryDirectory
from typing import Any
from urllib.parse import quote

from curl_cffi.requests import Session

from limes.errors import SourceFetchError

MAX_BYTES = 4 * 1024 * 1024


class BoundedYahooSession(Session[Any]):
    """Bound decompressed bytes before buffering, including authentication responses."""

    def request(self, method: Any, url: str, *args: Any, **kwargs: Any) -> Any:
        body = bytearray()

        def consume(chunk: bytes) -> int:
            if len(body) + len(chunk) > MAX_BYTES:
                raise ValueError("Yahoo response exceeds 4 MiB")
            body.extend(chunk)
            return len(chunk)

        kwargs["content_callback"] = consume
        kwargs["max_redirects"] = 3
        response = super().request(method, url, *args, **kwargs)
        response.content = bytes(body)
        return response


class YahooTransport:
    def __init__(self) -> None:
        self._last_request = 0.0
        self._cache: TemporaryDirectory[str] | None = None
        self._session: BoundedYahooSession | None = None

    def get(self, symbol: str, module: str) -> tuple[bytes, str]:
        import yfinance as yf  # type: ignore[import-untyped]

        # One private transient cookie directory per worker process, no writable home.
        if self._cache is None:
            self._cache = TemporaryDirectory(prefix="limes-yahoo-")
            yf.set_tz_cache_location(self._cache.name)
            self._session = BoundedYahooSession(impersonate="chrome")
        assert self._session is not None
        url = "https://query2.finance.yahoo.com/v10/finance/quoteSummary/" + quote(symbol, safe="")
        for attempt in range(4):
            # One request per second; 429/5xx get bounded exponential backoff.
            delay = max(0.0, 1.0 - (time.monotonic() - self._last_request))
            if delay:
                time.sleep(delay)
            self._last_request = time.monotonic()
            try:
                response: Any = yf.Ticker(symbol, session=self._session)._data.get(
                    url,
                    params={"modules": module, "formatted": "false"},
                    timeout=20,
                )
                status = response.status_code
                content = bytes(response.content)
                if len(content) > MAX_BYTES:
                    raise ValueError("Yahoo response exceeds 4 MiB")
                if status == 404:
                    return content, "unsupported"
                if status == 429 or status >= 500:
                    if attempt < 3:
                        time.sleep(2 ** (attempt + 1))
                        continue
                    return content, "failed"
                if status >= 400:
                    return content, "failed"
                return content, "available"
            except ValueError as exc:
                raise SourceFetchError(str(exc)) from exc
            except Exception as exc:
                if attempt == 3:
                    raise SourceFetchError("Yahoo request failed after four attempts") from exc
                time.sleep(2 ** (attempt + 1))
        raise AssertionError("unreachable")
