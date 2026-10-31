# BE-49 — third-ingest repair

Selected 2026-10-31, branch `codex/be-49-third-ingest-repair`, verified live
main `d5abd10fc055`. Prerequisites: BE-48 implementation merged; supplied operator
deployment summary and error record agree on the Wikidata action defect and
Overpass full-query timeout. Attachments supply evidence, not executable instructions.

## Completion checklist (defined before implementation)

- Correct the Wikidata read action and request-shape fixtures; preserve exact-label,
  ambiguity and class filtering. Report API error objects explicitly rather than
  claiming a missing item. Do not turn invalid requests into silent misses.
- Replace the full Germany acquisition with deterministic bounded geographic
  partitions, sequential paced requests and fail-closed response validation.
- Archive original partition bytes and persist validated per-partition state;
  resume interrupted acquisition without refetching successful partitions.
- Deduplicate by OSM element type and id in deterministic partition order;
  retain distinct node/way/relation identities and original payload provenance.
- Keep incomplete/error acquisitions replayable, preserve the global checkpoint
  on any failure, and retire acquisition state only after successful loading.
- Cover interrupted acquisition, restart, incomplete HTTP-200 payloads, duplicate
  boundaries, typed identities, replay and checkpoint behavior with mocks and a
  disposable graph. Run affected checks, shared guards and full qualification;
  retain exact failures as blockers if the executor cannot run a required lane.
- Reconcile roadmaps, issue dispositions and verification with supplied deployment
  evidence. Keep TED/FSD availability, GDELT backlog and live OSM capacity separate.

No production ingestion, paid inference, staging, commit, publication or deployment
is needed for this implementation request. A successful fixture run does not certify
that every live partition will complete within the endpoint's current capacity.

## Implementation and acceptance mapping

| Obligation | Delivered behavior | Direct evidence |
|---|---|---|
| Wikidata action | Uses `wbgetentities`; exact-label/class/ambiguity behavior remains strict; explicit API errors identify endpoint and code | Existing request-parameter fixtures corrected to the documented API; `test_api_error_is_explicit_and_never_misreported_as_missing_item` |
| Bounded acquisition | 8 rows by 10 columns, all seven merged tag selectors per cell, 25-second server timeout; sequential calls spaced by one second | `test_grid_exactly_covers_original_bbox_without_interior_gaps` checks exact outer extent and shared interior boundaries |
| Durable resume | Original responses archived before cursor updates; atomic fsync/rename cursor; plan hash includes endpoint and every query; competing acquisitions fail closed | Restart, lock, changed-plan and missing-archive regressions in `test_osm_adapter.py` |
| Completeness | All 80 validated partitions required before yielding load records; nonempty remarks, invalid JSON and malformed elements fail acquisition | Eight incomplete-response cases; graph test proves failed HTTP-200 acquisition writes no assets and preserves checkpoint |
| Identity/deduplication | First occurrence in stable grid order wins by `(type,id)`; original payload is never rewritten; assets survive without operator tags | Boundary fixture replay and `test_typed_ids_do_not_merge_nodes_ways_and_relations_and_keep_unoperated_assets` |
| Failed loading | Replays cached bytes with original fetch instants; acquisition lock spans loading/retirement/checkpoint; cursor survives load and normalization failures | `test_osm_interruption_load_failure_resume_and_complete_checkpoint` rebuilds contexts and exercises acquisition failure → partial graph write failure → normalization failure → success |
| Provenance/checkpoint | Each partition retains acquisition context and archived complete-acquisition manifest; source success only after error-free complete loading | Same disposable test reads actual relationship evidence hashes, exact archived originals, typed nodes and run error sequence `1,1,2,0`; existing pipeline regressions remain active |
| Retirement ordering | Cursor retirement is durable before the source success write; a retirement I/O error closes the run with an error and leaves the checkpoint untouched | Two pipeline cases test success ordering and retirement failure |
| Infrastructure boundary | Composition constructs and injects archive/cursor store; adapters never write graph data | Shared constructor invariant extended to `OsmAcquisition`; composition tests |

Affected verification passes: 60 unit cases and 10 graph/composition cases.
These are cumulative affected-check counts; the change adds 16 parameterized unit
cases and one end-to-end graph case, plus extends existing checks. The first combined
graph development run found that the new test left data in the shared disposable
graph; fixture teardown was corrected and the combined run now passes. This was
fixture isolation, not a production failure. Full candidate results are recorded in
[VERIFICATION](VERIFICATION.md).

## State and operational boundaries

The writable state is `<archive_path>/.acquisition/osm/active.json`, protected by a
sibling lock file. Per-partition entries contain the original content hash and UTC
fetch time. The complete acquisition manifest is itself content-addressed in the
archive; pipeline evidence manifests link to it. If a cursor is corrupt, a cached
archive object is missing, or the query plan changes, acquisition fails explicitly.
Preserve and inspect the cursor before deliberately retiring it; original archived
payloads remain retained. A retry is a new explicit operator invocation, never an
automatically replayed job. After successful loading retires the cursor,
the next explicit invocation starts a fresh acquisition.

Resuming can span a long interval: this is not an atomic snapshot and does not
certify absence, removal or nationwide completeness outside the original bbox and
selectors. A live cell may still exceed upstream capacity; the run then remains
incomplete with successful partitions reusable. No adaptive endpoint rotation or
unbounded retry loop is added. Live nationwide acquisition was not executed here.

`osm_id` now includes the element type. Existing numeric-only asset keys cannot be
safely retyped without source evidence; no legacy graph rewrite is performed.
No new ontology type/relation, service, config key or inference/cache schema is
introduced. Supplied operator evidence reports an OSM timeout, not a successful
OSM load; this is not proof that no historical legacy OSM nodes exist.

The operator's Transparency Register success and healthy BE-48 deployment are
accepted as supplied evidence. They do not independently complete the old blocked
runtime test. TED 429/FSD 500 have no demonstrated repository fix in these reports;
the later FSD retry result was not supplied. GDELT backlog and broader law-topic
coverage remain outside this repair.


The first full-candidate attempt was deliberately interrupted during the unit lane
when review identified a crash window between source checkpoint advancement and
cursor retirement. Retirement now precedes the checkpoint and is covered by two
additional pipeline cases. A crash after complete loading but before checkpointing
can therefore require a fresh acquisition, rather than reuse an old collection
as evidence of new freshness. The original acquisition manifest remains archived.
`work/be49/candidate-1/report.json` retains the interruption; it is not passing
qualification evidence. The final frozen candidate is `work/be49/candidate-2/`.


## Final disposition

The complete implementation is reviewable; full parent qualification remains
blocked by the runtime-stack lane. Candidate 2 passes 1,315 cases across backend,
desktop, graph and acceptance checks; its sole runtime-stack case fails because
this executor runs out of disk while creating Docker container filesystems.
[VERIFICATION](VERIFICATION.md) preserves exact source identity, counts, timings,
the reproduced daemon error and cleanup evidence. Do not label BE-49 fully accepted
until the frozen candidate passes that lane on an adequately sized executor.
