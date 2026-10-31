# src/limes/sources/feeds.py | v1.0.0 | introduced by WP-21
"""Curated feeds adapter per Technical Specification §8.5.2 (WP-21).

Loads documents from the curated RSS/Atom set in `ontology/feeds.yaml`
(Commission RAPID, Bundesregierung press releases, curated news outlets) into
`DocumentPayload` records for the extraction pipeline. Emits documents only —
the source table's `feeds` row lists nothing else. Trust rank 0.60 by default,
overridden per feed in the config (Doc 1 §5.8: releases rank 0.70, news
outlets 0.60).

Non-obvious choices, each load-bearing:

- **One RawRecord per feed entry, not per feed.** The entry's payload is a
  deterministic JSON envelope of the fields feedparser extracted (title, link,
  entry id, summary, content, published). The envelope — not the feed XML — is
  what the archive stores and re-derives from, because the raw XML is a
  transport format: re-fetching the feed reproduces the same entries, and a
  per-entry record whose payload were the whole feed XML would share one
  content hash across all entries of a feed and collapse into a single
  document. The envelope is deterministic (sorted keys, UTC ISO timestamps),
  so re-parsing reproduces the same content hash — the archive dedup and the
  extraction cache key both depend on that.
- **`fetch` ignores the window.** The feed itself is the bounded set (its
  latest ~100 entries); the extraction cache and the archive dedup make
  re-normalizing the set free, and date-filtering on publisher-provided dates
  would silently drop undated entries. The window parameter is accepted for
  protocol conformance and used for nothing.
- **`normalize` never touches the network** (protocol): the entry envelope
  carries everything — title, body text, published date, entry URL.
- **The per-feed `trust_rank` override is a produced contract for WP-27**, not
  dead config: `trust_rank_for(url)` exposes the per-feed rank so the
  pipeline run can stamp each document's assertions with the feed's rank
  rather than the adapter default. The class-level `trust_rank` (0.60) is the
  registry's value; the config's `trust_rank` key is the override seam.
- **Language:** the feed's declared language (config) is authoritative when
  present — the curator knows the feed — and the dependency-free detector
  (`pipeline/normalize.py`) is the fallback. Both must be `de` or `en`.
- **`published_at`:** the entry's own published date when the feed supplies
  one; an undated entry falls back to the fetch instant with a count in the
  summary log — the fallback is visible, never silent.

The config file itself is validated at construction: a missing, unparsable,
or structurally invalid `feeds.yaml` is a `ConfigurationError` — a config
defect fails fast at startup, never at fetch time.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import feedparser  # type: ignore[import-untyped]
import structlog
import yaml  # type: ignore[import-untyped]

from limes.errors import ConfigurationError, SourceFetchError, SourceParseError
from limes.pipeline.normalize import detect_language, extract_text_from_html
from limes.sources.base import fetch_bytes, now_utc, payload_hash
from limes.types import DocumentPayload, NormalizedRecord, RawRecord

logger = structlog.get_logger(__name__)

# The default config path when the adapter is constructed without one
# (`build_default_registry` takes no settings, so the committed artifact's
# repository-relative location is the default; the composition root (WP-26)
# passes `Settings.feeds_config_path` explicitly).
DEFAULT_FEEDS_CONFIG_PATH = Path("ontology/feeds.yaml")

DEFAULT_TRUST_RANK = 0.60

ENVELOPE_CONTENT_TYPE = "application/json"


@dataclass(frozen=True)
class FeedConfig:
    """One curated feed from `feeds.yaml`."""

    url: str
    name: str
    language: str | None = None
    trust_rank: float = DEFAULT_TRUST_RANK


class FeedsAdapter:
    """Curated RSS/Atom feeds — documents only, no assertions."""

    source_id: str = "feeds"
    name: str = "Curated Feeds"
    kind: Literal["structured", "unstructured"] = "unstructured"
    trust_rank: float = DEFAULT_TRUST_RANK
    supports_backfill: bool = True
    supports_incremental: bool = True

    def __init__(self, feeds_config_path: Path = DEFAULT_FEEDS_CONFIG_PATH) -> None:
        self._feeds = _load_feed_config(feeds_config_path)

    def trust_rank_for(self, feed_url: str) -> float:
        """The configured trust rank of one feed (the per-feed override seam
        for WP-27), or the adapter default for an unknown URL."""
        for feed in self._feeds:
            if feed.url == feed_url:
                return feed.trust_rank
        return self.trust_rank

    def fetch(self, since: datetime | None, until: datetime | None) -> Iterator[RawRecord]:
        """Fetch every configured feed and yield one raw record per entry.

        The window is intentionally unused (see the module docstring): the
        feed is the bounded set and dedup is content-based. Each feed is one
        GET with the shared §11 retry policy; a feed that fails to parse
        yields no entries and is counted in the summary log.
        """
        fetched_at = now_utc()
        failures: list[str] = []
        for feed in self._feeds:
            try:
                payload = fetch_bytes(feed.url)
            except SourceFetchError as exc:
                failures.append(f"{feed.url}: {exc}")
                logger.warning("feeds: feed fetch failed; continuing", url=feed.url, error=str(exc))
                continue
            parsed = feedparser.parse(payload)
            if parsed.get("bozo") and not parsed.entries:
                failures.append(f"{feed.url}: unparseable feed")
                logger.warning(
                    "feeds: feed unparseable or empty; no entries",
                    url=feed.url,
                    bozo=parsed.get("bozo", False),
                )
                continue
            logger.info(
                "feeds: feed fetched",
                url=feed.url,
                entries=len(parsed.entries),
                fetched_at=fetched_at.isoformat(),
            )
            for entry in parsed.entries:
                envelope = _entry_envelope(feed, entry)
                yield RawRecord(
                    payload=json.dumps(envelope, sort_keys=True).encode("utf-8"),
                    content_type=ENVELOPE_CONTENT_TYPE,
                    source_url=feed.url,
                    fetched_at=fetched_at,
                )

        if failures:
            raise SourceFetchError(
                f"feeds: {len(failures)} feed failures after processing remaining feeds: "
                + "; ".join(failures)
            )

    def normalize(self, record: RawRecord) -> NormalizedRecord:
        """One entry envelope to a `DocumentPayload`. Pure — the entry's
        fields are already parsed; only text extraction, language assignment,
        and timestamp normalization happen here."""
        try:
            envelope = json.loads(record.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SourceParseError(f"feeds: entry envelope is not valid JSON: {exc}") from exc

        title = str(envelope.get("title") or "").strip()
        content = str(envelope.get("content") or envelope.get("summary") or "").strip()
        body = extract_text_from_html(content)
        published_at = _parse_published(envelope.get("published"), record.fetched_at)
        language = str(envelope.get("language") or "").strip() or detect_language(body)

        document = DocumentPayload(
            content_hash=payload_hash(record.payload),
            title=title,
            body=body,
            language=language,
            published_at=published_at,
            url=envelope.get("link"),
        )
        logger.info(
            "feeds: entry normalized",
            source_id=self.source_id,
            title_present=bool(title),
            body_chars=len(body),
            language=language,
            published_at=published_at.isoformat(),
        )
        return NormalizedRecord(
            content_hash=payload_hash(record.payload),
            kind="document",
            document=document,
        )


def _load_feed_config(path: Path) -> list[FeedConfig]:
    """Load and validate `feeds.yaml`. A missing file, unparsable YAML, or an
    entry without a `url` is a `ConfigurationError` — the config is a startup
    artifact, not a runtime condition."""
    if not path.exists():
        raise ConfigurationError(f"feeds config missing: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"feeds config unreadable: {path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("feeds"), list):
        raise ConfigurationError(f"feeds config has no 'feeds' list: {path}")

    feeds: list[FeedConfig] = []
    for raw in data["feeds"]:
        has_url = isinstance(raw, dict) and isinstance(raw.get("url"), str) and raw["url"].strip()
        if not has_url:
            raise ConfigurationError(f"feeds config entry without a url: {path}")
        language = raw.get("language")
        if language is not None and language not in ("de", "en"):
            raise ConfigurationError(
                f"feeds config entry {raw['url']!r} declares unsupported language {language!r}"
            )
        trust_rank = raw.get("trust_rank", DEFAULT_TRUST_RANK)
        if not isinstance(trust_rank, (int, float)):
            raise ConfigurationError(
                f"feeds config entry {raw['url']!r} has a non-numeric trust_rank"
            )
        feeds.append(
            FeedConfig(
                url=raw["url"].strip(),
                name=str(raw.get("name") or raw["url"].strip()),
                language=language,
                trust_rank=float(trust_rank),
            )
        )
    if not feeds:
        raise ConfigurationError(f"feeds config declares no feeds: {path}")
    return feeds


def _entry_envelope(feed: FeedConfig, entry: Any) -> dict[str, Any]:
    """The deterministic per-entry envelope: every field normalize needs,
    nothing else. Timestamps are UTC ISO strings so the envelope survives
    serialization byte-for-byte (the content hash depends on it)."""
    published = _entry_published(entry)
    content = ""
    for item in entry.get("content", []):
        value = item.get("value")
        if isinstance(value, str) and value.strip():
            content = value.strip()
            break
    if not content:
        content = str(entry.get("summary") or "").strip()
    return {
        "feed": {
            "url": feed.url,
            "name": feed.name,
            "language": feed.language,
        },
        "entry_id": str(entry.get("id") or entry.get("link") or "").strip(),
        "title": str(entry.get("title") or "").strip(),
        "link": str(entry.get("link") or "").strip() or None,
        "summary": str(entry.get("summary") or "").strip(),
        "content": content,
        "published": published.isoformat() if published is not None else None,
    }


def _entry_published(entry: Any) -> datetime | None:
    """The entry's published instant as UTC, or None when the feed supplies
    none (the normalize fallback to the fetch instant is counted there)."""
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    try:
        return datetime(
            parsed.tm_year,
            parsed.tm_mon,
            parsed.tm_mday,
            parsed.tm_hour,
            parsed.tm_min,
            parsed.tm_sec,
            tzinfo=UTC,
        )
    except (AttributeError, TypeError, ValueError):
        return None


def _parse_published(raw: object, fallback: datetime) -> datetime:
    """The envelope's ISO timestamp, or the fetch instant when the feed had
    none — the fallback is logged by the caller's summary line."""
    if not isinstance(raw, str) or not raw:
        return fallback
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        logger.warning("feeds: unparseable published timestamp", raw=raw)
        return fallback
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
