"""HTTP operations client; only HTTPS and local loopback may carry credentials."""

from __future__ import annotations

import time
from collections.abc import Callable
from urllib.parse import urlsplit
from uuid import UUID

import httpx

from limes.operations.models import Job, JobRequest


def validate_endpoint(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("an HTTP(S) API endpoint is required")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("endpoint must not contain credentials, query or fragment")
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("remote credentials require HTTPS or a loopback tunnel")


class OperationsClient:
    def __init__(self, url: str, token: str) -> None:
        validate_endpoint(url)
        if not token:
            raise ValueError("an operator credential is required")
        self.client = httpx.Client(
            base_url=url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
            follow_redirects=False,
        )

    def close(self) -> None:
        self.client.close()

    def submit(self, request: JobRequest) -> Job:
        response = self.client.post("/operations/jobs", json=request.model_dump(mode="json"))
        response.raise_for_status()
        return Job.model_validate(response.json())

    def get(self, key: UUID) -> Job:
        response = self.client.get(f"/operations/jobs/{key}")
        response.raise_for_status()
        return Job.model_validate(response.json())

    def wait(self, key: UUID, output: Callable[[str], None] = print) -> Job:
        previous = ""
        while True:
            job = self.get(key)
            if job.output != previous:
                output(
                    job.output[len(previous) :] if job.output.startswith(previous) else job.output
                )
                previous = job.output
            if job.status in {"succeeded", "failed"}:
                return job
            time.sleep(1)
