"""Archive-first bounded normalization chunks for compressed public snapshots.

The original compressed bytes remain a separate content-addressed raw record.
Derived chunks carry a manifest pointer to that original and source row offset;
they never replace the archived source artifact or invent a publication date.
"""

from __future__ import annotations

import bz2
import csv
import io
import zipfile
from collections.abc import Iterator
from datetime import datetime

from limes.errors import SourceFetchError
from limes.sources.base import payload_hash
from limes.types import RawRecord

CHUNK_ROWS = 1000
MAX_LINE_BYTES = 1024 * 1024
MAX_CHUNK_BYTES = 8 * 1024 * 1024
CSV_CONTENT_TYPE = "text/csv"


def zip_csv_records(payload: bytes, url: str, fetched_at: datetime) -> Iterator[RawRecord]:
    digest = payload_hash(payload)
    yield RawRecord(
        payload=payload,
        content_type="application/zip",
        source_url=url,
        fetched_at=fetched_at,
        acquisition_context={"archive_only": True},
    )
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
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
    try:
        with bz2.BZ2File(io.BytesIO(payload)) as stream:
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
