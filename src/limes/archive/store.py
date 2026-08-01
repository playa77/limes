# src/limes/archive/store.py | v1.0.0 | introduced by WP-05
"""Content-addressed raw payload archive per Technical Specification §8.4.

The archive is the system of record from which the entire graph is
re-derivable (Doc 1 §4.2): every fetched payload is stored under its SHA-256
content hash, gzip-compressed, in a two-level hex prefix directory, written
atomically by temporary name and rename. `put` is idempotent — the same
payload returns the same hash and writes nothing twice — which is what makes
re-ingestion free at the storage layer while the version triple is unchanged
(Doc 2 §8.3, AC-33).
"""

from __future__ import annotations

import gzip
import hashlib
import os
import uuid
from pathlib import Path


class ArchiveStore:
    """Durable, compressed, content-addressed storage of raw payloads."""

    def __init__(self, root: Path) -> None:
        """Store the archive root, creating it if absent."""
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def put(self, source_id: str, payload: bytes, content_type: str) -> str:
        """Store `payload` gzip-compressed under its SHA-256 content hash and
        return the hash. Idempotent: an existing hash is a no-op returning
        the same value. The write is atomic — a temporary name is renamed
        over the final path, so a crash never leaves a partial file."""
        del source_id, content_type  # interface contract (§8.4): the hash
        # addresses the content, not the source or type
        content_hash = hashlib.sha256(payload).hexdigest()
        final_path = self.path_for(content_hash)
        if final_path.exists():
            return content_hash

        final_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = final_path.with_name(f".tmp-{uuid.uuid4().hex}")
        try:
            temp_path.write_bytes(gzip.compress(payload))
            os.replace(temp_path, final_path)
        finally:
            temp_path.unlink(missing_ok=True)
        return content_hash

    def get(self, content_hash: str) -> bytes:
        """Return the exact original bytes stored under `content_hash`.
        Raises `FileNotFoundError` when the hash is not in the archive."""
        with gzip.open(self.path_for(content_hash), "rb") as handle:
            return handle.read()

    def exists(self, content_hash: str) -> bool:
        """Whether the archive holds `content_hash`."""
        return self.path_for(content_hash).exists()

    def path_for(self, content_hash: str) -> Path:
        """The full path a hash is stored at: `ab/cd/<hash>` under the root."""
        return self._root / content_hash[:2] / content_hash[2:4] / content_hash
