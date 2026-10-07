"""Operator-only job submission and status; no process execution in the API."""

from __future__ import annotations

from secrets import compare_digest
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from limes.api.deps import get_settings
from limes.config import Settings
from limes.operations.models import Job, JobRequest
from limes.operations.store import JobStore


def require_operator(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> None:
    expected = settings.operator_token.get_secret_value()
    credential = request.headers.get("Authorization", "").partition(" ")[2]
    if not expected or not compare_digest(credential.encode(), expected.encode()):
        raise HTTPException(403, "operator credential required")


router = APIRouter(prefix="/operations", dependencies=[Depends(require_operator)])


def store(settings: Annotated[Settings, Depends(get_settings)]) -> JobStore:
    return JobStore(settings.jobs_path)


@router.post("/jobs", response_model=Job, status_code=202)
def submit(request: JobRequest, jobs: Annotated[JobStore, Depends(store)]) -> Job:
    try:
        return jobs.submit(request)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except OverflowError as exc:
        raise HTTPException(429, str(exc)) from exc


@router.get("/jobs/{job_id}", response_model=Job)
def status(job_id: UUID, jobs: Annotated[JobStore, Depends(store)]) -> Job:
    job = jobs.get(str(job_id))
    if job is None:
        raise HTTPException(404, "job not found")
    return job


@router.get("/capabilities")
def capabilities() -> dict[str, bool]:
    return {"backup": True, "jobs": True}
