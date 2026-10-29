# DECISIONS — LIMES decision ledger

Append-only ledger per the global AGENTS.md §5. Entries are tagged by
reversibility: **R1** reversible in under an hour, **R2** bounded recoverable
cost, **R3** one-way door. Written when each decision is made, latest first.
Nothing here is a status report; unlogged decisions are unmade decisions.

## 2026-10-29 — D-83 (R2) — Cross-source temporal investigation and provider ownership

The user reiterated that selecting a free news provider/aggregator is the agent's
responsibility. D-82 already resolved that requirement; do not ask for provider
selection, subscriptions or a pre-existing annotated corpus again. A live fetch
found BE-43/DC-15 merged in PR #10 at `84c832df3cd5`; the supplied checkout was
fast-forwarded and the required baseline passed before implementation.

Deliver the next complete parent BE-44/DC-16 on
`codex/be-44-temporal-investigation`. Combine target-scoped qualified claims,
coded observations and existing source-stamped assertions in bounded read-only
queries; use shared validity/belief filters and preserve historical contradictions.
Same directed participants/predicate suggest unresolved event matches only.
Explicit operator reviews may connect other evidence pairs. They are immutable,
idempotent request-ID records with rationale, separate event/assessment/independence
labels and recorded-time history. Known shared report/dispatch/document identity
cannot be relabeled independent. Reviews never merge identities or rewrite evidence.

Additive infrastructure constraints/indexes provision through the existing lock
and one-DDL-per-transaction path; no ontology, extraction or cache change is needed.
The paired HTTP-only desktop supports network, coordinate-only map, both timeline
axes and exact source-span/archive-preview navigation. The new map has no tile
requests; missing graph coordinates stay unknown. The API mounts the shared
archive read-only and never creates storage while serving previews. Existing DC-14 map-policy and
manual/platform gaps remain assigned there. Preview decompression and result sizes
are bounded; partial results are explicit. No production ingestion, paid evaluation,
commit, publication or deployment is authorized by this implementation request.
After local acceptance, the user explicitly requested preparing and opening a PR,
authorizing staging, commit and push. Merge and deployment remain separate.

## 2026-10-28 — D-82 (R2) — Investigation-driven dynamic news acquisition

The user explicitly corrected the interpretation of BE-43 and confirmed that
“tracked” means an entity or relation is part of an ongoing investigation that
LIMES actively keeps informed about. LIMES must discover, set up and acquire news
feeds dynamically once these are tracked and adapt as their relevance evolves.
Provider setup and collection of evaluation material are implementation tasks.
An existing annotated corpus or user-supplied agency access is not a prerequisite.
This supersedes the blocking procurement/corpus language in D-78/79 and BE-43.

Use the existing API, worker, archive, resolver and graph. Tracking is persistent,
explicit investigation state, separate from merely viewing a node. Both entity
and relation targets are supported. Labels/aliases and relation endpoints refresh
from the graph on each acquisition cycle; stopping an investigation stops future
acquisition without deleting evidence. Automatic bounded cycles are specifically
in scope by this user instruction; failed/interrupted cycles require manual replay.
No production data run, paid evaluation, publication or deployment was requested
by the implementation instruction. On 2026-10-29, after local acceptance, the user
explicitly requested preparing and opening a PR, authorizing commit and push.

## 2026-10-28 — D-81 (R2) — BE-42 coded evidence and channel ownership

The user requested finishing the latest unfinished backend package, otherwise
implementing the next one. Live main b093599 includes merged BE-41 and BE-46
planning; the roadmap explicitly selects BE-42 as the next runtime repair.
Delivery is on codex/be-42-ingestion-repair; no commit/publication or data run is
requested by the implementation instruction. After local acceptance, the user
explicitly requested preparing and opening a PR, authorizing its commit and push.
The official export pinned by NEWS_REVIEW was fetched read-only and
its SHA-256 verified before coding. Three unchanged rows are the independent
format fixture; the FIPS/ISO crosswalk is attributed to GeoNames with source hash.

GDELT exports supply coded observations, not synthetic document prose. Preserve
archive/member/row/event/export/report identity and DATEADDED separately from
SQLDATE and ingestion recorded time. Nullable additive provenance fields pass
through the loader, authenticated API and desktop mirror; absent old fields
remain unknown. Multiple reports/export versions retain distinct assertion IDs.
Only SOURCEURL association is covered; Mentions ingestion is explicitly outside
this repair. Article text is unavailable, not silently synthesized or fetched.
No claim of independent corroboration follows from two observations.

Normalized output may carry both channels regardless of kind. Structured content
loads before document gating/cache/extraction. Mixed structured assertion identity
is separate from extracted identity, and interval closure respects channel.
Reextract bypasses cache, loads replacement first, then retracts only extracted
assertions (including legacy edges with extractor_model). Successful empty output
can retract old extracted evidence; partial extraction/validation is retryable,
not success-cached, and cannot advance the source checkpoint. Record errors also
block advancement. Checkpoints use covered until/run start and never regress.

GDELT window instants are normalized to UTC before slot rounding/URL formatting.
GDELT work bounds are explicit: 96 slots per request, 16 MiB compressed response,
128 MiB expanded export and 250,000 rows. Larger windows fail before network I/O;
operators submit consecutive bounded windows. Budget compatibility flags remain
ignored. These caps are defensive bounds, not measured resource qualification.
Fixtures/mock providers and disposable graph/API tests do not establish live
article coverage, paid extraction quality, representative memory or deployment.

## 2026-10-28 — D-80 (R2) — Wikipedia and Yahoo Finance enrichment within current scope

The user confirmed German and European policy as the current scope, deferred
comprehensive EU coverage to a possible later version, selected Yahoo Finance and
requested architecture/backend-roadmap integration of both proposed adapters,
including shareholder structure. This turn authorizes documentation changes.

Plan one full backend package BE-46: Wikipedia revision-linked DE/EN entity
context, Yahoo Finance available company/governance/shareholder/earnings-report
metadata and supporting identity, ontology, persistence and API migrations.
Reuse the existing worker, archive, resolver, loader, graph and authenticated API.
Extend Wikidata identity safely rather than treating the existing QID/alias lookup
as Wikipedia content. Keep company, security and listing identities distinct.

Preserve named holdings separately from aggregate ratios, share quantities and
percentage basis, class/currency and as-of dates where supplied. Overlapping holder
lists cannot be added into a complete cap table. Officers are not a complete board;
missing rows do not establish zero holdings, disposal or resignation. Secondary
source provenance and uncertain identity remain visible alongside registry data.

BE-46 follows BE-42's mixed-channel repair without making agency procurement,
BE-43/44 or production qualification prerequisites. Its schema changes must remain
compatible with whichever news changes land first. No comprehensive EU-27 promise,
new service or standalone finance application is added. Full implementation
acceptance remains planned in BACKEND_ROADMAP; runtime, production data and provider
access are unchanged by this documentation delivery. The user subsequently
requested PR publication of this session's documentation work; implementation and
deployment remain outside that request.

## 2026-10-27 — D-79 (R2) — Reconcile the repository around two explicit sequences

The user rejected news as a post-project addendum, required the finished-product
README, challenged blanket package completion, and made full documentation/status
repair the top priority before further runtime implementation. BE-41 is the
complete parent delivery on codex/core-news-design, based on main 3f1effd.

Backend IDs use BE-01–40 with the historical inserted BE-25a; desktop uses DC-01–13.
Namespaced IDs preserve the two actual histories without pretending the desktop
was part of the original backend sequence. New work extends each track's sequence.
BACKEND_ROADMAP.md and DESKTOP_ROADMAP.md are the only authoritative registers;
ROADMAP.md coordinates paired deliveries and the active acceptance checklist.
Original roadmap/desktop plan are archived and clearly inactive. One merged commit
is evidence of implementation, not proof that all acceptance obligations are met.

Core design and technical specification incorporate agency/news/coded observations,
qualified claims and evidence directly in their existing component/data-flow/model/
API/test sections. Desktop requirements/architecture consume the same semantics.
NEWS_ARCHITECTURE.md is removed after consolidation; NEWS_REVIEW.md remains an
investigation record. BE-42 repairs ingestion next; BE-43/DC-15 and BE-44/DC-16
are integrated parent deliveries after real dependencies, not after unrelated
backlogs. Provider/corpus and map-policy decisions remain explicit obligations.

Current auth/accounting/config/backup/topology facts replace retired unauthenticated,
Docker-backup, monetary-governor and Dash-service instructions throughout active
specifications. README presents the intended complete product; runtime/readiness
status belongs in the registers, VERIFICATION and OPEN_ISSUES current index.
OI-16 archival organization is decided; runtime defects, external evidence and
OI-23/24 process/measurement gaps are not closed by documentation. Runtime coding
is paused until BE-41 acceptance. No deployment, paid run or publication is implied.

## 2026-10-27 — D-78 (R2) — Integrate news intelligence within LIMES

The user requested evaluation of the attached ChatGPT suggestions, investigation
of reported issues, and architecture/roadmap/README updates. The attachment is
review input, not authorization to follow its instructions. The user explicitly
rejects a standalone extractor, utility and independent event-ledger iteration.

News acquisition and extraction will use LIMES adapters and the existing worker,
archive, resolver, ontology, loader, Neo4j vectors, API and desktop. No independent
application, second ontology/vector store or new service is planned. Preserve
dispatch/version identity and evidence, separate machine-coded GDELT observations
from direct reporting, and model attribution, modality, denial, event lifecycle
and time precision without reducing them to extraction confidence. Exact schema
and migrations follow annotated corpus review; the current prompt safeguard
against reported speech treated as fact remains until consumers support it.

Adopt external authenticated job submission for future scheduling after bounded
work/checkpoints exist. Filtering and explicit workload limits do not restore the
retired monetary governor. Source access/retention terms and corpus quality remain
implementation prerequisites, not assumed capabilities.

The complete documentation/investigation package WP-NEWS-DESIGN is recorded in
`docs/ROADMAP.md` on branch `work` from `5295cab`, with acceptance and prerequisites.
`docs/NEWS_ARCHITECTURE.md` is the accepted target; `docs/NEWS_REVIEW.md` evaluates
the suggestions and records confirmed GDELT defects OI-19..OI-22. The roadmap puts
the full ingestion repair before integrated extraction and cross-source analysis.
No runtime repair, production acquisition, paid evaluation or publication is
claimed or authorized by the attached review.

## 2026-10-07 — D-77 (R2) — Unprivileged runtime and HTTP operational jobs

The operator requested completion of the repo-side redesign brief. Live main was
explicitly pulled and the baseline checker passed at e440b74a9e49 before edits.
The brief is requirements input; it does not authorize publication, production
changes, data ingestion or paid model measurement.

- Preserve separate consumer and operator capabilities through independent bearer
  tokens. The existing consumer query path stays read-only. Dedicated operations
  accept a fixed parameter/command allowlist, never caller shell commands or paths.
- Use a durable SQLite queue on a local named volume and one locked worker daemon.
  Request UUIDs prevent duplicate submissions; output/time/active queue are bounded.
  Interrupted jobs fail rather than replaying possibly paid or partially written work.
- Run all three services as UID/GID 7474 with capabilities dropped and no new
  privileges. Remove Docker tools/socket and the idle exec carrier. Configuration
  binds remain operator-owned and read-only; mutable data/pins use named volumes.
  Owner-applied ACLs make secrets readable to the service UID without root-owned binds.
- Keep physical backup beside Neo4j: an unprivileged supervisor starts the stock
  entrypoint, provisions a validated app user, forwards termination, and exposes
  only a private token-protected backup action. Clean stop is required before dump;
  restart/readiness run even after dump failure. No online-backup or host-control
  privilege is invented for Community Edition. Archive and dumps share a volume.
- Desktop backup and operational Make/remote CLI use authenticated HTTP. Pin updates
  refresh API query contexts on next use, without administrator restart. Keep desktop
  credentials in memory and HTTPS/loopback transport for remote consumers/operators.
- Generate authoritative runtime/access docs from the checked contract, retaining
  old specs as historical references for surviving graph contracts. A clean-source
  deployment tool records OCI revision labels and immutable image IDs and fails on
  source drift. Disposable smoke replaces the old live bootstrap/data-run script.

The absent original ignored 18-finding review trail is an evidence gap, not a
license to invent closure. Historical deployment evidence and a real measured
model run are not claimed by repo implementation or disposable tests.

## 2026-10-07 — D-76 (R1) — Reconcile stale-checkout work with merged foundations

PR #2 was merged before this work began. The implementing agent failed to fetch
main before implementation and publication, duplicating the foundations in PR #3
from the old `0aa9d67` checkout. This was a workflow error, not a later concurrent
change. PR #3 was never merged; main's `304bbad` implementation remains authoritative.

The correction imports main into the PR branch and preserves its authentication,
three-service topology, split/locked configuration, strict ledger contract,
recorder implementation, CI, docs guards and existing closure evidence. Duplicate
code, the second workflow, incompatible config example, and misleading redesign
status/closure claims from the stale branch are removed from the resulting tree.

Only incremental role/stage pin-write validation and regression tests for failed
ledger writes, pin-file/environment precedence and failed/partial pin updates
remain in the PR diff. A tracked baseline checker fetches main and rejects stale
checkouts; a repository-local pre-push hook enforces it for publication and fails
closed on fetch failure. Fresh clones must install the hook; this does not change
platform initialization. Hosted graph CI exposed a missing libEGL.so.1 dependency:
the graph job now installs the same Qt runtime libraries and uses the same
headless Chromium flags as the offline job. No production changes or paid model
calls are involved.

## 2026-10-07 — D-75 (R2) — Testing-phase inference, authenticated access and guard updates

The operator requested continued implementation of the attached issues/redesign
brief. It supplies requirements; the operator request authorizes these repo changes.
R1 removes spending enforcement, retaining passive usage and run accounting.
A1/A2 use bearer authentication on every API surface with a fail-closed startup,
loopback API publication, session-only desktop credentials, and HTTPS/tunnel access.
The shipped Dash service is dropped (C4); its sources remain compatibility code.
A5 separates secrets, settings and atomic model-only pin writes, treating empty
environment variables as unset. B1 records configured chat parameters; B2/B3 validate
catalogue-derived pins, automate dates, and require complete scored measured runs.
Provisional confirmation is opt-in; paid production runs are not implementation
verification. R3/D2 guard inventory and replacements are in docs/TESTING_PHASE.md.
These reversible requirement changes supersede the initial-process gates; no
one-way-door ceremony is needed for ordinary model/prompt iteration. Invariants
for temporal assertions, ontology, read-only queries, coverage, archives and no
paid test calls survive. R4 and remote operational/backup redesign remain open;
this change does not claim rootless operation or a deployed revision.

Guards: test_spending_limit_cannot_prevent_a_request,
test_zero_legacy_budget_does_not_stop_ingestion,
test_missing_or_invalid_credentials_reject_every_surface,
test_api_refuses_to_start_without_a_credential,
test_empty_environment_does_not_shadow_pin_file,
test_concurrent_writers_preserve_both_roles,
test_inference_parameters_sent_and_logged_without_prompt,
and the rewritten AC-34/smoke publication guards. CI records suite results as JUnit
artifacts; local verification evidence is appended to OPEN_ISSUES.md.

## 2026-10-06 — D-74 (R1) — Cloud-safe backup and desktop resource lifetimes

Operator requested fixes for the three failures found during cloud onboarding.

- The backup integration harness uses a named archive volume, like production,
  and inspects dump names and sizes inside a disposable Docker container.
  Neo4j keeps its private directory permissions; the test no longer assumes
  matching host/container UIDs or a shared `/tmp`. Count, nonempty artifact,
  CLI-success, and database-reconnect assertions remain in
  `test_backup_stops_dumps_and_restarts`. Rejected alternative: widening
  archive permissions or skipping the artifact assertion.
- `neo4j_instance` is a yield fixture that removes its own container and
  anonymous volumes in `finally`, including startup failure. Re-exporting it
  into desktop integration now includes cleanup without relying on a second
  autouse fixture. Externally supplied databases remain untouched. Guards:
  `test_fixture_removes_container_and_volumes_on_teardown`,
  `test_fixture_removes_container_when_startup_fails`, and
  `test_fixture_preserves_externally_supplied_database`.
- Desktop integration uses context-managed FastAPI `TestClient` with `ExitStack`
  for synchronous HTTP and lifespan management. The former `ASGITransport` is
  async-only, and the custom lifespan thread could swallow startup failures.
  The NL inference stub is installed before client startup and the query.
- `VizPage` contains a WebEngine widget created only when shown. Hidden result
  updates retain the latest payload without implicitly calling `page()` and
  acquiring default-profile pages. A dedicated off-the-record profile is a
  child of its page, so the page's WebEngine destructor runs before profile
  cleanup; payloads flush after HTML loading. Guards:
  `test_result_does_not_initialize_hidden_viz_views` and subprocess-based
  `test_visible_page_flushes_latest_payload_and_shuts_down`, which checks real
  JavaScript delivery, native deletion order, and process exit status.

No dependency, lockfile, ontology, model, or inference-budget change.

## 2026-09-10 — D-73 (R2) — Documentation sweep: docs updated to the implementation, code untouched

Operator-instructed full-repo docs↔code reconciliation ("treat the code as
authoritative; update the documentation; never change code behaviour"). Seven
file-disjoint doc surfaces were reconciled in parallel and every edit verified
against the cited code line.

- **In-place edits, no version bumps or renames.** `docs/*` filenames and
  in-document version tables keep their versions; content is corrected where it
  described the tree wrongly. Rejected alternative: bumping the documents
  (Technical Specification v2.2.0 etc.) — it would invalidate every cross-document
  version reference and trip `check_docs.py` C6 while changing nothing about
  meaning.
- **Document numbering kept as found.** Design Document = 1 of 3, Technical
  Specification = 2 of 3, Desktop Client Requirements = 3 of 3 (the slot the
  deleted Implementation Roadmap vacated); the Desktop Client Architecture is an
  unnumbered companion of the Requirements doc. The specification's two
  surviving promises of a "Document 3 — Implementation Roadmap" (§2 prose and
  the closing line) are removed; no document was renumbered.
- **Statement classes.** Factual statements about what exists today (project
  tree, dependency manifests, counts, paths, write surfaces, Makefile targets,
  test layout) were corrected. Requirements and design statements the
  implementation does not (yet) satisfy were **reported, not rewritten** —
  rewriting a requirement to match a partial implementation would have made the
  documents consistent by making them weaker.
- **One inferred edit, disclosed:** `docs/LIMES_Desktop_Client_Requirements_v1.0.0.md`
  §3 cited `FR-DC-014`, which is defined nowhere in the document; it now cites
  `FR-DC-002`, the requirement that makes connection state visible at all times
  (banner implementation). If the author intended a dropped requirement, this is
  the line to revisit.
- **Gaps found and left standing** (implementation-side, out of a docs sweep's
  scope): FR-DC-002 promises "API version and graph summary" from `/health`,
  which returns only `status`/`neo4j`/`ontology_version`; FR-DC-033's `surface`
  dimension is discarded by `ApiClient.save_query` (the payload overwrites the
  `cypher` field) and the API model has no surface field; the Architecture's §4
  rows for "schema mismatch" and "subprocess/QWebEngine crash" describe handling
  absent from the client.
- **Historical records preserved.** `CHANGELOG.md` entries, the design
  document's Revision History, and the desktop implementation plan
  (`docs/superpowers/plans/2026-09-09-desktop-client.md`, now carrying an
  executed-status block with its checkboxes deliberately unticked) are records
  of what was decided at the time; only factual errors were corrected.

Environment finding, recorded because it blocks verification here: on this
machine Docker's published ports accept TCP but do not relay the wire protocol
(`tests/integration` + `tests/acceptance` fail at fixture setup —
"Neo4j did not become reachable at bolt://127.0.0.1:55239"). Proven with a raw
socket connect (TCP OK) versus a bolt handshake on the same port (no response),
the same defect already recorded for this host's postgres publishing. Pre-existing,
unrelated to this sweep; integration and acceptance remain verifiable only in CI.

## 2026-09-10 — D-72 (R1) — Single-instance guard removes a stale QLocalServer socket before listening

wp-desktop-client-v1 review finding (Task 5). A crashed prior instance leaves
the guard's QLocalServer socket file behind, and `server.listen(GUARD_NAME)`
then fails silently — the app exits as if another instance were running when
none is. `__main__` now calls `QLocalServer.removeServer(GUARD_NAME)` after
`already_running()` confirms no live owner, so only a stale socket is cleaned
up (a running instance's socket is never removed: `already_running` short-
circuits first). Rejected alternative: listening unconditionally after a
remove (removes the socket of a genuinely running second instance started
between the check and the remove; the ordered check-then-remove keeps that
race harmless — the loser exits). Covered by `test_app.py`'s guard tests.

## 2026-08-26 — Approval — review-followup-v1.0.0

The human approved review-followup-v1.0.0 (D-68 downgrade guard under the
provisioning lock, D-69 fence-tag boundary, D-70 exactly-once idempotency
assertion, D-71 public current_type, AGENTS.md verification-loop fix) and
instructed commit and push to main, in their own words: "Approved. Commit and
push this to main." This approval names the presented version and cannot be
reused for any other version of the task. Verification at presentation:
ruff/mypy clean; unit 697 / integration 164 / acceptance 86 passed against
live Neo4j.

## 2026-08-26 — D-68 (R2) — The §4.3 downgrade guard is evaluated under the provisioning lock

Review finding on refactor-v1.1.0, operator-approved. `_check_ontology_version`
read stamped versions from the graph *before* `_acquire_provision_lock`, so two
concurrent provisioners carrying different ontology artifacts could both pass
the guard before either wrote DDL; the serialization guarantee did not cover
the read it protects. The check now runs inside the held-lock region, after
acquisition and before the first DDL statement; release stays in `finally`, so
a guard rejection cannot leak the lock. Rejected alternative: leaving the guard
outside and documenting the window as benign (one artifact per process today) —
declined because the fix is a two-line move and the benign reading depends on a
deployment invariant nothing enforces. Guard tests unchanged:
`test_downgrade_guard_rejects_older_ontology` still passes (release-on-raise
verified), `test_concurrent_provision_is_serialized` still green.

## 2026-08-26 — D-69 (R1) — `strip_model_fence`'s tag parameter made an explicit boundary

Review finding on refactor-v1.1.0. `tag` was interpolated into the fence regex
unescaped from an untyped `str` parameter — safe with the current literal
callers ("json", "cypher"), fragile if ever externally sourced. The parameter
is now `Literal["json", "cypher"]` (mypy rejects a new tag until it is added
deliberately) and `re.escape(tag)` precedes interpolation. Behavior identical:
both tags are escape-inert. R1: single-module change, callers pinned by unit
tests.

## 2026-08-26 — D-70 (R1) — Provisioning idempotency asserted exactly-once per index name

Review nit on `test_provision_is_idempotent`: it counted all Entity-labeled
indexes (`>= 1`) under a comment claiming "exactly once" — duplicates would
have passed. It now reuses the concurrent test's stronger check: every §5.3
index name appears exactly once in `SHOW INDEXES`. The parsing snippet moved
into one shared helper (`_expected_index_names`) used by both tests instead of
a near-duplicate; the label-counting `_index_count` helper had no remaining
caller and was removed with this decision as its record. Test-only, R1.

## 2026-08-26 — D-71 (R1) — `components.builder._current_type` promoted to public `current_type`

Review nit: `ui/callbacks/builder.py` imported the underscore-private
`_current_type` across modules (moved verbatim by the S6 split). Promoted to
public `current_type`; the render loop's same-named local renamed to
`hop_type` in both the component and the callback, because a local assigned
the function's own name would shadow it function-wide (UnboundLocalError, not
style). Consumers updated: components/builder.py, callbacks/builder.py,
test_ui_components.py. No behavior change; UI purity scan untouched. R1.

## 2026-08-24 — D-67 (R2) — Provisioning serialized via a transient mutex transaction

Operator instruction on the [CONFLICT] finding: "serialize provisioning.
now." Chosen mechanism: `provision()` opens a dedicated session and begins
a transaction whose only statement is `MERGE (n:_SchemaProvisionMutex ...)`;
that write lock blocks any concurrent provisioner until the holder finishes,
then the transaction is **rolled back** — the sentinel never persists, so
§5.8's system-node catalog is untouched. Crash of a holder releases the lock
with its connection. Rejected alternatives: (a) tolerating
`EquivalentSchemaRuleAlreadyExists` on `IF NOT EXISTS` statements — the
explicitly declined branch (operator chose serialize over tolerate);
(b) batching all DDL into one schema transaction to inherit Neo4j's schema
lock — rejected because this file documents Neo4j's bounded-window
compilation limit ("insanly frequent schema changes") that fails many-DDL
transactions; (c) reusing `:AdvisoryLock` as the sentinel — rejected:
phase-6 T1 names cli/main.py its sole writer, and a persistent sentinel node
would extend §5.8 without spec cover. Known bound, accepted: a waiter sits
in a normal transaction, so the §13.4 transaction timeout (120 s production)
caps how long it may wait — provisioning is seconds-long.

**G3-refactor (guarded)** — Concurrent invocations of `provision()` both
succeed and leave each index exactly once → guard
`tests/integration/test_schema_provision.py::test_concurrent_provision_is_serialized`.

## 2026-08-24 — Approval — refactor-v1.1.0

The human approved refactor-v1.1.0 (architecture consolidation S1–S6 plus
the provisioning serialization repair S7) on 2026-08-24 and instructed
merge and push, in their own words: "approved. i explicitly allow you and
instruct you to merge and push also." Delivered as branch
`refactor-consolidation` (9 commits), merged to `main` and pushed; the
topic branch is pushed as well. This approval names the presented version
and cannot be reused for any other version of the task.

## 2026-08-24 — D-67b (R2) — Correction: the transient-mutex design of D-67 does not hold; replaced by an AdvisoryLock polling mutex

D-67's first implementation (a rolled-back MERGE sentinel transaction) is
wrong and is removed by this commit: `MERGE` takes no lock when nothing
matches, so two simultaneous provisioners on an empty database both created
the sentinel and raced anyway — reproduced deterministically by the new
concurrent guard test, not merely inferred. A second intermediate design
(create-then-count verification) had its own TOCTOU and was also removed.
Delivered mechanism: `_ensure_lock_constraint()` creates the existing
`lock_source` uniqueness constraint FIRST (bounded retries; the one-statement
bootstrap window is the only place an equivalent-rule error is ever retried
in this codebase); acquisition then `CREATE`s an `:AdvisoryLock` row with
source_id `__ontology_provision__`, where the constraint turns a lost race
into a loud `ConstraintValidationFailed`; losers poll with jittered backoff
up to 60 s, stale holders are reclaimed after 120 s (provisioning takes
seconds), release deletes by own run_id. T1 flag from phase 6, discharged:
this makes graph/schema.py a second WRITER of `:AdvisoryLock` beside
cli/main.py — reviewed here under the operator's explicit "serialize
provisioning" instruction, logged so no future reader mistakes it for an
accident. Evidence: concurrent guard test 5/5 green
(`test_concurrent_provision_is_serialized`, two threads through a barrier);
unit 697 / integration 164 / acceptance 86 all passed; live-stack proof via
`tools/smoke_test.py --clean` follows this entry in the session record.

## 2026-08-24 — Refactor complete — trajectory and final measurements (all metrics met)

All five metric targets met within budget (8 commits of 10; ~3.5 h of 4 h).
Final measurements, each command run against the delivered tree at `7230d7e`
(+ ledger/changelog commit):

- **M1** — `ruff check src tests` + `ruff format --check src tests`: clean
  (was 16 E501 + 6 deviating files). Met in S1.
- **M2a** — `grep -rn "Assertion(" src/limes/sources/*.py | grep -v base.py`:
  0 (was 13). One canonical `make_assertion()`; 11 adapters migrated; 12
  local helper copies deleted. Met in S2.
- **M2b** — identity-digest definitions outside `base.py`: 0 for all three
  families (`topic_endpoint`, `address_location`, `coordinate_location`);
  digest inputs byte-identical, so entity_ids and loader merges are
  unchanged. The TED buyer digest stays local by design (single-site
  convention). Met in S3.
- **M2c** — retry/backoff implementations across sources+extraction: exactly
  one (`request_with_retry()`); four hand-rolled copies delegate;
  `graph/driver.py` excluded as deliberately distinct. Met in S4.
- **M3** — `ui/callbacks/query.py`: 318 lines ≤ 500 (was 557) via
  `ui/callbacks/builder.py`. Met in S6.
- S5 (fence stripping, prompt-path resolution) was scope hygiene inside the
  same budget, not a numbered metric.

Evidence: unit 697 passed, integration 163 passed (live Neo4j), acceptance
86 passed — full three-suite run green after the final code change (S6);
ruff/mypy clean at every commit; each step reviewed before commit. Live-stack
verification: guards G1–G4 static checks pass; fresh `make up` healthy;
`make ingest SOURCE=gisco_nuts` completes end-to-end in the container
(804,812 nodes created, 1,932 assertions written, 0 errors) through the
refactored adapter path.

## 2026-08-24 — [CONFLICT] pre-existing: concurrent provision() races on a fresh volume

Discovered by the final smoke-test run, NOT introduced by this refactor (the
branch touches no `graph/`, compose, or Dockerfile code — verified by diff).
On a fresh volume, the api container's startup handler and the worker's first
command both run `provision()` (composition.py:88, api/main.py:81). Two
concurrent `CREATE INDEX … IF NOT EXISTS` statements for the same name can
collide server-side; observed: worker ingest failed with
`Neo.ClientError.Schema.EquivalentSchemaRuleAlreadyExists` on
`office_at_valid_from` ~27 s after `make up`, while the api's own provisioning
was still executing. Timestamp correlation stated per contract §10: api/worker
started together at 08:00:57 CEST; ingest began 06:01:24 UTC. Post-failure
inspection shows every index present exactly once — the second creator lost,
the schema is correct. Re-running `make ingest` alone completes cleanly.
The phase-9 smoke pass predated this observation; nothing in the interim
diff touched the path. Recommended follow-up (human decision, outside this
task's D-66 consolidation scope): make `provision()` tolerate the
equivalent-rule error on `IF NOT EXISTS` statements, or serialize startup
provisioning against the worker.

## 2026-08-23 — Refactor task: stop condition, scope decision, and invariants (derived at task start)

Operator instruction: "Refactor until you are happy with the architecture."
"Until happy" is rejected as a stop condition per global contract §7 even when
the human writes it. The substituted stop condition below was measured on a
clean tree at `bf3066f` before the first edit. Budget: **10 commits or 4 hours
wall-clock, whichever comes first**; exhausted with targets unmet means stop
and report the trajectory.

**D-66 (R2) — Scope: consolidation inside existing §2 modules only.**
Doc 2 §2 says "Paths are authoritative" and enumerates module lists per
directory (`ui/components/*.py` and `ui/callbacks/*.py` are the only
wildcards). Following the D-49 precedent that enumerated lists are closed:
all consolidation lands inside existing modules (shared helpers move into
`sources/base.py`, `extraction/openrouter_client.py`, etc.), plus one new
module allowed under the wildcarded `ui/callbacks/`. Rejected alternative:
same-directory splits of `cli/evaluate.py` (703), `pipeline/run.py` (659),
`nlq/validate.py` (679) — rejected because §2 enumerates those files closed;
the consequence of the rejection is that these three stay above 500 lines,
accepted as spec-shaped, not fixed here. Reversing this requires a human
spec amendment, not an agent choice.

Stop-condition metrics (measurement commands stated; values measured now):

- **M1 — Lint/format debt = 0.**
  `./venv/bin/ruff check src tests && ./venv/bin/ruff format --check src tests`.
  Now: 16 E501 errors + 6 files would be reformatted (pre-existing on main;
  lookups.py and test_loader.py already ledger-documented). Target: both
  exit clean.
- **M2 — Adapter duplication index = 0**, three identity/load-bearing
  families: (a) `Assertion(` construction sites in `src/limes/sources/*.py`
  outside `base.py`: **13 now → target 0** (one canonical constructor);
  (b) sha256 identity-digest definitions outside `base.py` for address /
  coordinate / topic identity: **5 sites now (gleif, ted×2, gdelt, osm) →
  target 0**; (c) retry/backoff loop implementations across `sources/` +
  `extraction/`: **3 files / 4 loops now → target exactly one shared
  implementation, all consumers delegating** (`graph/driver.py` excluded —
  deliberately distinct Neo4j-transient policy).
- **M3 — `src/limes/ui/callbacks/query.py` ≤ 500 lines** via the wildcarded
  `ui/callbacks/` split. Now: 557. (The other over-500 modules are covered by
  D-66's accepted deviation.)

Task invariants, derived per contract §6:

- **G1 (guarded)** — Full test suite green after every step (unit suite per
  commit; integration + acceptance against live Neo4j at milestones).
- **G2 (guarded)** — Every existing architecture guard test stays untouched
  and green: API write surface (AC-18), UI purity (§8.13), AC-40 composition
  root, loader sole-writership.
- **T1 (triggered)** — Any diff touching `graph/loader.py`, an `api/` write
  path, or a prompt `.md` file is flagged before commit (prompt *code* paths
  are in scope; prompt files themselves are not).
- **T2 (triggered)** — Behavior preservation: no observable behavior change;
  evidence is the unchanged, green suite plus review of each diff for
  semantic drift (e.g., identical digest inputs → identical entity_ids).

Branch: `refactor-consolidation` (repo convention is `wp-NN-slug` for work
packages; this is not a WP, so the refactor prefix states what it is).

## 2026-08-03 — Approval — phase-11-v1.0.0 (WP-40)

The human approved phase-11-v1.0.0 (100% line coverage suite) on
2026-08-03 and instructed merge, commit, and push. Delivered as branch
`wp-40-line-coverage`, merged to `main` and pushed; the topic branch is
pushed as well. This approval names the presented version and cannot be
reused for any other version of the phase.

## 2026-08-03 — D-63 (R2) — Operator-instructed 100% line coverage (WP-40)

The operator instructed "add tests until we have 100% test coverage".
Doc 2 §12.4 declares line coverage not a target ("the required condition
is that every error path in §11 and every rejection code in §8.10 is
triggered by at least one test"), but a later explicit operator
instruction overrides an earlier document sentence. Logged as the
delegation's basis so a future reader does not treat 100% as the spec's
own requirement. Measurement: statement coverage of `src/limes` over all
three suites combined (`unit` + `integration` + `acceptance`; separate
runs appended via `coverage run --append` because the acceptance
conftest's `pytest_plugins` is rejected by pytest 9.1.1 in whole-tree
collection — pre-existing quirk, not touched here). Subprocess-based
tests are invisible to the coverage tracer, which is why the CLI command
bodies that the integration suite runs as subprocesses needed in-process
unit tests.

## 2026-08-03 — D-62b (R2) — Dead builder-hold callback repaired in `ui/callbacks/query.py`

Found by the WP-40 coverage exercise: `builder_hop_change` decoded the
hop index with `triggered_index("builder")`, but every hop control's
pattern id is `{"type": "builder-rel"|"builder-dir"|…, "index": n}` — the
exact-type match can never succeed, so every hop-control interaction
raised `PreventUpdate` and the entire callback (lines 231–311) was dead
in production. The fix decodes the index from the same decoded control
type (`triggered_index(control)`), restoring the documented behavior
("applies whichever hop control changed"). Rejected alternative: testing
around the defect by driving the branches with a hand-built context — the
branches were unreachable through the callback's own contract, and
covering dead code would enshrine it. R2: bounded, restores the WP-36
design intent; the UI suite (`test_ui_callbacks.py`) now exercises every
branch.

## 2026-08-03 — D-64 (R1) — Test isolation from the repository `.env` (WP-40)

The pre-existing WP-02 failure documented in the phase-10 changelog
(`test_config.py::test_load_settings_missing_required_key_names_it` fails
when the repo's own `.env` exists at the CWD) was fixed in the test:
an autouse fixture forces `Settings(_env_file=None)` so the unit suite
asserts on the environment alone. R1 — test-only, no production change;
the phase-10 changelog's "not fixed here" note is now resolved.

## 2026-08-03 — D-65 (R2, user-approved) — `coverage` added to the dev dependency group

The task requires measuring coverage; the project venv had no coverage
tool (the system site-packages copy is ABI-compatible but outside the
project contract). The operator approved adding `coverage>=7.15` to
`[dependency-groups].dev` in pyproject.toml; installed into `./venv/`.
Host tooling lives in the venv per the global contract §3.

## 2026-08-03 — Approval — phase-10-v1.0.0 (WP-39)

The human approved phase-10-v1.0.0 (acceptance test suite) on 2026-08-03
and instructed merge, commit, and push. Delivered as branch
`wp-39-acceptance-tests`, merged to `main` and pushed; the topic branch is
pushed as well. This approval names the presented version and cannot be
reused for any other version of the phase.
---

## 2026-08-03 — Phase 10 invariants (WP-39), derived at phase start

Derived from the roadmap's WP-39 entry and Doc 2 §12.4/§14, per the global
contract §6. Guarded (automatically tested) and triggered (review-trigger)
invariants, logged when derived:

- **G1 (guarded)** — Every AC-01…AC-44 has a mechanical test in
  `tests/acceptance/` and the suite passes → asserted by the meta-test
  `test_ac00_meta_coverage.py` (scans for `test_acNN_*` functions and
  fails on any gap) plus the suite itself.
- **G2 (guarded)** — No acceptance test touches a live external service;
  the paid boundary is respx-mocked or fixture-stubbed → enforced by the
  suite's construction: every test that crosses the paid boundary uses
  `respx.mock` or an injected fake; a test that performs live network
  access fails loudly (respx with no routes).
- **G3 (guarded)** — Cross-process acceptance tests cross a real process
  boundary via `subprocess` (AC-39's lookup read, AC-01's startup check,
  AC-44's check_docs run) per Doc 2 §12.2 rule 2.
- **G4 (guarded)** — No acceptance test hand-builds the graph state the
  production path produces: all graph state is established through
  `execute_run`, `load`, or the API (Doc 2 §12.2 rule 1) → enforced by
  the suite's construction and reviewable per test.
- **T1 (triggered)** — The `populated_graph` fixture's stub seam (class
  method replacements on the adapters and `composition.spacy.load`): any
  change to what is stubbed or how requires re-review that the production
  path still runs for real underneath.
- **T2 (triggered)** — AC-32's testable proxy: the test asserts the
  §13.4 declared caps sum below 11 GB, not a measured backfill resident
  set. A change to the caps or the ceiling requires re-review of the
  proxy's adequacy.

## 2026-08-03 — D-62 (R2) — Plan-gate row estimates repaired in `graph/driver.py`

Found by the AC-21 acceptance test: `_parse_plan` read the EXPLAIN row
estimate from a top-level `estimatedRows` key that the Neo4j 2026.06
server never emits — the estimate is nested under `args.EstimatedRows`.
Measured against a live container: every plan reported max=0/total=0, so
the §8.10 rejections `OPERATOR_ROWS_EXCEEDED` and `TOTAL_ROWS_EXCEEDED`
silently never fired; two of the five plan-gate rejections were dead code.
The fix reads `args.EstimatedRows` with the legacy top-level key as
fallback (one function, no signature change). Rejected alternative:
leaving the dead parsing and writing the AC-21 test against mocked plan
dicts — that would enshrine the defect and fail the criterion's letter
(a crafted query must produce the rejection against the real database).
The fix is R2 (bounded, spec-mandated — §8.10 requires the rejections);
the pre-existing `test_nlq_plan` unit suite never exercised the estimate
fields, which is why the defect shipped. The affected integration suites
(test_graph_driver, test_loader, test_resolution, test_ui,
test_api_query_*, test_pipeline_run_*) re-ran green after the fix.

## 2026-08-03 — Approval — phase-9-v1.0.0 (WP-37, WP-38)

The human approved phase-9-v1.0.0 (Docker images and Compose topology;
Makefile and bootstrap procedure) on 2026-08-03 and instructed merge,
commit, and push. Delivered as branch `wp-37-38-infrastructure`, merged to
`main` and pushed; the topic branch is pushed as well. This approval names
the presented version and cannot be reused for any other version of the
phase.

## 2026-08-03 — Phase 9 invariants (WP-37, WP-38), derived at phase start

Derived from the roadmap's WP-37/WP-38 entries, Doc 1 §8.1–§8.4/§6.6, and
Doc 2 §13.1–§13.4/§8.14, per the global contract §6. Guarded (automatically
tested) and triggered (review-trigger) invariants, logged when derived:

- **G1 (guarded)** — AC-34: the base Compose file publishes no ports, and
  the Neo4j port appears in neither file except as the `LIMES_NEO4J_URI`
  value → asserted by `tools/smoke_test.py` (compose config + source
  scan) before any stack action.
- **G2 (guarded)** — The `ui` service holds no credentials: no `env_file`
  and no Neo4j/OpenRouter key in its environment; its only variable is
  `LIMES_API_BASE_URL` (D-09) → asserted by `tools/smoke_test.py` against
  the rendered compose config.
- **G3 (guarded)** — Only the worker image installs the spaCy models: the
  api and ui Dockerfiles prune `de-core-news-md` and `en-core-web-md` from
  the lockfile export → asserted by `tools/smoke_test.py` (static scan of
  the three Dockerfiles plus a `python -c "import de_core_news_md"` check
  against the built images).
- **G4 (guarded)** — Every `make` target from Doc 2 §8.14 exists, and
  `backfill`/`reextract` refuse to run without `BUDGET` → asserted by
  `tools/smoke_test.py` (`make help` lists all eleven targets; a missing
  `BUDGET` invocation exits non-zero).
- **T1 (triggered)** — The neo4j boot wrapper's user-creation step: any
  change to the wrapper, to `LIMES_NEO4J_USER`/`LIMES_NEO4J_PASSWORD`
  handling, or to the neo4j image tag requires re-review of the auth flow
  (the wrapper is the only path that creates the production user).
- **T2 (triggered)** — The worker's docker-socket mount is host-level
  privilege: any topology change touching the socket mount, the worker's
  docker CLI, or the compose files mounted into the worker requires
  review of what a compromised worker could reach.

## 2026-08-03 — [CONFLICT] resolved by the human — the production `limes` Neo4j user is created by a boot wrapper (R2)

The documentation set defines no mechanism that creates the production
`limes` Neo4j user. Verified in the `neo4j:2026.06-community` image itself:
the entrypoint's only user mechanism is `NEO4J_AUTH`, which provisions the
first-boot `neo4j` admin only. `bootstrap-db` is a no-op, `up` is bare
`docker compose up -d`, and the topology is exactly four services — yet
`.env.example`, the API, the worker, and the WP-38 verification's own
`cypher-shell -u limes` all require `limes` to exist. Recorded as
`[CONFLICT]` per roadmap §1.3 and presented to the human with four
branches (entrypoint wrapper; `make up` gains a user-creation step; manual
operator step; connect as `neo4j`). The human chose the **entrypoint
wrapper**: the base compose overrides the neo4j service's entrypoint with a
bash wrapper that starts the stock `/startup/docker-entrypoint.sh neo4j` in
the background, polls `cypher-shell -u neo4j` until the database accepts
connections, runs `CREATE USER ${LIMES_NEO4J_USER:-limes} IF NOT EXISTS SET
PASSWORD '<escaped>' CHANGE NOT REQUIRED`, then `wait`s on the server. Any
other invocation is `exec "$@"`, so the WP-28 backup path
(`docker compose run --rm --no-deps neo4j neo4j-admin …`) bypasses the boot
logic. Idempotent per volume, consistent with "provisioning happens on
every context build". Rejected alternatives and their consequences were
presented; the operator's choice is recorded here and cannot be reused for
another phase.

## 2026-08-03 — D-59 (R2) — Dependency layer via `uv export` + `uv pip install --system`, not `uv sync`

`uv sync` unconditionally creates a virtual environment — verified locally
that `UV_PROJECT_ENVIRONMENT` merely redirects where the venv is created —
and Doc 2 §13.1 forbids a virtual environment inside an image. The shared
dependency layer therefore runs `uv export --frozen --no-dev
--no-emit-project` and `uv pip install --system -r` (system-prefix install,
no venv), then `uv pip install --system --no-deps .` for the project. The
api and ui exports additionally `--prune de-core-news-md --prune
en-core-web-md`; the worker's export keeps them, which is how "only the
worker installs spaCy models" is satisfied — from the locked 3.8.0 wheels
in the committed lockfile, not `python -m spacy download`. Same frozen
resolution either way.

## 2026-08-03 — D-58 (R2) — api image CMD uses the factory form

`src/limes/api/main.py` exposes `create_app` and no module-level `app`
(phase-8 observation, 2026-08-02); the roadmap's literal
`uvicorn limes.api.main:app` would fail at boot. The api.Dockerfile CMD is
`uvicorn limes.api.main:create_app --factory --host 0.0.0.0 --port 8000`.

## 2026-08-03 — D-57 (R2) — Worker carries the docker CLI and the compose context; project named `limes`; `.env` delivered by mount, never `env_file`

The WP-28 `backup` command orchestrates `docker compose stop/run/start`
from its process working directory, and `select_models` writes pins into
`Path(".env")` in its CWD — both execute inside the worker container via
the Makefile. The worker image therefore carries `docker.io` and
`docker-compose-v2`, and the base compose mounts into the worker: the
docker socket, `docker-compose.yml` and `docker-compose.override.yml`
(read-only, so compose resolves the project from `/app`), and `./.env`
(read-write, so the pins persist to the host). `name: limes` makes the
worker's compose invocations resolve the same project as the host's
regardless of directory.

Configuration is delivered to `api` and `worker` by the `./.env` mount and
the app's own dotenv read (`config.py`'s `env_file=".env"`) — **not** by
compose `env_file`. Verified empirically with the pinned pydantic-settings:
an environment variable set to the empty string shadows a dotenv value
(present-but-empty env wins over the file). Compose `env_file` passes the
empty pin keys from `.env.example`, so the container environment would
permanently dead-letter the pins `select_models` writes — the bootstrap's
step-3-to-step-7 sequence (pin, then backfill) would fail with "no
extraction model pinned" even though `.env` holds the pin. The mount keeps
every exec'd process reading the current `.env` from its working directory
(`/app`), pins included, without any restart. The api mount is read-only;
the worker's is read-write (it writes pins). These are host paths in the
base file; Doc 1 §8.4's "no host paths" governs storage, and these carry
the configuration and compose context the delivered CLI requires. Rejected:
`env_file` (proven to dead-letter the pins), baking the compose files into
the image (drift), or running backup from the host (the roadmap fixes the
target to `docker compose exec worker limes backup`).

## 2026-08-03 — D-56 (R2) — `stamp-embeddings` Makefile target

The WP-25a contract names WP-38 as the wiring point for
`stamp_missing_embeddings`, which no CLI command exposes, and Doc 1 §6.6's
target list names no such target. The Makefile gains `stamp-embeddings`,
which runs a `python -c` invocation inside the worker with the inference
context (`build_run_context(needs_inference=True)`); the bootstrap
documents it between steps 6 and 7 per §13.3. Rejected: extending the CLI
(outside WP-38's file scope) and folding the stamp into an existing target
(wrong semantics; the stamp is a one-shot, not an ingestion).

## 2026-08-03 — D-55 (R1) — `migrate` target variable, `.dockerignore`, neo4j healthcheck

Three small calls: (1) the roadmap's `migrate` usage line says
`ONTOLOGY_VERSION=<v>` while its recipe line says `$(VERSION)`; the target
uses `$(ONTOLOGY_VERSION)` so the documented invocation works. (2) A
`.dockerignore` exists (build-context hygiene; without it the repo, the
host venv, and `.git` are copied into every build context — Doc 2 §2 does
not list it, it sits beside `.gitignore`). (3) The neo4j service declares a
cypher-shell healthcheck (as the `limes` user) and api/worker use
`depends_on: condition: service_healthy`, so `make up` returns with the
stack actually ready instead of merely started.

## 2026-08-03 — D-60 (R1) — `select-models` arguments pass through `ARGS=`, not `make --`

GNU make treats everything after `--` as goals: `make select-models --
--provisional` (the form written in §13.3's bootstrap and the delivered
README) fails with "No rule to make target '--provisional'" — verified
locally. The Makefile's `select-models $(ARGS)` mechanism per the WP-38
task list therefore requires `make select-models ARGS="--provisional"`;
the bootstrap documentation written by this phase uses that form. The
spec's literal invocation is a defect in the operator syntax, not in the
target; nothing in the Makefile changed to work around it.

## 2026-08-03 — D-61 (R1) — Compose wiring facts discovered during live verification

Three verified behaviors shaped the delivered files; recorded so the next
topology change does not rediscover them:

1. **Compose drops the image CMD when `entrypoint` is overridden as a
   list** (reproduced minimally: `Cmd=null` in the created container). The
   neo4j service therefore restates `command: ["neo4j"]`, and the boot
   wrapper dispatches on `$0` — `bash -c script neo4j` puts the CMD in
   `$0`, not `$1` — re-executing arbitrary commands as `"$0" "$@"` so the
   WP-28 backup's `docker compose run --no-deps neo4j sh -c …` works.
2. **Debian trixie has no compose v2 plugin package** (`docker-compose-v2`
   does not exist there; only `docker-cli` and the python `docker-compose`
   v1). The worker image installs `docker-cli` and the pinned upstream
   compose v2.40.3 plugin binary, SHA-256-verified against the release
   checksums at build time.
3. **`docker stop`'s default 10 s grace kills Neo4j uncleanly**: the first
   backup attempt failed with "Active logical log detected" and the dump
   refused. The neo4j service sets `stop_grace_period: 180s`; a verified
   clean stop of a small graph took ~120 s (Doc 1 §8.3 budgets 5-20 GB).
   Also: `docker compose ps --format json` emits JSONL, one object per
   line — `tools/smoke_test.py` parses it line by line.

## 2026-08-02 — Approval — phase-8-v1.0.0 (WP-36)

The human approved phase-8-v1.0.0 (Dash UI: three synchronized panes, the
schema-generated builder, NL input and editable Cypher console, coverage
and provenance panels, saved queries, budget indicator) on 2026-08-02 and
instructed merge, commit, and push. Delivered as branch `wp-36-dash-ui`
(commits `48556d3`, `fb7cab1`), merged to `main` and pushed; the topic
branch is pushed as well. This approval names the presented version and
cannot be reused for any other version of the phase.

## 2026-08-02 — D-14 (R1) — Selection sync semantics for the three panes

AC-29's "all three panes react to a selection change" is implemented
symmetrically: a node selection highlights the node in the network, its
marker on the map, and the rows of its incident edges in the timeline; an
edge selection highlights the edge in the network, its row in the timeline,
and the markers of both endpoints on the map. The map can only highlight
coordinate-bearing nodes (the only points it renders), and the timeline can
only highlight edges present in the result — a pane reacts exactly as far
as the data it renders admits.

## 2026-08-02 — D-13 (R1) — Builder bounds: one property filter per hop, one instant picker

The generated builder offers one (property, value) filter per hop and a
date picker for `as_of`/`as_believed` instants, and caps no hop count.
Richer filters and instant precision are the console's job; the builder
guarantees admissibility, not completeness. The instant is date-only: the
API's parameter passing cannot string-match datetime properties anyway
(`coerce_filter_value` documents this), so a date picker cannot promise a
match the API cannot deliver.

## 2026-08-02 — Observations for later phases (triggered paths)

- `src/limes/api/main.py` exposes `create_app` but no module-level `app`.
  WP-37's api.Dockerfile CMD `uvicorn limes.api.main:app` will therefore
  fail; it needs `uvicorn limes.api.main:create_app --factory`. Flagged
  here because it is outside WP-36's scope (the UI test uses the factory
  form). The ui.Dockerfile CMD `python -m limes.ui.app` works as specified.
- `src/limes/graph/lookups.py` fails `ruff format --check` on `main`
  (pre-existing WP-08 formatting deviation, unrelated to this phase);
  left untouched as out of scope.

## 2026-08-02 — D-12 (R1) — Panes re-render from the full query response envelope

The `current-result` store holds the whole `QueryResponse` (results,
coverage, diagnosis, notes), not just the graph: the coverage panel and the
console need the API's annotations, and AC-27's merge operates on the
`results` slice only. `merge_neighborhood` always returns the envelope form,
so the store has one shape regardless of whether the view started from a
query, a search jump, or an expansion.

## 2026-08-02 — Phase 8 invariants (WP-36), derived at phase start

Derived from the roadmap's WP-36 entry, Doc 1 §6.5/§4.13, and Doc 2 §8.13,
per the global contract §6. Guarded (automatically tested) and triggered
(review-trigger) invariants, logged when derived:

- **G1 (guarded)** — The UI holds no credentials and performs no database
  access: no `neo4j`, `GraphDriver`, or `bolt://` reference anywhere in
  `src/limes/ui/` → `test_ui.py::test_ui_holds_no_credentials_and_no_database_access`
  (source scan).
- **G2 (guarded)** — No UI module contains a hardcoded ontology type name
  or relation name as a literal; the builder is generated from
  `/builder/schema` → `test_ui.py::test_ui_source_contains_no_ontology_literals`
  (AST literal scan against the loaded ontology).
- **G3 (guarded)** — Node click expands one hop through
  `/entity/{id}/neighbors` and merges into the current view without
  re-running the original query (AC-27) →
  `test_ui.py::test_ac27_node_click_expands_one_hop_without_rerunning_the_query`
  (recording fake api_client asserts no query-path call).
- **G4 (guarded)** — Edge selection displays full provenance including the
  originating sentence when the evidence document is available through the
  API (AC-28) → `test_ui.py::test_ac28_edge_selection_shows_provenance_and_sentence`.
- **G5 (guarded)** — All three panes react to a selection change and to a
  timeline brush within one interaction cycle; the brush triggers a re-query,
  never client-side filtering (AC-29, Doc 2 §8.13) →
  `test_ui.py::test_ac29_panes_react_to_selection_and_brush_in_one_cycle`.
- **T1 (triggered)** — The builder's per-hop options stay admissible as the
  ontology evolves: any change to `ontology/ontology.yaml` that adds or
  renames a type or relation requires re-review of the builder rendering and
  of the map's coordinate-type derivation (the schema-derived lookups in
  `ui/components/builder.py` and `ui/components/map.py` are the affected
  paths).

## 2026-08-02 — D-11 (R2) — Timeline brush re-queries with `as_of` = brush right edge

The brush stores `{as_of, range}` in `temporal-filter` and re-runs the
query that produced the current view through the same API path: the builder
path re-runs `POST /query/builder` with `as_of` qualifiers on temporal hops
(the schema's `temporal` flag decides, never a UI list), and the NL and raw
Cypher paths re-run their stored payload (`POST /query/nl` with the same
question, `POST /query/cypher` with the same cypher). The API surface (Doc
2 §6) has no temporal parameter for arbitrary Cypher, so those two paths
cannot carry the instant without the UI authoring Cypher fragments (which
§8.13 forbids); their re-run keeps the panes reproducible by the graph.
`as_of` = brush right edge means the panes show the state at the end of the
brushed period — the only single-instant semantics expressible through
`BuilderHop.temporal_qualifier` and the neighbors endpoint's `as_of`.
Rejected alternative: client-side interval filtering (explicitly forbidden
by §8.13); appending `WHERE` clauses in the UI (a Cypher fragment, also
forbidden).

## 2026-08-02 — D-10 (R2) — Originating sentence availability is bounded by the API

AC-28 requires the provenance panel to show the originating sentence for
news-extracted assertions. The API (Doc 2 §6) exposes no document-text
endpoint, and — as WP-32's search test documents — no production path
stamps `title`/`body` on `:Document` nodes today, so `get_entity()` returns
404 for an evidence document. The panel therefore displays the full `EdgeRef`
provenance plus the evidence coordinates and fetches the sentence via
`get_entity(evidence_document_id)` when the document node exists (the
sanctioned read path, and the mechanism that works unchanged once the
pipeline materializes document entities). When the document is absent the
panel states so explicitly — nothing is fabricated. This bounds AC-28's
mechanical testability for WP-39 to the API's current surface; recorded as a
seam gap rather than resolved by an out-of-scope API change.

## 2026-08-02 — D-09 (R1) — UI reads `LIMES_API_BASE_URL` from the environment, never `.env`

The UI is the one process that must hold no credentials (Doc 1 §7.4); it
never loads `Settings` and never parses `.env` (which carries the OpenRouter
key and the Neo4j password). It reads the single `LIMES_API_BASE_URL`
variable directly, defaulting to `http://127.0.0.1:8000` for a bare local
run; the compose `ui` service receives the value from the environment
(WP-37).

## 2026-08-02 — D-08 (R1) — UI callbacks are plain functions with a thin registration layer

Each `callbacks/*.py` module defines its logic as pure functions (inputs in,
outputs out) and a small `register(app)` that wires them into Dash. This
makes AC-27/28/29 mechanically testable without a browser (the functions
are called directly with recorded-fake API clients), keeps the Dash layer
to a thin shell, and keeps `api_client.py` the only module performing HTTP.

## 2026-08-02 — Approval — phase-7-v1.0.0 (WP-32…WP-35)

The human approved phase-7-v1.0.0 (query API foundation, NL-to-Cypher
service, coverage report and empty-result diagnosis, query routers with
the enumerated write surface) on 2026-08-02 and instructed merge, commit,
and push. Delivered as branch `wp-32-35-query-api` (commits `ef749e4`
… `a115610`), merged to `main` and pushed; the topic branch is pushed as
well. This approval names the presented version and cannot be reused for
any other version of the phase.

## 2026-08-02 — Phase 7 invariants (WP-32…WP-35), derived at phase start

Derived from the roadmap's WP-32…WP-35 entries and Doc 2 §6–§8.12, per the
global contract §6. Guarded (automatically tested) and triggered
(review-trigger) invariants, logged when derived:

- **G1 (guarded)** — The API's write surface is exactly the three
  enumerated writes of §7.3 and nothing else in `src/limes/api/` →
  `test_api_write_surface.py::test_ac18_grep_finds_only_the_sanctioned_writes`
  and `test_ac18_write_attempt_corpus_is_rejected` (obfuscation corpus).
- **G2 (guarded)** — Every §8.10 validation code is produced by a crafted
  query and blocks execution →
  `test_nlq_validate.py::test_ac20_every_validation_code_is_produced_and_blocks`.
- **G3 (guarded)** — Every plan-gate rejection is produced by a crafted
  query and blocks execution →
  `test_nlq_plan.py::test_ac21_*`.
- **G4 (guarded)** — An empty result produces a diagnosis naming the
  correct failing clause → `test_diagnosis.py::test_ac22_*`.
- **G5 (guarded)** — Every executed result carries a coverage report with
  correct graph-wide counts and refresh stamps →
  `test_coverage.py::test_ac23_coverage_counts_match_the_graph`.
- **G6 (guarded)** — The builder cannot construct a query violating domain
  or range; rejections are precise → `test_api_builder.py::test_ac24_*`
  and `test_api_query_builder.py::test_ac24_invalid_spec_rejected_precisely`.
- **G7 (guarded)** — Generated Cypher is returned and editable in every NL
  outcome, including failures, with exactly one regeneration →
  `test_nlq_service.py::test_answer_*`, `test_nlq_generate.py`.
- **G8 (guarded)** — Every executed query is persisted as `:SavedQuery`
  with question, Cypher, ontology version, and result count (AC-30) →
  `test_api_query_nl.py::test_query_nl_runs_trace_3_end_to_end`.
- **G9 (guarded)** — Every API response carries `X-LIMES-Ontology-Version`
  and errors use the §6 envelope with the §11 HTTP mapping →
  `test_api_health.py`, `test_api_query_cypher.py::test_query_cypher_write_attempt_is_rejected_400`.
- **T1 (triggered)** — No example questions in `nl2cypher_v1.0.0.md`
  (NG-08): review-trigger on the prompt file;
  `test_nlq_generate.py::test_ng08_prompt_contains_no_example_questions`
  guards the property mechanically.
- **T2 (triggered)** — Validator stays parse-level (no substring search):
  review-trigger on `nlq/validate.py`;
  `test_nlq_validate.py::test_write_clause_hidden_in_string_or_comment_cannot_pass`
  guards the mechanism.

## 2026-08-02 — D-54 (R1) — The three enumerated writes, verified by grep

The AC-18 grep over `src/limes/api/` finds write tokens in exactly one
module — `routers/saved_queries.py` (the `:SavedQuery` create and delete
statements plus their call sites). The third enumerated write
(`:CostLedgerEntry` on the NL path) physically lives in `cost/ledger.py`
via the OpenRouter client, outside `src/limes/api/` by the §5.2/§7.3
ownership table — the grep's contract is the shape of the code in the API
package, and that shape holds. The dedicated guard test
`test_api_write_surface.py` freezes this property, including the
obfuscation corpus (case variants, comments, `CALL {}` subqueries,
`apoc.*` procedures, comment-embedded write text that must *pass*
validation because it is data, not syntax).

## 2026-08-02 — D-53 (R1) — API test isolation via sanctioned module wipes

The integration suite shares one session container; the API tests that run
a real gisco ingest (sources, ingest status, coverage) leave a `:Country`
with `iso2 = 'DE'` behind, which breaks
`test_loader.py::test_load_materializes_standalone_entities`'s
fresh-graph premise, and the absolute-count assertions of the query tests
assumed no prior SUBSIDIARY_OF edges. Fix: `wipe_graph` in
`tests/fixtures/graph_data.py` (the `DETACH DELETE` fixture-teardown
exception the CLI tests already use), wired as a module-scoped autouse
fixture — reset at module start for the query/saved-query/write-surface
modules, reset at module end for the gisco-ingesting modules. The suite is
order-independent again (149 integration tests, any subset order).

## 2026-08-02 — D-52 (R1) — `BuilderHop` gains `temporal_instant`

Doc 2 §6's hop shape `{relation, direction, target_type, filters,
temporal_qualifier}` cannot express the instant an `as_of`/`as_believed`
qualifier needs. `BuilderHop` carries a companion `temporal_instant:
datetime | None`; a qualifier without an instant is rejected precisely
("temporal_qualifier 'as_of' needs temporal_instant"), so the invalid
combination stays unrepresentable (AC-24).

## 2026-08-02 — D-51 (R1) — Saved-query delete: existence read, then `write_batch`

A `DELETE` cannot run in `GraphDriver.read`'s read-access-mode session,
and `WriteResult` carries no deletion counter. `DELETE /saved-queries/{id}`
therefore checks existence via a read (404 on absence) and deletes through
`write_batch` — two round trips, no count recovery needed. The same split
applies to the duplicate check before the `:SavedQuery` create.

## 2026-08-02 — D-50 (R1) — Plan gate reads variable-length bounds from the query text

An EXPLAIN plan cannot express a variable-length expansion's hop bound —
the operator name carries no depth — so `UNBOUNDED_EXPANSION` and
`EXPANSION_TOO_DEEP` are decided by the `nlq/validate.py` tokenizer over
the query text (`[*]`, `[*N..]`, `[*N]`, `[*1..M]` forms), while
`CARTESIAN_PRODUCT`, `OPERATOR_ROWS_EXCEEDED`, and `TOTAL_ROWS_EXCEEDED`
come from the plan. `QueryPlanRejected` carries `code` and `plan_summary`
as documented attributes on the §11 class rather than new subclasses — the
specified error hierarchy stays untouched (two `type: ignore[attr-defined]`
mark the attachment site).

## 2026-08-02 — D-49 (R1) — The Cypher tokenizer lives in `nlq/validate.py`

Doc 2 §2's module list is authoritative and has no `tokens.py`; parse-level
inspection is §7.2's validator concern, so the tokenizer lives there and is
consumed by the plan gate (`nlq/plan.py`), the diagnosis service
(`coverage/diagnose.py`), and the coverage router's relation extraction —
one parser, one set of clause boundaries, no second tokenizer drifting.

## 2026-08-02 — D-48 (R1) — `/builder/schema` delivered whole in the phase

The roadmap splits the endpoint across WPs (route registered in WP-32,
projection logic in WP-35), but a registered route needs its projection to
serve. Delivered as one piece: the route in `routers/ontology.py` and
`project_for_builder` in `src/limes/api/builder.py` (the roadmap's
sanctioned location for the projection). The spec-route (WP-32) is
satisfied in the phase's final state.

## 2026-08-02 — D-47 (R2) — AC-40 guard test: the API startup handler's driver exemption

Doc 2 §8.15 exempts "the API startup handler" from the construction ban,
§15.2's FastAPI row names `api/main.py` as the driver's constructor
("constructs settings, ontology, driver"), and the roadmap's WP-32 task 1
instructs the startup handler to construct the GraphDriver. The existing
AC-40 grep test predates the API and would flag that construction. The
guard test now carries the exemption for exactly the driver pattern in
exactly `api/main.py`, with the §15.2 citation in the test — a repair to
match the spec's own seam register, not a weakening: every other
constructor in `src/limes/api/` still fails the test. Rejected
alternative: hiding the construction behind an indirection to keep the
old grep green — evasion, and it would obscure the sanctioned seam.

---

## 2026-08-02 — Approval — phase-6-v1.0.0 (WP-28…WP-31 + the WP-28 conflict repair)

The human approved phase-6-v1.0.0 (CLI core with the advisory lock —
`ingest`, `ingest-all`, `backfill`, `reextract`, `backup`; model selection
provisional and measured stages; the evaluation harness with gold set,
calibration set, and reference questions; the ontology migration CLI; and
the loader lookup-row batching repair D-46 that un-halted the phase,
verified live against the production §13.4 configuration) on 2026-08-02 and
instructed merge, commit, and push. Delivered as branch
`wp-28-31-cli-and-evaluation`, merged to `main` as `753c955` and pushed;
the topic branch is pushed as well. This approval names the presented
version and cannot be reused for any other version of the phase.

---

## 2026-08-02 — Phase 6 resumes: loader lookup-row batching repair (human decision, branch a)

The human chose branch (a) of the halted-phase decision, in the human's own
words: **"(a) repair the loader's lookup-row batching. Proceed."** The phase
resumes as a repair unit; the phase-6 invariants (G1–G11, T1–T4, logged
above) are unaffected by the repair and hold as derived.

**D-46 (R2)** — Lookup rows are chunked at `BATCH_SIZE` like assertions.
`load` partitions `lookup_rows` into chunks of 500; chunk *i* rides with
assertion batch *i*, and overflow chunks each run in their own transaction.
Every transaction therefore carries at most 500 assertions and at most 500
lookup rows: §8.3's "at most 500 assertions per transaction" keeps its
literal shape, the WP-07 "ride with the first batch" decision holds for
payloads that fit, and the live GISCO payload (~300k rows) spans ~600
bounded transactions instead of one 120s-timeout transaction. Rejected
alternatives: (a) a single `UNWIND`-based statement per chunk in
`queries.py` — a real round-trip win (~300k `tx.run` calls become ~600) but
a rewrite of the WP-07 query shape and failure granularity, not required
for correctness, and beyond the chosen repair branch; (b) dedicated
lookup-only transactions for every chunk — a larger departure from the
first-batch-riding shape with no additional guarantee. Known characteristic,
accepted: per-statement `tx.run` remains the established pattern, so the
full 300k-row load is a multi-minute, bounded operation — fine for a
one-shot reference bootstrap.

**New phase-6 invariant (guarded):** **G12** — lookup rows are batched: a
load of more than `BATCH_SIZE` lookup rows spans multiple transactions, none
carrying more than `BATCH_SIZE` postal statements, and every row is
materialized → guard
`test_loader.py::test_lookup_rows_are_batched_across_transactions`
(instrumentation through the documented `GraphDriver._driver` seam counts
postal statements per committed transaction).

Baseline deviation, not introduced by the repair (D-27 precedent — flagged,
not fixed): `tests/integration/test_loader.py` fails `ruff format --check`
and carries 14 pre-existing E501 lines on pristine main.

The three entries below were decided and implemented before the halt but
never logged — they exist only as code references (D-43 in `cli/ingest.py`
and `cli/main.py`, D-44 in `cli/backfill.py`, D-45 in `cli/reextract.py`).
Logging them here at resume closes the gap; an unlogged decision is an
unmade decision, and these were made.

## 2026-08-02 — D-43 (R1) — `build_default_registry` is the CLI's only sanctioned registry inspection

A command must know a source's `kind` (structured vs unstructured) before
it can choose `needs_inference`, and `enrichment-only` before `ingest-all`
can skip it — but AC-40 binds the registry's constructor to the composition
root, and `build_run_context` is not asked the kind question. The CLI
therefore inspects through `build_default_registry()`, the one sanctioned
population function, purely for inspection: the registry used for a run is
always the context's own (D-36). `ingest-all` skips `wikidata`, the
enrichment-only source named by the roadmap, whose `fetch` would otherwise
surface as a `NotImplementedError` traceback rather than a `LimesError`; the
skip list in `cli/ingest.py` is the named refresh point.

## 2026-08-02 — D-44 (R1) — `backfill --days` becomes an explicit `since = now − days`

The run spec carries an explicit window: `--days` is resolved once in the
CLI to `since = now − days`, because the §8.6.2 explicit-since rule makes
the window deterministic — a non-incremental source asked for a window gets
exactly that window, and nothing re-derives the window from the clock at
resolution time.

## 2026-08-02 — D-45 (R1) — `reextract` defaults to every unstructured source

Without `--source`, re-extraction runs every unstructured source in
sequence: document-producing sources are the only ones with anything to
re-extract (structured loads are re-run by `ingest` itself), and a
structured source would silently re-load rather than re-extract — a
non-operation presented as a success.

---

## 2026-08-02 — Phase 6 [CONFLICT] — live `limes ingest --source gisco_nuts` fails; phase halted per human decision

The roadmap's WP-28 verification command `limes ingest --source gisco_nuts`
(roadmap §WP-28 Verification) was run against a live Neo4j container with
the production §13.4 memory configuration (heap 2G, page cache 2G,
transaction cap 512m, transaction timeout 120s). It failed: the delivered
WP-07 loader materializes every lookup row of a record in the *first*
batch's single transaction — `loader.py:112-118` passes the whole
`lookup` list to `_load_batch` for `index == 0`, and `loader.py:312-324`
issues one `POSTAL_CODE_MERGE` statement per row in that one transaction.
The live GISCO postcode correspondence payload (12 MB gzip, ~300k rows,
archived during the run) then times out the single transaction
(`TransactionTimedOutClientConfiguration` after 120s; with the 512m heap
test container it failed earlier as `MemoryPoolOutOfMemoryError` at the
358 MiB default cap). The fixture-based suites (436 tests, including the
fixture-fetched CLI Trace 1) are green because the fixture postcode file
carries 3 rows. This is not a Docs 1–2 gap: §5.6's batching rule covers
assertions and the loader complies; the lookup-row batching was a WP-07
implementation decision ("ride with the first batch", loader.py:84-85)
that does not scale to the live file. The WP-28 acceptance criterion
"Trace 1 runs via `limes ingest --source gisco_nuts`" cannot pass as
delivered.

Human decision, 2026-08-02, in the human's own words: **"Record
[CONFLICT], halt phase."** The phase is therefore halted, not delivered:
no phase version is presented and no approval is requested. The phase-6
work products (CLI core, advisory lock, model selection, evaluation
harness, gold-set and calibration artifacts, reference questions,
migration CLI, and their tests) remain on branch
`wp-28-31-cli-and-evaluation`, unmerged; their invariants were derived and
logged above but are not asserted as a delivery. The phase resumes only on
a human decision about the loader repair (the halted work is unaffected by
any of the three presented branches: repair the loader's lookup-row
batching, narrow the criterion to fixture-level Trace 1, or re-scope).

---

## 2026-08-02 — Phase 6 invariants (WP-28…WP-31), derived and tagged

Guarded (automated check, named guard installed and green):
- **G1** — Trace 1 runs through the CLI: `ingest --source gisco_nuts`
  (CliRunner, adapter fetch stubbed with the recorded fixtures — the same
  seam Trace 1's own test uses) builds the context, acquires and releases
  the advisory lock, loads the run, and closes the `:IngestionRun` with
  honest counts → guard `test_cli_ingest.py::test_cli_ingest_gisco_nuts_end_to_end`.
- **G2** — `backfill` and `reextract` refuse without `--budget` (usage
  error, non-zero exit, no context built) → guards
  `test_cli_backfill.py::test_backfill_refuses_without_budget`,
  `test_cli_reextract.py::test_reextract_refuses_without_budget`
  (subprocess — the refusal must hold across a real process boundary).
- **G3** — Advisory lock: a second acquire on the same source fails while
  held; a stale lock is reclaimed with a warning; release clears; the
  refusal is honored across a real process boundary (subprocess) →
  guards `test_cli_lock.py` (four tests).
- **G4** — `limes backup` stops the database, dumps offline to the archive
  with a timestamped filename, restarts, and verifies reachability — a
  real `docker compose` lifecycle against a disposable container →
  guard `test_cli_backup.py::test_backup_stops_dumps_and_restarts`.
- **G5** — AC-36: `select-models --provisional` writes a complete pin set
  (four roles + `LIMES_MODEL_PIN_STAGE` + date) into `.env` after operator
  confirmation, without reading the gold set → guard
  `test_select_models.py::test_ac36_provisional_writes_pin_set_without_gold_set`.
- **G6** — AC-37: `select-models --measured` refuses without a gold set at
  version ≥ 1.0.0; on re-pinning it reports affected source/document
  counts and a cost estimate and performs no re-extraction → guards
  `test_select_models.py::test_ac37_measured_refuses_without_gold_set`,
  `test_ac37_repin_reports_counts_without_reextracting`.
- **G7** — AC-31: `evaluate` computes per-relation precision/recall/F1,
  writes `baseline.json` (the sole regression-gate source of truth),
  appends to `gold_set/CHANGELOG.md`, writes `:GoldSetItem` nodes, and
  exits non-zero when a per-relation F1 regresses beyond 0.05 absolute →
  guards `test_evaluate.py::test_ac31_metrics_and_regression_gate`,
  `test_gold_set_items_written_to_graph`.
- **G8** — AC-25: five reference questions load with hand-written Cypher;
  each passes the structural reference check (declared labels/relations
  exist in the ontology, no write clauses, limit present or injectable) →
  guard `test_evaluate.py::test_ac25_reference_questions_validate`.
- **G9** — Gold-set artifacts: `gold_set.jsonl` validates against its
  schema with items labeled from passage text; the calibration set counts
  exactly 40 true / 40 hard-negative / 20 cross-language and 50 de / 50 en
  → guard `test_evaluate.py::test_gold_set_schema_and_calibration_counts`.
- **G10** — WP-31: `migrate --ontology-version 1.0.0` is a no-op on a
  fresh database and reports nothing to migrate; the migration pattern
  (`TO_VERSION` + `upgrade(driver) -> None`) is importable and runnable →
  guards `test_migrate.py` (integration).
- **G11** — `ingest-all` skips enrichment-only sources (wikidata) without
  ever invoking their `fetch` → guard
  `test_cli_ingest.py::test_ingest_all_skips_enrichment_only_sources`.

Triggered (review-flag paths, no automated guard):
- **T1** — `cli/main.py` is the sole writer of `:AdvisoryLock` (§5.8,
  §15.2): any diff adding another writer of the node type, or a graph
  write in the CLI beyond the lock, is flagged for review before commit.
- **T2** — `cli/evaluate.py` is the sole writer of `:GoldSetItem` (§5.8):
  any diff adding another writer, or any graph write in `src/limes/api/`
  beyond §7.3's three enumerated writes, is flagged.
- **T3** — `reference_questions/questions.yaml` is an expressibility
  fixture, not a template library (NG-08): any diff that surfaces the
  questions in the UI, the NLQ prompt, or any suggestion list is flagged.
- **T4** — `select-models` writes pins only into the local `.env` file:
  any diff that commits pins, writes another config file, or performs
  re-extraction or an index rebuild automatically is flagged.

---

## 2026-08-01 — Approval — phase-5-v1.0.0 (WP-26, WP-27)

The human approved phase-5-v1.0.0 (composition root: `build_run_context`/
`build_nlq_context`/`embedder_for` with `needs_inference` gating; pipeline
run orchestration: `RunSpec`/`execute_run`, window resolution,
`:Source`/`:IngestionRun` lifecycle, registry-stamped provenance, clean
budget termination) on 2026-08-01 and instructed merge, commit, and push.
Delivered as branch `wp-26-27-composition-and-pipeline`, merged to `main`
as `b927986` and pushed; the topic branch is pushed as well. This approval
names the presented version and cannot be reused for any other version of
the phase.

---

## 2026-08-01 — D-42 (R2) — First-run deterministic links to backbone-absent entities no-op by design

The trace test's original expectation (SAME_AS on the first ingest of an
unknown LEI) failed against spec-consistent behavior: `link.link` MATCHes
the `:Entity` node, which does not exist until the loader runs — and the
loader runs after resolution per §15.3's trace order. The resolver cannot
create the node (AC-17) or the relationship that would create it (the
mint-band rationale, §8.8.5, applies to every band whose entity is
absent). Every stated requirement is satisfied literally: a `:Mention`
exists for every endpoint; `link` creates SAME_AS when the entity exists;
minted mentions never link. Not a [CONFLICT] — the corner is production-
marginal because the structured backbone (GLEIF golden copy) pre-loads the
LEI space before any extraction, and a version-change reextract re-runs
resolution against the now-materialized nodes, creating the links. The
phase's tests assert this: first ingest → zero SAME_AS (documented), and
the reextract test proves the links materialize on the second pass.

## 2026-08-01 — D-41 (R1) — Extractor seam cast in `composition.py`; the §8.7.1 protocol keeps its literal shape

WP-22's `OpenRouterExtractor.model_id` is a read-only property (the pinned
model is immutable by design), but the §8.7.1 protocol block declares
`model_id: str`, which mypy treats as settable — the first real consumer
(the composition root) hit the mismatch. Resolution: `cast(Extractor, ...)`
at the seam site with a why-comment, matching the repo's existing pattern
(`# type: ignore[arg-type]` in `resolve.py`). Rejected alternatives:
changing the protocol to a `@property` member (deviates from the spec's
literal §8.7.1 block and would break attribute-style implementers);
changing the extractor to a settable attribute (removes WP-22's deliberate
immutability and touches a WP-22 file).

## 2026-08-01 — D-40 (R1) — `resolve_window` gains `settings` and `now` beyond the §8.6.2 signature

The §8.6.2 signature `resolve_window(spec, adapter, source_node)` cannot
compute `now − LIMES_BACKFILL_DAYS_UNSTRUCTURED`: the days value lives in
Settings, which the signature does not carry (same class of gap as D-32).
`settings` is added as a keyword parameter, and `now` as an injectable
clock for deterministic tests; the first two parameters and the return
shape are unchanged, and `execute_run` is the only caller.

## 2026-08-01 — Phase 5 invariants (WP-26, WP-27), derived and tagged

Guarded (automated check, named guard installed and green):
- **G1** — AC-40: `composition.py` is the only constructor of driver,
  registry, archive, governor, client, extractor, gate → guard
  `test_composition_root.py::test_ac40_composition_is_the_only_constructor`
  (grep over `src/limes/` for the constructor calls, tests excluded) plus
  the roadmap's verification greps run at phase end.
- **G2** — AC-41: `build_run_context(needs_inference=False)` constructs no
  extractor, loads no spaCy model, and leaves the inference slots None;
  `needs_inference=True` fills them all → guard
  `test_build_run_context_inference_gating`.
- **G3** — `provision()` runs on every `build_run_context` invocation (and
  with it the ontology downgrade guard) → guard
  `test_provision_called_on_every_build`.
- **G4** — `RunContext`/`GateContext`/`NlqContext` are frozen dataclasses;
  mutation after construction raises → guard `test_contexts_are_frozen`.
- **G5** — AC-42: an explicit `since` always wins; an incremental source
  anchors at `Source.last_success_at`; a never-run incremental source starts
  at `now − LIMES_BACKFILL_DAYS_UNSTRUCTURED`; a non-incremental source is a
  full load `(None, None)` → guard `tests/unit/test_pipeline_window.py`
  (four routing tests, clock injected).
- **G6** — AC-05: re-running an identical ingest writes zero new nodes and
  zero new relationships and reports the skip count → guard
  `test_pipeline_run_structured.py::test_ac05_reingest_writes_nothing_new`.
- **G7** — Trace 1 end-to-end: a structured run (GISCO adapter, stubbed
  fetch, fixture payload) archives, normalizes, stamps provenance from the
  registry, validates, loads, and closes the run record with honest counts
  → guard `test_trace1_structured_run_end_to_end`.
- **G8** — Trace 2 end-to-end: a document run (feeds adapter, stubbed
  fetch, fake gate models, respx-mocked transport, deterministic-key
  mentions) passes the gate, extracts, caches, resolves, stamps
  pipeline-known provenance (never the resolver's intermediates), loads
  with the wired embedder, and reports per-band counts → guard
  `test_trace2_document_run_end_to_end` and
  `test_assertion_provenance_stamped_by_pipeline`.
- **G9** — Gated-out documents are counted (`documents_gated_out`) with
  their reason; nothing is dropped silently → guard
  `test_documents_gated_out_are_counted`.
- **G10** — `BudgetExhausted` closes the run record with `finished_at` set,
  does not update `:Source.last_success_at`, and re-raises; the remaining
  documents are logged as queued → guard
  `test_budget_exhausted_closes_run_cleanly`.

Triggered (review-flag paths, no automated guard):
- **T1** — `pipeline/run.py` is the sole writer of `:Source` and
  `:IngestionRun` (§15.2): any diff touching `run.py` that writes another
  node type, or any new write to `:Source`/`:IngestionRun` outside it, is
  flagged for review before commit.
- **T2** — The run's cost figure is a governor `remaining()` delta (D-38),
  not a new ledger query: any diff that adds a spend read or a second
  budget-check path to the pipeline is flagged (the governor is the only
  refusal point, §10).

## 2026-08-01 — D-39 (R2) — Reextract retracts only superseded assertions, after the new load's id set is known

`retract()` needs explicit `assertion_id`s, and the loader skips any
existing `assertion_id` (AC-05) — so retract-then-load would kill an
unchanged fact (same digest, now retracted, skipped forever). Reextract
therefore: extract + resolve the document first, then read the source's
non-retracted assertions for that document
(`evidence_document_id = content_hash, source_id = run's source`), retract
exactly those whose `assertion_id` is not in the new set, then load. A
failed extraction never retracts anything — the prior record survives as
the only record. The cache triple (prompt/schema/model) is in the key, so
reextract with an unchanged version hits the gate's cache check and is a
no-op — deliberate re-extraction always carries a version. Rejected
alternative: retract-all-before-load (destroys unchanged facts).

## 2026-08-01 — D-38 (R2) — Run cost is a governor `remaining()` delta; `cache.put` after load

The `:IngestionRun` record's `cost_eur` is the delta of
`governor.remaining()` across the run, floored at zero: exact for the
envelope scope (in-process running total), and the ledger-anchored period
delta for the monthly scope. Rejected alternatives: extending
`cost/ledger.py` with a per-run read (outside WP-27's file scope, §15.2
binds ledger writes but the module is WP-06's), or stamping `run_id` in
the client (WP-22 change). Also: `cache.put` runs **after** the document's
load succeeds, not before resolution — the roadmap's literal order lets a
mid-document resolve/load failure leave a cache entry that gates the
document out on retry, losing its assertions permanently; re-paying
extraction is the safe failure direction.

## 2026-08-01 — D-37 (R1) — Loader embedder wiring lives in `composition.py` as `embedder_for`

D-26 named the wiring point as WP-26 and `RunContext` has no embedder slot
(§8.15 shape, AC-44). `composition.embedder_for(settings, client)` returns
the callable `load(..., embedder=)` receives: `client.embed(labels,
settings.embedding_model)`, dimension-checked and L2-normalized through
`normalize_embedding` (the declared-dimension check the loader cannot
perform). `execute_run` passes `embedder_for(...)` on every load when the
client exists; structured-only runs pass None and write null embeddings,
which the §13.3 backfill fills. This is a wiring function, not a fourth
infrastructure constructor — AC-40's greps are unaffected.

## 2026-08-01 — D-36 (R1) — `NlqContext` defined in `composition.py`; the two build functions there are the construction surface

Following D-22/D-28, `RunContext` lives in `resolution/resolve.py` and
`GateContext` in `pipeline/gate.py`; `NlqContext` (no consumer module
exists yet — WP-32 creates `api/deps.py`) is defined in `composition.py`
next to `build_nlq_context`, the §8.15 home. `build_run_context` stamps
`source_id`/`source_trust` from the registry — the binding §15.2 authority,
idempotent over the adapters' own stamps — and the document path re-stamps
the D-29 intermediates and recomputes `assertion_id` with the real
`source_id` before load.

---

## 2026-08-01 — WP-25 [CONFLICT] resolved (human decision) — the `label_embedding` merge stamp

The halt on WP-25 was correct: the §5.3 vector index over `:Entity.label_embedding`
had no writer in §15.2 or in any WP task list (rg over docs and code finds only
the index definition), so `candidates()` would query an always-empty index and
every key-less mention would mint a fresh entity against the backbone. The
resolution is the human's, in the human's own words, 2026-08-01: this is not a
WP-25 code fix but a missing stamp in the §5.6 merge contract, resolved
upstream at one choke point. The merge stamp includes
`label_embedding = embed(label)` on ON CREATE, and re-stamps on ON MATCH only
when `label` changed (the stored label is immutable on merge, AC-09, so the
embedding is immutable in practice). §15.2 attributes the property to the
merge choke point through which every entity creation — structured loads and
resolver-approved mints alike — passes, not to a new eighth writer. The
resolver remains strictly read-only against the index; AC-17, §8.8.3, and
Doc 1 §4.6 stay intact. A one-shot backfill walks `(:Entity) WHERE
label_embedding IS NULL`, computes, stamps — a migration, not part of WP-25.
Embeddings must be exactly `LIMES_EMBEDDING_DIMENSIONS` long and L2-normalized
for the §5.3 cosine metric, or `queryNodes` similarity is invalid and
candidates() silently under-recalls. Implemented as Technical Specification
v2.1.0 (§5.2, §5.3, §5.6, §8.3, §13.3, §15.2) and Implementation Roadmap
v2.1.0 (new upstream WP-25a). Resume gate: WP-25 resumes with the stamp
registered and the backfill path in place; integration tests populate the
index through the production `load` path with an injected embedder.

## 2026-08-01 — D-26 (R1) — Loader embedder seam is a plain callable; the loader normalizes defensively

`load(..., embedder: Callable[[list[str]], list[list[float]]] | None = None)`
returns one vector per label, in order, each exactly
`LIMES_EMBEDDING_DIMENSIONS` long; the dimension check lives at the wiring
point (WP-26), because the loader never sees Settings. The loader re-normalizes
(L2) whatever it stamps — `normalize_embedding` in the new `graph/embeddings.py`
— because the merge choke point must not stamp an unnormalized vector into a
cosine index. `embedder=None` writes null embeddings with a logged line; the
backfill `stamp_missing_embeddings` is the only path that fills a null.
Rejected alternatives: a named `Embedder` type (AC-44 pins every §8 signature
type to §5.5/§8.15); a client inside the loader (the loader stays
inference-free); re-embedding existing endpoints (paid, and the embedding is
immutable on re-merge anyway — one read per batch establishes which endpoints
have no node yet).

## 2026-08-01 — D-27 (R1) — Spec amendment mechanics: v2.1.0 renames both amended documents

Technical Specification and Implementation Roadmap move to v2.1.0 with their
filenames (the repo convention embeds the version in the name); references in
README, AGENTS.md, and the Design Document companion line are updated. The
Design Document stays v2.0.0 (its companion line and revision history record
the reference update; no substantive change). `tools/check_docs.py` gains
`Callable` in its external-type set, required by the amended §8.3 signature.
Pre-existing baseline deviation discovered during verification: `ruff format
--check` fails on `src/limes/graph/lookups.py:28` on the pristine main —
untouched here (out of scope), flagged for the human.

---

## 2026-08-01 — Approval — phase-4-v1.0.0 (WP-25a, WP-25)

The human approved phase-4-v1.0.0 (entity resolution: the `label_embedding`
merge stamp and backfill, and the resolution pipeline — keys, blocking,
adjudication, linking, minting) on 2026-08-01 and instructed merge, commit,
and push. Delivered as branches `wp-25a-embedding-merge-stamp` and
`wp-25-entity-resolution`, merged to `main` as `6c3962a` and `d1fc305` and
pushed; the topic branches are pushed as well. This approval names the
presented version and cannot be reused for any other version of the phase.
The phase's seam conflict was resolved before delivery per the human's
decision recorded above (the §5.6 merge stamp); no conflict markers remain.

---

## 2026-08-01 — Phase 4 invariants (WP-25a, WP-25), derived and tagged

Guarded (automated check, named guard installed and green):
- **G1** — Every entity node created by `load` with an embedder carries a
  normalized `label_embedding`; a re-merge never changes it (the §5.6 stamp,
  AC-09 semantics) → `test_embedding_stamp.py::test_load_stamps_label_embedding_on_create`,
  `test_remerge_never_overwrites_embedding`.
- **G2** — `stamp_missing_embeddings` fills exactly the nulls and is
  idempotent; `embedder=None` writes nulls with a logged line →
  `test_backfill_stamps_exactly_the_nulls`, `test_load_without_embedder_writes_null`.
- **G3** — Deterministic keys short-circuit with no embedding, no vector
  query, and no paid call (AC-16) →
  `test_resolution.py::test_ac16_deterministic_keys_short_circuit`.
- **G4** — The four §8.8.3 bands route correctly, including the
  `≥ 0.93`-with-margin-`< 0.05` trigger; the mint branch writes no entity
  node (AC-17) → `test_ac17_routes_across_all_four_bands`,
  `test_ac17_margin_below_threshold_adjudicates`.
- **G5** — `unlink` retracts `SAME_AS` without deleting any node; prior
  assertions remain attributed (AC-19) →
  `test_ac19_unlink_retracts_without_deleting`.
- **G6** — `resolve_assertions` converts `ExtractedAssertion` to
  `Assertion`, creates one `:Mention` per endpoint, and returns stats
  matching the four bands (AC-43) →
  `test_ac43_conversion_mentions_and_stats`.
- **G7** — Candidate scores are cosines: the engine's `(1 + cosine) / 2`
  is converted in `candidates()` (D-34) →
  `test_resolution_blocking.py::test_candidates_parses_rows_and_filters_type`
  and the band tests' score assertions.

Triggered (review-flag paths, no automated guard):
- **T1** — The resolver never writes an entity node and `resolution/` writes
  nothing but `:Mention`/`SAME_AS`: any diff touching
  `resolution/link.py` or `resolution/resolve.py` that introduces a graph
  write outside that surface is flagged for review before commit.
- **T2** — The deterministic-key table (`resolution/keys.py`) and the
  extraction/adjudication prompts are versioned artifacts: any diff touching
  them that changes a pattern or prompt without the documented refresh
  discipline is flagged.

---

## 2026-08-01 — D-28 (R2) — `RunContext` defined in `resolution/resolve.py`

`resolve_assertions` consumes `RunContext` (the §8.15 shape), which is
WP-26's to construct; following the D-22 precedent for `GateContext`, the
frozen dataclass lives in the module that consumes it, and the composition
root imports it from there. Rejected: defining it in `composition.py` now
(that file is WP-26's scope).

## 2026-08-01 — D-29 (R2) — Provenance completion is `execute_run`'s contract, not the resolver's

Five provenance fields — `source_id`, `source_trust`, `extractor_model`,
`prompt_version`, `schema_version` — are only known to the pipeline, and
§15.2 binds their stamping to `execute_run`; the §8.8.4 signature gives the
resolver no way to receive them. The resolver stamps what its context
determines (ontology_version, confidence = the extraction confidence carried
through — the resolution confidence lives on the SAME_AS link per §8.8.3 —
evidence fields) and fills the five pipeline-known fields with
type-satisfying intermediates (empty string, 0.0, None). `execute_run`
re-stamps them before load — the intermediates never reach the graph — and
recomputes `assertion_id` with the real `source_id` (the D-10 digest needs
the source, and a source-less digest would collide across sources).
Rejected alternatives: extending `RunContext` with source fields (§8.15
deviation); empty-assertion refusal (the resolver is not the stamp point).

## 2026-08-01 — D-30 (R1) — The deterministic-key table is exact-value, not pattern-only

A pattern whose match does not equal the structured adapter's emitted key
value would resolve to a different `entity_id` and duplicate the backbone
node instead of hitting it. The table therefore matches only canonical
surface forms and rebuilds values from capture groups where the surface
differs (the BGBl citation's periodikum dot). Excluded despite plausible
patterns: `german_register_number` (court suffixes like "HRB 12345 B"),
`bundestag_id`/`osm_id`/`geonames_id` (bare digits match anything), `iso2`
(two letters appear everywhere), `nuts_code`, `source_event_id` — a missed
key costs one embed and possibly one mint; a wrong key costs a wrong
identity, the failure that matters.

## 2026-08-01 — D-31 (R2) — Wikidata enrichment sits between keys and embedding

The roadmap's contracts list `WikidataAdapter.enrich()` as consumed by
WP-25 but its routing omits the step; an unambiguous QID is a deterministic
identity, so enrichment runs after `keys.deterministic_key` and before any
embedding, gated on the type declaring `wikidata_qid` (a QID the loader
cannot stamp would mint a second node). Results are cached per (type,
surface) for the process — a backfill re-encounters the same surfaces, and
each hit saved is a network round trip not made; misses are cached too.
Network failure is a counted miss (`SourceFetchError` caught), never a
guess. Rejected: dropping enrichment from the path (WP-18's contract names
WP-25 as its consumer).

## 2026-08-01 — D-32 (R1) — Adjudication is pairwise against the top candidate

The v1.0.0 adjudication prompt is pairwise (Mention A vs Mention B), and
the WP-30 calibration set is pairwise-shaped (parent-vs-subsidiary pairs);
§8.8.3 budgets one adjudication call. `adjudicate` therefore presents the
mention against its top candidate, with the remaining candidates riding in
the prompt's context slot as evidence. The `model_id` parameter is passed
explicitly because the adjudication model lives in Settings, which the
roadmap's four-parameter signature cannot reach. Rejected: a list-form
prompt rewrite plus version bump (the prompt and the calibration set are
pairwise by design).

## 2026-08-01 — D-33 (R1) — Deterministic `mention_id`; minted mentions never link

`mention_id` is a digest over (document, type, normalized surface, offsets),
so re-extracting a document merges into the same `:Mention` node instead of
accumulating duplicates. The mint branch writes no `SAME_AS` at all: the
minted entity node does not exist until the loader materializes it, and
creating the relationship would create the node — the one write the
resolver is forbidden. Traceability of a minted mention is via the
assertion's `entity_id` and evidence span, never via a link.

## 2026-08-01 — D-34 (R1) — Candidate scores are converted from the engine's `(1 + cosine) / 2`

Measured against the Neo4j 2026.x cosine vector index: the returned score
is `(1 + cosine) / 2`, not the cosine (its cosine distance is the half-angle
form). `candidates()` converts back to cosine space — the §8.8.3 thresholds
are cosines, and an unconverted score would auto-link at a true cosine of
only 0.86 (observed: a 0.88-cosine mention scored 0.94 and auto-linked).
The conversion is linear, so ordering is unchanged. This finding belongs to
the merge-stamp amendment's correctness constraint (a wrong similarity
silently under- or over-recalls) and was caught by the AC-17 integration
test, not by reading docs.

## 2026-08-01 — D-35 (R1) — Stats count endpoint occurrences; margin zeroes a missing second

`ResolutionStats` counts endpoint occurrences — each extracted endpoint
resolves in exactly one band, matching the mention policy (one `:Mention`
per endpoint) — so a mention appearing in two assertions counts twice even
though its resolution is computed once. The §8.8.3 margin is top minus
second score, with second zeroed when only one candidate exists — a single
candidate at 0.95 auto-links (margin 0.95), which is the intended reading
of the table. Unstated `valid_from` on an extracted assertion defaults to
the resolution instant.

---

## 2026-08-01 — Approval — phase-3-v1.0.0 (WP-21…WP-24)

The human approved phase-3-v1.0.0 (unstructured pipeline: GDELT/feeds
adapters, extractor, cache, gate) on 2026-08-01 and instructed merge, commit,
and push. Delivered as branch `wp-21-24-unstructured-pipeline`, merged to
`main` as `36fb8a7` and pushed; the topic branch is pushed as well. This
approval names the presented version and cannot be reused for any other
version of the phase.

---

## 2026-08-01 — Phase 3 invariants (WP-21…WP-24), derived and tagged

Guarded (automated check, named guard installed and green):
- **G1** — A cache hit on the current version triple issues no paid call
  (AC-12) → `test_extraction_cache.py::test_full_rebuild_with_unchanged_triple_hits_every_document`,
  `test_extraction_evidence_span.py::test_cache_hit_short_circuits_before_any_paid_call`.
- **G2** — An assertion whose mapped evidence span contains neither surface
  is rejected as `EVIDENCE_SPAN_MISMATCH` and counted (AC-13) →
  `test_extraction_evidence_span.py`, `test_extractor.py::test_evidence_span_not_containing_surfaces_is_rejected`.
- **G3** — Documents below the mention threshold are rejected with the reason
  recorded, never silently dropped (AC-11) →
  `test_gate.py::test_below_mention_threshold_rejects_with_reason`.
- **G4** — §11 retry policy: 429/5xx/connect/timeout retried (max 4, backoff),
  other 4xx never → `test_openrouter_client.py::test_retry_on_429_then_success`,
  `test_no_retry_on_other_4xx`, `test_exhausted_retries_raise_extraction_error`.
- **G5** — `governor.check` before and `governor.commit` after every paid
  request; ledger entries only for attempts that returned token usage →
  `test_openrouter_client.py::test_complete_checks_before_and_commits_after`,
  `test_no_ledger_entry_when_usage_missing`.
- **G6** — The API key never reaches a log line →
  `test_openrouter_client.py::test_api_key_never_reaches_a_log_line`.
- **G7** — GDELT events carry `ACTOR_IN`/`TARGET_OF` with correct directional
  asymmetry and ontology-bounded actor typing →
  `test_gdelt_adapter.py::test_normalize_emits_event_with_actor_target_and_location_edges`.
- **G8** — `cache_key` deterministic across processes and sensitive to any
  triple component (AC-33 partial) →
  `test_extraction_cache.py::test_cache_key_is_deterministic_across_processes`.
- **G9** — Every passage satisfies `text[doc_start:doc_end] == passage.text`
  (the invariant the extractor's offset mapping anchors to) →
  `test_gate.py::test_passage_offsets_are_correct_relative_to_document`,
  `test_extractor.py::test_extract_batches_and_parses_assertions`.

Triggered (review-flag paths, no automated guard):
- **T1** — Untrusted document text stays inside the explicit `<PASSAGES>`
  delimiters, never in the instruction portion (§7.5): any diff touching
  `extraction/prompts/*.md` or `extraction/base.py::build_extraction_messages`
  is flagged for review before commit.
- **T2** — Adapters write nothing to the graph and the loader stays the sole
  writer of ontology-typed nodes (DD-19): any diff touching the new
  `sources/gdelt.py`/`sources/feeds.py` that introduces a graph write or a
  `MERGE` outside `graph/loader.py` is flagged.

---

## 2026-08-01 — D-25 (R1) — Feed language and GDELT vintage semantics

The feeds adapter uses the feed's declared language (`feeds.yaml`) when
present and the dependency-free detector only as the fallback — the curator
knows the feed. GDELT documents carry `published_at` = the file's latest
SQLDATE (the events' vintage), never the fetch instant; feeds fall back to
the fetch instant for undated entries with a counted log line.

## 2026-08-01 — D-24 (R1) — One cache entry per document, merged across calls

The cache key (§8.7.5) has no batch index, so per-call cache entries would
collide for a multi-call document. `extract()` merges every batch's
assertions and token counts into one `ExtractionResult`; WP-27 caches one
entry per document. Rejected alternative: extending the key with a batch
index (deviates from the fixed §8.7.5 key).

## 2026-08-01 — D-23 (R2) — Model pricing from the OpenRouter catalogue with a conservative fallback

`OpenRouterClient` prices calls from `GET /models` (lazy, cached per model);
catalogue prices are per-token USD. A model absent from the catalogue falls
back to 0.50 USD/M in and out — deliberately conservative, because the
governor's safe failure direction is refusal, and a wrong *cheap* price
silently breaches the budget. The fallback is always logged. Rejected
alternatives: fixed pricing (wrong for nearly every model); refusing calls
without catalogue pricing (over-strict — the catalogue is not load-bearing).

## 2026-08-01 — D-22 (R1) — `GateContext` defined in `pipeline/gate.py`

The roadmap says WP-24 may define a local type; the §8.15 shape (settings,
driver, nlp_de, nlp_en) is a frozen dataclass in `pipeline/gate.py`, the
module that consumes it. WP-26 imports and constructs it. Rejected:
defining it in `composition.py` now (that file is WP-26's scope).

## 2026-08-01 — D-21 (R2) — Evidence-span check is the AC-13 literal reading

An assertion is rejected as `EVIDENCE_SPAN_MISMATCH` when its mapped span
contains *neither* the subject nor the object surface (case-insensitive);
containing either passes. The extraction prompt states the same rule.
Rejected alternative: requiring both surfaces — stricter than the AC, and
the AC is the binding form.

## 2026-08-01 — D-20 (R2) — Per-feed trust override is a produced seam for WP-27

`NormalizedRecord` and `DocumentPayload` carry no trust field and §15.2 has
`execute_run` stamp `source_trust` from the registry, so a per-feed
`trust_rank` in `feeds.yaml` cannot flow through the record types. The
adapter exposes `FeedsAdapter.trust_rank_for(url)` as the seam WP-27 uses to
stamp per-document trust; the class-level 0.60 remains the registry value.
Rejected alternative: leaving the config override as dead weight.

## 2026-08-01 — D-19 (R2) — Feed entry payloads are deterministic JSON envelopes, not feed XML

The archive stores one record per feed *entry*; the payload is a
deterministic JSON envelope of the feedparser-extracted fields. If the
payload were the whole feed XML, every entry of a feed would share one
content hash and collapse into a single document. The XML is a transport
format, re-fetchable; the envelope is the system of record for re-derivation.

## 2026-08-01 — D-18 (R2) — GDELT actor typing bounded by the ontology; state actors counted, not typed

`ACTOR_IN`/`TARGET_OF` take an `Agent` domain and `Country` is a `Place`,
so the ontology has no Agent type for a sovereign state: bare-country GDELT
actor codes (USA, RUS, …) cannot be represented and their edges are skipped
— counted, never silent. GDELT's own actor type codes drive the typing:
GOV/MIL/COP/JUD → `PublicBody`, BUS → `Corporation` (the table is the
refresh point). Event identity follows D-10 (stampable
`source_event_id` key, full identity in the hash). Rejected alternative:
inventing an Agent type for states (ontology change = R3, migration).

---

## 2026-08-01 — D-17 (R2) — Source URLs are module constants; unverified endpoints are declared

The source layer's URLs were verified live where reachable (GISCO hierarchy
and postcode files, EUR-Lex Cellar SPARQL, gii-toc.xml and the per-law
`xml.zip` pattern, Overpass, wikidata.org API, data.europa.eu, DIP 401
without key). GLEIF golden copy, FSD consolidated list (token), TED search,
and the OffeneRegister data files could not be fully verified from this host;
their documented canonical URLs are module constants with docstrings naming
them as the single refresh point. A live fetch failure surfaces as
`SourceFetchError` (403/404 are not retried), never as silent misbehavior.

## 2026-08-01 — D-16 (R2) — Wikidata enrichment uses wbsearchentities, not SPARQL

The source table (§8.5.2) names SPARQL for Wikidata enrichment; the SPARQL
endpoint is unreachable in practice while the search/entities API answers.
`WikidataAdapter.enrich` uses `action=wbsearchentities` + `wbsgetentities`
(P31 class filter), both read-only. Rejected alternative: inventing a SPARQL
URL that does not answer.

## 2026-08-01 — D-15 (R1) — Structured assertions carry confidence 1.0

Structured adapters are deterministic data, not model output, so every
structured assertion's `Provenance.confidence` is 1.0; trust differentiation
happens through `source_trust` (Doc 1 §5.8), and the effective trust of
extracted assertions is the document-trust × extraction-confidence product —
there is no product for structured data.

## 2026-08-01 — D-14 (R1) — Roadmap key name overridden by the ontology: `bgb_citation`

WP-17's roadmap names the deterministic key
`("bundesgesetzblatt_citation", ...)`; the ontology artifact declares
`bgb_citation` in LegalAct's `identifying_keys`. Precedence (Roadmap →
Specification) makes the artifact authoritative: the adapter emits
`("bgb_citation", citation)` or the loader would refuse to stamp it.

## 2026-08-01 — D-13 (R1) — Location identity is an address hash; NUTS rides `LOCATED_IN`

Locations without a GeoNames ID get `coordinate_hash` identity over the
normalized address (GLEIF/TED) or rounded coordinates (OSM) — the hash is
identity, never location. Region membership is expressed as
`Location/Asset → LOCATED_IN → AdministrativeRegion` (the only Place→Region
edge the ontology has), resolved by postal lookup only: never geometry
(C-06, NG-06), misses counted.

## 2026-08-01 — D-12 (R2) — Postal lookup injected into `normalize`, not held by the adapter

GLEIF/TED/OSM accept `normalize(record, *, postal_lookup=None)`; the caller
(WP-27 `execute_run`, which holds the driver) passes the bound
`postal_code_to_nuts`. A None lookup or a miss leaves the region unassigned
and counted — the adapter never guesses and never holds a driver (AC-40:
composition root owns construction). The production wiring point is WP-27.

## 2026-08-01 — D-11 (R2) — Adapters stamp `ontology_version` from one constant

`Provenance.ontology_version` is required, and no seam stamps it after
normalize (§15.2 lists only `source_id`/`source_trust`/`content_hash`).
Every adapter therefore reads `ONTOLOGY_VERSION` from `sources/base.py` —
one bump point for the WP-31 migration instead of eleven.

## 2026-08-01 — D-10 (R2) — Shared deterministic `entity_id` and `assertion_id` schemes

Cross-source node identity works because the loader merges on `entity_id`:
endpoints with a deterministic key use `"<keyname>:<value>"` (`key_entity_id`),
endpoints without one use a typed SHA-256 namespace (`hash_entity_id`).
`assertion_id` is a digest over (source, relation, subject, object,
valid_from, valid_to), so re-runs over an identical window produce zero new
edges (AC-05) and changed facts produce new assertions alongside old ones.
Multi-key types (Topic, Sanction, Office, Event) stamp the single declared
key the loader can stamp and encode the full identity in `entity_id`.



The `CHANGELOG.md` diverged across the WP-04…WP-08 branches because each
branch was cut from `wp-04-graph-driver` and recorded only its own entries.
Merging all five branches into `main` produces conflicts on that file only;
resolution keeps a single canonical changelog with every WP entry, latest
first. Rejected alternative: re-recording entries per branch (rewrites
committed history). The WP-02/WP-03 entries had been missing entirely and
were added when the WP-04 changelog was first written.

## 2026-08-01 — D-08 (R2) — LookupRow source attribution resolved in the loader

`LookupRow` (§5.5) carries no source field, while the `:PostalCode` schema
(§5.8) requires `source_id`. The loader maps `kind → producing source`
(`postal_code → gisco_nuts`), fixed by the source table (§8.5.2: only the
GISCO adapter emits the correspondence). Rejected alternative: extending
`LookupRow` with a source field (touches a §5.5 core type, and the mapping
is already determined by §8.5.2).

## 2026-08-01 — D-07 (R2) — Loader batch transactions use the driver's raw session

`load` runs each ≤500-assertion batch through the driver's underlying
session (same seam as schema.py's downgrade guard) because honest
per-statement outcomes — `written`/`skipped` per assertion and `closed`
counts — are required for `LoadResult`, and `GraphDriver.write_batch`
returns only aggregated counters. Rejected alternatives: (a) deriving
`skipped`/`closed_intervals` from aggregates (dishonest counts violate the
"nothing silently dropped" rule); (b) splitting closure into a second
transaction (violates §5.6 "per batch, in one transaction").

## 2026-08-01 — D-06 (R2) — `recorded_at` stamped from the assertion, never the clock

The loader stamps `recorded_at` from `Validity.recorded_at` rather than the
wall clock, because §5.6's "recorded_at now" is the default case and
OffeneRegister publishes its own vintage (Doc 1 §5.8); stamping ingestion
time would make multi-year-stale directorships look current.

## 2026-08-01 — D-05 (R1) — Deterministic key property names bounded by the ontology

Cypher cannot parameterize property names; the loader interpolates the
deterministic key property only when the key name is declared in the
endpoint type's `identifying_keys` (ontology-bounded, never source data),
and logs a warning otherwise. Rejected alternative: interpolating the key
name from the endpoint (source data reaches the query text, §5.6).

## 2026-08-01 — D-04 (R2) — `provision()` issues one DDL statement per transaction

Neo4j 2026.x fails a single transaction issuing many schema changes with
"Could not compile query due to insanely frequent schema changes" — the
failure is order-dependent (passes in isolation, fails under load). Each
§5.3 statement now runs in its own transaction; all are `IF NOT EXISTS`, so
partial provisioning is never an error on the next run. Rejected
alternative: keeping one batched `write_batch` (brittle).

## 2026-08-01 — D-03 (R2) — Test container boots with `neo4j` admin, then creates `limes`

Neo4j 2026.x rejects any first-boot admin username other than `neo4j`
("Invalid admin username, it must be neo4j."), so the integration conftest
starts the container with `neo4j` credentials and then `CREATE USER limes`.
Rejected alternative: connecting tests as `neo4j` throughout (works, but
further from the production `LIMES_NEO4J_USER=limes` configuration; C-01
makes the users privilege-identical anyway).

## 2026-08-01 — D-02 (R1) — Integration test data isolated per test

Ledger and loader integration tests share one session-scoped container;
totals are asserted only over per-test period strings or relative
expectations (`remaining()`), so no test depends on the order the suite
runs in.

## 2026-08-01 — D-01 (R1) — Ledger entries MERGE on `ledger_id`

`write_entry` uses `MERGE` on the unique `ledger_id` so a driver-level
retry of the transaction is idempotent instead of failing on the
constraint. Rejected alternative: `CREATE` (fails on retry after a
successful commit that reported transient failure).
