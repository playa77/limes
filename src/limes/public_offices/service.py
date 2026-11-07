"""Acquired current/as-of membership and set reconciliation. Reads never acquire data."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from limes.api.models import native_datetime
from limes.graph.driver import GraphDriver
from limes.public_offices.catalogue import BY_CODE, SCOPES
from limes.public_offices.models import OfficesResponse, ScopeCoverage


def read_offices(
    driver: GraphDriver,
    *,
    scope: str | None = None,
    term: str | None = None,
    as_of: datetime | None = None,
    believed: datetime | None = None,
    limit: int = 200,
    include_members: bool = True,
) -> OfficesResponse:
    result = OfficesResponse()
    reference = as_of or datetime.now(UTC)
    chosen = [BY_CODE[scope]] if scope else list(SCOPES)
    remaining = limit
    for item in chosen:
        coverage = ScopeCoverage(scope=item.code, institution=item.name)
        result.scopes.append(coverage)
        rows = driver.read(
            "MATCH (s:RosterSnapshot {scope:$scope}) "
            "WHERE ($as_of IS NULL OR s.observed_at <= $as_of) "
            "AND ($believed IS NULL OR s.created_at <= $believed) "
            "AND ($term IS NULL OR s.term=$term) "
            "WITH s ORDER BY s.observed_at DESC, s.created_at DESC, s.entity_id LIMIT 1 "
            "OPTIONAL MATCH (c:RosterLoadCheck {snapshot_id:s.entity_id}) "
            "WHERE $believed IS NULL OR c.checked_at <= $believed "
            "WITH s,c ORDER BY c.checked_at DESC LIMIT 1 "
            "OPTIONAL MATCH (r:IngestionRun {run_id:coalesce(c.run_id,s.run_id)}) "
            "RETURN properties(s) AS snapshot, r.finished_at AS run_finished, "
            "r.errors AS run_errors",
            {"scope": item.code, "as_of": as_of, "believed": believed, "term": term},
            30,
        )
        failures = driver.read(
            "MATCH (s:Source {source_id:$source}) RETURN s.office_failure AS failure, "
            "s.office_failed_at AS failed_at, s.last_success_at AS success",
            {"source": "public_offices_" + item.code},
            30,
        )
        if not rows:
            coverage.diagnosis.append("No acquired roster for this scope/time/term.")
            if failures and failures[0].get("failure"):
                failed_at = native_datetime(failures[0].get("failed_at"))
                if not believed or (failed_at is not None and failed_at <= believed):
                    coverage.status = "failed"
                    coverage.diagnosis.append(str(failures[0]["failure"]))
            continue
        snapshot: dict[str, Any] = rows[0]["snapshot"]
        coverage.snapshot_id = str(snapshot["entity_id"])
        coverage.observed_at = native_datetime(snapshot["observed_at"])
        coverage.term = snapshot.get("term")
        coverage.check_basis = snapshot.get("check_basis")
        coverage.expected = snapshot.get("expected_count")
        expected_ids = set(json.loads(snapshot["expected_ids"]))
        coverage.acquired = len(expected_ids)
        coverage.stale = bool(
            coverage.observed_at and coverage.observed_at < reference - timedelta(days=7)
        )
        members = driver.read(
            "MATCH (m:RosterMembership {snapshot_id:$snapshot})"
            "-[binding:ROSTER_PERSON]->(p:Person) "
            "WHERE coalesce(m.is_current,true) AND "
            "($believed IS NULL OR binding.recorded_at <= $believed) "
            "CALL (m) { OPTIONAL MATCH (r:PersonIdentityReview {external_id:m.external_id}) "
            "WHERE $believed IS NULL OR r.recorded_at <= $believed "
            "RETURN r ORDER BY r.recorded_at DESC LIMIT 1 } "
            "OPTIONAL MATCH (canonical:Person {entity_id:r.person_id}) "
            "RETURN DISTINCT properties(m) AS member, "
            "coalesce(canonical.entity_id,p.entity_id) AS person_id, "
            "coalesce(canonical.label,p.label) AS person_label, properties(r) AS identity_review "
            "ORDER BY member.external_id LIMIT 5001",
            {"snapshot": snapshot["entity_id"], "believed": believed},
            30,
        )
        actual_ids: set[str] = set()
        persons: set[str] = set()
        for row in members:
            member = {
                k: (v.to_native() if hasattr(v, "to_native") else v)
                for k, v in dict(row["member"]).items()
            }
            if row.get("identity_review"):
                member["identity_status"] = "operator_reviewed"
                member["identity_review_evidence"] = row["identity_review"]["evidence_hash"]
                member["identity_review_note"] = row["identity_review"]["note"]
            for field in (
                "service_start",
                "service_end",
                "party_label",
                "group_label",
                "constituency",
                "mandate_kind",
                "term",
                "represented_land",
                "profile_member_class",
                "profile_evidence_hash",
                "service_precision",
                "source_updated_text",
            ):
                member.setdefault(field, None)
            prefix = f"official:{item.code}:"
            actual_ids.add(str(member["external_id"]).removeprefix(prefix))
            persons.add(str(row["person_id"]))
            if member.get("identity_status") == "candidate_review_required":
                coverage.unresolved += 1
            # Observation-as-of and source-provided service intervals are
            # independent filters; missing dates stay explicitly unknown.
            if as_of:
                start = member.get("service_start")
                end = member.get("service_end")
                if (isinstance(start, datetime) and start > as_of) or (
                    isinstance(end, datetime) and end <= as_of
                ):
                    continue
            if not include_members:
                continue
            if remaining:
                member["person_id"] = row["person_id"]
                member["person_label"] = row["person_label"]
                result.members.append(member)
                remaining -= 1
            else:
                result.truncated = True
        coverage.loaded = len(actual_ids)
        coverage.distinct_persons = len(persons)
        coverage.failed_rows = len(expected_ids - actual_ids)
        conflicts = sum(
            bool(json.loads(str(row["member"].get("conflicts") or "[]"))) for row in members
        )
        coverage.failed_rows += conflicts
        if len(members) > 5000 or actual_ids != expected_ids:
            coverage.status = "partial"
            coverage.diagnosis.append("Persisted member set differs from official acquired IDs.")
        elif coverage.unresolved:
            coverage.status = "partial"
            coverage.diagnosis.append(
                "Name candidates require verified identity evidence; no name-only merge."
            )
        elif coverage.expected is None:
            coverage.status = "unverified"
            coverage.diagnosis.append(
                "Official directory set reconciled; independent serving count unavailable."
            )
        else:
            coverage.status = "reconciled"
        if conflicts:
            coverage.status = "partial"
            coverage.diagnosis.append(
                "Official roster/profile claims conflict; inspect retained evidence."
            )
        run_finished = native_datetime(rows[0].get("run_finished"))
        if (
            run_finished is None
            or rows[0].get("run_errors") != 0
            or (believed is not None and run_finished > believed)
        ):
            coverage.status = "failed" if rows[0].get("run_errors") else "partial"
            coverage.diagnosis.append(
                "Snapshot ingestion is incomplete or failed; no successful coverage checkpoint."
            )
        coverage.diagnosis.extend(json.loads(snapshot.get("source_updates") or "[]"))
        if coverage.stale:
            coverage.diagnosis.append("Roster observation is older than seven days.")
        if failures and failures[0].get("failure"):
            failed_at = native_datetime(failures[0].get("failed_at"))
            if not believed or (failed_at is not None and failed_at <= believed):
                coverage.status = "failed"
                coverage.diagnosis.append(str(failures[0]["failure"]))
    if result.truncated:
        result.diagnosis.append("Member response truncated; select a scope or narrower term/time.")
    if result.scopes and all(s.status == "reconciled" and not s.stale for s in result.scopes):
        result.coverage_status = "reconciled"
    result.diagnosis.append(
        "Current means observed on the dated official serving roster. Unknown service dates "
        "remain unknown; an absent row does not establish a resignation date. "
        "Freshness measures observation age; provider update time may remain unknown. "
        "Coverage scopes and mandate observations are not distinct-person national totals."
    )
    return result
