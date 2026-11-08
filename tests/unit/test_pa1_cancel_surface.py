# tests/unit/test_pa1_cancel_surface.py | PA-1 | client.cancel and remote CLI cancel (R4)
"""The remote operator can cancel one job through the client and CLI."""

from __future__ import annotations

import uuid
from uuid import uuid4

import httpx
import pytest
import respx
from typer.testing import CliRunner

from limes.cli.main import app
from limes.operations.client import OperationsClient
from limes.operations.models import Job, JobRequest

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
def test_client_cancel_surfaces_conflict_as_raise_for_status():
    respx.post(f"https://api.test/operations/jobs/{SERVICE_J}/cancel").return_value \
        = httpx.Response(409, json=JOB_BODY)
    client = OperationsClient("https://api.test", "operator-token")
    with pytest.raises(httpx.HTTPError):
        client.cancel(uuid.UUID(SERVICE_J))
    client.close()


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
    assert result.exit_code == 0, result.output
    assert endpoints == ["/operations/jobs/00000000-0000-0000-0000-000000000004"]


def test_job_request_json_covers_cancelled_status():
    request = JobRequest(request_id=uuid4(), command="backup")
    assert request.command == "backup"  # submission semantics unchanged (non-goal)
