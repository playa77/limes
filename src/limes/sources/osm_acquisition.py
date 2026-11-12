"""Durable OSM acquisition cursor; original response bytes live in ArchiveStore.

This is acquisition state, never a graph-load checkpoint. Replays yield all
partitions again, including cached ones, until the pipeline acknowledges a
successful complete load. A lock excludes competing acquisitions; atomic writes
make interruption safe. No job is automatically resumed or submitted here.
"""

from __future__ import annotations

import fcntl
import json
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError

from limes.archive.store import ArchiveStore
from limes.data_scope import require_source_date, source_date_eligible
from limes.errors import SourceFetchError
from limes.sources.base import now_utc, payload_hash


class PartitionEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    fetched_at: AwareDatetime


class FailedLeaf(BaseModel):
    """Acquisition failure only; absent payload means no response was available."""

    model_config = ConfigDict(extra="forbid")
    phase: Literal["fetch"] = "fetch"
    state: Literal["failed"] = "failed"
    failed_at: AwareDatetime = Field(default_factory=now_utc)
    error: str
    content_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class AcquisitionState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    acquisition_id: str = Field(default_factory=lambda: uuid.uuid4().hex, pattern=r"^[0-9a-f]{32}$")
    plan_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    started_at: AwareDatetime = Field(default_factory=now_utc)
    partitions: dict[str, PartitionEntry] = Field(default_factory=dict)
    splits: list[str] = Field(default_factory=list)
    failed_leaves: dict[str, FailedLeaf] = Field(default_factory=dict)


class OsmAcquisition:
    """Composition supplies the archive and private writable cursor directory."""

    def __init__(self, archive: ArchiveStore, root: Path) -> None:
        self.archive = archive
        self.root = root

    @contextmanager
    def locked(self) -> Iterator[None]:
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / "lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise SourceFetchError("osm: another acquisition is active") from exc
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def read(self, plan_hash: str) -> AcquisitionState:
        path = self.root / "active.json"
        if not path.exists():
            state = AcquisitionState(plan_hash=plan_hash)
            self.write(state)
            return state
        try:
            state = AcquisitionState.model_validate_json(path.read_bytes())
        except (ValidationError, ValueError) as exc:
            raise SourceFetchError(
                "osm: invalid acquisition cursor; preserve for inspection") from exc
        if (not source_date_eligible(state.started_at)
                or any(not source_date_eligible(entry.fetched_at)
                       for entry in state.partitions.values())):
            # Preserve legacy progress metadata and original archive bytes. Start
            # a fresh CURRENT collection rather than disabling the OSM source or
            # reading pre-scope cached payloads.
            retained = self.root / f"pre-2020-{state.acquisition_id}.json"
            if not retained.exists():
                retained.write_bytes(path.read_bytes())
            state = AcquisitionState(plan_hash=plan_hash)
            self.write(state)
            return state
        if state.plan_hash != plan_hash:
            raise SourceFetchError(
                "osm: acquisition plan changed; retain or retire old cursor first")
        return state

    def write(self, state: AcquisitionState) -> None:
        path = self.root / "active.json"
        temporary = self.root / f".tmp-{uuid.uuid4().hex}"
        try:
            with temporary.open("w") as output:
                output.write(state.model_dump_json(indent=2) + "\n")
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, path)
            descriptor = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        finally:
            temporary.unlink(missing_ok=True)

    def payload(self, entry: PartitionEntry) -> bytes:
        require_source_date(entry.fetched_at, "osm")
        try:
            payload = self.archive.get(entry.content_hash)
        except (OSError, EOFError) as exc:
            raise SourceFetchError("osm: cached partition archive is unavailable") from exc
        if payload_hash(payload) != entry.content_hash:
            raise SourceFetchError("osm: cached partition archive hash mismatch")
        return payload

    def manifest(self, state: AcquisitionState) -> str:
        return self.archive.put("osm", state.model_dump_json().encode(), "application/json")

    def complete(self, acquisition_id: str, *, already_locked: bool = False) -> None:
        """Called after successful loading and before the source success checkpoint."""
        with nullcontext() if already_locked else self.locked():
            path = self.root / "active.json"
            if path.exists():
                data = json.loads(path.read_bytes())
                if data.get("acquisition_id") == acquisition_id:
                    path.unlink()
                    descriptor = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
                    try:
                        os.fsync(descriptor)
                    finally:
                        os.close(descriptor)
