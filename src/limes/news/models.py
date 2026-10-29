"""Versioned reporting semantics; absent historical qualifiers remain unknown."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ClaimQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attribution: str | None = Field(default=None, max_length=500)
    modality: Literal["asserted", "reported", "denied", "proposed", "conditional", "unknown"]
    assessment: Literal["unassessed", "supported", "disputed", "refuted"] = "unassessed"
    event_status: Literal[
        "unknown", "proposed", "planned", "ongoing", "completed", "cancelled", "denied"
    ] = "unknown"
    time_precision: Literal["unknown", "instant", "day", "month", "year", "interval"] = "unknown"
    event_candidate: str | None = Field(default=None, max_length=500)
    # A reported label is a candidate, never an automatic cross-source event identity.


class TrackingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    investigation_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    title: str = Field(min_length=1, max_length=200)
    entity_ids: list[str] = Field(default_factory=list, max_length=20)
    assertion_ids: list[str] = Field(default_factory=list, max_length=20)
    active: bool = True
    interval_minutes: int = Field(default=60, ge=15, le=10080)


class Investigation(TrackingRequest):
    revision: int = 1
    job_id: str | None = None
    next_due: str | None = None
    last_success: str | None = None
    status: Literal["ready", "queued", "running", "succeeded", "failed", "paused"] = "ready"


class EvaluationReview(BaseModel):
    """Human annotation of acquired evidence; never an automatic truth label."""

    model_config = ConfigDict(extra="forbid")
    expected_modality: Literal[
        "asserted", "reported", "denied", "proposed", "conditional", "unknown"
    ]
    expected_event_status: Literal[
        "unknown", "proposed", "planned", "ongoing", "completed", "cancelled", "denied"
    ]
    expected_time_precision: Literal["unknown", "instant", "day", "month", "year", "interval"]
    notes: str = Field(min_length=1, max_length=2000)


class NewsClaimView(ClaimQualifiers):
    claim_id: str
    subject_id: str
    subject_label: str
    object_id: str
    object_label: str
    relation: str
    evidence_document_id: str
    evidence_start: int | None = None
    evidence_end: int | None = None
    source_id: str | None = None
    source_trust: float | None = None
    confidence: float | None = None
    investigation_id: str | None = None
    dispatch_id: str | None = None
    publisher: str | None = None
    syndication_key: str | None = None
    report_url: str | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    recorded_at: datetime | None = None
    retracted_at: datetime | None = None
    ontology_version: str | None = None
    prompt_version: str | None = None
    schema_version: str | None = None
    extractor_model: str | None = None
