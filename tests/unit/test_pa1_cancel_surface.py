# tests/unit/test_pa1_cancel_surface.py | PA-1 | client.cancel and remote CLI cancel (R4)
"""The remote operator can cancel one job through the client and CLI."""

from __future__ import annotations

import uuid

import httpx
import respx
from typer.testing import CliRunner

from limes.cli.main import app
from limes.operations.client import OperationsClient
from limes.operations.models import Job

runner = CliRunner()

JOB_BODY = {
    "job_id": "00000000-0000-0000-0000-000000000001",
    "request": {"request_id": "00000000-0000-0000-0000-000000000002", "command": "backup"},
    "status": "cancelled",
    "created_at": "2026-11-08T00:00:00+00:00",
    "updated_at": "2026-11-08T00:00:01+00:00",
    "output": "Cancelled while queued.",
    "exit_code": None,
}


SERVICE_J = "00000000-0000-0000-0000-000000000001"


@respx.mock
def test_client_cancel_posts_the_endpoint():
    route = respx.post(f"https://api.test/operations/jobs/{SERVICE_J}/cancel")
    route.return_value = httpx.Response(200, json=JOB_BODY)
    client = OperationsClient("https://api.test", "operator-token")
    result = client.cancel(uuid.UUID(SERVICE_J))
    client.close()
    assert result.status == "cancelled"


@respx.mock
def test_client_cancel_conflict_returns_record_not_error():
    respx.post(f"https://api.test/operations/jobs/{SERVICE_J}/cancel").return_value \
        = httpx.Response(409, json=JOB_BODY)
    client = OperationsClient("https://api.test", "operator-token")
    result = client.cancel(uuid.UUID(SERVICE_J))
    client.close()
    assert result.status == "cancelled"  # documented no-op, not an HTTP error


def test_remote_cli_cancel_commands(monkeypatch):
    endpoints: list[str] = []

    def fake_client(url, token):
        assert token == "op-token"

        class Fake:
            def cancel(self, job_id):  # noqa: ANN001
                endpoints.append(f"/operations/jobs/{job_id}")
                return Job.model_validate(JOB_BODY)

            def close(self) -> None:
                pass

        return Fake()

    monkeypatch.setattr("limes.cli.remote.OperationsClient", fake_client)
    monkeypatch.setenv("LIMES_OPERATOR_TOKEN", "op-token")
    result = runner.invoke(
        app,
        [
            "remote",
            "cancel",
            "00000000-0000-0000-0000-000000000004",
            "--url",
            "https://api.test",
        ],
    )
    assert result.exit_code == 1, result.output  # cancelled ends the wait abnormally
    assert endpoints == ["/operations/jobs/00000000-0000-0000-0000-000000000004"]


def test_cancelled_job_round_trips_through_the_model():
    job = Job.model_validate(JOB_BODY)
    encoded = job.model_dump_json()
    assert '"status":"cancelled"' in encoded


def test_client_wait_returns_on_cancelled(monkeypatch):
    import httpx as _httpx
    import respx as _respx

    url = f"https://api.test/operations/jobs/{JOB_BODY['job_id']}"
    with _respx.mock:
        _respx.get(url).return_value = _httpx.Response(200, json=JOB_BODY)
        client = OperationsClient("https://api.test", "operator-token")
        result = client.wait(uuid.UUID(JOB_BODY["job_id"]), output=lambda *_: None)
        client.close()
    assert result.status == "cancelled"


def test_client_cancel_idempotent_on_conflict():
    import httpx as _httpx
    import respx as _respx

    url = f"https://api.test/operations/jobs/{JOB_BODY['job_id']}"
    with _respx.mock:
        _respx.post(f"{url}/cancel").return_value = _httpx.Response(409, json=JOB_BODY)
        client = OperationsClient("https://api.test", "operator-token")
        result = client.cancel(uuid.UUID(JOB_BODY["job_id"]))
        client.close()
    assert result.status == "cancelled"  # the documented no-op, not an error
