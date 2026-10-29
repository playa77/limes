"""SQLite queue on a local named volume; transactions serialize competing writers."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path

from limes.operations.models import Job, JobRequest

OUTPUT_LIMIT = 32768


def output_tail(value: str) -> str:
    return value.encode()[-OUTPUT_LIMIT:].decode(errors="ignore")


class JobStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, request TEXT NOT NULL, status TEXT NOT NULL,
                created TEXT NOT NULL, updated TEXT NOT NULL,
                output TEXT NOT NULL DEFAULT '', exit_code INTEGER)""")

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        with closing(sqlite3.connect(self.path, timeout=30)) as db, db:
            db.row_factory = sqlite3.Row
            yield db

    @staticmethod
    def now() -> str:
        return datetime.now(UTC).isoformat()

    def submit(self, request: JobRequest) -> Job:
        key, payload = str(request.request_id), request.model_dump_json()
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT request FROM jobs WHERE id = ?", (key,)).fetchone()
            if existing:
                # Additive request fields must not break reconnect idempotency
                # for operations persisted by an older worker/API version.
                if JobRequest.model_validate_json(existing["request"]) != request:
                    raise ValueError("request_id already belongs to a different operation")
            else:
                count = db.execute(
                    "SELECT count(*) FROM jobs WHERE status IN ('queued', 'running')"
                ).fetchone()[0]
                if count >= 256:
                    raise OverflowError("operational queue is full")
                now = self.now()
                db.execute(
                    "INSERT INTO jobs(id, request, status, created, updated) VALUES(?,?,?,?,?)",
                    (key, payload, "queued", now, now),
                )
        result = self.get(key)
        assert result is not None
        return result

    def get(self, key: str) -> Job | None:
        with self.connection() as db:
            row = db.execute("SELECT * FROM jobs WHERE id = ?", (key,)).fetchone()
        if row is None:
            return None
        return Job(
            job_id=row["id"],
            request=JobRequest.model_validate_json(row["request"]),
            status=row["status"],
            created_at=row["created"],
            updated_at=row["updated"],
            output=row["output"],
            exit_code=row["exit_code"],
        )

    def claim(self) -> Job | None:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT id FROM jobs WHERE status = 'queued' ORDER BY created, id LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            db.execute(
                "UPDATE jobs SET status = 'running', updated = ? WHERE id = ?",
                (self.now(), row["id"]),
            )
        return self.get(row["id"])

    def finish(self, key: str, code: int, output: str) -> None:
        with self.connection() as db:
            db.execute(
                "UPDATE jobs SET status=?, exit_code=?, output=?, updated=? WHERE id=?",
                (
                    "succeeded" if code == 0 else "failed",
                    code,
                    output_tail(output),
                    self.now(),
                    key,
                ),
            )

    def output(self, key: str, output: str) -> None:
        with self.connection() as db:
            db.execute(
                "UPDATE jobs SET output=?, updated=? WHERE id=?",
                (output_tail(output), self.now(), key),
            )

    def recover(self) -> None:
        # Never replay an interrupted operation: it may already have spent money or written data.
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("SELECT id, output FROM jobs WHERE status='running'").fetchall()
            for row in rows:
                output = output_tail(
                    row["output"]
                    + "\nWorker interrupted; inspect results before submitting a new job."
                )
                db.execute(
                    "UPDATE jobs SET status='failed', exit_code=1, updated=?, output=? WHERE id=?",
                    (self.now(), output, row["id"]),
                )
