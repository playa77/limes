# src/limes/sources/base.py | v1.0.0 | introduced by WP-09
"""Source adapter protocol per Technical Specification §8.5.1.

An adapter owns fetching from one source and converting its records into
ontology-typed assertions (Doc 1 §4.1). It declares its identity, trust rank,
and incremental capability; it writes nothing to the graph — the loader does.
`fetch` yields raw payloads for the archive; `normalize` turns one raw record
into a `NormalizedRecord` of assertions, standalone entities, lookup rows, and
optionally a document payload.

The helpers below are shared by every adapter and keep three invariants
uniform across the source layer:

- `entity_id` values are deterministic and cross-source stable: for endpoints
  with a deterministic key, `key:value`; for endpoints without one (resolved
  by name), a short SHA-256 digest in a typed namespace. Two adapters that
  name the same LEI therefore address the same node, because the loader
  merges on `entity_id` (Doc 2 §5.6).
- `assertion_id` is a digest over the assertion's meaningful fields, so a
  re-run over an identical window is a no-op: the loader skips an existing
  relationship with the same `assertion_id` (AC-05).
- `ONTOLOGY_VERSION` is the single source of truth for the ontology version
  stamped on every assertion's provenance; the migration WP (WP-31) bumps it
  here and nowhere else.
"""

from __future__ import annotations

import fcntl
import hashlib
import logging
import math
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Literal, Protocol, TextIO, runtime_checkable
from urllib.parse import urlsplit

import httpx
import structlog
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from limes.errors import SourceFetchError, SourceRunBudgetExceeded
from limes.types import (
    Assertion,
    EntityEndpoint,
    NormalizedRecord,
    Provenance,
    RawRecord,
    Validity,
)

logger = structlog.get_logger(__name__)


class _RunBudget:
    """PA-1 R3 run-scoped budget: a wall-clock deadline and the consecutive
    failed-attempt cap for one source run. lives on the module scope set by
    `source_run_scope` from `pipeline/run.py` (one run per subprocess thread)."""

    def __init__(self, deadline: float | None, transport_attempts: int | None) -> None:
        self.deadline = deadline
        self.transport_attempts = transport_attempts
        self.failures = 0

    def record_failure(self) -> None:
        self.failures += 1
        if self.transport_attempts and self.failures >= self.transport_attempts:
            raise SourceRunBudgetExceeded(
                "source transport budget exhausted after "
                f"{self.failures} consecutive failed HTTP attempts "
                "(endpoint rotation does not reset this budget)"
            )

    def record_success(self) -> None:
        self.failures = 0


_scope: ContextVar[_RunBudget | None] = ContextVar("limes_source_run_budget", default=None)


@contextmanager
def source_run_scope(
    deadline: float | None, transport_attempts: int | None
) -> Iterator[_RunBudget | None]:
    """Bind the PA-1 R3 budget for one source run; remove it again on exit.

    A ContextVar (not a module global) keeps concurrent in-process timelines
    from bleeding failure counts across runs.
    """
    token = _scope.set(_RunBudget(deadline, transport_attempts))
    try:
        yield _scope.get()
    finally:
        _scope.reset(token)


def run_consecutive_failures() -> int:
    """Consecutive failed HTTP attempts inside the active run (0 without one)."""
    scope = _scope.get()
    return scope.failures if scope is not None else 0


def run_time_left() -> float | None:
    """Seconds left in the active run budget (None without one)."""
    scope = _scope.get()
    return None if scope is None or scope.deadline is None else scope.deadline - time.monotonic()

# The ontology artifact version the adapters emit against (ontology/ontology.yaml).
# One place to bump on migration (WP-31); the loader stamps nodes with the
# *loaded* ontology's version, so a stale constant here only mislabels
# assertions, never nodes.
ONTOLOGY_VERSION = "1.4.0"

# §11 retry policy, as module constants matching the §4.2 defaults: adapters
# are constructed without Settings (build_default_registry takes none), so the
# policy lives here, in one place.
HTTP_TIMEOUT_SECONDS = 60
HTTP_MAX_ATTEMPTS = 4

# Statuses that are retried per §11: 429 and 5xx. Never other 4xx.
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})

# PA-1 R5 netiquette caps: slots per upstream host across concurrent sources.
HOST_CONCURRENCY_OVERRIDES: dict[str, int] = {
    "abgeordnetenwatch.de": 1,
    "ted.europa.eu": 1,
    "webgate.ec.europa.eu": 1,
    "overpass": 1,  # matches any overpass host by substring
    "bundestag.de": 1,
}

# A user agent that names the project; several sources (FSD, GISCO) are picky
# about UA strings and rate-limit anonymous scraping.
USER_AGENT = "limes/0.1.0 (personal research artifact)"


@runtime_checkable
class SourceAdapter(Protocol):
    """One ingestable source (Doc 2 §8.5.1).

    `runtime_checkable` so the registry can `isinstance`-check adapters at
    registration time; the check is structural (attribute presence), which is
    exactly the honesty the registry needs.

    `supports_incremental` governs window resolution (§8.6.2): an incremental
    source fetches only since `Source.last_success_at`, a non-incremental one
    is always a full load. `fetch` never touches the graph; `normalize` never
    touches the network.
    """

    source_id: str
    name: str
    kind: Literal["structured", "unstructured"]
    trust_rank: float
    supports_backfill: bool
    supports_incremental: bool

    def fetch(self, since: datetime | None, until: datetime | None) -> Iterator[RawRecord]: ...

    def normalize(self, record: RawRecord) -> NormalizedRecord: ...


def key_entity_id(key: tuple[str, str]) -> str:
    """Deterministic `entity_id` for an endpoint carrying a deterministic key.

    The scheme is `key_name:key_value` — e.g. `lei:549300...`. The loader
    merges nodes on `entity_id`, so every adapter that emits the same key
    value must produce the same `entity_id` or the node is duplicated; this
    function is what makes that uniform.
    """
    name, value = key
    return f"{name}:{value}"


def hash_entity_id(namespace: str, *parts: str) -> str:
    """Deterministic `entity_id` for an endpoint without a deterministic key
    (e.g. a person resolved by name, an operator read from an OSM tag).

    The digest is short (32 hex chars of SHA-256) — enough to be unique, small
    enough to read. The namespace prefix (e.g. `person`, `operator`) keeps
    name-derived ids of different types from colliding.
    """
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]
    return f"{namespace}:{digest}"


def topic_endpoint(vocabulary: str, code: str, *, label: str | None = None) -> EntityEndpoint:
    """A Topic under the shared multi-key identity convention.

    The ontology declares `[vocabulary, code]` as a Topic's identifying keys,
    but the loader stamps one key property; the vocabulary therefore rides in
    the `entity_id` while the deterministic key is the code alone. Every
    adapter that emits topics (TED/CPV, EUR-Lex/EuroVoc, Gesetze im Internet/
    Sachgebiet, OSM/KRITIS) must use this constructor — two vocabularies or
    two code spellings for the same topic would fork the node.
    """
    return EntityEndpoint(
        entity_id=f"topic:{vocabulary}:{code}",
        type="Topic",
        label=label if label is not None else code,
        deterministic_key=("code", code),
    )


def address_location(country: str, postal: str, city: str) -> EntityEndpoint:
    """A Location whose identity is the address hash, not coordinates.

    Shared by GLEIF and TED: the digest over `country|postal|city` is the
    node's identity — stable across runs and across the two sources — never
    geometry (neither source geocodes here). The key name stays
    `coordinate_hash` for identity compatibility with the nodes already
    written under it.
    """
    addr_hash = hashlib.sha256("|".join([country, postal, city]).encode("utf-8")).hexdigest()
    return EntityEndpoint(
        entity_id=key_entity_id(("coordinate_hash", addr_hash)),
        type="Location",
        label=city or f"Address in {country}",
        deterministic_key=("coordinate_hash", addr_hash),
    )


def coordinate_location(lat: float, lon: float, *, label: str | None = None) -> EntityEndpoint:
    """A Location whose identity is the rounded-coordinate digest (D-13).

    Shared by GDELT and OSM: five decimal places (~1 m) rounded before
    hashing, so re-readings of the same place converge on one node. The hash
    is identity, never geometry.
    """
    coordinate_key = f"{lat:.5f},{lon:.5f}"
    digest = hashlib.sha256(coordinate_key.encode("utf-8")).hexdigest()
    return EntityEndpoint(
        entity_id=key_entity_id(("coordinate_hash", digest)),
        type="Location",
        label=label if label is not None else f"{lat:.5f}, {lon:.5f}",
        deterministic_key=("coordinate_hash", digest),
    )


def deterministic_assertion_id(
    source_id: str,
    relation: str,
    subject_id: str,
    object_id: str,
    valid_from: datetime,
    valid_to: datetime | None = None,
) -> str:
    """Deterministic `assertion_id` over the assertion's meaning.

    A full SHA-256 digest of the concatenated fields. The relationship merge
    is idempotent by `assertion_id` (Doc 2 §5.6 step 3), so a re-run over the
    same window produces the same digest and zero new edges (AC-05). An
    assertion that *changes* — a different interval, a different object —
    produces a new digest and is written alongside, not on top of, the old
    one.
    """
    material = "|".join(
        [
            source_id,
            relation,
            subject_id,
            object_id,
            valid_from.isoformat(),
            valid_to.isoformat() if valid_to is not None else "",
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def payload_hash(payload: bytes) -> str:
    """SHA-256 of a raw payload — the same digest `ArchiveStore.put` computes,
    so `NormalizedRecord.content_hash` filled here matches the archive hash
    `execute_run` re-stamps from `ArchiveStore.put` (§15.2)."""
    return hashlib.sha256(payload).hexdigest()


def make_assertion(
    adapter: SourceAdapter,
    record: RawRecord,
    subject: EntityEndpoint,
    relation: str,
    object_: EntityEndpoint,
    *,
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
    recorded_at: datetime | None = None,
) -> Assertion:
    """The one assertion constructor for the source layer.

    Every adapter previously carried its own `_assertion`/`_provenance` pair
    that assembled the same five-part shape; twelve near-copies drifted in
    parameter order and none in semantics. This function is the single place
    that decides what an adapter-emitted assertion looks like: deterministic
    id over the assertion's meaning, `recorded_at` from the record's fetch
    instant, provenance stamped with the adapter's identity and trust rank and
    the shared `ONTOLOGY_VERSION`.

    Defaults follow the two patterns adapters actually use: an assertion
    without a source-stated start date is valid from its fetch instant
    (`valid_from=None`), and `recorded_at` is the fetch instant — except for
    sources that publish their own vintage, which pass their dataset
    publication date explicitly (`offeneregister`; the recorded_at-honesty
    rule). `valid_to` stays `None` unless the source states an end date; a
    `valid_to` on a non-temporal relation is rejected downstream by the
    ontology validator.
    """
    effective_valid_from = valid_from if valid_from is not None else record.fetched_at
    return Assertion(
        assertion_id=deterministic_assertion_id(
            adapter.source_id,
            relation,
            subject.entity_id,
            object_.entity_id,
            effective_valid_from,
            valid_to,
        ),
        subject=subject,
        relation=relation,
        object=object_,
        validity=Validity(
            valid_from=effective_valid_from,
            valid_to=valid_to,
            recorded_at=recorded_at if recorded_at is not None else record.fetched_at,
        ),
        provenance=Provenance(
            source_id=adapter.source_id,
            source_trust=adapter.trust_rank,
            confidence=1.0,
            ontology_version=ONTOLOGY_VERSION,
        ),
    )


class TransientFailure(Exception):
    """Internal marker, optionally carrying a server's minimum retry delay."""

    def __init__(self, reason: str, retry_after: float | None = None,
                 status_code: int | None = None) -> None:
        super().__init__(reason)
        self.retry_after = retry_after
        self.status_code = status_code


def _retry_after_seconds(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            when = parsedate_to_datetime(value)
            if when.tzinfo is None:
                return None
            seconds = (when - datetime.now(UTC)).total_seconds()
        except (TypeError, ValueError, OverflowError):
            return None
    return max(0.0, seconds) if math.isfinite(seconds) else None


def _retry_wait(state: Any) -> float:
    fallback = wait_exponential_jitter(initial=2.0, max=60.0, jitter=2.0)(state)
    error = state.outcome.exception()
    delay = error.retry_after if isinstance(error, TransientFailure) else None
    wait = max(fallback, delay or 0.0)
    left = run_time_left()
    if left is not None and wait >= left:
        raise SourceRunBudgetExceeded(
            "source run cannot honor retry cooldown within remaining budget; retry later"
        )
    return wait



def is_transient(exc: BaseException) -> bool:
    """Whether the §11 policy may retry this exception: the marker raised by
    `request_with_retry` itself, plus connection errors and timeouts."""
    if isinstance(exc, TransientFailure):
        return True
    # Connection errors and timeouts are always transient (§11).
    return isinstance(
        exc,
        (
            httpx.ConnectError,
            httpx.TimeoutException,
            httpx.ReadError,
            httpx.WriteError,
            httpx.RemoteProtocolError,
        ),
    )


class RetryExhausted(Exception):
    """The §11 policy ran out of attempts. Attributes carry what the layer
    wrappers need to phrase their own error: `attempts`, `url`, `reason`."""

    def __init__(self, attempts: int, url: str, reason: str) -> None:
        super().__init__(reason)
        self.attempts = attempts
        self.url = url
        self.reason = reason


class PermanentStatus(Exception):
    """A non-retryable HTTP status (a 4xx other than 429). The wrapper maps
    it onto the layer's own error type; the status is never retried."""

    def __init__(self, url: str, status_code: int, response_body: bytes = b"") -> None:
        super().__init__(f"HTTP {status_code} from {url}")
        self.url = url
        self.status_code = status_code
        self.response_body = response_body[:16384]


def request_with_retry(
    method: str,
    url: str,
    *,
    json_body: dict[str, Any] | None = None,
    form_body: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    timeout_s: float = HTTP_TIMEOUT_SECONDS,
    read_timeout_s: float | None = None,
    fallback_urls: tuple[str, ...] = (),
    follow_redirects: bool = True,
    log: Any = logger,
    max_bytes: int | None = None,
    output_path: Path | None = None,
) -> httpx.Response:
    """The one §11 retry transport: exponential backoff from 2 s, factor 2,
    jittered, at most `HTTP_MAX_ATTEMPTS` attempts, on connection errors,
    timeouts, 429, and 5xx — never on other 4xx.

    Returns the successful `httpx.Response`; the caller decides how to read
    it (bytes, JSON) and which layer error its failures map to, via the two
    public markers `RetryExhausted` and `PermanentStatus`. `log` keeps the
    backoff warnings attributed to the calling module. This function exists
    because the identical scaffolding was hand-rolled four times across the
    source and extraction layers and drifted; the §11 policy is stated here
    once.
    """
    attempts = 0
    endpoint_index = 0
    endpoints = (url, *fallback_urls)

    def _budget_failure(step: str, detail: str) -> None:
        scope = _scope.get()
        if scope is None:
            return
        scope.record_failure()
        logger.warning(
            "source transport attempt failed; budget consumed",
            url=url,
            step=step,
            detail=detail,
            consecutive_failures=scope.failures,
            budget_attempts=scope.transport_attempts,
        )

    @retry(
        stop=stop_after_attempt(HTTP_MAX_ATTEMPTS),
        wait=_retry_wait,
        retry=retry_if_exception(is_transient),
        before_sleep=before_sleep_log(log, logging.WARNING),
        reraise=True,
    )
    def _call() -> httpx.Response:
        from limes.sources.acquisition import active_acquisition

        nonlocal attempts, endpoint_index
        scope = _scope.get()
        acquisition = active_acquisition.get()
        if scope is not None and scope.deadline is not None and time.monotonic() >= scope.deadline:
            raise SourceRunBudgetExceeded(
                "source run budget elapsed; refusing another HTTP attempt"
            )
        attempt_url = endpoints[endpoint_index % len(endpoints)]
        attempts += 1
        remaining = run_time_left()
        effective_timeout = (min(timeout_s, max(0.001, remaining))
                             if remaining is not None else timeout_s)
        effective_read = read_timeout_s or timeout_s
        if remaining is not None:
            effective_read = min(effective_read, max(0.001, remaining))
        if read_timeout_s is not None:
            log.info("source HTTP attempt", endpoint=attempt_url, attempt=attempts)
        # PA-1 R5: one host slot per request, held until the response body
        # is consumed — never released mid-stream.
        with host_slot(attempt_url), httpx.Client(
            timeout=httpx.Timeout(effective_timeout, read=effective_read),
            follow_redirects=follow_redirects,
            headers=headers,
        ) as client:
            try:
                if max_bytes is None and output_path is None:
                    response = (
                        client.post(attempt_url, data=form_body)
                        if form_body is not None
                        else client.post(attempt_url, json=json_body)
                        if method == "POST"
                        else client.get(attempt_url)
                    )
                else:
                    with client.stream(
                        method, attempt_url, json=json_body, data=form_body
                    ) as streamed:
                        chunks = bytearray()
                        size = 0
                        # Never publish error bodies as successful source artifacts.
                        destination = output_path if streamed.is_success else None
                        with destination.open("wb") if destination else nullcontext() as output:
                            for chunk in streamed.iter_bytes():
                                if destination and acquisition and acquisition.progress:
                                    acquisition.progress("downloading", None)
                                left = run_time_left()
                                if left is not None and left <= 0:
                                    raise SourceRunBudgetExceeded("source deadline during download")
                                size += len(chunk)
                                if max_bytes is not None and size > max_bytes:
                                    raise SourceFetchError("source response exceeds byte limit")
                                if output is not None:
                                    output.write(chunk)
                                elif output_path is None:
                                    chunks.extend(chunk)
                                elif len(chunks) < 16384:
                                    chunks.extend(chunk[:16384 - len(chunks)])
                            if output is not None:
                                output.flush()
                                os.fsync(output.fileno())
                        response = httpx.Response(
                            streamed.status_code,
                            # iter_bytes() already decoded HTTP content encoding.
                            # Retaining gzip/br headers would decode a second time.
                            headers={
                                key: value
                                for key, value in streamed.headers.items()
                                if key.lower() not in ("content-encoding", "content-length")
                            },
                            content=bytes(chunks),
                            request=streamed.request,
                        )
            except httpx.TransportError as exc:
                if not is_transient(exc):
                    raise
                log.warning(
                    "HTTP attempt failed", method=method, url=attempt_url, attempt=attempts,
                    max_attempts=HTTP_MAX_ATTEMPTS, outcome="transport_failure",
                    error_type=type(exc).__name__,
                )
                endpoint_index += 1
                if acquisition and acquisition.progress:
                    acquisition.progress("transport_failure", type(exc).__name__)
                _budget_failure("transport", type(exc).__name__)
                raise TransientFailure(str(exc)) from exc
            delay = _retry_after_seconds(response.headers.get("Retry-After"))
            if acquisition is not None and acquisition.progress is not None:
                acquisition.progress(
                    "rate_limited" if response.status_code == 429 else
                    "upstream_failure" if response.status_code >= 500 else "acquiring",
                    f"HTTP {response.status_code} from {attempt_url}"
                    if response.status_code >= 400 else None,
                )
            if response.headers.get("x-amzn-waf-action") in ("challenge", "captcha"):
                raise SourceFetchError(
                    f"source access blocked by WAF challenge: {attempt_url} "
                    f"(HTTP {response.status_code}); no usable source payload"
                )
            log.info(
                "HTTP attempt completed", method=method, url=attempt_url, attempt=attempts,
                max_attempts=HTTP_MAX_ATTEMPTS, status_code=response.status_code,
                outcome=("rate_limited" if response.status_code == 429 else
                         "upstream_failure" if response.status_code >= 500 else
                         "client_failure" if response.status_code >= 400 else "success"),
                retry_after_seconds=delay,
                retryable=response.status_code in RETRYABLE_STATUSES,
            )
            if response.status_code in RETRYABLE_STATUSES:
                # Keep operator jobs bounded without violating a server cooldown.
                _budget_failure("retryable_status", f"HTTP {response.status_code}")
                if delay is not None and delay > 300:
                    raise RetryExhausted(
                        attempts, url,
                        f"HTTP {response.status_code}; Retry-After exceeds 300s; retry later",
                    )
                if response.status_code >= 500:
                    endpoint_index += 1
                raise TransientFailure(
                    f"HTTP {response.status_code} from {attempt_url}", delay,
                    status_code=response.status_code)
            if response.status_code >= 400:
                raise PermanentStatus(
                    url=attempt_url, status_code=response.status_code,
                    response_body=response.content
                )
            if max_bytes is None:
                response.read()  # body consumed inside the host slot (PA-1 R5)
            if scope is not None:
                scope.record_success()
            return response

    try:
        return _call()
    except TransientFailure as exc:
        raise RetryExhausted(attempts, url, str(exc)) from exc


def fetch_bytes(
    url: str,
    *,
    timeout_s: int = HTTP_TIMEOUT_SECONDS,
    max_bytes: int | None = None,
    headers: dict[str, str] | None = None,
) -> bytes:
    """GET a URL with the §11 retry policy: exponential backoff from 2 s,
    factor 2, jittered, at most 4 attempts, on connection errors, timeouts,
    429, and 5xx — never on other 4xx.

    After the last attempt, raises `SourceFetchError` with the URL and the
    final status or reason. HTTP 404 is a permanent miss (the URL constant is
    wrong or the resource moved) and is reported as such without retries.
    """
    return _fetch("GET", url, timeout_s=timeout_s, max_bytes=max_bytes, headers=headers)


def fetch_bytes_post(
    url: str, json_body: dict[str, object], *, timeout_s: int = HTTP_TIMEOUT_SECONDS
) -> bytes:
    """POST a JSON body to a URL with the same §11 retry policy as `fetch_bytes`.

    Needed by adapters whose source only accepts POST (TED's notice search).
    The body is sent as JSON; a 4xx response that is not 429 is a permanent
    miss and surfaces as `SourceFetchError` without retries.
    """
    return _fetch("POST", url, json_body=json_body, timeout_s=timeout_s)


def fetch_bytes_form(
    url: str, form_body: dict[str, str], *, read_timeout_s: float | None = None,
    fallback_urls: tuple[str, ...] = (),
) -> bytes:
    """POST URL-encoded form data through the shared source retry policy."""
    return _fetch("POST", url, form_body=form_body,
                  read_timeout_s=read_timeout_s, fallback_urls=fallback_urls)


def _fetch(
    method: str,
    url: str,
    *,
    json_body: dict[str, object] | None = None,
    form_body: dict[str, str] | None = None,
    timeout_s: int = HTTP_TIMEOUT_SECONDS,
    max_bytes: int | None = None,
    headers: dict[str, str] | None = None,
    read_timeout_s: float | None = None,
    fallback_urls: tuple[str, ...] = (),
) -> bytes:
    from limes.sources.acquisition import active_acquisition, request_key

    acquisition = active_acquisition.get()
    if acquisition is not None:
        acquisition.last_response_key = None
    key = request_key(method, url, json=json_body, form=form_body, headers=headers)
    if acquisition is not None and acquisition.source_id not in ("feeds", "osm"):
        # Poll every publisher again; a dead feed must not freeze healthy feeds.
        cached = acquisition.response(key)
        if cached is not None:
            if max_bytes is not None and len(cached) > max_bytes:
                raise SourceFetchError("cached source response exceeds byte limit")
            return cached
    try:
        response = request_with_retry(
            method,
            url,
            json_body=json_body,
            form_body=form_body,
            headers={"User-Agent": USER_AGENT, "Accept": "*/*", **(headers or {})},
            timeout_s=timeout_s,
            log=logger,
            max_bytes=max_bytes,
            read_timeout_s=read_timeout_s, fallback_urls=fallback_urls,
        )
    except httpx.DecodingError as exc:
        raise SourceFetchError("invalid source response encoding") from exc
    except PermanentStatus as exc:
        raise SourceFetchError(f"fetch failed: {exc.url} returned HTTP {exc.status_code}") from exc
    except RetryExhausted as exc:
        raise SourceFetchError(
            f"fetch failed after {exc.attempts} attempts: {exc.url} ({exc.reason})"
        ) from exc
    if acquisition is not None and acquisition.source_id != "osm":
        acquisition.save_response(key, response.content)
    return response.content


def now_utc() -> datetime:
    """The current UTC instant, timezone-aware. Adapters use this for
    `fetched_at` and, in the absence of a source-stated date, `valid_from`."""
    from limes.sources.acquisition import active_acquisition

    acquisition = active_acquisition.get()
    return (acquisition.last_fetched_at if acquisition is not None and acquisition.last_fetched_at
            else datetime.now(UTC))


# ---------------- PA-1 R5: cross-process per-host netiquette slots ----------------

HOST_SLOT_DIR = "/data/host-slots"
HOST_SLOT_WAIT_SECONDS = 10


def _host_key(url: str) -> str:
    """The netiquette key for a URL: overpass mirrors share one cap, every
    explicit override matches its domain suffix, everything else is per-host."""
    hostname = urlsplit(url).hostname or "unknown"
    if "overpass" in hostname:
        return "overpass"
    return hostname


def _host_cap(key: str) -> int:
    for suffix, cap in HOST_CONCURRENCY_OVERRIDES.items():
        if key == suffix or key.endswith("." + suffix) or (suffix in key and suffix == "overpass"):
            return cap
    return int(os.environ.get("LIMES_HOST_CONCURRENCY_DEFAULT", "2"))


def _acquire_host_slot(
    directory: Path, cap: int, deadline: float, key: str
) -> TextIO:
    while True:
        for index in range(cap):
            handle = (directory / f"{index}.lock").open("a")
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                handle.close()
                continue
            return handle
        if time.monotonic() >= deadline:
            raise SourceFetchError(
                f"host concurrency slot for {key} stayed busy past the "
                f"{os.environ.get('LIMES_HOST_SLOT_WAIT_SECONDS', '10')}s wait"
            )
        time.sleep(0.05)


@contextmanager
def host_slot(url: str) -> Iterator[None]:
    """PA-1 R5: acquire one per-host flock slot for a single HTTP request.

    Slots live at `$LIMES_HOST_SLOT_DIR/<key>/<i>.lock` (default
    `/data/host-slots`), counted to the host's cap (explicit override or
    `LIMES_HOST_CONCURRENCY_DEFAULT`). The bounded `LIMES_HOST_SLOT_WAIT_SECONDS`
    wait expires into a `SourceFetchError` — kernel crash semantics release
    the lock if a holder dies.
    """
    key = _host_key(url)
    cap = _host_cap(key)
    directory = Path(os.environ.get("LIMES_HOST_SLOT_DIR", HOST_SLOT_DIR)) / key
    directory.mkdir(parents=True, exist_ok=True)
    wait = float(os.environ.get("LIMES_HOST_SLOT_WAIT_SECONDS", str(HOST_SLOT_WAIT_SECONDS)))
    handle = _acquire_host_slot(directory, cap, time.monotonic() + wait, key)
    try:
        yield
    finally:
        fcntl.flock(handle, fcntl.LOCK_UN)
        handle.close()
