"""Persistent investigation lifecycle on the existing operational SQLite volume."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from limes.news.models import Investigation, TrackingRequest
from limes.operations.models import JobRequest
from limes.operations.store import JobStore


class TrackingStore(JobStore):
    def __init__(self, path: Path) -> None:
        super().__init__(path)
        with self.connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS investigations (id TEXT PRIMARY KEY, data TEXT)")

    def list(self) -> list[Investigation]:
        with self.connection() as db:
            rows = db.execute("SELECT data FROM investigations ORDER BY id LIMIT 257").fetchall()
        return [Investigation.model_validate_json(row[0]) for row in rows]

    def get_investigation(self, key: str) -> Investigation | None:
        with self.connection() as db:
            row = db.execute("SELECT data FROM investigations WHERE id=?", (key,)).fetchone()
        return Investigation.model_validate_json(row[0]) if row else None

    def save(self, request: TrackingRequest) -> Investigation:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT data FROM investigations WHERE id=?", (request.investigation_id,)
            ).fetchone()
            old = Investigation.model_validate_json(row[0]) if row else None
            if (
                old is None
                and db.execute("SELECT count(*) FROM investigations").fetchone()[0] >= 256
            ):
                raise OverflowError("investigation limit reached")
            outstanding = self.get(old.job_id) if old and old.job_id else None
            preserve = outstanding and outstanding.status in ("queued", "running", "failed")
            item = Investigation(
                **request.model_dump(),
                revision=(old.revision + 1 if old else 1),
                last_success=old.last_success if old else None,
                # Preserve an outstanding job so an update cannot queue overlapping acquisition.
                job_id=old.job_id if old and preserve else None,
                status="ready" if request.active else "paused",
            )
            db.execute(
                "INSERT OR REPLACE INTO investigations VALUES(?,?)",
                (item.investigation_id, item.model_dump_json()),
            )
        return item

    def schedule(self, now: datetime | None = None) -> None:
        """Only fresh cycles are automatic; failure/interruption needs explicit replay.

        Job UUID is persisted before submission. A crash between those steps resumes
        the same idempotent submission; it cannot lose or duplicate the cycle.
        """
        now = now or datetime.now(UTC)
        for item in self.list():
            if not item.active:
                continue
            if item.job_id:
                job = self.get(item.job_id)
                if job is None:
                    self.submit(
                        JobRequest(
                            request_id=UUID(item.job_id),
                            command="news-refresh",
                            investigation_id=item.investigation_id,
                        )
                    )
                    continue
                if job.status in ("queued", "running"):
                    self._update(item.investigation_id, status=job.status)
                    continue
                if job.status == "failed":
                    self._update(item.investigation_id, status="failed")
                    continue
                if item.status != "succeeded":
                    self._update(
                        item.investigation_id,
                        status="succeeded",
                        last_success=job.updated_at,
                        next_due=(now + timedelta(minutes=item.interval_minutes)).isoformat(),
                    )
                    continue
            if item.next_due and datetime.fromisoformat(item.next_due) > now:
                continue
            key = str(uuid4())
            self._update(item.investigation_id, job_id=key, status="queued")
            self.submit(
                JobRequest(
                    request_id=UUID(key),
                    command="news-refresh",
                    investigation_id=item.investigation_id,
                )
            )

    def replay(self, key: str) -> Investigation:
        item = self.get_investigation(key)
        if item is None:
            raise KeyError(key)
        if item.job_id and (job := self.get(item.job_id)) and job.status in ("queued", "running"):
            raise ValueError("acquisition already pending")
        self._update(key, job_id=None, next_due=None, status="ready")
        return self.get_investigation(key) or item

    def _update(self, key: str, **values: object) -> None:
        # Merge into the latest revision; a completed cycle must not overwrite a pause/edit.
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT data FROM investigations WHERE id=?", (key,)).fetchone()
            if row:
                data = json.loads(row[0])
                data.update(values)
                db.execute("UPDATE investigations SET data=? WHERE id=?", (json.dumps(data), key))
