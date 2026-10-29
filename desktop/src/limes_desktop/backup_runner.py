"""Asynchronous authenticated API backup; the desktop needs no host access."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from PySide6.QtCore import QObject, QThread, Signal

from limes_desktop.config import ConnectionProfile


class _BackupTask(QThread):
    output_line = Signal(str)
    completed = Signal(int, object, object)
    job_started = Signal(str)

    def __init__(self, factory: Callable[[], Any], parent: QObject) -> None:
        super().__init__(parent)
        self.factory = factory

    def run(self) -> None:
        dump: str | None = None
        try:
            client = self.factory()
            job = client.submit_backup(str(uuid4()))
            self.job_started.emit(job.job_id)
            self.output_line.emit(f"Backup job: {job.job_id}")
            previous = ""
            while True:
                job = client.operation_status(job.job_id)
                output = job.output
                if output != previous:
                    added = output[len(previous) :] if output.startswith(previous) else output
                    for line in added.splitlines():
                        self.output_line.emit(line)
                    previous = output
                    match = re.search(r"limes-[0-9T]+-[a-f0-9]+\.dump", output)
                    if match:
                        dump = match.group(0)
                if job.status == "failed":
                    self.completed.emit(1, None, dump)
                    return
                if job.status == "succeeded":
                    try:
                        info = client.health()
                        healthy = info.status == "ok" and info.neo4j
                    except Exception:
                        healthy = False
                    self.completed.emit(0, healthy, dump)
                    return
                if self.isInterruptionRequested():
                    self.output_line.emit(
                        "Disconnected; the server job continues. Use its ID to check status."
                    )
                    self.completed.emit(1, None, dump)
                    return
                time.sleep(1)
        except Exception:
            self.output_line.emit(
                "Backup request failed; check the operator credential and job status."
            )
            self.completed.emit(1, None, dump)


class BackupRunner(QObject):
    output_line = Signal(str)
    finished = Signal(int, object)

    def __init__(self, client_factory: Callable[[], Any], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._client_factory = client_factory
        self._task: _BackupTask | None = None
        self.health_ok: bool | None = None
        self.dump_path: str | None = None
        self.job_id: str | None = None

    def prerequisites(self, profile: ConnectionProfile) -> list[str]:
        from limes_desktop.api.errors import ApiError, ApiUnreachable

        try:
            allowed = self._client_factory().operation_capabilities()
        except ApiUnreachable:
            return ["Backup unavailable: API unreachable."]
        except ApiError as exc:
            return [
                "Backup requires an operator credential."
                if exc.status in (401, 403)
                else "Backup capabilities unavailable from API."
            ]
        except Exception:
            return ["Backup requires a reachable API and an operator credential."]
        return [] if allowed.get("backup") else ["API does not offer backup capability."]

    def run(self, profile: ConnectionProfile) -> None:
        if self._task is not None:
            return
        self.health_ok = None
        self.dump_path = None
        task = _BackupTask(self._client_factory, self)
        self._task = task
        task.job_started.connect(self._remember_job)
        task.output_line.connect(self.output_line)
        task.completed.connect(self._complete)
        task.finished.connect(self._cleanup)
        task.start()

    def _remember_job(self, job_id: str) -> None:
        self.job_id = job_id

    def _complete(self, code: int, health: bool | None, dump: str | None) -> None:
        self.health_ok, self.dump_path = health, dump
        self.finished.emit(code, health)

    def _cleanup(self) -> None:
        if self._task is not None:
            self._task.deleteLater()
            self._task = None

    def close(self) -> None:
        if self._task is not None:
            self._task.requestInterruption()
            self._task.wait()
