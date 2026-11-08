# tests/unit/test_pa1_jobs.py | PA-1 | job pool, cancellation and store migration
"""PA-1 IP-1 unit tests: cancel surface, worker pool and store migration."""

from __future__ import annotations

import sqlite3
import sys
import threading
import time
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from limes.api.main import create_app
from limes.operations.models import Job, JobRequest
from limes.operations.store import JobStore
from limes.operations import worker


def request(command: str = "backup", **kwargs) -> JobRequest:
    return JobRequest(request_id=uuid4(), command=command, **kwargs)


def _legacy_store(path) -> JobStore:
    """A jobs table in the pre-PA-1 shape, without `cancel_requested`."""
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE jobs (id TEXT PRIMARY KEY, request TEXT NOT NULL, status TEXT NOT NULL,"
        " created TEXT NOT NULL, updated TEXT NOT NULL,"
        " output TEXT NOT NULL DEFAULT '', exit_code INTEGER)"
    )
    conn.commit()
    conn.close()


def test_store_migrates_legacy_jobs_without_cancel_column(tmp_path):
    path = tmp_path / "jobs.sqlite3"
    _legacy_store(path)
    store = JobStore(path)
    job = store.submit(request())
    store.claim()
    conn = sqlite3.connect(path)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
    conn.close()
    assert "cancel_requested" in columns
    migrated = store.get(str(job.job_id))
    assert migrated.status == "running"


def test_cancel_queued_job_is_immediately_cancelled(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    job = store.submit(request())
    result = store.request_cancel(str(job.job_id))
    assert result.status == "cancelled"
    assert result.exit_code is None
    assert "cancel" in result.output.lower()
    assert store.claim() is None


def test_worker_sees_cancel_requests(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    job = store.submit(request())
    claimed = store.claim()
    assert store.cancel_requested_ids() == set()
    store.request_cancel(str(claimed.job_id))
    assert store.cancel_requested_ids() == {str(job.job_id)}
    # a terminal job never re-enters the observation set
    store.finish(str(job.job_id), -15, "cancelled", status="cancelled")
    assert store.cancel_requested_ids() == set()


def test_cancel_terminal_job_is_noop(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    job = store.submit(request())
    store.claim()
    store.finish(str(job.job_id), 0, "done")
    result = store.request_cancel(str(job.job_id))
    assert result.status == "succeeded"


def test_recover_maps_running_with_cancel_request_to_failed(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    job = store.submit(request())
    claimed = store.claim()
    store.request_cancel(str(claimed.job_id))
    store.recover()
    assert store.get(str(job.job_id)).status == "failed"


def test_job_model_admits_cancelled_status():
    job = Job(
        job_id=uuid4(), request=request(), status="cancelled", created_at="", updated_at=""
    )
    assert job.exit_code is None


def test_execute_terminates_on_cancel_and_records_cancelled(tmp_path, monkeypatch):
    store = JobStore(tmp_path / "jobs.sqlite3")
    store.submit(request())
    job = store.claim()
    monkeypatch.setattr(
        JobRequest,
        "argv",
        lambda _: [
            sys.executable,
            "-c",
            "print('started', flush=True); import time; time.sleep(300)",
        ],
    )
    cancel = threading.Event()
    container: dict = {}

    def run() -> None:
        container["job"] = worker.execute(job, store, 60, threading.Event(), cancel)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 20
    while "started" not in store.get(str(job.job_id)).output:
        assert time.monotonic() < deadline, "subprocess never started"
        time.sleep(0.1)
    cancel.set()
    thread.join(timeout=30)
    assert not thread.is_alive()
    done = store.get(str(job.job_id))
    assert done.status == "cancelled"
    assert done.exit_code == -15


def test_execute_ignores_calm_cancel_event(tmp_path, monkeypatch):
    store = JobStore(tmp_path / "jobs.sqlite3")
    store.submit(request())
    job = store.claim()
    monkeypatch.setattr(JobRequest, "argv", lambda _: [sys.executable, "-c", "print('ok')"])
    worker.execute(job, store, 30, threading.Event(), threading.Event())
    assert store.get(str(job.job_id)).status == "succeeded"


def test_execute_no_longer_touches_the_heartbeat(tmp_path, monkeypatch):
    store = JobStore(tmp_path / "jobs.sqlite3")
    store.submit(request())
    job = store.claim()
    monkeypatch.setattr(JobRequest, "argv", lambda _: [sys.executable, "-c", "print('ok')"])
    worker.execute(job, store, 30, threading.Event(), threading.Event())
    assert not (tmp_path / "jobs.heartbeat").exists()


def test_pool_runs_sources_concurrently_and_cancels_one(tmp_path, monkeypatch):
    store = JobStore(tmp_path / "jobs.sqlite3")
    slow = store.submit(request("migrate", version="1.0.0"))
    for _ in range(3):
        store.submit(request("backup"))
    other_ids = [
        row_id
        for row_id in _queue_ids(store)
        if row_id != str(slow.job_id)
    ]

    def argv(self) -> list[str]:
        script = (
            "print('started', flush=True); import time; time.sleep(120)"
            if self.command == "migrate"
            else "import time; time.sleep(0.5); print('done')"
        )
        return [sys.executable, "-c", script]

    monkeypatch.setattr(JobRequest, "argv", argv)

    stop = threading.Event()
    settings = SimpleNamespace(
        jobs_path=tmp_path / "jobs.sqlite3",
        job_timeout_seconds=6000,
        job_concurrency=4,
    )

    def run_loop() -> None:
        worker.run_pool(store, settings, stop)

    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 60
        while "started" not in store.get(str(slow.job_id)).output:
            assert time.monotonic() < deadline, "slow job never started"
            time.sleep(0.2)
        store.request_cancel(str(slow.job_id))
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            cancelled = store.get(str(slow.job_id))
            if cancelled.status in {"cancelled", "failed"}:
                break
            time.sleep(0.2)
        assert cancelled.status == "cancelled", cancelled
        assert cancelled.exit_code == -15
        deadline = time.monotonic() + 30
        statuses = []
        while time.monotonic() < deadline:
            statuses = [store.get(job_id).status for job_id in other_ids]
            if all(status == "succeeded" for status in statuses):
                break
            time.sleep(0.2)
        assert all(status == "succeeded" for status in statuses), statuses
    finally:
        stop.set()
        thread.join(timeout=60)
    assert not thread.is_alive()


def _queue_ids(store: JobStore) -> list[str]:
    with store.connection() as db:
        return [row[0] for row in db.execute("SELECT id FROM jobs ORDER BY created")]


def _settings(tmp_path):
    from tests.unit.test_api_auth import settings as base

    return base(tmp_path).model_copy(
        update={
            "operator_token": SecretStr("operator-test"),
            "jobs_path": tmp_path / "jobs.sqlite3",
        }
    )


def _patch_app(monkeypatch, loaded) -> None:
    driver = SimpleNamespace(read=lambda *args: [{"one": 1}], close=lambda: None)
    monkeypatch.setattr("limes.api.main.GraphDriver", lambda *args, **kwargs: driver)
    monkeypatch.setattr("limes.api.main.provision", lambda *args: None)


def test_cancel_queued_job_via_api(tmp_path, monkeypatch):
    loaded = _settings(tmp_path)
    _patch_app(monkeypatch, loaded)
    with TestClient(create_app(loaded)) as client:
        headers = {"Authorization": "Bearer operator-test"}
        missing = client.post(f"/operations/jobs/{uuid4()}/cancel", headers=headers)
        assert missing.status_code == 404
        submitted = client.post(
            "/operations/jobs",
            json=request().model_dump(mode="json"),
            headers=headers,
        ).json()
        cancelled = client.post(
            f"/operations/jobs/{submitted['job_id']}/cancel", headers=headers
        )
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"
        again = client.post(
            f"/operations/jobs/{submitted['job_id']}/cancel", headers=headers
        )
        assert again.status_code == 409
        assert again.json()["status"] == "cancelled"


def test_cancel_running_job_via_api_persists_flag(tmp_path, monkeypatch):
    loaded = _settings(tmp_path)
    _patch_app(monkeypatch, loaded)
    store = JobStore(tmp_path / "jobs.sqlite3")
    with TestClient(create_app(loaded)) as client:
        headers = {"Authorization": "Bearer operator-test"}
        submitted = client.post(
            "/operations/jobs",
            json=request().model_dump(mode="json"),
            headers=headers,
        ).json()
        store.claim()
        response = client.post(
            f"/operations/jobs/{submitted['job_id']}/cancel", headers=headers
        )
        assert response.status_code == 202
        assert response.json()["status"] == "running"
        assert store.cancel_requested_ids() == {submitted["job_id"]}
