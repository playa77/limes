"""The operational allowlist; callers cannot supply shell commands or paths."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Command = Literal[
    "ingest",
    "ingest-all",
    "backfill",
    "reextract",
    "select-models",
    "evaluate",
    "migrate",
    "backup",
    "stamp-embeddings",
]


class JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    command: Command
    source: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{0,63}$")
    days: int | None = Field(default=None, ge=1, le=36500)
    version: str | None = Field(default=None, pattern=r"^\d{1,4}\.\d{1,4}\.\d{1,4}$")
    stage: Literal["provisional", "measured"] | None = None
    evaluation: Literal["extraction", "resolution", "nl2cypher"] | None = None

    @model_validator(mode="after")
    def validate_parameters(self) -> JobRequest:
        permitted = {
            "ingest": {"source"},
            "backfill": {"source", "days"},
            "reextract": {"source", "version"},
            "migrate": {"version"},
            "select-models": {"stage"},
            "evaluate": {"evaluation"},
        }.get(self.command, set())
        for field in ("source", "days", "version", "stage", "evaluation"):
            if getattr(self, field) is not None and field not in permitted:
                raise ValueError(f"{field} is not supported by {self.command}")
        required = {
            "ingest": ("source",),
            "backfill": ("source", "days"),
            "reextract": ("version",),
            "migrate": ("version",),
            "select-models": ("stage",),
        }.get(self.command, ())
        if any(getattr(self, field) is None for field in required):
            raise ValueError(f"{self.command} requires {', '.join(required)}")
        if self.source:
            from limes.sources.registry import build_default_registry

            if (
                self.source == "wikidata"
                or self.source not in build_default_registry().source_ids()
            ):
                raise ValueError("unknown or enrichment-only source")
        return self

    def argv(self) -> list[str]:
        args = ["limes", self.command]
        if self.source:
            args += ["--source", self.source]
        if self.days:
            args += ["--days", str(self.days)]
        if self.version:
            option = "--ontology-version" if self.command == "migrate" else "--prompt-version"
            args += [option, self.version]
        if self.stage:
            args += [f"--{self.stage}"]
        if self.evaluation and self.evaluation != "extraction":
            args += [f"--{self.evaluation}"]
        return args


class Job(BaseModel):
    job_id: UUID
    request: JobRequest
    status: Literal["queued", "running", "succeeded", "failed"]
    created_at: str
    updated_at: str
    output: str = ""
    exit_code: int | None = None
