"""Archive-first bounded normalization chunks for compressed public snapshots.

The original compressed bytes remain a separate content-addressed raw record.
Derived chunks carry a manifest pointer to that original and source row offset;
they never replace the archived source artifact or invent a publication date.
"""

from __future__ import annotations

import bz2
import csv
import io
import json
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import BinaryIO

import httpx

from limes.errors import SourceFetchError
from limes.sources.base import (
    USER_AGENT,
    PermanentStatus,
    RetryExhausted,
    now_utc,
    payload_hash,
    request_with_retry,
)
from limes.types import RawRecord

CHUNK_ROWS = 1000
MAX_LINE_BYTES = 1024 * 1024
MAX_CHUNK_BYTES = 8 * 1024 * 1024
CSV_CONTENT_TYPE = "text/csv"


@dataclass
class Artifact:
    stream: BinaryIO
    content_hash: str
    fetched_at: datetime


@contextmanager
def fetch_artifact(url: str, *, max_bytes: int = 2 * 1024**3) -> Iterator[Artifact]:
    """Stream large downloads to disk; reuse the archived artifact after interruption.

    A partially downloaded file is never a cache hit. A failed attempt restarts
    that package, while completed packages and load receipts survive restarts.
    """
    from limes.sources.acquisition import active_acquisition, request_key

    acquisition = active_acquisition.get()
    if acquisition is not None:
        acquisition.last_response_key = None
    key = request_key("ARTIFACT", url)
    digest = acquisition.response_hash(key) if acquisition else None
    if acquisition is not None and digest is not None:
        with acquisition.archive.open(digest) as stream:
            yield Artifact(stream, digest, now_utc())
        return
    with TemporaryDirectory(prefix="limes-artifact-") as temporary:
        path = Path(temporary) / "source.part"
        try:
            request_with_retry(
                "GET", url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"},
                max_bytes=max_bytes, output_path=path,
            )
        except (RetryExhausted, PermanentStatus, httpx.DecodingError) as exc:
            raise SourceFetchError(f"bulk artifact download failed: {url}: {exc}") from exc
        if acquisition is not None:
            digest = acquisition.archive.put_file(path)
            acquisition.save_response_hash(key, digest)
        else:
            import hashlib

            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
        with path.open("rb") as stream:
            yield Artifact(stream, digest, now_utc())


def zip_csv_records(payload: bytes, url: str, fetched_at: datetime) -> Iterator[RawRecord]:
    digest = payload_hash(payload)
    yield RawRecord(
        payload=payload,
        content_type="application/zip",
        source_url=url,
        fetched_at=fetched_at,
        acquisition_context={"archive_only": True},
    )
    yield from _zip_csv_chunks(io.BytesIO(payload), url, fetched_at, digest)


def zip_csv_artifact_records(url: str, fetched_at: datetime) -> Iterator[RawRecord]:
    from limes.sources.acquisition import active_acquisition

    acquisition = active_acquisition.get()
    if acquisition is not None and acquisition.unit_loaded(url):
        return
    record_keys: list[str] = []
    with fetch_artifact(url) as artifact:
        fetched_at = artifact.fetched_at
        yield _artifact_manifest(url, fetched_at, artifact.content_hash)
        for raw in _zip_csv_chunks(artifact.stream, url, fetched_at, artifact.content_hash):
            raw.acquisition_context = {**(raw.acquisition_context or {}), "unit": url}
            if acquisition is not None:
                record_keys.append(acquisition.record_key(raw))
            yield raw
    if acquisition is not None:
        acquisition.finish_unit(url, record_keys)


def _artifact_manifest(url: str, fetched_at: datetime, digest: str) -> RawRecord:
    return RawRecord(
        payload=json.dumps({"source_archive_hash": digest, "source_url": url}).encode(),
        content_type="application/json", source_url=url, fetched_at=fetched_at,
        acquisition_context={"archive_only": True, "source_archive_hash": digest},
    )


def _zip_csv_chunks(
    source: BinaryIO, url: str, fetched_at: datetime, digest: str
) -> Iterator[RawRecord]:
    try:
        with zipfile.ZipFile(source) as archive:
            members = [n for n in archive.namelist() if n.lower().endswith(".csv")]
            if len(members) != 1:
                raise SourceFetchError("bulk: expected exactly one CSV member")
            member = members[0]
            with archive.open(member) as stream:
                reader = csv.reader(io.TextIOWrapper(stream, encoding="utf-8-sig", newline=""))
                header = next(reader, None)
                if not header:
                    raise SourceFetchError("bulk: missing CSV header")
                offset = 0
                rows: list[list[str]] = []
                chunk_bytes = 0
                for row in reader:
                    if sum(len(value.encode()) for value in row) > MAX_LINE_BYTES:
                        raise SourceFetchError("bulk: CSV row exceeds byte limit")
                    if len(row) != len(header):
                        raise SourceFetchError("bulk: CSV column count changed")
                    row_bytes = sum(len(value.encode()) for value in row) + len(row) * 3
                    if rows and chunk_bytes + row_bytes > MAX_CHUNK_BYTES:
                        yield _csv_chunk(header, rows, url, fetched_at, digest, member, offset)
                        offset += len(rows)
                        rows = []
                        chunk_bytes = 0
                    rows.append(row)
                    chunk_bytes += row_bytes
                    if len(rows) == CHUNK_ROWS:
                        yield _csv_chunk(header, rows, url, fetched_at, digest, member, offset)
                        offset += len(rows)
                        rows = []
                        chunk_bytes = 0
                if rows:
                    yield _csv_chunk(header, rows, url, fetched_at, digest, member, offset)
                elif offset == 0:
                    raise SourceFetchError("bulk: CSV has no data rows")
    except (OSError, EOFError, ValueError, csv.Error, zipfile.BadZipFile) as exc:
        raise SourceFetchError("bulk: invalid ZIP/CSV snapshot") from exc


def _csv_chunk(
    header: list[str],
    rows: list[list[str]],
    url: str,
    fetched_at: datetime,
    digest: str,
    member: str,
    offset: int,
) -> RawRecord:
    text = io.StringIO(newline="")
    writer = csv.writer(text)
    writer.writerow(header)
    writer.writerows(rows)
    return RawRecord(
        payload=text.getvalue().encode(),
        content_type=CSV_CONTENT_TYPE,
        source_url=url,
        fetched_at=fetched_at,
        acquisition_context={
            "source_archive_hash": digest,
            "source_member": member,
            "source_row_offset": offset,
            "rows": len(rows),
        },
    )


def bz2_jsonl_records(payload: bytes, url: str, fetched_at: datetime) -> Iterator[RawRecord]:
    digest = payload_hash(payload)
    yield RawRecord(
        payload=payload,
        content_type="application/x-bzip2",
        source_url=url,
        fetched_at=fetched_at,
        acquisition_context={"archive_only": True},
    )
    yield from _bz2_jsonl_chunks(io.BytesIO(payload), url, fetched_at, digest)


def bz2_jsonl_artifact_records(url: str, fetched_at: datetime) -> Iterator[RawRecord]:
    from limes.sources.acquisition import active_acquisition

    acquisition = active_acquisition.get()
    if acquisition is not None and acquisition.unit_loaded(url):
        return
    record_keys: list[str] = []
    with fetch_artifact(url) as artifact:
        fetched_at = artifact.fetched_at
        yield _artifact_manifest(url, fetched_at, artifact.content_hash)
        for raw in _bz2_jsonl_chunks(artifact.stream, url, fetched_at, artifact.content_hash):
            raw.acquisition_context = {**(raw.acquisition_context or {}), "unit": url}
            if acquisition is not None:
                record_keys.append(acquisition.record_key(raw))
            yield raw
    if acquisition is not None:
        acquisition.finish_unit(url, record_keys)


def line_artifact_records(url: str, fetched_at: datetime) -> Iterator[RawRecord]:
    """GISCO's line-oriented CSV, with the original header in every bounded chunk."""
    with fetch_artifact(url) as artifact:
        fetched_at = artifact.fetched_at
        yield _artifact_manifest(url, fetched_at, artifact.content_hash)
        header = artifact.stream.readline(MAX_LINE_BYTES + 1)
        if not header or len(header) > MAX_LINE_BYTES:
            raise SourceFetchError("bulk: missing or oversized table header")
        lines: list[bytes] = []
        offset = 0
        while line := artifact.stream.readline(MAX_LINE_BYTES + 1):
            if len(line) > MAX_LINE_BYTES:
                raise SourceFetchError("bulk: table row exceeds byte limit")
            lines.append(line)
            if len(lines) == CHUNK_ROWS:
                yield RawRecord(
                    payload=header + b"".join(lines), content_type=CSV_CONTENT_TYPE,
                    source_url=url, fetched_at=fetched_at,
                    acquisition_context={"source_archive_hash": artifact.content_hash,
                                         "source_row_offset": offset, "rows": len(lines)},
                )
                offset += len(lines)
                lines = []
        if lines:
            yield RawRecord(
                payload=header + b"".join(lines), content_type=CSV_CONTENT_TYPE,
                source_url=url, fetched_at=fetched_at,
                acquisition_context={"source_archive_hash": artifact.content_hash,
                                     "source_row_offset": offset, "rows": len(lines)},
            )
        elif offset == 0:
            raise SourceFetchError("bulk: table has no data rows")


def _bz2_jsonl_chunks(
    source: BinaryIO, url: str, fetched_at: datetime, digest: str
) -> Iterator[RawRecord]:
    try:
        with bz2.BZ2File(source) as stream:
            rows: list[bytes] = []
            offset = 0
            chunk_bytes = 0
            while line := stream.readline(MAX_LINE_BYTES + 1):
                if len(line) > MAX_LINE_BYTES:
                    raise SourceFetchError("bulk: JSONL row exceeds byte limit")
                if rows and chunk_bytes + len(line) > MAX_CHUNK_BYTES:
                    yield _jsonl_chunk(rows, url, fetched_at, digest, offset)
                    offset += len(rows)
                    rows = []
                    chunk_bytes = 0
                rows.append(line)
                chunk_bytes += len(line)
                if len(rows) == CHUNK_ROWS:
                    yield _jsonl_chunk(rows, url, fetched_at, digest, offset)
                    offset += len(rows)
                    rows = []
                    chunk_bytes = 0
            if rows:
                yield _jsonl_chunk(rows, url, fetched_at, digest, offset)
            elif offset == 0:
                raise SourceFetchError("bulk: empty JSONL snapshot")
    except (OSError, EOFError, ValueError) as exc:
        raise SourceFetchError("bulk: invalid bzip2 snapshot") from exc


def _jsonl_chunk(
    rows: list[bytes], url: str, fetched_at: datetime, digest: str, offset: int
) -> RawRecord:
    return RawRecord(
        payload=bz2.compress(b"".join(rows)),
        content_type="application/x-bzip2",
        source_url=url,
        fetched_at=fetched_at,
        acquisition_context={
            "source_archive_hash": digest,
            "source_row_offset": offset,
            "rows": len(rows),
        },
    )
