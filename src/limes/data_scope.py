"""Source publication/observation boundary; never a fact-validity cutoff."""

from datetime import UTC, datetime

from limes.errors import SourceFetchError

DATA_START = datetime(2020, 1, 1, tzinfo=UTC)
DATA_SCOPE_VERSION = "source-evidence-from-2020-01-01-v1"


def utc(value: datetime) -> datetime:
    """Interpret legacy naive dates as UTC, as source adapters already do."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def scoped_window(
    since: datetime | None, until: datetime | None
) -> tuple[datetime, datetime | None]:
    """Clamp the lower bound; reject windows wholly outside project scope."""
    start = max(DATA_START, utc(since)) if since is not None else DATA_START
    end = utc(until) if until is not None else None
    if end is not None and end < start:
        raise SourceFetchError(
            "data scope starts 2020-01-01 (inclusive); window end precedes its scoped start"
        )
    return start, end


def source_date_eligible(value: datetime) -> bool:
    """Validate acquisition/edition metadata, never internal historical fact dates."""
    return utc(value) >= DATA_START


def require_source_date(value: datetime, source_id: str) -> None:
    if not source_date_eligible(value):
        raise SourceFetchError(
            f"{source_id}: acquisition/edition observation {value.isoformat()} "
            "precedes 2020-01-01; download time cannot refresh old evidence"
        )
