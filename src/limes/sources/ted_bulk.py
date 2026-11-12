"""TED's supported monthly XML corpus and daily incremental packages.

Closed whole months use one request. Partial months discover one OJ S issue
per publication day through the Search API, then download its entire package.
This avoids the website's per-notice rendering endpoint and calendar WAF.
"""

from __future__ import annotations

import gzip
import json
import re
import tarfile
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import PurePosixPath
from typing import BinaryIO, cast

import structlog
from lxml import etree  # type: ignore[import-untyped]

from limes.errors import SourceFetchError, SourceRunBudgetExceeded
from limes.sources.acquisition import active_acquisition
from limes.sources.base import fetch_bytes_post, now_utc, run_time_left
from limes.sources.bulk import fetch_artifact
from limes.sources.ted import CORPUS_START, DAILY_URL, MONTHLY_URL, SEARCH_URL
from limes.types import RawRecord

logger = structlog.get_logger(__name__)
MAX_NOTICE_BYTES = 16 * 1024**2
MAX_EXPANDED_BYTES = 32 * 1024**3


def _next_month(day: date) -> date:
    return date(day.year + (day.month == 12), day.month % 12 + 1, 1)


def _monthly_available(month: date, today: date) -> bool:
    # TED guarantees monthly packages by the fifth working day of next month.
    ready = _next_month(month)
    count = 0
    while count < 5:
        if ready.weekday() < 5:
            count += 1
        ready += timedelta(days=1)
    return today >= ready


def package_urls(since: datetime, until: datetime) -> Iterator[str]:
    day, end = since.astimezone(UTC).date(), until.astimezone(UTC).date()
    if day < CORPUS_START.date():
        raise SourceFetchError("ted: XML package coverage starts January 2020")
    today = now_utc().date()
    seen: set[str] = set()
    while day <= end:
        following = _next_month(day)
        if day.day == 1 and following <= end + timedelta(days=1) and _monthly_available(
            day, today
        ):
            yield MONTHLY_URL.format(year=day.year, month=day.month)
            day = following
            continue
        body: dict[str, object] = {
            "query": f"PD = {day:%Y%m%d}", "limit": 1,
            "fields": ["publication-number", "ojs-number"],
            "paginationMode": "PAGE_NUMBER", "page": 1,
            "scope": "ALL", "onlyLatestVersions": False,
        }
        try:
            document = json.loads(fetch_bytes_post(SEARCH_URL, body))
            total = document["totalNoticeCount"]
            notices = document["notices"]
            if document.get("timedOut") or type(total) is not int or total < 0:
                raise ValueError("invalid count or timed out")
            if not isinstance(notices, list) or bool(total) != bool(notices):
                raise ValueError("inconsistent results")
            if not total and _monthly_available(day, today):
                # Search does not expose all archived years (2011 returns zero
                # despite a populated official package). Never equate that
                # search result with an empty historical publication window.
                yield MONTHLY_URL.format(year=day.year, month=day.month)
                day = following
                continue
            if total:
                match = re.fullmatch(r"(\d+)/(\d{4})", notices[0]["ojs-number"])
                if match is None or int(match[2]) != day.year:
                    raise ValueError("invalid OJ S number")
                url = DAILY_URL.format(year=int(match[2]), issue=int(match[1]))
                if url not in seen:
                    seen.add(url)
                    yield url
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise SourceFetchError(f"ted: invalid package discovery for {day}") from exc
        day += timedelta(days=1)


def fetch_packages(since: datetime, until: datetime) -> Iterator[RawRecord]:
    for url in package_urls(since, until):
        acquisition = active_acquisition.get()
        if acquisition is not None and acquisition.unit_loaded(url):
            logger.info("ted: package already fully loaded; retained receipt", package=url)
            continue
        count = 0
        package_count = 0
        monthly = re.search(r"/monthly/(\d{4})-(\d{1,2})$", url)
        partial_month = False
        if monthly:
            month = date(int(monthly[1]), int(monthly[2]), 1)
            partial_month = (since.date() > month or
                             until.date() < _next_month(month) - timedelta(days=1))
        record_keys: list[str] = []
        expanded = [0]
        members: set[str] = set()
        fetched_at = now_utc()
        logger.info("ted: downloading XML package", package=url,
                    coverage="incomplete until every member is loaded")
        with fetch_artifact(url) as artifact:
            fetched_at = artifact.fetched_at
            try:
                for member_name, payload in _xml_members(artifact.stream, "", 0, expanded, members):
                    match = re.fullmatch(
                        r"0*(\d+)[_-](\d{4})\.xml", PurePosixPath(member_name).name.lower()
                    )
                    if match is None:
                        raise SourceFetchError("ted: unexpected notice filename")
                    if int(match[2]) < CORPUS_START.year:
                        raise SourceFetchError("ted: package contains a pre-2020 publication")
                    package_count += 1
                    if partial_month and not (
                        since.date() <= _publication_date(payload) <= until.date()
                    ):
                        continue
                    notice_id = f"{int(match[1])}-{match[2]}"
                    count += 1
                    raw = RawRecord(
                        payload=payload, content_type="application/xml",
                        source_url=f"https://ted.europa.eu/en/notice/{notice_id}/xml",
                        fetched_at=fetched_at,
                        acquisition_context={
                            "requested_notice_id": notice_id,
                            "source_archive_hash": artifact.content_hash,
                            "source_member": member_name, "package_url": url, "unit": url,
                        },
                    )
                    if acquisition is not None:
                        record_keys.append(acquisition.record_key(raw))
                    yield raw
            except (tarfile.TarError, EOFError, OSError) as exc:
                raise SourceFetchError(f"ted: invalid XML package {url}") from exc
        if not package_count:
            raise SourceFetchError(f"ted: package has no XML notices: {url}")
        if acquisition is not None:
            acquisition.finish_unit(url, record_keys)
        logger.info("ted: XML package traversed", package=url, notices=count,
                    package_notices=package_count, expanded_bytes=expanded[0])


def _publication_date(payload: bytes) -> date:
    """Filter an archive fallback by actual publication date, never issue date."""
    try:
        root = etree.fromstring(payload, etree.XMLParser(resolve_entities=False, no_network=True))
        for name in ("DATE_PUB", "DT_PUBLISH", "PublicationDate"):
            for element in root.iter():
                if not isinstance(element.tag, str) or etree.QName(element).localname != name:
                    continue
                value = (element.text or "").strip()
                if re.fullmatch(r"\d{8}", value):
                    return datetime.strptime(value, "%Y%m%d").date()
                return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except (etree.XMLSyntaxError, ValueError) as exc:
        raise SourceFetchError("ted: invalid publication date in partial-month archive") from exc
    raise SourceFetchError("ted: partial-month archive member lacks publication date")


def _xml_members(
    stream: BinaryIO, prefix: str, depth: int, expanded: list[int], members: set[str]
) -> Iterator[tuple[str, bytes]]:
    """Historical monthly packages wrap daily tar.gz files; others contain XML directly."""
    if depth > 1:
        raise SourceFetchError("ted: package nesting exceeds monthly/daily layout")
    with gzip.GzipFile(fileobj=stream, mode="rb") as decoded, tarfile.open(
        fileobj=decoded, mode="r|"
    ) as archive:
        for member in archive:
            left = run_time_left()
            if left is not None and left <= 0:
                raise SourceRunBudgetExceeded("source deadline during package traversal")
            if member.isdir():
                continue
            if not member.isfile():
                raise SourceFetchError("ted: package contains non-regular member")
            path = PurePosixPath(member.name)
            name = prefix + member.name
            if path.is_absolute() or ".." in path.parts or name in members:
                raise SourceFetchError("ted: unsafe or duplicate package member")
            members.add(name)
            expanded[0] += member.size + 512
            if expanded[0] > MAX_EXPANDED_BYTES or len(members) > 1_000_000:
                raise SourceFetchError("ted: expanded package exceeds limits")
            if member.name.lower().endswith((".tar.gz", ".tgz")):
                nested = archive.extractfile(member)
                if nested is None:
                    raise SourceFetchError("ted: unreadable daily package")
                with nested:
                    yield from _xml_members(cast(BinaryIO, nested), name + "!/", depth + 1,
                                            expanded, members)
                continue
            if path.suffix.lower() != ".xml":
                continue
            if not 0 < member.size <= MAX_NOTICE_BYTES:
                raise SourceFetchError("ted: notice exceeds byte limit or is empty")
            entry = archive.extractfile(member)
            if entry is None:
                raise SourceFetchError("ted: unreadable notice member")
            payload = entry.read(MAX_NOTICE_BYTES + 1)
            if len(payload) != member.size:
                raise SourceFetchError("ted: truncated notice member")
            yield name, payload
        while trailer := decoded.read(1024 * 1024):
            expanded[0] += len(trailer)
            if expanded[0] > MAX_EXPANDED_BYTES:
                raise SourceFetchError("ted: expanded package trailer exceeds limit")
