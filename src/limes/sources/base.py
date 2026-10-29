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

import hashlib
import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, runtime_checkable

import httpx
import structlog
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from limes.errors import SourceFetchError
from limes.types import (
    Assertion,
    EntityEndpoint,
    NormalizedRecord,
    Provenance,
    RawRecord,
    Validity,
)

logger = structlog.get_logger(__name__)

# The ontology artifact version the adapters emit against (ontology/ontology.yaml).
# One place to bump on migration (WP-31); the loader stamps nodes with the
# *loaded* ontology's version, so a stale constant here only mislabels
# assertions, never nodes.
ONTOLOGY_VERSION = "1.3.0"

# §11 retry policy, as module constants matching the §4.2 defaults: adapters
# are constructed without Settings (build_default_registry takes none), so the
# policy lives here, in one place.
HTTP_TIMEOUT_SECONDS = 60
HTTP_MAX_ATTEMPTS = 4

# Statuses that are retried per §11: 429 and 5xx. Never other 4xx.
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})

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
    """Internal marker: a transient failure the §11 policy may retry."""


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

    def __init__(self, url: str, status_code: int) -> None:
        super().__init__(f"HTTP {status_code} from {url}")
        self.url = url
        self.status_code = status_code


def request_with_retry(
    method: str,
    url: str,
    *,
    json_body: dict[str, Any] | None = None,
    form_body: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    timeout_s: float = HTTP_TIMEOUT_SECONDS,
    follow_redirects: bool = True,
    log: Any = logger,
    max_bytes: int | None = None,
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

    @retry(
        stop=stop_after_attempt(HTTP_MAX_ATTEMPTS),
        wait=wait_exponential_jitter(initial=2.0, max=60.0, jitter=2.0),
        retry=retry_if_exception(is_transient),
        before_sleep=before_sleep_log(log, logging.WARNING),
        reraise=True,
    )
    def _call() -> httpx.Response:
        nonlocal attempts
        attempts += 1
        with httpx.Client(
            timeout=httpx.Timeout(timeout_s),
            follow_redirects=follow_redirects,
            headers=headers,
        ) as client:
            try:
                if max_bytes is None:
                    response = (
                        client.post(url, data=form_body)
                        if form_body is not None
                        else client.post(url, json=json_body)
                        if method == "POST"
                        else client.get(url)
                    )
                else:
                    with client.stream(method, url, json=json_body, data=form_body) as streamed:
                        chunks = bytearray()
                        for chunk in streamed.iter_bytes():
                            if len(chunks) + len(chunk) > max_bytes:
                                raise SourceFetchError("source response exceeds byte limit")
                            chunks.extend(chunk)
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
                raise TransientFailure(str(exc)) from exc
            if response.status_code in RETRYABLE_STATUSES:
                raise TransientFailure(f"HTTP {response.status_code} from {url}")
            if response.status_code >= 400:
                raise PermanentStatus(url=url, status_code=response.status_code)
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


def fetch_bytes_form(url: str, form_body: dict[str, str]) -> bytes:
    """POST URL-encoded form data through the shared source retry policy."""
    return _fetch("POST", url, form_body=form_body)


def _fetch(
    method: str,
    url: str,
    *,
    json_body: dict[str, object] | None = None,
    form_body: dict[str, str] | None = None,
    timeout_s: int = HTTP_TIMEOUT_SECONDS,
    max_bytes: int | None = None,
    headers: dict[str, str] | None = None,
) -> bytes:
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
        )
    except httpx.DecodingError as exc:
        raise SourceFetchError("invalid source response encoding") from exc
    except PermanentStatus as exc:
        raise SourceFetchError(f"fetch failed: {exc.url} returned HTTP {exc.status_code}") from exc
    except RetryExhausted as exc:
        raise SourceFetchError(
            f"fetch failed after {exc.attempts} attempts: {exc.url} ({exc.reason})"
        ) from exc
    return response.content


def now_utc() -> datetime:
    """The current UTC instant, timezone-aware. Adapters use this for
    `fetched_at` and, in the absence of a source-stated date, `valid_from`."""
    return datetime.now(UTC)
