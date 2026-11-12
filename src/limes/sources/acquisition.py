"""Durable source acquisition and load receipts, independent of graph checkpoints.

An interrupted invocation resumes its pinned window and successful HTTP responses.
Only records loaded without errors receive receipts. A receipt is written AFTER
the graph write, so a crash can cause an idempotent replay but cannot lose work.
Source checkpoints advance only after iterator exhaustion and clean processing.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sqlite3
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from limes.archive.store import ArchiveStore
from limes.data_scope import DATA_SCOPE_VERSION, require_source_date
from limes.errors import SourceFetchError
from limes.types import RawRecord

active_acquisition: ContextVar[AcquisitionSession | None] = ContextVar(
    "limes_acquisition", default=None
)


def request_key(method: str, url: str | None, **parameters: Any) -> str:
    """Only the digest is persisted; authorization headers never enter the journal."""
    return hashlib.sha256(json.dumps(
        [method, url, parameters], sort_keys=True, default=str
    ).encode()).hexdigest()


class AcquisitionStore:
    def __init__(self, archive: ArchiveStore, root: Path) -> None:
        self.archive = archive
        self.root = root

    @contextmanager
    def session(
        self, source_id: str, request: dict[str, Any], version: str
    ) -> Iterator[AcquisitionSession]:
        # source_id comes from the registered adapter, not an arbitrary file path.
        directory = self.root / DATA_SCOPE_VERSION / hashlib.sha256(source_id.encode()).hexdigest()
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / "lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise SourceFetchError(f"{source_id}: acquisition already active") from exc
            connection = sqlite3.connect(directory / "progress.sqlite3")
            try:
                session = AcquisitionSession(connection, self.archive, directory, source_id)
                session.begin(request, version)
                token = active_acquisition.set(session)
                try:
                    yield session
                finally:
                    active_acquisition.reset(token)
            finally:
                connection.close()
                fcntl.flock(lock, fcntl.LOCK_UN)


class AcquisitionSession:
    def __init__(
        self, db: sqlite3.Connection, archive: ArchiveStore, directory: Path, source_id: str
    ) -> None:
        self.db = db
        self.archive = archive
        self.directory = directory
        self.source_id = source_id
        self.version = ""
        self.started_at = datetime.now(UTC)
        self.progress: Callable[[str, str | None], None] | None = None
        self.flush: Callable[[], None] | None = None
        self.last_response_key: str | None = None
        self.new_loads = 0
        self.new_responses = 0
        self.last_fetched_at: datetime | None = None
        self.incomplete_reason: str | None = None
        self.db.executescript("""
            PRAGMA synchronous=FULL;
            CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS responses (
                key TEXT PRIMARY KEY, hash TEXT NOT NULL, fetched_at TEXT);
            CREATE TABLE IF NOT EXISTS loaded (
                key TEXT PRIMARY KEY, version TEXT NOT NULL, unit TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS units (
                key TEXT PRIMARY KEY, version TEXT NOT NULL, records INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS loaded_unit_version ON loaded(unit, version);
        """)
        columns = {row[1] for row in self.db.execute("PRAGMA table_info(responses)")}
        if "fetched_at" not in columns:
            self.db.execute("ALTER TABLE responses ADD COLUMN fetched_at TEXT")

    def begin(self, request: dict[str, Any], version: str) -> None:
        signature = json.dumps(request, sort_keys=True, default=str)
        previous = self._get("request")
        if previous is not None and previous != signature:
            raise SourceFetchError(
                f"{self.source_id}: unfinished acquisition for another request; "
                "resume the original request before changing its window"
            )
        self.version = version
        if previous is None:
            self._set("request", signature)
            self._set("started_at", self.started_at.isoformat())
        else:
            started = self._get("started_at")
            if started is None:
                raise SourceFetchError("acquisition: missing start timestamp")
            self.started_at = datetime.fromisoformat(started)

    def window(
        self, since: datetime | None, until: datetime | None
    ) -> tuple[datetime | None, datetime | None]:
        previous = self._get("window")
        if previous is None:
            # Freeze the upper bound even when the original request omitted it.
            until = until or self.started_at
            self._set("window", json.dumps([
                since.isoformat() if since else None, until.isoformat()
            ]))
            return since, until
        values = json.loads(previous)
        return tuple(datetime.fromisoformat(v) if v else None for v in values)  # type: ignore[return-value]

    def response_hash(self, key: str) -> str | None:
        row = self.db.execute(
            "SELECT hash, fetched_at FROM responses WHERE key=?", (key,)
        ).fetchone()
        if row:
            self.last_response_key = key
            self.last_fetched_at = (datetime.fromisoformat(row[1]) if row[1] else
                                    datetime.fromtimestamp(
                                        self.archive.path_for(row[0]).stat().st_mtime, UTC))
        return str(row[0]) if row else None

    def response(self, key: str) -> bytes | None:
        digest = self.response_hash(key)
        if digest is None:
            return None
        if self.last_fetched_at is not None:
            require_source_date(self.last_fetched_at, self.source_id)
        payload = self.archive.get(digest)
        if hashlib.sha256(payload).hexdigest() != digest:
            raise SourceFetchError("acquisition: cached response hash mismatch")
        return payload

    def save_response(self, key: str, payload: bytes) -> None:
        digest = self.archive.put(self.source_id, payload, "application/octet-stream")
        self.save_response_hash(key, digest)

    def save_response_hash(self, key: str, digest: str) -> None:
        fetched_at = datetime.now(UTC)
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO responses VALUES (?, ?, ?)", (
                key, digest, fetched_at.isoformat()
            ))
        self.last_response_key = key
        self.last_fetched_at = fetched_at
        self.new_responses += 1

    def discard_last_response(self) -> None:
        """A successfully downloaded but invalid response must be refreshable."""
        if self.last_response_key is not None:
            with self.db:
                self.db.execute("DELETE FROM responses WHERE key=?", (self.last_response_key,))

    def invalidate(self, raw: RawRecord) -> None:
        hashes = [hashlib.sha256(raw.payload).hexdigest(),
                  str((raw.acquisition_context or {}).get("source_archive_hash", ""))]
        with self.db:
            self.db.execute("DELETE FROM responses WHERE hash IN (?, ?)", hashes)

    def record_key(self, raw: RawRecord) -> str:
        digest = hashlib.sha256(raw.payload).hexdigest()
        context = {key: value for key, value in (raw.acquisition_context or {}).items()
                   if key != "manifest_hash"}
        return request_key("RECORD", raw.source_url, payload=digest, context=context)

    def is_loaded(self, raw: RawRecord) -> bool:
        return self.db.execute(
            "SELECT 1 FROM loaded WHERE key=? AND version=?", (self.record_key(raw), self.version)
        ).fetchone() is not None

    def acknowledge(self, raw: RawRecord) -> None:
        with self.db:
            cursor = self.db.execute("""INSERT INTO loaded VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET version=excluded.version, unit=excluded.unit
                WHERE loaded.version<>excluded.version""", (
                self.record_key(raw), self.version,
                str((raw.acquisition_context or {}).get("unit", "")),
            ))
        self.new_loads += cursor.rowcount

    def unit_loaded(self, key: str) -> bool:
        return self.db.execute(
            "SELECT 1 FROM units WHERE key=? AND version=?", (key, self.version)
        ).fetchone() is not None

    def finish_unit(self, key: str, record_keys: list[str]) -> None:
        if self.flush is not None:
            self.flush()
        # Compare this traversal's actual inventory. A prior malformed response
        # may have been refreshed: equally many stale receipts are not proof
        # that the changed package's current members have all loaded.
        if record_keys and all(self.db.execute(
            "SELECT 1 FROM loaded WHERE key=? AND unit=? AND version=?",
            (record_key, key, self.version),
        ).fetchone() is not None for record_key in record_keys):
            with self.db:
                self.db.execute("INSERT OR REPLACE INTO units VALUES (?, ?, ?)", (
                    key, self.version, len(record_keys)
                ))

    def complete(self) -> None:
        """Retire only AFTER the graph's complete-window checkpoint is committed."""
        with self.db:
            self.db.execute("DELETE FROM state")
            self.db.execute("DELETE FROM responses")
            self.db.execute("DELETE FROM loaded")
            self.db.execute("DELETE FROM units")
        for path in self.directory.glob("*.part"):
            path.unlink(missing_ok=True)

    def manifest(self) -> str:
        """Retain the complete inventory/receipts after retiring the active cursor."""
        with tempfile.TemporaryDirectory(dir=self.directory) as temporary:
            path = Path(temporary) / "inventory.sqlite3"
            destination = sqlite3.connect(path)
            try:
                self.db.backup(destination)
            finally:
                destination.close()
            inventory_hash = self.archive.put_file(path)
        counts = {
            table: self.db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("responses", "loaded", "units")
        }
        payload = json.dumps({
            "source_id": self.source_id, "version": self.version,
            "request": json.loads(self._get("request") or "{}"),
            "window": json.loads(self._get("window") or "null"),
            "started_at": self.started_at.isoformat(),
            "completed_at": datetime.now(UTC).isoformat(),
            "inventory_hash": inventory_hash, "counts": counts,
        }, sort_keys=True).encode()
        return self.archive.put(self.source_id, payload, "application/json")

    def _get(self, key: str) -> str | None:
        row = self.db.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return str(row[0]) if row else None

    def _set(self, key: str, value: str) -> None:
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO state VALUES (?, ?)", (key, value))
        # SQLite FULL sync makes the journal durable before progress is used.
        descriptor = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
