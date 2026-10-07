"""Desktop backup uses the authenticated API and keeps the Qt thread responsive."""

from typing import Any

import pytest
from limes_desktop.api.models import OperationJob, OperationRequest
from limes_desktop.backup_runner import BackupRunner
from limes_desktop.config import ConnectionProfile
from limes_desktop.views.backup import BackupDialog


class Client:
    def __init__(self, status="succeeded", healthy=True, allowed=True):
        self.status = status
        self.healthy = healthy
        self.allowed = allowed
        self.submitted = []
        self.health_calls = 0

    def operation_capabilities(self):
        if not self.allowed:
            raise RuntimeError("forbidden")
        return {"backup": True}

    def submit_backup(self, key):
        self.submitted.append(key)
        return self.operation_status("job-id")

    def operation_status(self, key):
        assert key == "job-id"
        return OperationJob(
            job_id=key,
            request=OperationRequest(request_id="request-id", command="backup"),
            status=self.status,
            created_at="",
            updated_at="",
            output="backup: complete (limes-20261007T120000-abcd.dump)",
        )

    def health(self):
        self.health_calls += 1
        if not self.healthy:
            raise RuntimeError("unreachable")


@pytest.mark.parametrize(
    "status,healthy,expected",
    [
        ("succeeded", True, (0, True)),
        ("succeeded", False, (0, False)),
        ("failed", True, (1, None)),
    ],
)
def test_backup_status_and_recovery(qtbot: Any, status, healthy, expected):
    client = Client(status, healthy)
    runner = BackupRunner(lambda: client)
    results = []
    lines = []
    runner.finished.connect(lambda code, health: results.append((code, health)))
    runner.output_line.connect(lines.append)
    profile = ConnectionProfile(name="remote", base_url="https://example.test")
    assert runner.prerequisites(profile) == []
    try:
        runner.run(profile)
        runner.run(profile)  # no second submission while active
        qtbot.waitUntil(lambda: bool(results), timeout=5000)
        assert results == [expected]
        assert len(client.submitted) == 1
        assert runner.dump_path == "limes-20261007T120000-abcd.dump"
        assert any("Backup job: job-id" in line for line in lines)
        assert client.health_calls == (1 if status == "succeeded" else 0)
    finally:
        runner.close()


def test_dialog_disabled_for_consumer_credential(qtbot: Any):
    runner = BackupRunner(lambda: Client(allowed=False))
    dialog = BackupDialog(runner)
    qtbot.addWidget(dialog)
    dialog.set_profile(ConnectionProfile(name="remote"))
    assert not dialog.run_button.isEnabled()
    assert "operator credential" in dialog.reason_label.text()


def test_backup_enabled_without_docker_or_compose_root(qtbot: Any):
    runner = BackupRunner(lambda: Client())
    dialog = BackupDialog(runner)
    qtbot.addWidget(dialog)
    dialog.set_profile(ConnectionProfile(name="remote", base_url="https://example.test"))
    assert dialog.run_button.isEnabled()
    assert "180 seconds" in dialog.consequence_label.text()
