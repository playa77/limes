# LIMES roadmap

## Active work package: WP-NEWS-DESIGN — integrated news architecture and review

Selected 2026-10-27 on branch `work`, starting at `5295cab`; prepared for delivery
on branch `codex/integrated-news-architecture`. This package covers
evaluation of the supplied ChatGPT review, investigation of its reported issues,
and coherent architecture, roadmap, README and related documentation. It does
not implement the news module or repair runtime ingestion. Those are complete
future packages below, not unfinished children of this documentation package.

Actual prerequisites: current-main baseline verified; source, pipeline, schema,
ontology and existing tests available; public GDELT metadata and a bounded export
available for read-only format verification. No production access, paid inference,
agency subscription or deployment is required for this package.

Acceptance checklist:

- [x] Evaluate suggestions against implementation and record adopted, deferred
  and rejected recommendations, including the explicit rejection of a standalone
  extractor, utility and event ledger.
- [x] Investigate the reported GDELT defects with reproducible evidence and track
  remaining repairs without claiming runtime fixes.
- [x] Document the integrated target, source/evidence and claim semantics, identity
  ownership, operational boundaries and compatibility requirements.
- [x] Order full implementation packages by real prerequisites and define their
  acceptance, blockers and revisit triggers.
- [x] Update generated architecture, README, operations/testing guidance and
  historical-document navigation; pass relevant lightweight checks.

Handoff: suggestion disposition and issue reproduction are in
[NEWS_REVIEW](NEWS_REVIEW.md); source/claim/identity/operational contracts are in
[NEWS_ARCHITECTURE](NEWS_ARCHITECTURE.md); implementation package acceptance and
blockers follow below. README and generated architecture/operations/testing
documents link to these targets; historical design/specification notices identify
the extension. Validation commands/results are recorded in NEWS_REVIEW. No blocker
remains for this documentation package. OI-19..OI-22 repairs, provider/corpus
selection and integrated runtime behavior remain explicit future obligations.

## Delivery sequence

Each row is a full work package for one session, branch and PR; its internal
steps may be commits. Define the concrete branch, selected source/corpus and
acceptance evidence before implementing it. Do not split packages merely to fit
a turn. The current runtime and previously open desktop/deployment issues remain
as recorded in [OPEN_ISSUES](../OPEN_ISSUES.md); this roadmap does not close them.

### WP-NEWS-INGEST — trustworthy GDELT ingestion and mixed-record routing

Prerequisites: findings OI-19..OI-22 in
[the review](NEWS_REVIEW.md); pinned upstream format reference and a small,
independently sourced representative fixture. No paid model call is needed.

Deliver the source-to-loader correctness repair as one package: GDELT 2.0 ZIP/TSV
transport and complete column mapping, explicit handling of structured plus
document outputs, and event-to-report/archive provenance. Select and version the
mixed-record interface before coding; do not merely change `kind` and lose the
other payload. Preserve the existing source adapter protocol where possible.

Acceptance:

- Published export filenames and 61-column TSV rows decode correctly, including
  ADM2 positions, dates, source URLs and country-code conversion. Corrupt archives,
  schema drift and invalid rows fail or are counted explicitly; decompression and
  input sizes are bounded. No synthetic summary is represented as article text.
- Structured assertions reach validation and loading even when a document is
  gated, cached or produces no extraction. Document extraction still runs when
  requested. Retries, partial failure, counters, source checkpoints and reextract
  semantics cannot silently lose or retract the other channel's evidence.
- A coded event retains export hash, row/event identity and report URL; multiple
  reports can be associated without conflating their evidence. Missing article
  content is visible and triggers no fabricated evidence spans. Define whether
  Mentions-table support is required for the selected coverage; label coverage
  honestly if only the Event table's single SOURCEURL is retained.
- A fixture through the real pipeline into a disposable graph proves the coded
  edges and provenance survive; affected tests plus shared invariants pass, with
  one authoritative full pre-merge candidate run. Existing malformed-format
  fixtures cannot serve as the external format oracle.

Blockers: current adapter and routing defects. Exact fail-closed CI evidence and
candidate revision accompany the handoff; no production ingestion is implied.

### WP-NEWS-EXTRACT — integrated agency/news extraction in LIMES

Prerequisites: WP-NEWS-INGEST complete; one selected, accessible agency/feed format
and retention/use terms; representative DE/EN corpus with independently annotated
entities, events, claims and evidence. Provider, credentials, corpus and quality
thresholds must be selected before coding; they are currently unresolved. Existing
RSS support is a starting point, not proof of licensed full-dispatch coverage.

Deliver adapters and shared worker extraction, versioned claim/event schema and
ontology migration, resolver/loader support, and API/desktop evidence presentation
together. There is no standalone utility, separate ledger application or service.

Acceptance:

- One dispatch/version remains independently archived, identifiable and linked
  to exact evidence; updates, corrections, duplicates and syndicated copies retain
  lineage. Multiple dispatches may support an event without independent-source
  corroboration being inferred from copied reporting.
- Typed claim mode, modality, attribution, assessment, event lifecycle and time
  precision round-trip through extraction, resolution, validation, storage, API and
  desktop. Announcing a proposed merger does not assert a completed merger;
  a denial does not assert the denied proposition. Unknown attribution and dates
  stay unknown. Migration/replay preserves old assertions and contradictions.
- Entity identities come from LIMES resolution; cross-source event matching uses
  reviewed, non-destructive candidates rather than matching labels or dates alone.
- Cheap language/topic/dedup filters precede inference; configured work limits,
  skip/defer reasons, checkpoints and cost measurements are visible. Run limits
  are implemented and tested explicitly; ignored legacy `--budget` arguments are
  never described as protection. No monetary governor is introduced implicitly.
- Annotated corpus evaluation reports distinct failure modes and extraction
  quality separately from truth assessment, plus usage/latency. Set justified
  acceptance thresholds from the corpus before implementation, not test quotas.
  Offline automated checks mock paid calls; actual paid evaluation is an explicit
  operator run. A disposable end-to-end run proves analyst-visible provenance.

Blockers: source access/terms, corpus and schema/migration design. Revisit the exact
taxonomy after corpus review, within this package; do not add speculative entity
types in advance. External scheduling may invoke bounded authenticated LIMES jobs
only after work limits/checkpoint semantics exist; it adds no fourth service.

### WP-NEWS-ANALYSIS — cross-source developments and temporal investigation

Prerequisites: WP-NEWS-EXTRACT complete with measured evidence and sufficient
registry/news overlap; stable claim and evidence API.

Deliver graph/API queries and desktop network/timeline workflows comparing coded
observations, agency reports and official records. Acceptance: an analyst can
follow a proposal, denial, agreement and later registry/award confirmation;
inspect each source, attribution and revision; query validity versus recorded
time; and see disputes, evidence gaps and source dependence. Similar timestamps
must not be presented as causal or proof of coordination. Event matching retains
unmerged alternatives and provenance; an end-to-end scenario exercises all views.

Blocker: no demonstrated integrated news corpus yet. Revisit scope when ingestion
and extraction evidence identifies a useful research question. Automated alerts,
causal inference, a second vector store and an internal scheduler are deferred
until a measured need and a separate complete package justify them.

## Workflow review

After the first three implementation PRs under this roadmap, compare accepted
whole-package delivery, implementation effort, validation latency and merge delay
separately where evidence permits. Investigate sustained CI growth, copied tests
or registrations, repeated corrections or partial handoffs immediately. Use shared
invariant coverage and separate runners for independent CI lanes; keep one stable
fail-closed required status and exact candidate evidence. Adjust the active process
instead of shrinking delivery boundaries.
