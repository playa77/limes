# src/limes/logging_setup.py | v1.0.0 | introduced by WP-02
"""Structured logging per Technical Specification §10.

JSON log lines with `run_id`, `source_id`, `module`, and `event` on every
line. A redaction processor masks values whose keys match a configured
secret-key list (`LIMES_OPENROUTER_API_KEY`, `LIMES_NEO4J_PASSWORD`, and
anything added later) before emission, so the API key never reaches a log
line (§7.4). Configuration is per-process; the composition root (WP-26) calls
`configure_logging` once at startup.
"""

from __future__ import annotations

import logging
from collections.abc import MutableMapping
from typing import Any

import structlog

from limes.config import Settings

DEFAULT_SECRET_KEYS = ("LIMES_OPENROUTER_API_KEY", "LIMES_NEO4J_PASSWORD")

REDACTED = "***REDACTED***"


class SecretRedactor:
    """Mask values of keys whose names match a secret key. A key matches when
    it contains the secret name or is contained by it, case-insensitively, so
    `LIMES_OPENROUTER_API_KEY`, `openrouter_api_key`, and `api_key` all
    redact. Applies recursively to nested dicts and lists."""

    def __init__(self, secret_keys: tuple[str, ...] = DEFAULT_SECRET_KEYS) -> None:
        self._needles = tuple(k.lower() for k in secret_keys)

    def _redact(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                k: (
                    REDACTED
                    if any(n in k.lower() or k.lower() in n for n in self._needles)
                    else self._redact(v)
                )
                for k, v in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [self._redact(v) for v in value]
        return value

    def __call__(
        self, _logger: Any, _method: str, event_dict: MutableMapping[str, Any]
    ) -> MutableMapping[str, Any]:
        redacted = self._redact(event_dict)
        assert isinstance(redacted, dict)
        return redacted


def configure_logging(
    settings: Settings,
    secret_keys: tuple[str, ...] = DEFAULT_SECRET_KEYS,
) -> None:
    """Configure structlog for this process.

    JSON by default; `console` renders human-readable lines for development.
    The log level is taken from `LIMES_LOG_LEVEL`. `run_id`/`source_id` are
    expected to be bound via `structlog.contextvars` by the composition root
    or the CLI; `module` is captured from the logging call site.
    """
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    renderer = (
        structlog.processors.JSONRenderer()
        if settings.log_format == "json"
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.CallsiteParameterAdder(
                [
                    structlog.processors.CallsiteParameter.MODULE,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                ]
            ),
            SecretRedactor(secret_keys),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )
