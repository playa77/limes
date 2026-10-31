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
import uuid
from contextlib import nullcontext
from datetime import UTC, datetime
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
)
from limes.extraction.cache import put as cache_put
from limes.graph.loader import load, news_claim_id, retract, save_claims, save_document
from limes.ontology.validator import validate_assertions
from limes.pipeline import window as window_module
from limes.pipeline.gate import gate_document
from limes.resolution.resolve import resolve_assertions
from limes.sources.base import SourceAdapter, deterministic_assertion_id, hash_entity_id
from limes.types import (
    Assertion,
    IngestionRunRecord,
    NormalizedRecord,
    RawRecord,
    SourceRecord,
)

if TYPE_CHECKING:
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
    r.cost_eur = $cost_eur
"""

_SOURCE_SUCCESS = """
MATCH (s:Source {source_id: $source_id})
SET s.last_success_at = CASE
    WHEN s.last_success_at > $last_success_at THEN s.last_success_at
    ELSE $last_success_at END,
    s.last_run_id = $last_run_id
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


def execute_run(spec: RunSpec, ctx: RunContext) -> IngestionRunRecord:
    """Execute one ingestion run end-to-end and return its durable record.

    `ctx` is the composition root's `RunContext` (owned by
    `resolution/resolve.py` per D-28); `execute_run` constructs nothing
    and consumes only what the context carries (§8.15).
    """
    adapter = ctx.registry.get(spec.source_id)
    run_scope = getattr(adapter, "run_scope", nullcontext)
    with run_scope():
        return _execute_run(spec, ctx)


def _execute_run(spec: RunSpec, ctx: RunContext) -> IngestionRunRecord:
    """Run while the adapter's optional acquisition scope remains active."""
    adapter = ctx.registry.get(spec.source_id)

    ctx.driver.write_batch([(_SOURCE_MERGE, _source_params(adapter))])
    source_node = _read_source(ctx, spec.source_id)
    since, until = window_module.resolve_window(spec, adapter, source_node, ctx.settings)

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
    try:
        for raw in adapter.fetch(since, until):
            record.records_fetched += 1
            _process_record(spec, ctx, adapter, raw, record)
        # Retire an acquisition only after complete loading, but BEFORE the
        # success checkpoint: a crash between these steps must trigger a fresh
        # acquisition rather than certify an old collection as freshly fetched.
        if not record.errors:
            complete_fetch = getattr(adapter, "complete_fetch", None)
            if complete_fetch is not None:
                complete_fetch()
    except (SourceFetchError, SourceParseError, ExtractionError, GraphWriteError, OSError) as exc:
        # Fetch and configuration failures abort the run; the durable record
        # still closes with the error counted (Doc 2 §8.6.1).
        record.errors += 1
        _close_run(ctx, record, cost_before)
        logger.error(
            "ingestion run aborted",
            run_id=record.run_id,
            source_id=spec.source_id,
            error_type=type(exc).__name__,
            error=str(exc),
        )
        raise

    _close_run(ctx, record, cost_before)
    # A partial parse must be replayable. Never skip an unprocessed record or
    # the interval between an explicit historical until and run completion.
    if record.errors:
        return record
    ctx.driver.write_batch(
        [
            (
                _SOURCE_SUCCESS,
                {
                    "source_id": spec.source_id,
                    "last_success_at": until or record.started_at,
                    "last_run_id": record.run_id,
                },
            )
        ]
    )
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
) -> None:
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
        return
    normalized.content_hash = content_hash
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
        _process_structured(spec, ctx, normalized, record)
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
        return
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
    )
    record.nodes_created += result.nodes_created
    record.nodes_matched += result.nodes_matched
    record.assertions_written += result.written
    record.assertions_skipped += result.skipped
    record.assertions_rejected += result.rejected
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
