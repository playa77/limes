"""Official federal profile joins: explicit roles/intervals, never inferred party identity."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from lxml import html  # type: ignore[import-untyped]

from limes.errors import SourceParseError
from limes.public_offices.models import Member
from limes.public_offices.parsing import text


def apply_profile(scope: str, row: Member, raw: bytes, digest: str) -> None:
    root = html.fromstring(raw.decode("utf-8"))
    row.profile_evidence_hash = digest
    if scope.startswith("bverfg"):
        headlines = root.xpath('//main//h1[@class="c-person-cv__headline"]')
        if len(headlines) != 1 or text(headlines[0]) != row.name:
            raise SourceParseError("court: profile join does not match the official roster name")
        row.leadership = [
            text(e) for e in root.xpath('//main//*[@class="c-person-cv__subline"]/p') if text(e)
        ]
        for tr in root.xpath("//main//table/tbody/tr"):
            cells = tr.xpath("./td")
            if len(cells) == 2 and "Bundesverfassungsgericht" in text(cells[1]):
                row.service_evidence.append(
                    {
                        "interval": text(cells[0]),
                        "statement": text(cells[1]),
                        "locator": root.getroottree().getpath(tr),
                    }
                )
    elif scope == "br":
        main = root.xpath("//main")
        if len(main) != 1:
            raise SourceParseError("Bundesrat: member profile missing")
        statements = [
            text(e)
            for e in main[0].xpath(".//li")
            if re.match(r"(?:Stellvertretendes )?Mitglied des Bundesrates für", text(e))
        ]
        expected = "Stellvertretendes Mitglied" if row.role == "deputy" else "Mitglied"
        if not statements:
            statements = [
                text(e)
                for e in main[0].xpath(".//p")
                if re.match(r"(?:Stellvertretendes )?Mitglied des Bundesrates seit", text(e))
            ]
        if len(statements) != 1:
            raise SourceParseError("Bundesrat: current profile membership statement missing")
        row.profile_member_class = (
            "deputy" if statements[0].startswith("Stellvertretendes") else "regular"
        )
        if not statements[0].startswith(expected):
            row.conflicts.append("Official directory/profile member classes disagree")
        row.service_evidence.append({"statement": statements[0], "locator": "//main//li"})
        for paragraph in main[0].xpath(".//p"):
            statement = text(paragraph)
            if "Mitglied des Bundesrates" not in statement:
                continue
            row.service_evidence.append(
                {"statement": statement, "locator": root.getroottree().getpath(paragraph)}
            )
            matches = list(
                re.finditer(
                    r"seit (\d{2}\.\d{2}\.\d{4}) "
                    r"(Stellvertretendes Mitglied|Mitglied) des Bundesrates",
                    statement,
                    re.I,
                )
            )
            reverse = re.search(
                r"^(Stellvertretendes Mitglied|Mitglied) des Bundesrates "
                r"seit (\d{2}\.\d{2}\.\d{4})",
                statement,
                re.I,
            )
            if reverse and row.profile_member_class == row.role:
                row.service_start = datetime.strptime(reverse[2], "%d.%m.%Y").replace(tzinfo=UTC)
                row.service_precision = "day"
            if matches:
                last = matches[-1]
                profile_role = (
                    "deputy" if last[2].lower().startswith("stellvertretendes") else "regular"
                )
                if profile_role != row.role:
                    row.conflicts.append("Dated profile membership conflicts with official roster")
                    continue
                row.service_start = datetime.strptime(last[1], "%d.%m.%Y").replace(tzinfo=UTC)
                row.service_precision = "day"
    elif scope == "bp":
        # The biography distinguishes re-election from taking office. Retain
        # the published term statements; an election date is not a tenure start.
        for paragraph in root.xpath("//main//p"):
            for statement in re.split(r"(?<=[.!?])\s+", text(paragraph)):
                if (
                    "Amtszeit" in statement
                    or "Amt des Bundespräsidenten" in statement
                    or ("Bundespräsidenten" in statement and "gewählt" in statement)
                ):
                    row.service_evidence.append(
                        {
                            "statement": statement,
                            "locator": root.getroottree().getpath(paragraph),
                            "kind": "election_statement"
                            if "gewählt" in statement
                            else "term_reference",
                        }
                    )
