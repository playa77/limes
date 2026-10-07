# src/limes/config_files.py | v1.0.0 | atomic non-secret model configuration
"""Update model pins without ever opening the secret configuration file."""

from __future__ import annotations

import fcntl
import os
import re
import tempfile
from pathlib import Path

from dotenv import dotenv_values

from limes.errors import ConfigurationError

MODEL_KEYS = frozenset(
    {
        "LIMES_EXTRACTION_MODEL",
        "LIMES_ADJUDICATION_MODEL",
        "LIMES_EMBEDDING_MODEL",
        "LIMES_NL2CYPHER_MODEL",
        "LIMES_MODEL_PIN_STAGE",
        "LIMES_MODEL_PIN_DATE",
    }
)


def update_model_pins(path: Path, updates: dict[str, str]) -> None:
    """Serialize writers and atomically replace a validated pin-only file.

    The separate lock survives rename. Identical updates leave the file intact.
    A failed write leaves the previous pins usable.
    """
    if not updates.keys() <= MODEL_KEYS:
        raise ConfigurationError("model configuration contains a non-model key")
    if path.name in {".env", "secrets.env", "settings.env"}:
        raise ConfigurationError("model pins must use a dedicated model configuration file")
    if any(not re.fullmatch(r"[A-Za-z0-9._/@:+-]+", value) for value in updates.values()):
        raise ConfigurationError("model pin values must be nonempty single tokens")
    if path.is_symlink():
        raise ConfigurationError("model configuration must not be a symbolic link")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(path.suffix + ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        previous = dict(dotenv_values(path, interpolate=False)) if path.exists() else {}
        if not previous.keys() <= MODEL_KEYS:
            raise ConfigurationError("model configuration contains a non-model key")
        values = {**previous, **updates}
        if any(
            value and not re.fullmatch(r"[A-Za-z0-9._/@:+-]+", value) for value in values.values()
        ):
            raise ConfigurationError("model configuration contains an invalid value")
        content = "".join(f"{key}={value}\n" for key, value in sorted(values.items()))
        if path.exists() and path.read_text(encoding="utf-8") == content:
            return
        atomic_write_text(path, content)


def atomic_write_text(path: Path, content: str) -> None:
    """Publish a complete configuration/report, preserving old data on failure."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".models-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
