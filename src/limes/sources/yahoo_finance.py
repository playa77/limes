"""Yahoo secondary observations, scoped to reviewed company/listing selections."""

from __future__ import annotations

import json
import math
from collections.abc import Iterator
from datetime import datetime
from typing import Any, Literal

from limes.enrichment.common import date, raw, snapshot
from limes.enrichment.models import AcquisitionTarget, SectionStatus
from limes.enrichment.transport import MAX_BYTES, YahooTransport
from limes.errors import SourceFetchError, SourceParseError
from limes.sources.base import now_utc
from limes.types import NormalizedRecord, RawRecord

MODULES = (
    "price",
    "assetProfile",
    "institutionOwnership",
    "fundOwnership",
    "majorDirectHolders",
    "majorHoldersBreakdown",
    "calendarEvents",
    "secFilings",
)


def number(value: Any) -> int | float | None:
    value = raw(value)
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return value
    return None


def governance_role(officer: dict[str, Any]) -> tuple[str, str | None]:
    """Classify only explicit role/body words, keeping the exact source title too."""
    title = str(officer.get("title") or "").casefold()
    body = officer.get("body")
    if body is None:
        for phrases, name in (
            (("supervisory board", "aufsichtsrat"), "supervisory_board"),
            (("management board", "managing board", "vorstand"), "management_board"),
            (("board of directors",), "board_of_directors"),
        ):
            if any(phrase in title for phrase in phrases):
                body = name
                break
    kind = officer.get("roleType")
    if kind is None:
        if body == "supervisory_board":
            kind = "supervisory"
        elif body in ("management_board", "board_of_directors"):
            kind = "board_role"
        elif any(word in title for word in ("chief ", "ceo", "cfo", "coo", "cto")):
            kind = "executive"
        else:
            kind = "unspecified_officer"
    return str(kind), str(body) if body is not None else None


class YahooFinanceAdapter:
    source_id = "yahoo_finance"
    name = "Yahoo Finance"
    kind: Literal["structured", "unstructured"] = "structured"
    trust_rank = 0.70
    supports_backfill = False
    supports_incremental = False

    def __init__(self, transport: YahooTransport | None = None) -> None:
        self.targets: list[AcquisitionTarget] = []
        self.transport = transport or YahooTransport()

    def configure(self, targets: list[AcquisitionTarget]) -> None:
        if not 1 <= len(targets) <= 10:
            raise SourceFetchError("select between one and ten companies")
        self.targets = targets

    def fetch(self, since: datetime | None, until: datetime | None) -> Iterator[RawRecord]:
        if not self.targets:
            raise SourceFetchError("Yahoo requires reviewed enrichment selections")
        for target in self.targets:
            selection = target.selection
            if not selection.symbol or target.entity.type != "Corporation":
                raise SourceFetchError(
                    "Yahoo selection requires a corporation and reviewed listing"
                )
            identity_ok = False
            blocked_state = "failed"
            # Fetch each section independently; one failure cannot erase other evidence.
            for section in MODULES:
                state = "available"
                try:
                    if section != "price" and not identity_ok:
                        payload, state = b'{"error":"listing identity unavailable"}', blocked_state
                    else:
                        payload, state = self.transport.get(selection.symbol, section)
                    if section == "price" and state == "unsupported":
                        blocked_state = "unsupported"
                    if section == "price" and state == "available":
                        try:
                            price = json.loads(payload)["quoteSummary"]["result"][0]["price"]
                            identity_ok = (
                                price.get("symbol") == selection.symbol
                                and price.get("exchange") == selection.exchange
                            )
                        except (ValueError, TypeError, KeyError, IndexError):
                            identity_ok = False
                except SourceFetchError:
                    payload, state = b'{"error":"provider request failed"}', "failed"
                yield RawRecord(
                    payload=payload,
                    content_type="application/json",
                    fetched_at=now_utc(),
                    source_url=f"https://finance.yahoo.com/quote/{selection.symbol}/",
                    acquisition_context={
                        "target": target.model_dump(mode="json"),
                        "section": section,
                        "status": state,
                    },
                )

    def normalize(self, record: RawRecord) -> NormalizedRecord:
        try:
            return self._normalize(record)
        except (ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
            context = record.acquisition_context or {}
            if "target" in context and "section" in context:
                return snapshot(
                    self,
                    record,
                    SectionStatus(
                        section=str(context["section"]),
                        status="failed",
                        reason="malformed or oversized provider section",
                    ),
                    [],
                )
            raise SourceParseError(f"Yahoo malformed payload: {exc}") from exc

    def _normalize(self, record: RawRecord) -> NormalizedRecord:
        if len(record.payload) > MAX_BYTES:
            raise ValueError("response too large")
        context = record.acquisition_context or {}
        target = AcquisitionTarget.model_validate(context["target"])
        selection = target.selection
        section = str(context["section"])
        if section not in MODULES:
            raise ValueError("unknown section")
        state = str(context.get("status", "available"))
        if state != "available":
            status = SectionStatus(section=section, status=state)  # type: ignore[arg-type]
            return snapshot(self, record, status, [])
        data = json.loads(record.payload)
        response = data["quoteSummary"]
        if response.get("error"):
            return snapshot(
                self,
                record,
                SectionStatus(section=section, status="failed", reason="provider error"),
                [],
            )
        result = response.get("result")
        if not isinstance(result, list) or len(result) != 1:
            raise ValueError("expected one quoteSummary result")
        data = result[0].get(section)
        if not isinstance(data, dict) or not data:
            return snapshot(self, record, SectionStatus(section=section, status="missing"), [])
        observations: list[dict[str, Any]] = []
        if section == "price":
            if data.get("symbol") != selection.symbol or data.get("exchange") != selection.exchange:
                return snapshot(
                    self,
                    record,
                    SectionStatus(
                        section=section, status="ambiguous", reason="listing identity mismatch"
                    ),
                    [],
                )
            observations.append(
                {
                    "kind": "listing",
                    "name": data.get("longName"),
                    "currency": data.get("currency"),
                    "quote_type": data.get("quoteType"),
                }
            )
        elif section == "assetProfile":
            observations.append(
                {
                    "kind": "profile",
                    "name": target.entity.label,
                    **{
                        {
                            "longBusinessSummary": "business_summary",
                            "fullTimeEmployees": "employees_count",
                        }.get(key, key): data.get(key)
                        for key in (
                            "country",
                            "city",
                            "website",
                            "industry",
                            "sector",
                            "longBusinessSummary",
                            "fullTimeEmployees",
                        )
                    },
                }
            )
            officers = data.get("companyOfficers", [])
            if not isinstance(officers, list) or len(officers) > 500:
                raise ValueError("invalid or oversized officer roster")
            for index, officer in enumerate(officers):
                title = officer.get("title")
                role_kind, body = governance_role(officer)
                # Exact title retained. Do not infer director membership from an executive title.
                observations.append(
                    {
                        "kind": "governance",
                        "name": officer.get("name"),
                        "role_title": title,
                        "body": body,
                        "role_kind": role_kind,
                        "term_start": date(officer.get("startDate")),
                        "term_end": date(officer.get("endDate")),
                        "source_as_of": date(officer.get("asOfDate")),
                        "evidence_field": f"assetProfile.companyOfficers[{index}]",
                        "identity_status": "unresolved",
                    }
                )
            observations.append(
                {
                    "kind": "section_availability",
                    "name": "board_structure",
                    "status": "missing",
                    "reason": "Officer roster does not establish complete board structure",
                    "evidence_field": "assetProfile.companyOfficers",
                }
            )
        elif section in ("institutionOwnership", "fundOwnership", "majorDirectHolders"):
            rows = data.get("ownershipList" if section != "majorDirectHolders" else "holders", [])
            if not isinstance(rows, list) or len(rows) > 1000:
                raise ValueError("invalid or oversized holder section")
            row_field = "holders" if section == "majorDirectHolders" else "ownershipList"
            for index, owner in enumerate(rows):
                observations.append(
                    {
                        "kind": "holding",
                        "name": owner.get("organization") or owner.get("name"),
                        "shares": number(owner.get("position", owner.get("positionDirect"))),
                        "ratio": number(owner.get("pctHeld")),
                        "ratio_basis": "unknown",
                        "quantity_unit": "shares",
                        "ratio_unit": "fraction",
                        "value": number(owner.get("value", owner.get("valueDirect"))),
                        "currency": owner.get("currency"),
                        "source_as_of": date(owner.get("reportDate")),
                        "interest_kind": owner.get("ownership", "unknown"),
                        "evidence_field": f"{section}.{row_field}[{index}]",
                        "identity_status": "unresolved",
                        "overlap_policy": "do_not_sum",
                    }
                )
        elif section == "majorHoldersBreakdown":
            for field, basis in (
                ("insidersPercentHeld", "shares"),
                ("institutionsPercentHeld", "shares"),
                ("institutionsFloatPercentHeld", "float"),
                ("freeFloatPercentHeld", "shares"),
            ):
                if number(data.get(field)) is not None:
                    observations.append(
                        {
                            "kind": "aggregate_ratio",
                            "name": field,
                            "ratio": number(data[field]),
                            "ratio_basis": basis,
                            "ratio_unit": "fraction",
                            "evidence_field": f"{section}.{field}",
                        }
                    )
        elif section == "calendarEvents":
            earnings = data.get("earnings", {})
            dates = earnings.get("earningsDate", [])
            if not isinstance(dates, list) or len(dates) > 20:
                raise ValueError("invalid calendar")
            for value in dates:
                observations.append(
                    {
                        "kind": "earnings_calendar",
                        "event_date": date(value),
                        "event_status": (
                            "estimated"
                            if earnings.get("isEarningsDateEstimate") is True
                            else "confirmed"
                            if earnings.get("isEarningsDateEstimate") is False
                            else "unknown"
                        ),
                        "fiscal_period": earnings.get("fiscalPeriod"),
                        "report_kind": None,
                        "publication_date": None,
                    }
                )
        elif section == "secFilings":
            filings = data.get("filings", [])
            if not isinstance(filings, list) or len(filings) > 1000:
                raise ValueError("invalid filings")
            for index, filing in enumerate(filings):
                observations.append(
                    {
                        "kind": "report_metadata",
                        "report_kind": filing.get("type"),
                        "publication_date": date(filing.get("date")),
                        "fiscal_period": filing.get("fiscalPeriod"),
                        "report_url": filing.get("edgarUrl") or filing.get("url"),
                        "event_status": "published",
                        "evidence_field": f"secFilings.filings[{index}]",
                    }
                )
        extra = {
            "symbol": selection.symbol,
            "exchange": selection.exchange,
            "listing_id": f"yahoo:{selection.exchange}:{selection.symbol}",
            "security_id": f"isin:{selection.isin}" if selection.isin else None,
            "share_class": selection.share_class,
            "wikidata_qid": selection.qid,
        }
        return snapshot(
            self,
            record,
            SectionStatus(section=section, status="available"),
            observations,
            extra=extra,
        )
