"""The operational allowlist; callers cannot supply shell commands or paths."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from limes.enrichment.models import EnrichmentSelection

Command = Literal[
    "enrich",
    "news-reextract",
    "news-refresh",
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
    investigation_id: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    after_document: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    selections: list[EnrichmentSelection] | None = Field(default=None, min_length=1, max_length=10)
    extract_context: bool | None = None
    days: int | None = Field(default=None, ge=1, le=36500)
    version: str | None = Field(default=None, pattern=r"^\d{1,4}\.\d{1,4}\.\d{1,4}$")
    stage: Literal["provisional", "measured"] | None = None
    evaluation: Literal["extraction", "resolution", "nl2cypher"] | None = None

    @model_validator(mode="after")
    def validate_parameters(self) -> JobRequest:
        permitted = {
            "enrich": {"source", "selections", "extract_context"},
            "news-reextract": {"investigation_id", "version", "after_document"},
            "news-refresh": {"investigation_id"},
            "ingest": {"source"},
            "backfill": {"source", "days"},
            "reextract": {"source", "version"},
            "migrate": {"version"},
            "select-models": {"stage"},
            "evaluate": {"evaluation"},
        }.get(self.command, set())
        for field in (
            "selections", "extract_context",
            "source",
            "days",
            "version",
            "stage",
            "evaluation",
            "investigation_id",
            "after_document",
        ):
            if getattr(self, field) is not None and field not in permitted:
                raise ValueError(f"{field} is not supported by {self.command}")
        required = {
            "enrich": ("source", "selections"),
            "news-reextract": ("investigation_id", "version"),
            "news-refresh": ("investigation_id",),
            "ingest": ("source",),
            "backfill": ("source", "days"),
            "reextract": ("version",),
            "migrate": ("version",),
            "select-models": ("stage",),
        }.get(self.command, ())
        if any(getattr(self, field) is None for field in required):
            raise ValueError(f"{self.command} requires {', '.join(required)}")
        if self.command == "enrich":
            if self.source not in ("wikipedia", "yahoo_finance"):
                raise ValueError("enrich requires wikipedia or yahoo_finance")
            if self.extract_context and self.source != "wikipedia":
                raise ValueError("context extraction requires Wikipedia")
            for selection in self.selections or []:
                if self.source == "wikipedia" and not selection.qid:
                    raise ValueError("Wikipedia requires reviewed QID")
                if self.source == "yahoo_finance" and not selection.symbol:
                    raise ValueError("Yahoo requires reviewed listing")
        elif self.source:
            from limes.sources.registry import build_default_registry

            if (
                self.source in ("wikidata", "news", "wikipedia", "yahoo_finance")
                or self.source not in build_default_registry().source_ids()
            ):
                raise ValueError("unknown or enrichment-only source")
        return self

    def argv(self) -> list[str]:
        args = ["limes", self.command]
        if self.selections:
            import json

            args += ["--selections", json.dumps([s.model_dump() for s in self.selections])]
        if self.extract_context:
            args += ["--extract-context"]
        if self.after_document:
            args += ["--after-document", self.after_document]
        if self.investigation_id:
            args += ["--investigation-id", self.investigation_id]
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
