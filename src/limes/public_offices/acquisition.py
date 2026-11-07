"""Bounded, archived roster snapshots with durable explicit-resubmission progress."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from limes.archive.store import ArchiveStore
from limes.errors import SourceFetchError, SourceParseError
from limes.graph.driver import GraphDriver
from limes.public_offices.catalogue import BY_CODE, Scope
from limes.public_offices.models import Member, Snapshot
from limes.public_offices.parsing import parse_page
from limes.sources.base import fetch_bytes

MAX_PAGES = 512
MAX_PAGE_BYTES = 5_000_000
MAX_TOTAL_BYTES = 40_000_000
MAX_SECONDS = 1800
AW_PARLIAMENTS = {
    "bt": 5,
    "bw": 6,
    "by": 13,
    "be": 2,
    "bb": 16,
    "hb": 10,
    "hh": 3,
    "he": 11,
    "mv": 9,
    "ni": 12,
    "nw": 4,
    "rp": 7,
    "sl": 14,
    "sn": 17,
    "st": 8,
    "sh": 18,
    "th": 15,
}


def _fetch(url: str) -> bytes:
    return fetch_bytes(url, timeout_s=20, max_bytes=MAX_PAGE_BYTES)


class Acquisition:
    """Constructed only by composition. Source-scoped ingestion locks serialize cursors.

    Cached pages are acquisition progress, never coverage. Every resumed snapshot
    is independently re-read before it can be emitted. Only explicit jobs resume;
    a failure never marks a source successful or closes a person's service interval.
    """

    def __init__(
        self, driver: GraphDriver, archive: ArchiveStore, fetch: Callable[[str], bytes] = _fetch
    ) -> None:
        self.driver = driver
        self.archive = archive
        self.fetch = fetch

    def acquire(self, scope: Scope) -> Snapshot:
        started = time.monotonic()
        source = "public_offices_" + scope.code
        rows = self.driver.read(
            "MATCH (s:Source {source_id:$source}) "
            "OPTIONAL MATCH (r:IngestionRun {source_id:$source}) "
            "RETURN s.office_cursor AS cursor, s.last_run_id AS successful_run, "
            "r.run_id AS active_run ORDER BY r.started_at DESC LIMIT 1",
            {"source": source},
            30,
        )
        cursor: dict[str, object] = {}
        if rows and rows[0].get("cursor"):
            cursor = json.loads(str(rows[0]["cursor"]))
            observed = datetime.fromisoformat(str(cursor["observed_at"]))
            success = rows[0].get("successful_run")
            if (success and success == cursor.get("run_id")) or observed < datetime.now(
                UTC
            ) - timedelta(days=1):
                cursor = {}
        if not cursor:
            cursor = {
                "observed_at": datetime.now(UTC).isoformat(),
                "pages": {},
                "run_id": rows[0].get("active_run") if rows else None,
            }
        cache = cursor["pages"]
        if not isinstance(cache, dict):
            raise SourceFetchError("invalid public offices acquisition cursor")
        cursor["run_id"] = rows[0].get("active_run") if rows else None
        self._save(source, cursor)
        total_bytes = 0
        page_reads = 0

        def read(url: str, fresh: bool) -> tuple[bytes, str, str]:
            nonlocal total_bytes, page_reads
            self._allow(scope, url)
            page_reads += 1
            if time.monotonic() - started > MAX_SECONDS or page_reads > MAX_PAGES * 2 + 4:
                raise SourceFetchError("public offices: time/page bound exceeded")
            cached = cache.get(url) if not fresh else None
            digest = cached.get("sha256") if isinstance(cached, dict) else None
            retrieved_at = str(cached.get("retrieved_at")) if isinstance(cached, dict) else ""
            if isinstance(digest, str) and self.archive.exists(digest):
                raw = self.archive.get(digest)
            else:
                raw = self.fetch(url)
                # Archive exact bytes before any parser sees them.
                digest = self.archive.put(source, raw, "application/octet-stream")
                retrieved_at = datetime.now(UTC).isoformat()
                if not fresh:
                    cache[url] = {"sha256": digest, "retrieved_at": retrieved_at}
                    self._save(source, cursor)
            total_bytes += len(raw)
            if len(raw) > MAX_PAGE_BYTES or total_bytes > MAX_TOTAL_BYTES * 2:
                raise SourceFetchError("public offices: byte bound exceeded")
            return raw, str(digest), retrieved_at

        try:
            first = self._collect(scope, read, False, str(cursor["observed_at"]))
            checked = self._collect(scope, read, True, str(cursor["observed_at"]))
            if _signature(first) != _signature(checked):
                # Keep the old raw evidence, discard mixed-time cached progress.
                self._save(source, {"observed_at": cursor["observed_at"], "pages": {}})
                raise SourceFetchError(
                    "public offices: roster changed during acquisition; resubmit"
                )
            checked.consistent = True
            self.driver.write_batch(
                [
                    (
                        "MATCH (s:Source {source_id:$source}) SET s.office_failure=null",
                        {"source": source},
                    )
                ]
            )
            return checked
        except (SourceFetchError, SourceParseError, ValueError, KeyError, TypeError) as exc:
            self.driver.write_batch(
                [
                    (
                        "MATCH (s:Source {source_id:$source}) SET s.office_failure=$failure, "
                        "s.office_failed_at=$at",
                        {"source": source, "failure": str(exc)[:1000], "at": datetime.now(UTC)},
                    )
                ]
            )
            if isinstance(exc, (ValueError, KeyError, TypeError)):
                raise SourceParseError(f"Malformed roster metadata: {exc}") from exc
            raise

    def _save(self, source: str, cursor: dict[str, object]) -> None:
        self.driver.write_batch(
            [
                (
                    "MATCH (s:Source {source_id:$source}) SET s.office_cursor=$cursor",
                    {"source": source, "cursor": json.dumps(cursor, sort_keys=True)},
                )
            ]
        )

    @staticmethod
    def _allow(scope: Scope, url: str) -> None:
        parts = urlsplit(url)
        hosts = {urlsplit(scope.url).hostname, "www.abgeordnetenwatch.de"}
        if scope.code == "hb":
            hosts.add("static.bremische-buergerschaft.de")
        if scope.code == "rp":
            hosts.add("api.landtag-rlp.de")
        if (
            parts.scheme != "https"
            or parts.hostname not in hosts
            or parts.username
            or parts.password
            or parts.port not in (None, 443)
        ):
            raise SourceFetchError("public offices: unqualified acquisition URL")

    @staticmethod
    def _collect(
        scope: Scope,
        read: Callable[[str, bool], tuple[bytes, str, str]],
        fresh: bool,
        observed: str,
    ) -> Snapshot:
        todo = [scope.url]
        seen: set[str] = set()
        members: dict[str, Member] = {}
        pages: list[dict[str, str]] = []
        counts: set[int] = set()
        terms: set[str] = set()
        departures: set[str] = set()
        entry_dates: dict[str, datetime] = {}
        source_updates: set[str] = set()
        historical_members: list[Member] = []
        name_aliases: dict[str, list[str]] = {}
        while todo:
            url = todo.pop(0)
            if url in seen:
                continue
            if len(seen) >= MAX_PAGES:
                raise SourceFetchError("public offices: pagination bound exceeded")
            seen.add(url)
            raw, digest, retrieved_at = read(url, fresh)
            pages.append({"url": url, "sha256": digest, "retrieved_at": retrieved_at})
            page = parse_page(scope.code, raw, url)
            if page.source_update_note:
                source_updates.add(page.source_update_note)
            if page.expected_count is not None:
                counts.add(page.expected_count)
            if page.term:
                terms.add(page.term)
            name_aliases.update(page.name_aliases)
            for former in page.historical_members:
                former.evidence_hash = digest
                former.evidence_url = url
                historical_members.append(former)
            departures.update(page.departed_ids)
            entry_dates.update(page.entry_dates)
            for member in page.members:
                member.evidence_hash = digest
                member.evidence_url = url
                prior = members.get(member.external_id)
                if prior is not None:
                    # Alphabet pages may link back to the initial letter. A
                    # conflicting duplicate is never silently selected.
                    old = prior.model_dump(exclude={"evidence_hash", "evidence_url", "locator"})
                    new = member.model_dump(exclude={"evidence_hash", "evidence_url", "locator"})
                    if old != new:
                        raise SourceParseError("conflicting duplicate official person ID")
                members[member.external_id] = member
            if page.pagination and any(u in seen for u in page.next_urls):
                raise SourceFetchError("public offices: pagination cycle; checkpoint unchanged")
            todo.extend(u for u in page.next_urls if u not in seen)
        for former in historical_members:
            listed = members.get(former.external_id)
            if listed is not None:
                former.name, former.group = listed.name, listed.group
        for departed in departures:
            ends = [
                m.service_end
                for m in historical_members
                if m.external_id == departed and m.service_end is not None
            ]
            last_exit = max(ends) if ends else None
            reentry = entry_dates.get(departed)
            if last_exit is None or reentry is None or reentry <= last_exit:
                members.pop(departed, None)
        if not members or len(counts) > 1:
            raise SourceParseError("empty roster or inconsistent published serving counts")
        expected = next(iter(counts)) if counts else None
        if expected is not None and expected != len(members):
            raise SourceParseError(
                "published serving count does not reconcile to actual member set"
            )
        term = next(iter(terms)) if len(terms) == 1 else None
        basis = "official_set_and_count" if expected is not None else "official_directory_set"
        if scope.kind == "parliament" and term is None:
            # Qualified secondary term metadata, separately archived. Never
            # confuse an election project with a serving legislative period.
            parliament_url = (
                f"https://www.abgeordnetenwatch.de/api/v2/parliaments/{AW_PARLIAMENTS[scope.code]}"
            )
            raw, digest, retrieved_at = read(parliament_url, fresh)
            pages.append({"url": parliament_url, "sha256": digest, "retrieved_at": retrieved_at})
            project = json.loads(raw)["data"]["current_project"]
            period_id = int(project["id"])
            period_url = f"https://www.abgeordnetenwatch.de/api/v2/parliament-periods/{period_id}"
            raw, digest, retrieved_at = read(period_url, fresh)
            pages.append({"url": period_url, "sha256": digest, "retrieved_at": retrieved_at})
            period = json.loads(raw)["data"]
            as_of = datetime.fromisoformat(observed).date()
            if (
                period["type"] != "legislature"
                or int(period["parliament"]["id"]) != AW_PARLIAMENTS[scope.code]
                or not period.get("start_date_period")
                or datetime.fromisoformat(period["start_date_period"]).date() > as_of
            ):
                raise SourceParseError("secondary current term is unqualified or not yet serving")
            term = f"abgeordnetenwatch:period:{period_id} ({period['label']})"
            basis += ";secondary_term_metadata"
        for member in [*members.values(), *historical_members]:
            member.aliases = name_aliases.get(member.external_id, [])
            member.term = term if scope.kind == "parliament" else None
            if member.service_end is None and member.external_id in entry_dates:
                member.service_start = entry_dates[member.external_id]
                member.service_precision = "day"
            if scope.kind != "parliament":
                from limes.public_offices.profiles import apply_profile

                profile_url = member.profile_url
                if scope.code == "bp":
                    profile_url = (
                        "https://www.bundespraesident.de/DE/bundespraesident/"
                        "biographie/biographie_node.html"
                    )
                raw, digest, retrieved_at = read(profile_url, fresh)
                pages.append({"url": profile_url, "sha256": digest, "retrieved_at": retrieved_at})
                apply_profile(scope.code, member, raw, digest)
        # BR must traverse exactly all 16 distinct official Land selectors.
        if scope.code == "br":
            from urllib.parse import parse_qs

            states = {parse_qs(urlsplit(p["url"]).query).get("param1", [""])[0] for p in pages}
            if not {f"state-{i}" for i in range(2, 18)} <= states:
                raise SourceParseError("Bundesrat Land coverage is incomplete")
            if {m.role for m in members.values()} != {"regular", "deputy"}:
                raise SourceParseError("Bundesrat member-class coverage is incomplete")
        return Snapshot(
            scope=scope.code,
            observed_at=datetime.fromisoformat(observed),
            members=sorted(members.values(), key=lambda m: m.external_id),
            expected_ids=sorted(members),
            pages=pages,
            term=term,
            expected_count=expected,
            check_basis=basis,
            source_updates=sorted(source_updates),
            historical_members=historical_members,
        )


def _signature(snapshot: Snapshot) -> str:
    data = snapshot.model_dump(mode="json", exclude={"pages", "consistent"})
    for member in [*data["members"], *data["historical_members"]]:
        member.pop("evidence_hash", None)
        member.pop("locator", None)
        member.pop("profile_evidence_hash", None)
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def selected_scope(code: str) -> Scope:
    try:
        return BY_CODE[code]
    except KeyError as exc:
        raise SourceFetchError("unknown public office coverage scope") from exc
