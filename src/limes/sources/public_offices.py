"""Official roster adapter; a coherent archived snapshot is the structured record."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import Literal

from limes.errors import SourceFetchError, SourceParseError
from limes.public_offices.acquisition import Acquisition
from limes.public_offices.catalogue import Scope
from limes.public_offices.models import Snapshot
from limes.public_offices.normalization import normalize_snapshot
from limes.types import NormalizedRecord, RawRecord


class PublicOfficesAdapter:
    kind: Literal["structured", "unstructured"] = "structured"
    trust_rank = 1.0
    supports_backfill = False
    supports_incremental = False

    def __init__(self, scope: Scope, acquisition: Acquisition | None = None) -> None:
        self.scope = scope
        self.source_id = "public_offices_" + scope.code
        self.name = scope.name + " — official serving roster"
        self.acquisition = acquisition

    def fetch(self, since: datetime | None, until: datetime | None) -> Iterator[RawRecord]:
        del since, until  # Current roster observations, never historical backfill.
        if self.acquisition is None:
            raise SourceFetchError("public offices acquisition is not composed")
        snapshot = self.acquisition.acquire(self.scope)
        yield RawRecord(
            payload=snapshot.model_dump_json().encode(),
            content_type="application/json",
            source_url=self.scope.url,
            fetched_at=snapshot.observed_at,
            acquisition_context={
                "scope": self.scope.code,
                "raw_pages": snapshot.pages,
                "check_basis": snapshot.check_basis,
            },
        )

    def normalize(self, record: RawRecord) -> NormalizedRecord:
        try:
            snapshot = Snapshot.model_validate_json(record.payload)
        except ValueError as exc:
            raise SourceParseError("public offices: invalid archived snapshot") from exc
        if snapshot.scope != self.scope.code or not snapshot.consistent:
            raise SourceParseError("public offices: inconsistent or wrong-scope snapshot")
        if not snapshot.members:
            raise SourceParseError("public offices: empty snapshot cannot certify serving coverage")
        if sorted(m.external_id for m in snapshot.members) != sorted(snapshot.expected_ids):
            raise SourceParseError("public offices: member set does not reconcile")
        if len(set(snapshot.expected_ids)) != len(snapshot.members):
            raise SourceParseError("public offices: duplicate member ID")
        return normalize_snapshot(self, record, snapshot)
