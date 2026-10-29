"""Versioned operator selections and immutable observation contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from limes.types import EntityEndpoint


class EnrichmentSelection(BaseModel):
    """An operator-reviewed mapping; evidence is retained in every acquisition manifest.

    Symbol and exchange identify a listing, never the canonical corporation.
    Security/share-class identity is optional and must be reviewed separately.
    """

    model_config = ConfigDict(extra="forbid")
    entity_id: str = Field(min_length=1, max_length=256)
    qid: str | None = Field(default=None, pattern=r"^Q[1-9][0-9]{0,15}$")
    symbol: str | None = Field(default=None, pattern=r"^[A-Z0-9][A-Z0-9.^=-]{0,31}$")
    exchange: str | None = Field(default=None, pattern=r"^[A-Z0-9_-]{1,32}$")
    isin: str | None = Field(default=None, pattern=r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
    share_class: str | None = Field(default=None, min_length=1, max_length=128)
    evidence_url: str = Field(pattern=r"^https://[^\s]{1,2000}$")
    rationale: str = Field(min_length=10, max_length=2000)

    @model_validator(mode="after")
    def coherent(self) -> EnrichmentSelection:
        if bool(self.symbol) != bool(self.exchange):
            raise ValueError("symbol and exchange must be reviewed together")
        if not self.qid and not self.symbol:
            raise ValueError("a QID or reviewed listing is required")
        if (self.isin or self.share_class) and not self.symbol:
            raise ValueError("security mapping requires a listing")
        return self


class AcquisitionTarget(BaseModel):
    selection: EnrichmentSelection
    entity: EntityEndpoint


class SectionStatus(BaseModel):
    section: str
    status: Literal["available", "missing", "unsupported", "failed", "ambiguous"]
    reason: str | None = None
    complete: bool = False
    source_as_of: datetime | None = None
    rows: int = 0


class EnrichmentResponse(BaseModel):
    entity_id: str
    snapshots: list[dict[str, object]] = []
    truncated: bool = False
    diagnosis: list[str] = []
