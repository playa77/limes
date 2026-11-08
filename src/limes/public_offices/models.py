"""Wire and acquisition contracts; dates describe service only when explicitly supplied."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Member(BaseModel):
    model_config = ConfigDict(extra="forbid")
    external_id: str = Field(min_length=1, max_length=2048)
    name: str = Field(min_length=1, max_length=256)
    aliases: list[str] = []
    profile_url: str
    role: str = "member"
    land: str | None = None
    term: str | None = None
    group: str | None = None
    party: str | None = None
    constituency: str | None = None
    mandate_kind: str | None = None
    service_start: datetime | None = None
    service_end: datetime | None = None
    source_updated_text: str | None = None
    service_precision: str | None = None
    bundestag_id: str | None = None
    locator: str
    evidence_hash: str = ""
    evidence_url: str = ""
    profile_evidence_hash: str | None = None
    profile_member_class: str | None = None
    conflicts: list[str] = []
    leadership: list[str] = []
    service_evidence: list[dict[str, str]] = []


class Page(BaseModel):
    members: list[Member] = []
    next_urls: list[str] = []
    expected_count: int | None = None
    term: str | None = None
    # Listing without an independent set/count remains visibly unverified.
    check_basis: str = "official_directory_set"
    departed_ids: list[str] = []
    entry_dates: dict[str, datetime] = {}
    pagination: bool = False
    source_update_note: str | None = None
    historical_members: list[Member] = []
    name_aliases: dict[str, list[str]] = {}


class Snapshot(BaseModel):
    scope: str
    observed_at: datetime
    members: list[Member]
    expected_ids: list[str]
    pages: list[dict[str, str]]
    term: str | None = None
    expected_count: int | None = None
    check_basis: str = "official_directory_set"
    consistent: bool = False
    source_updates: list[str] = []
    historical_members: list[Member] = []


class ScopeCoverage(BaseModel):
    scope: str
    institution: str
    snapshot_id: str | None = None
    status: Literal["missing", "failed", "partial", "reconciled", "unverified"] = "missing"
    observed_at: datetime | None = None
    term: str | None = None
    expected: int | None = None
    acquired: int = 0
    loaded: int = 0
    distinct_persons: int = 0
    unresolved: int = 0
    failed_rows: int | None = None
    stale: bool | None = None
    check_basis: str | None = None
    diagnosis: list[str] = []


class OfficesResponse(BaseModel):
    coverage_status: Literal["partial", "reconciled"] = "partial"
    scopes: list[ScopeCoverage] = []
    members: list[dict[str, object]] = []
    truncated: bool = False
    diagnosis: list[str] = []


class IdentityReview(BaseModel):
    """An operator's explicit, evidence-backed canonical identity decision."""

    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    external_id: str = Field(min_length=1, max_length=2048)
    person_id: str = Field(min_length=1, max_length=2048)
    evidence_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    note: str = Field(min_length=1, max_length=2000)
