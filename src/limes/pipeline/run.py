# src/limes/pipeline/run.py | v1.0.0 | introduced by WP-27
"""Pipeline run orchestration per Technical Specification §8.6.1 and
§15.3 traces 1 and 2 (Doc 1 §3.4–3.5, §9.1–9.2).

`execute_run` is the one function that runs an ingestion end-to-end:
adapter fetch → archive → normalize → (structured: validate + load;
document: gate → extract → cache → resolve → validate + load) → close the
`:IngestionRun` record. It constructs nothing (§8.15) and owns exactly two
node types — `:Source` and `:IngestionRun` (§15.2). Nothing is dropped
without a counter: every skip, rejection, and gate-out lands in the run
record with its reason logged.

**Provenance stamping (§15.2).** `source_id` and `source_trust` are stamped
here from the registry on every assertion — the binding authority, idempotent
over the adapters' own stamps — and `content_hash` from `ArchiveStore.put`.
For document records the resolver's five pipeline-known intermediates
(D-29) are re-stamped before load and `assertion_id` is recomputed with the
real `source_id`; the intermediates never reach the graph.

**Failure semantics (§8.6.1).** Record-level failures (`SourceParseError` —
the only record-level error any module raises today; `ExtractionSchemaError`,
`ValidationRejected`, and `EndpointUnidentified` are specified for future
raisers and land in `errors` when they arrive) are counted in `errors` and
skipped. Fetch and configuration failures (`SourceFetchError`,
`ExtractionError`, `GraphWriteError`) abort the run: the run record is
closed with `errors` counted, then re-raised. `BudgetExhausted` closes the
run cleanly — `finished_at` set, `last_success_at` untouched — logs the
queued remainder, and re-raises so the CLI can report the termination
(AC-14).

**The cache ordering (D-38).** `cache.put` runs only after the document's
load succeeded; a mid-document failure leaves no cache entry that would
gate the document out on retry and lose its assertions permanently.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from contextlib import ExitStack, nullcontext
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Literal

import structlog
from pydantic import BaseModel

from limes.composition import embedder_for
from limes.errors import (
    ExtractionError,
    GraphWriteError,
    SourceFetchError,
    SourceParseError,
    SourceRunBudgetExceeded,
    SourceSliceEnded,
)
from limes.extraction.cache import put as cache_put
from limes.graph.loader import load, news_claim_id, retract, save_claims, save_document
from limes.ontology.validator import validate_assertions
from limes.pipeline import window as window_module
from limes.pipeline.gate import gate_document
from limes.resolution.resolve import resolve_assertions
from limes.sources.acquisition import AcquisitionSession
from limes.sources.base import (
    SourceAdapter,
    deterministic_assertion_id,
    hash_entity_id,
    source_run_scope,
)
from limes.types import (
    Assertion,
    IngestionRunRecord,
    NormalizedRecord,
    RawRecord,
    SourceRecord,
)

if TYPE_CHECKING:
    from limes.config import Settings
    from limes.resolution.resolve import RunContext

logger = structlog.get_logger(__name__)

_SOURCE_MERGE = """
MERGE (s:Source {source_id: $source_id})
ON CREATE SET s.name = $name,
              s.kind = $kind,
              s.trust_rank = $trust_rank
ON MATCH SET s.name = $name,
             s.kind = $kind,
             s.trust_rank = $trust_rank
RETURN s
"""

_SOURCE_READ = """
MATCH (s:Source {source_id: $source_id})
RETURN s.source_id AS source_id,
       s.name AS name,
       s.kind AS kind,
       s.trust_rank AS trust_rank,
       s.last_success_at AS last_success_at,
       s.corpus_complete AS corpus_complete,
       s.last_run_id AS last_run_id,
       s.initial_window_from AS initial_window_from
"""

_RUN_OPEN = """
MATCH (s:Source {source_id: $source_id})
SET s.initial_window_from = coalesce(s.initial_window_from, $initial_window_from)
CREATE (r:IngestionRun {
    run_id: $run_id,
    source_id: $source_id,
    mode: $mode,
    started_at: $started_at,
    window_from: $window_from,
    window_to: $window_to
})
"""

_RUN_CLOSE = """
MATCH (r:IngestionRun {run_id: $run_id})
SET r.finished_at = $finished_at,
    r.records_fetched = $records_fetched,
    r.nodes_created = $nodes_created,
    r.nodes_matched = $nodes_matched,
    r.assertions_written = $assertions_written,
    r.assertions_skipped = $assertions_skipped,
    r.assertions_rejected = $assertions_rejected,
    r.documents_gated_out = $documents_gated_out,
    r.errors = $errors,
    r.cost_eur = $cost_eur,
    r.state = $state,
    r.last_progress_at = $finished_at,
    r.last_error = $last_error
"""

_RUN_PROGRESS = """
MATCH (r:IngestionRun {run_id: $run_id})
SET r.state = $state, r.last_progress_at = $last_progress_at,
    r.last_error = $last_error, r.records_fetched = $records_fetched,
    r.assertions_written = $assertions_written, r.errors = $errors
"""

_SOURCE_SUCCESS = """
MATCH (s:Source {source_id: $source_id})
SET s.last_success_at = CASE
    WHEN s.last_success_at > $last_success_at THEN s.last_success_at
    ELSE $last_success_at END,
    s.last_run_id = $last_run_id,
    s.corpus_complete = coalesce(s.corpus_complete, false) OR $corpus_complete,
    s.acquisition_manifest_hash = $acquisition_manifest_hash
WITH s
MATCH (r:IngestionRun {run_id: $last_run_id})
SET r.acquisition_manifest_hash = $acquisition_manifest_hash
"""

_PRIOR_DOCUMENT_ASSERTIONS = """
MATCH ()-[r]->()
WHERE r.evidence_document_id = $content_hash
  AND r.source_id = $source_id
  AND r.retracted_at IS NULL
  AND (r.evidence_channel = 'extracted'
       OR (r.evidence_channel IS NULL AND r.extractor_model IS NOT NULL))
RETURN r.assertion_id AS assertion_id
"""


class RunSpec(BaseModel):
    """An ingestion request; the legacy budget_eur field is ignored."""

    source_id: str
    mode: Literal["ingest", "backfill", "reextract"]
    since: datetime | None = None
    until: datetime | None = None
    budget_eur: Decimal | None = None
    relative_days: int | None = None


def execute_run(spec: RunSpec, ctx: RunContext) -> IngestionRunRecord:
    """Execute one ingestion run end-to-end and return its durable record.

    `ctx` is the composition root's `RunContext` (owned by
    `resolution/resolve.py` per D-28); `execute_run` constructs nothing
    and consumes only what the context carries (§8.15).
    """
    adapter = ctx.registry.get(spec.source_id)
    run_scope = getattr(adapter, "run_scope", nullcontext)
    with run_scope():
        if ctx.acquisitions is None or spec.mode == "reextract" or spec.source_id in (
            "news", "wikipedia", "yahoo_finance"
        ) or spec.source_id.startswith("public_offices_"):
            return _execute_run(spec, ctx)
        version = json.dumps([
            "BE57-1", ctx.settings.revision, ctx.ontology.version, ctx.settings.extraction_model,
            ctx.settings.extraction_prompt_version, ctx.settings.extraction_schema_version,
        ])
        request = {"mode": spec.mode,
                   "since": None if spec.relative_days is not None else spec.since,
                   "relative_days": spec.relative_days, "until": spec.until,
                   "target": [ctx.settings.neo4j_uri, ctx.settings.neo4j_database]}
        with ctx.acquisitions.session(spec.source_id, request, version) as acquisition:
            return _execute_run(spec, ctx, acquisition)


def _source_budget(settings: Settings, source_id: str) -> tuple[int, int]:
    """PA-1 R3: (wall-clock seconds, consecutive-attempt cap) for one run.

    Operators may pin a per-source floor/override as
    `LIMES_SOURCE_BUDGET_<ID>_SECONDS` (upper-cased source id, e.g.
    `LIMES_SOURCE_BUDGET_GLEIF_SECONDS`); the generic run budget applies
    otherwise. Attempt caps are global by design.
    """
    override = os.environ.get(f"LIMES_SOURCE_BUDGET_{source_id.upper()}_SECONDS")
    seconds = settings.source_run_budget_seconds
    if override:
        try:
            seconds = int(override)
        except ValueError as exc:
            raise SourceRunBudgetExceeded(
                f"invalid {f'LIMES_SOURCE_BUDGET_{source_id.upper()}_SECONDS'}: {override}"
            ) from exc
    return seconds, settings.source_transport_budget_attempts


def _execute_run(
    spec: RunSpec, ctx: RunContext, acquisition: AcquisitionSession | None = None
) -> IngestionRunRecord:
    """Run while the adapter's optional acquisition scope remains active."""
    adapter = ctx.registry.get(spec.source_id)
    started = time.monotonic()  # PA-1 R3: budget measured from run start

    ctx.driver.write_batch([(_SOURCE_MERGE, _source_params(adapter))])
    source_node = _read_source(ctx, spec.source_id)
    since, until = window_module.resolve_window(spec, adapter, source_node, ctx.settings)
    if acquisition is not None:
        since, until = acquisition.window(since, until)

    record = IngestionRunRecord(
        run_id=uuid.uuid4().hex,
        source_id=spec.source_id,
        mode=spec.mode,
        started_at=datetime.now(UTC),
        window_from=since,
        window_to=until,
    )
    ctx.driver.write_batch(
        [
            (
                _RUN_OPEN,
                {
                    "run_id": record.run_id,
                    "source_id": record.source_id,
                    "mode": record.mode,
                    "started_at": record.started_at,
                    "window_from": since,
                    "window_to": until,
                    "initial_window_from": since if spec.since is None else None,
                },
            )
        ]
    )
    logger.info(
        "ingestion run opened",
        run_id=record.run_id,
        source_id=spec.source_id,
        mode=spec.mode,
        window_from=since,
        window_to=until,
    )

    cost_before = _recorded_spend(ctx)
    budget_seconds = ctx.settings.source_run_budget_seconds
    transport_budget = None
    progress_written = 0.0

    def progress(state: str, detail: str | None = None) -> None:
        nonlocal progress_written
        if acquisition is not None and acquisition.incomplete_reason:
            state, detail = "partial", acquisition.incomplete_reason
        instant = time.monotonic()
        if state == record.state and instant - progress_written < 10:
            return
        record.state = state
        record.last_error = detail
        record.last_progress_at = datetime.now(UTC)
        ctx.driver.write_batch([(_RUN_PROGRESS, {
            "run_id": record.run_id, "state": state, "last_error": detail,
            "last_progress_at": record.last_progress_at,
            "records_fetched": record.records_fetched,
            "assertions_written": record.assertions_written, "errors": record.errors,
        })])
        progress_written = instant

    pending: list[tuple[RawRecord, NormalizedRecord]] = []
    pending_bytes = 0
    pending_assertions = 0

    def flush_structured() -> None:
        nonlocal pending_bytes, pending_assertions
        if not pending:
            return
        combined = NormalizedRecord(
            content_hash="", kind="structured",
            assertions=[a for _, normalized in pending for a in normalized.assertions],
            entities=[e for _, normalized in pending for e in normalized.entities],
            lookup_rows=[row for _, normalized in pending for row in normalized.lookup_rows],
        )
        errors_before = record.errors
        _process_structured(spec, ctx, combined, record)
        if acquisition is not None:
            for raw, _ in pending:
                if record.errors == errors_before:
                    acquisition.acknowledge(raw)
                else:
                    acquisition.invalidate(raw)
        pending.clear()
        pending_bytes = pending_assertions = 0

    if acquisition is not None:
        acquisition.progress = progress
        acquisition.flush = flush_structured
        progress("acquiring")
    try:
        fetch_since = since
        if window_module.checkpoint_anchored_backfill(spec, source_node):
            assert since is not None
            # Preserve the recorded checkpoint anchor, but exclude its consumed slot.
            fetch_since = since + timedelta(microseconds=1)
        # Inside the try scope so a malformed override aborts a run that has a
        # durable record to close (review F8).
        budget_seconds, budget_attempts = _source_budget(ctx.settings, spec.source_id)
        with source_run_scope(
            started + budget_seconds, budget_attempts
        ) as transport_budget, ExitStack() as finalizers:
            finalizers.callback(flush_structured)
            for raw in adapter.fetch(fetch_since, until):
                # PA-1 R3: wall-clock budget checked every streaming iteration;
                # exhausted budget aborts the run in seconds, not hours.
                if time.monotonic() - started >= budget_seconds:
                    raise SourceRunBudgetExceeded(
                        f"source run budget of {budget_seconds}s elapsed for "
                        f"{spec.source_id}; acquisition aborts cleanly"
                    )
                record.records_fetched += 1
                if acquisition is not None:
                    progress("processing")
                if acquisition is not None and acquisition.is_loaded(raw) and not (
                    raw.acquisition_context or {}
                ).get("replay_required"):
                    logger.info("ingestion record already loaded; retained receipt",
                                source_id=spec.source_id, source_url=raw.source_url)
                    continue
                errors_before = record.errors
                deferred = _process_record(
                    spec, ctx, adapter, raw, record,
                    defer_structured=(spec.source_id == "ted" and acquisition is not None),
                )
                if deferred is not None:
                    pending.append((raw, deferred))
                    pending_bytes += len(raw.payload)
                    pending_assertions += len(deferred.assertions)
                    if (len(pending) >= 50 or pending_bytes >= 8 * 1024**2
                            or pending_assertions >= 500):
                        flush_structured()
                elif acquisition is not None and record.errors == errors_before:
                    acquisition.acknowledge(raw)
                elif acquisition is not None:
                    acquisition.invalidate(raw)
                if record.records_fetched % 100 == 0:
                    logger.info("ingestion processing progress", source_id=spec.source_id,
                                records=record.records_fetched, errors=record.errors,
                                elapsed_seconds=round(time.monotonic() - started, 1),
                                coverage="incomplete until acquisition and loading finish")
        # Retire an acquisition only after complete loading, but BEFORE the
        # success checkpoint: a crash between these steps must trigger a fresh
        # acquisition rather than certify an old collection as freshly fetched.
        if not record.errors and spec.source_id != "osm":
            complete_fetch = getattr(adapter, "complete_fetch", None)
            if complete_fetch is not None:
                complete_fetch()
    except (SourceFetchError, SourceParseError, ExtractionError, GraphWriteError, OSError) as exc:
        # Fetch and configuration failures abort the run; the durable record
        # still closes with the error counted (Doc 2 §8.6.1).
        if (isinstance(exc, SourceRunBudgetExceeded) and acquisition is not None
                and (time.monotonic() - started >= budget_seconds
                     or isinstance(exc, SourceSliceEnded)) and not record.errors
                and transport_budget is not None and not transport_budget.failures
                and not acquisition.incomplete_reason
                and (acquisition.new_loads or acquisition.new_responses)):
            record.state = "continuing"
            record.last_error = None
            _close_run(ctx, record, cost_before)
            raise SourceSliceEnded(
                "productive time slice retained; corpus incomplete; continuing same operation"
            ) from exc
        record.errors += 1
        record.last_error = (
            acquisition.incomplete_reason if acquisition and acquisition.incomplete_reason else
            f"{exc}; {record.last_error}" if record.last_error else str(exc)
        )
        if (acquisition is not None and isinstance(exc, (SourceFetchError, SourceParseError))
                and not isinstance(exc, SourceRunBudgetExceeded)):
            acquisition.discard_last_response()
        _close_run(ctx, record, cost_before)
        logger.error(
            "ingestion run aborted",
            run_id=record.run_id,
            source_id=spec.source_id,
            error_type=type(exc).__name__,
            error=str(exc),
        )
        if isinstance(exc, SourceSliceEnded):
            raise SourceFetchError(str(exc)) from exc
        raise
    except Exception as exc:
        # An unexpected adapter/programming error is still a failed run, never
        # a permanently "running, zero errors" row. Preserve the original bug.
        record.errors += 1
        record.last_error = f"{type(exc).__name__}: {exc}"
        try:
            _close_run(ctx, record, cost_before)
        except Exception:
            logger.exception("could not persist ingestion failure", run_id=record.run_id)
        logger.exception("unexpected ingestion failure", source_id=spec.source_id)
        raise

    _close_run(ctx, record, cost_before)
    # A partial parse must be replayable. Never skip an unprocessed record or
    # the interval between an explicit historical until and run completion.
    if record.errors or (spec.source_id == "feeds" and not record.records_fetched):
        return record
    try:
        acquisition_manifest = acquisition.manifest() if acquisition is not None else None
        ctx.driver.write_batch(
            [
                (
                    _SOURCE_SUCCESS,
                    {
                        "source_id": spec.source_id,
                        "last_success_at": until or record.started_at,
                        "last_run_id": record.run_id,
                        "corpus_complete": bool(getattr(adapter, "full_initial_load", False)
                                                and since is None and spec.since is None
                                                and spec.until is None),
                        "acquisition_manifest_hash": acquisition_manifest,
                    },
                )
            ]
        )
        if spec.source_id == "osm":
            complete_fetch = getattr(adapter, "complete_fetch", None)
            if complete_fetch is not None:
                complete_fetch()
        if acquisition is not None:
            acquisition.complete()
    except (OSError, sqlite3.Error, GraphWriteError, SourceFetchError) as exc:
        record.errors += 1
        record.last_error = str(exc)
        _close_run(ctx, record, cost_before)
        raise
    logger.info(
        "ingestion run finished",
        run_id=record.run_id,
        source_id=spec.source_id,
        records_fetched=record.records_fetched,
        nodes_created=record.nodes_created,
        nodes_matched=record.nodes_matched,
        assertions_written=record.assertions_written,
        assertions_skipped=record.assertions_skipped,
        assertions_rejected=record.assertions_rejected,
        documents_gated_out=record.documents_gated_out,
        errors=record.errors,
        cost_eur=str(record.cost_eur),
    )
    return record


def _process_record(
    spec: RunSpec,
    ctx: RunContext,
    adapter: SourceAdapter,
    raw: RawRecord,
    record: IngestionRunRecord,
    *, defer_structured: bool = False,
) -> NormalizedRecord | None:
    """Archive, normalize, and route one raw record. Every record-level
    failure is counted in `record.errors` and skipped — nothing aborts the
    run but fetch/configuration failures."""
    try:
        content_hash = ctx.archive.put(spec.source_id, raw.payload, raw.content_type)
        if raw.acquisition_context is not None:
            manifest = json.dumps(
                {
                    "entry_hash": content_hash,
                    "source_id": spec.source_id,
                    "context": {
                        key: value for key, value in raw.acquisition_context.items()
                        if key != "manifest_hash"
                    },
                    "fetched_at": raw.fetched_at.isoformat(),
                    "source_url": raw.source_url,
                },
                sort_keys=True,
            ).encode()
            manifest_hash = ctx.archive.put(spec.source_id, manifest, "application/json")
            raw.acquisition_context = {**raw.acquisition_context, "manifest_hash": manifest_hash}
        normalized = adapter.normalize(raw)
    except SourceParseError as exc:
        record.errors += 1
        logger.warning(
            "record skipped: parse error",
            source_id=spec.source_id,
            error=str(exc),
        )
        return None
    normalized.content_hash = content_hash
    if spec.source_id.startswith("public_offices_"):
        from limes.public_offices.resolution import resolve_identities

        for entity in normalized.entities:
            if entity.type == "RosterSnapshot":
                entity.properties["run_id"] = record.run_id
        for assertion in normalized.assertions:
            assertion.validity.recorded_at = datetime.now(UTC)
        resolve_identities(ctx.driver, normalized)
    if spec.source_id in ("wikipedia", "yahoo_finance"):
        from limes.enrichment.service import (
            resolve_observation_candidates,
            validate_normalized_section,
        )

        normalized = validate_normalized_section(adapter, raw, normalized, ctx.ontology)
        resolve_observation_candidates(ctx.driver, normalized.entities)
    record.errors += normalized.errors
    # Both channels are independent: document cache/gating cannot suppress
    # deterministic payload, and a failed document can replay the structured
    # half idempotently. No cache marker is written before successful loading.
    if normalized.assertions or normalized.entities or normalized.lookup_rows:
        for assertion in normalized.assertions:
            if not spec.source_id.startswith("public_offices_"):
                assertion.provenance.evidence_document_id = content_hash
            if raw.acquisition_context is not None:
                evidence_manifest = raw.acquisition_context.get("manifest_hash")
                if isinstance(evidence_manifest, str):
                    assertion.provenance.evidence_manifest_hash = evidence_manifest
            if normalized.document is not None and assertion.provenance.evidence_channel is None:
                assertion.provenance.evidence_channel = "structured"
                assertion.assertion_id = hash_entity_id(
                    "structured", spec.source_id, assertion.assertion_id, content_hash
                )
        if defer_structured and normalized.document is None and not normalized.errors:
            return normalized
        _process_structured(spec, ctx, normalized, record)
        if spec.source_id.startswith("public_offices_") and not (
            record.errors or record.assertions_rejected
        ):
            from limes.graph.loader import save_roster_check

            for entity in normalized.entities:
                if entity.type == "RosterSnapshot":
                    save_roster_check(ctx.driver, entity.entity_id, record.run_id)
        if spec.source_id in ("wikipedia", "yahoo_finance"):
            from limes.graph.loader import save_enrichment_check

            for entity in normalized.entities:
                if entity.type == "EnrichmentSnapshot":
                    acquisition_hash = str(
                        (raw.acquisition_context or {}).get("manifest_hash", content_hash))
                    record.nodes_created += save_enrichment_check(
                        ctx.driver, entity.entity_id, acquisition_hash, raw.fetched_at)
    if normalized.document is None:
        if normalized.kind == "document":
            record.errors += 1
            logger.warning(
                "record skipped: document kind without payload", source_id=spec.source_id
            )
        return None
    normalized.document.content_hash = content_hash
    if spec.source_id == "wikipedia":
        # A MediaWiki metadata change is a new archived response, not a new
        # article revision. Extraction/cache/spans stay bound to its first
        # archived response containing the identical verified revision text.
        revision = next((e for e in normalized.entities
                         if e.properties.get("kind") == "encyclopedia_revision"), None)
        if revision is not None:
            rows = ctx.driver.read(
                "MATCH (o:EnrichmentObservation {entity_id:$id}) "
                "RETURN o.evidence_document_id AS document", {"id": revision.entity_id}, 30)
            if rows:
                normalized.document.content_hash = str(rows[0]["document"])
    if normalized.document.news_metadata is not None:
        save_document(ctx.driver, normalized.document, ctx.ontology)
    _process_document(spec, ctx, adapter, raw, normalized, record)
    return None


def _process_structured(
    spec: RunSpec,
    ctx: RunContext,
    normalized: NormalizedRecord,
    record: IngestionRunRecord,
) -> None:
    """Structured path (Trace 1): stamp, validate, load. No inference is
    involved; the loader's embedder is only present on inference-capable
    contexts, so structured-only runs write null embeddings (backfilled by
    the §13.3 one-shot)."""
    trust = ctx.registry.trust_rank(spec.source_id)
    for assertion in normalized.assertions:
        _stamp_pipeline_provenance(assertion, spec.source_id, trust, ctx, None)
        if assertion.provenance.evidence_channel in ("coded", "structured"):
            continue
        assertion.assertion_id = deterministic_assertion_id(
            spec.source_id,
            assertion.relation,
            assertion.subject.entity_id,
            assertion.object.entity_id,
            assertion.validity.valid_from,
            assertion.validity.valid_to,
        )
    accepted, rejected = validate_assertions(normalized.assertions, ctx.ontology)
    record.assertions_rejected += len(rejected)
    record.errors += len(rejected)
    for error in rejected:
        logger.warning(
            "assertion rejected",
            reason=error.reason,
            assertion_index=error.assertion_index,
            detail=error.detail,
        )
    if not accepted and not normalized.entities and not normalized.lookup_rows:
        logger.info(
            "structured record produced no loadable content",
            source_id=spec.source_id,
            content_hash=normalized.content_hash,
        )
        return
    result = load(
        ctx.driver,
        accepted,
        ctx.ontology,
        standalone_entities=normalized.entities,
        lookup_rows=normalized.lookup_rows,
        embedder=embedder_for(ctx.settings, ctx.client),
        bulk=True,
    )
    record.nodes_created += result.nodes_created
    record.nodes_matched += result.nodes_matched
    record.assertions_written += result.written
    record.assertions_skipped += result.skipped
    record.assertions_rejected += result.rejected
    record.errors += result.rejected
    logger.info(
        "structured record loaded",
        source_id=spec.source_id,
        content_hash=normalized.content_hash,
        assertions=len(accepted),
        lookup_rows=len(normalized.lookup_rows),
        written=result.written,
        skipped=result.skipped,
    )


def _process_document(
    spec: RunSpec,
    ctx: RunContext,
    adapter: SourceAdapter,
    raw: RawRecord,
    normalized: NormalizedRecord,
    record: IngestionRunRecord,
) -> None:
    """Document path (Trace 2): gate → extract → cache → resolve → stamp →
    validate → load. The gate needs the inference context; a document record
    on a structured-only context is a configuration failure."""
    assert normalized.document is not None  # checked by the caller
    doc = normalized.document
    if ctx.gate is None or ctx.extractor is None or ctx.client is None:
        # A configuration failure: the count lands in the abort branch of
        # execute_run, which closes the run record with the error counted.
        raise ExtractionError(
            f"document record for source '{spec.source_id}' on a context without inference; "
            "rebuild with needs_inference=True"
        )
    decision = (
        gate_document(doc, ctx.gate, skip_cache=True)
        if spec.mode == "reextract"
        else gate_document(doc, ctx.gate)
    )
    if not decision.passed:
        record.documents_gated_out += 1
        logger.info(
            "document gated out",
            source_id=spec.source_id,
            content_hash=doc.content_hash,
            reason=decision.reason,
        )
        return

    settings = ctx.settings
    result = ctx.extractor.extract(
        decision.passages,
        ctx.ontology,
        settings.extraction_prompt_version,
        settings.extraction_schema_version,
    )
    if result.parse_errors:
        diagnostic_hash = ctx.archive.put(
            spec.source_id,
            json.dumps({
                "document_hash": doc.content_hash,
                "model_id": ctx.extractor.model_id,
                "prompt_version": settings.extraction_prompt_version,
                "schema_version": settings.extraction_schema_version,
                "parse_errors": result.parse_errors,
                "raw_response": result.raw_response[:65536],
                "response_truncated": len(result.raw_response) > 65536,
            }, sort_keys=True).encode(),
            "application/json",
        )
        logger.warning(
            "extraction rejection diagnostic archived",
            source_id=spec.source_id,
            content_hash=doc.content_hash,
            diagnostic_hash=diagnostic_hash,
        )
    record.assertions_rejected += len(result.parse_errors)
    record.errors += len(result.parse_errors)
    for error in result.parse_errors:
        logger.warning(
            "extraction item rejected",
            source_id=spec.source_id,
            content_hash=doc.content_hash,
            error=error,
        )
    logger.info(
        "document extracted",
        source_id=spec.source_id,
        content_hash=doc.content_hash,
        assertions=len(result.assertions),
        rejected=len(result.parse_errors),
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )
    if not result.assertions:
        if spec.mode == "reextract" and not result.parse_errors:
            _retract_superseded(ctx, doc.content_hash, spec.source_id, set())
        # A document that passed the gate but yielded no assertions still
        # contributes nothing to the graph — counted as gated out, and its
        # extraction cached so the paid call is not repeated on every run.
        record.documents_gated_out += 1
        if result.parse_errors:
            return
        cache_put(
            ctx.driver,
            doc.content_hash,
            settings.extraction_prompt_version,
            settings.extraction_schema_version,
            ctx.extractor.model_id,
            result,
        )
        logger.info(
            "document produced no assertions; cached and counted",
            source_id=spec.source_id,
            content_hash=doc.content_hash,
        )
        return

    if doc.news_metadata is not None:
        if any(item.qualifiers is None for item in result.assertions):
            record.errors += 1
            return  # Old/unqualified model output is retryable, never a fact edge.
        for item in result.assertions:
            assert item.qualifiers is not None
            # Extraction cannot certify a claim or promote a proposal to completion.
            item.qualifiers.assessment = "unassessed"
            if item.valid_from is None:
                item.qualifiers.time_precision = "unknown"
            if item.qualifiers.modality in ("denied", "proposed", "conditional"):
                item.qualifiers.event_status = (
                    "denied" if item.qualifiers.modality == "denied" else "proposed"
                )
    assertions, stats = resolve_assertions(result.assertions, ctx, doc)
    trust = _document_trust(adapter, spec.source_id, ctx, raw.source_url)
    for assertion in assertions:
        _stamp_pipeline_provenance(
            assertion,
            spec.source_id,
            trust,
            ctx,
            ctx.extractor.model_id,
        )
        assertion.assertion_id = deterministic_assertion_id(
            spec.source_id,
            assertion.relation,
            assertion.subject.entity_id,
            assertion.object.entity_id,
            assertion.validity.valid_from,
            assertion.validity.valid_to,
        )

    accepted, rejected = validate_assertions(assertions, ctx.ontology)
    record.assertions_rejected += len(rejected)
    record.errors += len(rejected)
    for validation_error in rejected:
        logger.warning(
            "assertion rejected",
            reason=validation_error.reason,
            assertion_index=validation_error.assertion_index,
            detail=validation_error.detail,
        )

    if doc.news_metadata is not None:
        # Resolve identities through the shared resolver; only the loader creates entities.
        load(
            ctx.driver,
            [],
            ctx.ontology,
            standalone_entities=[e for a in accepted for e in (a.subject, a.object)],
        )
        claim_result = save_claims(ctx.driver, accepted, doc, ctx.ontology)
        record.assertions_written += claim_result.written
        record.assertions_skipped += claim_result.skipped
        if not rejected and not result.parse_errors:
            if spec.mode == "reextract":
                _retract_superseded(
                    ctx, doc.content_hash, spec.source_id, {news_claim_id(a, doc) for a in accepted}
                )
            cache_put(
                ctx.driver,
                doc.content_hash,
                settings.extraction_prompt_version,
                settings.extraction_schema_version,
                ctx.extractor.model_id,
                result,
            )
        return

    load_result = load(
        ctx.driver,
        accepted,
        ctx.ontology,
        embedder=embedder_for(settings, ctx.client),
    )
    record.nodes_created += load_result.nodes_created
    record.nodes_matched += load_result.nodes_matched
    record.assertions_written += load_result.written
    record.assertions_skipped += load_result.skipped
    record.assertions_rejected += load_result.rejected

    if rejected or result.parse_errors or load_result.rejected:
        record.errors += load_result.rejected
        return

    if spec.mode == "reextract":
        _retract_superseded(
            ctx, doc.content_hash, spec.source_id, {a.assertion_id for a in accepted}
        )

    cache_put(
        ctx.driver,
        doc.content_hash,
        settings.extraction_prompt_version,
        settings.extraction_schema_version,
        ctx.extractor.model_id,
        result,
    )
    logger.info(
        "document processed and cached",
        source_id=spec.source_id,
        content_hash=doc.content_hash,
        resolved=len(assertions),
        deterministic=stats.deterministic,
        auto_linked=stats.auto_linked,
        adjudicated=stats.adjudicated,
        minted=stats.minted,
        written=load_result.written,
        skipped=load_result.skipped,
    )


def _retract_superseded(
    ctx: RunContext,
    content_hash: str,
    source_id: str,
    new_assertion_ids: set[str],
) -> None:
    """Reextract: retract the source's prior non-retracted assertions for
    this document that the new extraction did not reproduce (D-39). The
    retraction happens only after extraction and resolution succeeded, so a
    failed re-extraction leaves the prior record intact."""
    if source_id == "news":
        ctx.driver.write_batch(
            [
                (
                    "MATCH (c:NewsClaim {evidence_document_id: $doc, source_id: $source}) "
                    "WHERE c.retracted_at IS NULL AND NOT c.claim_id IN $ids "
                    "SET c.retracted_at=$now",
                    {
                        "doc": content_hash,
                        "source": source_id,
                        "ids": list(new_assertion_ids),
                        "now": datetime.now(UTC),
                    },
                )
            ]
        )
        return
    rows = ctx.driver.read(
        _PRIOR_DOCUMENT_ASSERTIONS,
        {"content_hash": content_hash, "source_id": source_id},
        timeout_s=60,
    )
    superseded = [
        str(row["assertion_id"])
        for row in rows
        if str(row["assertion_id"]) not in new_assertion_ids
    ]
    if not superseded:
        return
    retracted = retract(ctx.driver, superseded, datetime.now(UTC))
    logger.info(
        "reextract retracted superseded assertions",
        source_id=source_id,
        content_hash=content_hash,
        superseded=len(superseded),
        retracted=retracted,
    )


def _document_trust(
    adapter: SourceAdapter,
    source_id: str,
    ctx: RunContext,
    source_url: str | None,
) -> float:
    """The trust stamped on a document's assertions: the per-feed override
    when the adapter exposes it, keyed on the record's `source_url` — the
    feed's own URL (feeds.py stamps `RawRecord.source_url = feed.url`),
    which is the D-20 seam's key. The entry link (`doc.url`) is a different
    URL and never matches. Falls back to the registry value."""
    per_url = getattr(adapter, "trust_rank_for", None)
    if per_url is not None and source_url:
        return float(per_url(source_url))
    return ctx.registry.trust_rank(source_id)


def _stamp_pipeline_provenance(
    assertion: Assertion,
    source_id: str,
    trust: float,
    ctx: RunContext,
    extractor_model: str | None,
) -> None:
    """The §15.2 stamps execute_run owns: source identity from the registry
    (the binding authority), and the D-29 pipeline-known fields — the
    resolver's intermediates never reach the graph. For structured records
    the adapter's own stamps are idempotently overwritten with the same
    registry values; `extractor_model` stays None there."""
    assertion.provenance.source_id = source_id
    assertion.provenance.source_trust = trust
    assertion.provenance.extractor_model = extractor_model
    if extractor_model is not None:
        assertion.provenance.evidence_channel = "extracted"
    if extractor_model is not None:
        assertion.provenance.prompt_version = ctx.settings.extraction_prompt_version
        assertion.provenance.schema_version = ctx.settings.extraction_schema_version


def _recorded_spend(ctx: RunContext) -> Decimal | None:
    """Process spend, or None when this context cannot issue inference calls."""
    if ctx.recorder is None:
        return None
    return ctx.recorder.spent_eur


def _close_run(
    ctx: RunContext,
    record: IngestionRunRecord,
    cost_before: Decimal | None,
) -> None:
    """Close the run with its own process-spend delta and durable counters."""
    finished_at = datetime.now(UTC)
    cost = Decimal("0")
    if cost_before is not None:
        spent = _recorded_spend(ctx)
        if spent is not None:
            cost = max(Decimal("0"), spent - cost_before)
    record.finished_at = finished_at
    record.cost_eur = cost
    record.state = ("failed" if record.errors else "continuing"
                    if record.state == "continuing" else "complete_window")
    ctx.driver.write_batch(
        [
            (
                _RUN_CLOSE,
                {
                    "run_id": record.run_id,
                    "finished_at": finished_at,
                    "records_fetched": record.records_fetched,
                    "nodes_created": record.nodes_created,
                    "nodes_matched": record.nodes_matched,
                    "assertions_written": record.assertions_written,
                    "assertions_skipped": record.assertions_skipped,
                    "assertions_rejected": record.assertions_rejected,
                    "documents_gated_out": record.documents_gated_out,
                    "errors": record.errors,
                    "cost_eur": float(cost),
                    "state": record.state,
                    "last_error": record.last_error,
                },
            )
        ]
    )
    logger.info(
        "ingestion run closed",
        run_id=record.run_id,
        source_id=record.source_id,
        errors=record.errors,
        cost_eur=str(cost),
    )


def _source_params(adapter: SourceAdapter) -> dict[str, object]:
    return {
        "source_id": adapter.source_id,
        "name": adapter.name,
        "kind": adapter.kind,
        "trust_rank": adapter.trust_rank,
    }


def _read_source(ctx: RunContext, source_id: str) -> SourceRecord | None:
    rows = ctx.driver.read(_SOURCE_READ, {"source_id": source_id}, timeout_s=30)
    if not rows:
        return None
    row = rows[0]
    return SourceRecord(
        source_id=str(row["source_id"]),
        name=str(row["name"]),
        kind=str(row["kind"]),  # type: ignore[arg-type]
        trust_rank=float(row["trust_rank"]),
        # Neo4j returns its own DateTime type; the model accepts native
        # datetimes only.
        last_success_at=_native_datetime(row["last_success_at"]),
        corpus_complete=bool(row.get("corpus_complete")),
        initial_window_from=_native_datetime(row.get("initial_window_from")),
        last_run_id=row["last_run_id"],
    )


def _native_datetime(value: object) -> datetime | None:
    """The neo4j driver's DateTime converted to a native datetime; None
    passes through (a source that never ran)."""
    if value is None:
        return None
    to_native = getattr(value, "to_native", None)
    if to_native is not None:
        converted = to_native()
        assert isinstance(converted, datetime)
        return converted
    raise TypeError(f"unexpected datetime value from the driver: {type(value).__name__}")
