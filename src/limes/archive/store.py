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
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, cast


class ArchiveStore:
    """Durable, compressed, content-addressed storage of raw payloads."""

    def __init__(self, root: Path, *, create: bool = True) -> None:
        """Store the archive root, creating it if absent."""
        self._root = root
        if create:
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
            with temp_path.open("wb") as output:
                output.write(gzip.compress(payload))
                output.flush()
                os.fsync(output.fileno())
            os.replace(temp_path, final_path)
            descriptor = os.open(final_path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        finally:
            temp_path.unlink(missing_ok=True)
        return content_hash

    def get(self, content_hash: str) -> bytes:
        """Return the exact original bytes stored under `content_hash`.
        Raises `FileNotFoundError` when the hash is not in the archive."""
        with gzip.open(self.path_for(content_hash), "rb") as handle:
            return handle.read()

    def put_file(self, path: Path) -> str:
        """Archive a large source artifact with bounded memory and durable publication."""
        digest = hashlib.sha256()
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
        content_hash = digest.hexdigest()
        final = self.path_for(content_hash)
        if final.exists():
            return content_hash
        final.parent.mkdir(parents=True, exist_ok=True)
        temporary = final.with_name(f".tmp-{uuid.uuid4().hex}")
        try:
            with path.open("rb") as source, temporary.open("wb") as output:
                with gzip.GzipFile(fileobj=output, mode="wb") as compressed:
                    while chunk := source.read(1024 * 1024):
                        compressed.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, final)
            descriptor = os.open(final.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        finally:
            temporary.unlink(missing_ok=True)
        return content_hash

    @contextmanager
    def open(self, content_hash: str) -> Iterator[BinaryIO]:
        """Stream the original artifact instead of expanding it into RAM."""
        with gzip.open(self.path_for(content_hash), "rb") as handle:
            yield cast(BinaryIO, handle)

    def preview(self, content_hash: str, limit: int = 65536) -> tuple[bytes, bool]:
        """Bound decompression for interactive evidence inspection, including old archives."""
        import re

        if not re.fullmatch(r"[0-9a-f]{64}", content_hash) or not 1 <= limit <= 65536:
            raise ValueError("invalid archive hash or preview limit")
        with gzip.open(self.path_for(content_hash), "rb") as handle:
            payload = handle.read(limit + 1)
        return payload[:limit], len(payload) > limit

    def exists(self, content_hash: str) -> bool:
        """Whether the archive holds `content_hash`."""
        return self.path_for(content_hash).exists()

    def path_for(self, content_hash: str) -> Path:
        """The full path a hash is stored at: `ab/cd/<hash>` under the root."""
        return self._root / content_hash[:2] / content_hash[2:4] / content_hash
