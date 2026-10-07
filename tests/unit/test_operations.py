"""Operational boundaries, durable replay protection, worker failure recovery."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from limes.api.main import create_app
from limes.operations.client import validate_endpoint
from limes.operations.models import JobRequest
from limes.operations.store import OUTPUT_LIMIT, JobStore
from limes.operations.worker import execute
from tests.unit.test_api_auth import TOKEN, settings


@pytest.fixture
def ops_client(tmp_path, monkeypatch):
    loaded = settings(tmp_path).model_copy(
        update={
            "operator_token": SecretStr("operator-test"),
            "jobs_path": tmp_path / "jobs.sqlite3",
        }
    )
    driver = SimpleNamespace(read=lambda *args: [{"one": 1}], close=lambda: None)
    monkeypatch.setattr("limes.api.main.GraphDriver", lambda *args: driver)
    monkeypatch.setattr("limes.api.main.provision", lambda *args: None)
    with TestClient(create_app(loaded)) as client:
        yield client


def request(**kwargs):
    return JobRequest(request_id=uuid4(), command="backup", **kwargs)


@pytest.mark.parametrize("path", ["/operations/jobs", "/operations/capabilities"])
def test_consumer_cannot_control_operations(ops_client, path):
    response = ops_client.request(
        "POST" if path.endswith("jobs") else "GET",
        path,
        headers={"Authorization": f"Bearer {TOKEN}"},
        json=request().model_dump(mode="json") if path.endswith("jobs") else None,
    )
    assert response.status_code == 403


def test_operator_submit_retry_and_status(ops_client):
    payload = request().model_dump(mode="json")
    headers = {"Authorization": "Bearer operator-test"}
    first = ops_client.post("/operations/jobs", json=payload, headers=headers)
    again = ops_client.post("/operations/jobs", json=payload, headers=headers)
    assert first.status_code == again.status_code == 202
    assert first.json()["job_id"] == again.json()["job_id"]
    key = first.json()["job_id"]
    assert ops_client.get(f"/operations/jobs/{key}", headers=headers).json()["status"] == "queued"
    payload["command"] = "ingest-all"
    assert ops_client.post("/operations/jobs", json=payload, headers=headers).status_code == 409
    assert ops_client.get(f"/operations/jobs/{uuid4()}", headers=headers).status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"command": "sh"},
        {"command": "backup", "argv": ["rm", "-rf", "/"]},
        {"command": "backup", "source": "gleif"},
        {"command": "ingest"},
        {"command": "ingest", "source": "--help"},
        {"command": "ingest", "source": "wikidata"},
        {"command": "ingest", "source": "made_up"},
        {"command": "backfill", "source": "gleif", "days": 0},
        {"command": "backfill", "source": "gleif", "days": 36501},
        {"command": "migrate", "version": "../../script"},
        {"command": "select-models", "stage": "fake"},
    ],
)
def test_operation_parameters_fail_closed(payload):
    with pytest.raises(ValidationError):
        JobRequest.model_validate({"request_id": uuid4(), **payload})


def test_store_serializes_claims_and_preserves_status(tmp_path):
    path = tmp_path / "jobs.sqlite3"
    store = JobStore(path)
    jobs = [store.submit(request()) for _ in range(10)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        claimed = list(pool.map(lambda _: JobStore(path).claim(), jobs))
    assert len({str(job.job_id) for job in claimed}) == 10
    assert store.claim() is None
    store.finish(str(jobs[0].job_id), 0, "x" * (OUTPUT_LIMIT + 10))
    store.recover()
    assert store.get(str(jobs[0].job_id)).status == "succeeded"
    assert len(store.get(str(jobs[0].job_id)).output) == OUTPUT_LIMIT
    assert all(store.get(str(job.job_id)).status == "failed" for job in jobs[1:])
    assert store.claim() is None  # interrupted paid operations are never replayed


def test_queue_is_bounded(tmp_path):
    store = JobStore(tmp_path / "queue.sqlite3")
    for _ in range(256):
        store.submit(request())
    with pytest.raises(OverflowError):
        store.submit(request())


def test_worker_reports_real_exit_code_and_caps_output(tmp_path, monkeypatch):
    import sys

    store = JobStore(tmp_path / "jobs.sqlite3")
    job = store.submit(request())
    job = store.claim()
    monkeypatch.setattr(
        JobRequest,
        "argv",
        lambda _: [
            sys.executable,
            "-c",
            "print('x' * 100000); raise SystemExit(7)",
        ],
    )
    execute(job, store, 5, Event())
    result = store.get(str(job.job_id))
    assert result.status == "failed" and result.exit_code == 7
    assert len(result.output) <= OUTPUT_LIMIT


@pytest.mark.parametrize("url", ["http://remote.test", "file:///tmp/test", "https://u:p@x.test"])
def test_remote_credentials_require_secure_transport(url):
    with pytest.raises(ValueError):
        validate_endpoint(url)


def test_output_stays_bounded_and_valid_utf8_after_recovery(tmp_path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    store.submit(request())
    job = store.claim()
    store.output(str(job.job_id), "€" * OUTPUT_LIMIT)
    store.recover()
    result = store.get(str(job.job_id))
    assert result.status == "failed"
    assert len(result.output.encode()) <= OUTPUT_LIMIT
    assert "Worker interrupted" in result.output
