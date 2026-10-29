# Verification and acceptance evidence

## 2026-10-29 — PR #13 hosted tool-lint correction

Hosted OFFLINE rejected the initial BE-46 commit because the README template in
`tools/generate_runtime_docs.py:89` exceeded Ruff's 100-character limit. The
candidate aggregate correctly failed closed. Local qualification had checked
runtime/tests and qualify.py but omitted the separate CI tools-lint command;
its earlier passing report did not establish that hosted lane's tool coverage.

Wrap the generator line and regenerate README. Add the complete hosted tool list
to a separate local tools-lint check, with a regression comparing that list to the
actual OFFLINE workflow command. CI requirements and the aggregate stay intact.
The qualified runtime, ontology, adapters and integration fixtures are unchanged;
only the generator, qualification tool and one new unit case differ in the source
manifest. Generated README wraps the same text.

Validation: both exact CI Ruff commands pass; qualification/runtime-doc focused
suites pass (15 cases); docs C1–C9, generated-document drift and whitespace pass.
The original 1,256-test full run remains evidence for its recorded parent source,
not a fresh full run of this tool correction. Updated source manifest is retained
in work/be46/lint-fix/source.json, SHA-256
`9f5783b4e36c1cefc9ad3d2fc6cdfbe3f3435d9520b6fa4807072cca8e766287`.
Hosted checks will rerun for the pushed correction; no skipped guard or weakened
required status is used to accept it.

## 2026-10-29 — BE-46 enrichment candidate verification

Complete selected parent: Wikipedia context plus Yahoo Finance enrichment and
supporting identity/ontology/property/loader/API/desktop compatibility. Branch
`codex/be-46-entity-enrichment`; live-fetched baseline
`b892875123350f26a87efd095fab32c947d419d0` (BE-45 merged in PR #12).
The supplied clean checkout was fast-forwarded before implementation and the
baseline checker passed; the repository-local publication hook is installed.
No staging, commit, push, publication, production ingestion or paid model run is
requested. The canonical frozen all-package environment was synchronized.

Full candidate command: `venv/bin/python tools/qualify.py --output work/be46/final-5`.
Source manifest SHA-256:
`b897154b606767fc6562361f1cc087325e36e42f82e9cdbc16f26c2ef169f8c4`.
The runner retains exact source mappings, commands, elapsed durations, logs and
JUnit under ignored `work/be46/final-5/`. The fail-closed report passes in
588.520s and confirms no source drift. All five suites pass with no failures,
errors or skips (1,256 cumulative passes, not a test quota). Its source set includes runtime, tests,
fixtures, ontology, dependency files, tools, CI, Docker and runtime JSON; handoff
documentation updates do not change that source fingerprint.

Publication update: after local acceptance, the user explicitly requested preparing
and opening a PR for this session, authorizing staging, commit and push.
The qualified source fingerprint remains unchanged; merge and deployment
remain separate.

### Final candidate results

| Suite | Result | Command elapsed | JUnit |
|---|---|---:|---|
| Backend unit | 856 passed | 142.087s | unit.xml |
| Desktop unit/contract | 140 passed | 5.530s | desktop.xml |
| Graph integration | 173 passed | 365.307s | integration.xml |
| Acceptance | 85 passed | 47.080s | acceptance.xml |
| Desktop integration | 2 passed | 27.198s | desktop-integration.xml |

JUnit/log paths are under work/be46/final-5/. Pytest's own suite durations are
140.07s, 4.04s, 363.16s, 44.82s and 25.40s respectively; command durations include
startup/teardown. Existing root-unit runtime warnings (3) and Starlette deprecation
warnings remain, with no guard skipped. Lint, strict mypy (167 source files), C1–C9,
generated-document drift, static runtime guards, live baseline and whitespace pass.
Qt uses offscreen/WebEngine test flags; graph suites use fixture-owned containers,
volumes and synthetic data. No production database or paid transport is used.

These are validation durations, not implementation effort or merge delay. Publication
is unrequested. The BE-45 reference unit/integration command durations were
139.247s/378.529s; this candidate's 142.087s/365.307s do not establish sustained CI
growth across different fixture/build-cache inputs. Repeated development corrections
were traced to source inventories/default selection assumptions across registry,
API, bulk/re-extraction and acceptance tests. The final review checked those
consumers together and supplied actual fixtures before restarting qualification;
no smaller delivery package, copied pair suite or numerical quota was introduced.

Acceptance mapping:

- Composition's authoritative registry includes both selection-only adapters;
  `enrich` accepts at most ten reviewed existing graph-entity mappings. Operator
  bearer authentication, persistent jobs/request UUID replay and the existing
  worker timeout remain intact. Generic ingest-all cannot implicitly acquire
  enrichment. Yahoo validates the returned exchange/symbol before acquiring
  remaining sections; Wikipedia resolves reviewed QIDs through DE/EN sitelinks
  and validates actual page QIDs, missing/ambiguous pages and redirects. Wikipedia
  accepts any existing ontology entity (including countries/places); Yahoo remains
  corporation-only. The generic EnrichmentObservation type and target_id avoid
  assigning company semantics to non-company context.
- Original provider responses and acquisition manifests reach the content archive.
  Wikipedia supplies exact page/revision IDs and dates, revision/canonical/history
  URLs, contributor attribution, license and wikitext, including without inference.
  Snapshot version identity uses verified revision/text identity; unrelated page
  metadata changes remain archived but cannot create a new context version or
  repeat extraction. Shared prompt/schema 2.0.0, gate, resolver, cache and loader
  retain exact original revision spans as qualified claims. Unqualified replacement
  output cannot produce factual edges; empty re-extraction leaves context intact.
- Yahoo's replaceable yfinance 1.7.0 raw transport bounds decompressed buffering
  before allocation grows past 4 MiB, has three redirects, 20-second requests,
  rate spacing/backoff and four outer attempts. Cookie state is private/transient,
  compatible with runtime UID 7474 and no writable home. Individual failures retain
  available sections, explicit failed/missing/unsupported status and manual replay;
  failed runs do not advance the checkpoint. EnrichmentCheck retains new acquisition
  attempts independently from immutable source versions; unchanged success after
  failure is visible as checked again. Replaying identical raw context does not
  recursively embed previous manifest hashes or invent additional checks.
- Profile/governance, named major/institutional/fund holdings, separate aggregate
  ratios, calendar estimates and available filing metadata retain dates, roles,
  quantities, units/basis, currency and field/row locators. Explicit title words
  distinguish executive and named board bodies; no officer roster establishes a
  complete board structure. Missing currency, term/as-of/fiscal/publication dates
  stay unknown. Estimated calendar dates never create published-report observations.
  Overlapping holder lists have a do-not-sum policy and remain incomplete.
- Ontology 1.2.0 is additive: four artifact types/four connecting relations plus
  Corporation QID support. Ontology-declared scalar/datetime properties are checked
  before batch commits and stamped only on creation; protected registry fields
  cannot be injected or overwritten. Reviewed QIDs reuse existing canonical
  corporations; securities and exchange/provider-qualified listings are distinct.
  Holder/officer names yield unresolved shared-resolver candidates. Source/section
  versions coexist and disappearance never retracts registry/other-section evidence.
  Schema changes retain old stamps, use the provision lock and one DDL per transaction.
- Authenticated enrichment reads expose bounded source/section history, independent
  source/recorded/check dates, freshness basis, unknown-time rows, unresolved identity,
  evidence and truncation/empty diagnosis. Consumer reads make no provider requests.
  Numeric properties remain accessible to ontology-generated builder/Cypher queries.
  Desktop job/response mirrors and the HTTP client match the API. The actual entity
  property view displays revision/license values; existing archive evidence preview
  retrieves the original response through its assertion hash and section locator.

Evidence sources: `tests/unit/test_enrichment.py` adds 16 distinct cases and
`tests/unit/test_sources_base.py` adds one shared compressed-transport regression;
`tests/integration/test_enrichment.py` adds two full graph/API/desktop/shared-pipeline
scenarios. Existing ontology-version assertions and mirror contracts are updated,
not duplicated. Independent raw fixtures and provenance/access review live in
`tests/fixtures/enrichment/README.md`. The source-format probes fetched DE/EN
Siemens revisions, SIE.DE/SIEGY/BMW.DE/ASML.AS quoteSummary responses and VOW.DE/
VOW3.DE prices. BMW3.DE and an unlisted symbol returned 404, and an uncredentialed
quoteSummary returned 401. Two further read-only price calls confirmed the bounded
transport handles sequential listings. A subsequent original English Germany revision (page 11867, revision 1381631157,
Q183) was acquired through the actual bounded MediaWiki transport for country
coverage. That compressed response exposed the shared helper retaining gzip headers
on already-decoded bytes; the helper now strips transport encoding/length before
constructing the buffered response. Regression coverage independently checks one
decode and the decompressed bound. No provider/model call occurs in tests.

Development checks passed for source/property/job contracts and the disposable
scenarios before source freeze. An initial bounded subset without sandbox network
permission stalled the ASGI test loop and was terminated, then passed with the
required environment permission (89 cases). Development integration corrections
fixed fixture imports, mock embeddings and absent Neo4j null-property assertions;
these were test defects, not silently skipped guards. The final source includes
the metadata-only revision replay regression and acquisition-manifest idempotence.
The first candidate attempt stopped after 853 unit passes and two compatibility
failures: an obsolete Corporation-QID undeclared-key assertion and prepended new
relations changing the legacy builder default. The negative key fixture now uses
an actually undeclared ticker key, and new ontology types/relations are appended
to preserve existing order. The focused 49-case regression passed.
The second attempt passed all 855 then-current backend units and 140 desktop
checks. Integration found an old registry allowlist omitting the two new sources;
that fixture is updated. The run was deliberately interrupted during integration
for the non-agent Wikipedia scope correction and newly exposed compressed HTTP
repair. It is not acceptance evidence for the final source. Failure/interruption
reports remain under work/be46/final/ and work/be46/final-2/. The final-3 candidate
includes generic entity context, independent country evidence and the shared gzip
regression; affected source and graph/API checks pass before the final freeze.
The third attempt passed 856 backend units and 140 desktop checks; graph
integration had 172 passes and one outdated ingest-all exclusion expectation.
The expectation now includes both selection-only adapters. Reviewing that failure
also corrected default re-extraction to exclude Wikipedia and to reject explicit
enrichment sources without reviewed selection jobs. The fourth attempt was
stopped during units after identifying the remaining shared acceptance registry
allowlist. AC-04 now includes both adapters and their actual independent fixtures;
the affected ten acceptance cases pass, as do 33 source/CLI/graph cases.

The final candidate also validates normalized enrichment properties against the
loaded ontology before writing. Provider scalar drift becomes an archived, durable
failed section with errors/finished_at, preserving earlier evidence and preventing
checkpoint advancement. The graph/API scenario injects an invalid employee-count
scalar and verifies its failed-section visibility and completed run record. These
corrections remain within BE-46; no guard or failure is waived. Final evidence is
under work/be46/final-5/; earlier attempts remain retained and non-authoritative.
A transient execution-tool disconnect was retried after runtime readiness was
confirmed; it did not erase work or change the managed environment.
Full-suite results, rather than development passes, govern acceptance.

Source availability is partial. Wikipedia context is wikitext, not a rendered
article; Yahoo does not supply complete boards, holdings, terms or reports.
Reviewer-supplied company/security mappings are explicit evidence-bearing inputs,
not automatically certified by names or tickers. Source-format checks do not
certify model quality, commercial redistribution/production retention rights,
production coverage, deployment, or reference-platform desktop performance.
BE-45/DC-14 and the current issue index retain those separate boundaries.

### Change accounting against live base (local acceptance snapshot)

Nineteen new cases: 16 enrichment unit cases, one shared gzip-bound regression,
and two integration scenarios. Other tests/fixtures/expected versions are updated
in place. Pass totals above are cumulative across the repository.

| Category | Added | Deleted | Net |
|---|---:|---:|---:|
| Handwritten runtime | 1343 | 9 | 1334 |
| Tests/helpers | 874 | 34 | 840 |
| Fixture data and attribution | 57 | 0 | 57 |
| Ontology artifact | 127 | 2 | 125 |
| Dependencies | 129 | 4 | 125 |
| Documentation renderer | 52 | 23 | 29 |
| Generated docs | 52 | 23 | 29 |
| Handwritten docs | 448 | 37 | 411 |

Fixture JSON size: 498,797 bytes. Unchanged raw responses are
single lines. No files are staged or committed; the final source fingerprint
remains unchanged after this documentation-only handoff.

## 2026-10-29 — BE-45 candidate qualification under D-84 waiver

Complete selected delivery: reproducible candidate qualification, physical dump
recovery and bounded fixture observations, with the user's explicit waiver of
operator-evidence and separate production/paid-run authorization requirements.
Branch `codex/be-45-qualification`; live-fetched base
`44ab4eb605a26ac87fcf8f77eb60848030fb5fc3`. Verification preceded commit; the
working source manifest, rather than the base commit alone, identifies this candidate.
The user subsequently requested preparing and opening a PR, authorizing staging,
commit and push. Publication checks confirm the source manifest still matches.
No production endpoint, operator data or paid model was used.

Command: `venv/bin/python tools/qualify.py --output work/be45/final`.
One authoritative full candidate run passed in 588.812s.
Exact commands, return codes, elapsed durations, logs, JUnit and source manifest
are retained in ignored `work/be45/final/`. The atomic `report.json` says `passed`.
Source manifest SHA-256: `d8739e499c3b264644b01dbd15a4b54cf813d89a0974d27a30fe1f1a949452b9`.
The hash is SHA-256 of JSON-serialized sorted path-to-file-SHA-256 mappings;
`source.json` retains the mappings. The allowlisted roots are defined in
`tools/qualify.py` and include runtime, tests/fixtures, tools, ontology, Docker,
root dependency files, CI, Compose and runtime contract. Documentation handoff
edits follow the source freeze; no runtime/test/tool/CI source changed after it.

| Suite | Result | Command elapsed | JUnit under work/be45/final |
|---|---|---|---|
| unit | 839 passed | 139.247s | `unit.xml` |
| desktop | 140 passed | 5.939s | `desktop.xml` |
| integration | 171 passed | 378.529s | `integration.xml` |
| acceptance | 85 passed | 39.744s | `acceptance.xml` |
| desktop-integration | 2 passed | 22.997s | `desktop-integration.xml` |

Durations are command wall time including interpreter startup and teardown, not
active implementation effort. Pytest's own suite durations were 137.30s, 4.38s,
376.56s, 37.49s and 21.33s respectively. All suites had zero failures, errors and
skips. Existing backend-unit warnings (3) and Starlette deprecation warnings
(integration/acceptance/desktop integration) remain; no guard was skipped.
Live baseline, ruff, strict mypy, C1–C9, generated-document drift, static runtime
smoke guards and whitespace passed in the same candidate run. The canonical venv
was synchronized with frozen all-package dependencies before verification.

Acceptance mapping:

- `tools/qualify.py` uses a fresh evidence directory, snapshots allowlisted
  tracked and untracked source, writes running state before execution, rejects
  nonzero commands and missing/empty/failed/all-skipped JUnit, and checks source
  drift before passing. Exceptions/interruption cannot preserve a green report;
  timed-out child process groups are terminated. It refuses external test database
  selection, uses bounded per-check timeouts and never submits production jobs.
- Eight new unit cases cover distinct false-green, failure reporting, evidence
  reuse and source identity/drift boundaries. The extended recovery case is an
  existing test, not an additional test count. All automated model/provider calls
  remain mocked. The existing hosted offline and graph lanes remain separate;
  only lint registration for the new qualification tool changes in CI.
- `test_backup_stops_dumps_and_restarts` creates a unique marker and 1,000
  synthetic 1,024-byte payload nodes, backs up through the real supervisor,
  deletes the live marker, stops Neo4j, loads the dump offline and restarts.
  The exact marker, node count and independently stated 1,024,000 payload bytes
  survive. The non-root image, authentication and shutdown behavior remain covered.
  Existing archive/pipeline/API suites retain exact content-hash evidence checks.
- Final recovery observations in integration JUnit: dump **70,922 bytes**;
  offline load/start/connectivity/content verification **24.193s** (excludes the
  preceding clean stop); post-restore Docker memory sample **981.5 MiB**;
  database storage **3,344 KiB**, transaction storage **526,348 KiB**, archive
  storage **156 KiB**. Archive storage includes both the original dump and its
  restore copy. The sample is neither peak memory nor a representative production
  workload benchmark; no production resource threshold is inferred. Recovery test
  elapsed 109.989s and packaged runtime test 156.326s, including fixture work.
- Hosted base evidence: PR #11 run
  [40824901246](https://github.com/playa77/limes/actions/runs/40824901246) passed
  offline/graph/candidate-check; main run
  [40827109504](https://github.com/playa77/limes/actions/runs/40827109504) passed
  bounded smoke/candidate-check and skipped full lanes. These are exact prior
  revisions, not hosted execution of this unpublished candidate. The required-status
  protection endpoint returned HTTP 403; its configuration is unverified. Sanitized
  API observations are retained in `work/be45/hosted/` and referenced in OPEN_ISSUES.

D-84 removes the external operator-evidence gate for this delivery. OI-01/03/09
are explicitly waived/unmeasured, not falsely closed by tests. OI-23 now has hosted
execution evidence while required-check configuration remains waived/unverified.
OI-24 has direct bounded recovery/resource observations; production scale, paid
quality and reference-platform/manual evidence remain unmeasured. The missing
OI-05 historical review trail remains missing, and DC-14/OI-10/11/18 correctness
obligations remain open. No deployment, paid evaluation, historical review recovery
or blanket product-release certification is claimed. BE-45 acceptance under this
explicit waiver is satisfied; BE-46 is the next backend implementation package.

Development checks: focused qualification units passed; an earlier real recovery
probe passed in 105.99s before adding the synthetic-workload observations and
switching JUnit metrics to suite properties. Only the final full candidate above
is authoritative. ROADMAP records separate hosted-validation and merge intervals;
engineering effort remains unmeasured. Handoff docs/renderer drift and source
manifest identity are rechecked after documentation updates.

Change accounting against live base (new unit cases: 8; existing integration
case extended; no standalone fixture dataset or product-runtime code added):

| Category | Added | Deleted | Net |
|---|---:|---:|---:|
| CI configuration | 1 | 1 | 0 |
| Handwritten documentation | 245 | 16 | 229 |
| Generated documentation | 15 | 1 | 14 |
| Tests/helpers | 157 | 1 | 156 |
| Documentation renderer | 15 | 1 | 14 |
| Qualification tooling | 156 | 0 | 156 |

## 2026-10-29 — BE-44/DC-16 candidate verification

Complete parent: cross-source temporal investigation, including paired desktop
network/map/timeline and evidence/review workflows. Branch
`codex/be-44-temporal-investigation`; live-fetched main `84c832df3cd5`
(PR #10). The clean supplied checkout was fast-forwarded before implementation;
`python3 tools/check_git_baseline.py` passed with environment network access.
The local publication hook is installed. After local acceptance, the user requested
PR publication, authorizing staging, commit and push.
D-83 preserves provider selection as the agent's implementation responsibility.

Final source manifest SHA-256:
`2c7fbb819c72aa525f417bc427682abcd5e80c54934643444303d4c6f109b205`.
Uses the same sorted unique path + NUL + bytes + NUL procedure and source path
set as BE-43 below, additionally including `docker-compose.yml` and
`docs/runtime-contract.json`. Authoritative logs, JUnit and manifest are under
ignored `work/be44/final/`; exploratory checks and the offscreen preview remain
under `work/be44/candidate/`. Documentation-only acceptance/handoff updates
follow the final source freeze. All five final suites pass.

Earlier development verification found a synthetic-company identifier collision
with a later module fixture (167 integration passes, four setup errors). The new
scenario now uses a distinct identifier and tears down its graph. An intermediate
graph retry was stopped while the API archive-volume mount was corrected. API
previews now use an explicitly read-only archive mount and a storage dependency
that never creates missing directories. The real runtime-stack test checks shared
archive visibility and write denial in the API container. A visual inspection also
split report/tracking and cross-source controls into tabs (minimum height reduced
from 1,013 to 661 pixels in the offscreen preview); desktop regressions were rerun.
Those development passes/interrupted runs are not substituted for final results.
The final full candidate starts after these corrections; all source files are frozen.

### Final results

| Suite | Result | JUnit |
|---|---|---|
| Backend units | 831 passed; 136.53s | `work/be44/final/unit.xml` |
| Desktop units/contracts | 140 passed; 3.59s | `work/be44/final/desktop.xml` |
| Integration | 171 passed; 292.32s | `work/be44/final/integration.xml` |
| Acceptance | 85 passed; 37.14s | `work/be44/final/acceptance.xml` |
| Desktop integration | 2 passed; 22.73s | `work/be44/final/desktop-integration.xml` |

Commands: `venv/bin/python -m pytest PATHS -q --tb=short --junitxml=FILE`.
Paths are, respectively, `tests/unit`, `desktop/tests/unit desktop/tests/contract`,
`tests/integration`, `tests/acceptance`, `desktop/tests/integration`. Qt uses
`QT_QPA_PLATFORM=offscreen` and
`QTWEBENGINE_CHROMIUM_FLAGS='--no-sandbox --disable-gpu'`. Runtime builds use
`BUILDX_CONFIG=/workspace/limes/work/be44/buildx`. The runners preserve network
proxy/CA settings and own disposable containers/volumes; production is untouched.
Ruff (including the renderer), strict mypy (158 source files), documentation C1–C9,
generated-document checks and whitespace pass. Validation durations above are
pytest measurements, not implementation effort or merge wait.

Acceptance mapping:

- `news/developments.py` and authenticated news routes join investigation targets,
  qualified claims, coded observations and source-stamped assertions. Shared
  temporal fragments filter validity and recorded time independently. Target-hop
  and per-kind coverage, result caps, truncation and missing/unknown-time/geometry
  diagnosis stay explicit. Default results retain replaced/retracted history.
- Directional participant/predicate matches are unresolved hypotheses. Immutable
  operator reviews separate match, assessment and independence, retain rationale
  and server recorded-time history, and permit explicit cross-predicate review.
  Exact request replay is idempotent; changed reuse conflicts; known shared
  report/dispatch/document identity cannot be labeled independent. No factual
  edges or identity merges are created by claims, suggestions or reviews.
- `tests/integration/test_developments.py` loads independently authored proposal,
  denial, agreement, official award and coded-observation artifacts using the
  production archive/document/claim/assertion writers, then verifies actual
  authenticated API and desktop client/view round trips against disposable Neo4j.
  It checks earlier belief/validity views, dependent reporting, review history and
  authorization, exact archived official evidence and unchanged factual edge count.
  Source fixtures are synthetic behavioral examples, not independent live reporting
  or measured model/provider quality; existing BE-42/43 parser/pipeline tests retain
  their separate format/extraction evidence obligations.
- Desktop contract guards mirror all response fields. Network and timeline
  selection inspect exact source spans/versions or bounded raw archive previews;
  map markers inspect evidence for directly geolocated endpoints without tile
  requests. Unknown event time contributes no validity point. Failed loads clear
  old results, and request generations prevent cross-investigation stale replies.
  Desktop regressions cover these distinct failure/semantic boundaries.
- Archive preview tests bound decompression at 64 KiB and reject path-like hashes.
  Additive infrastructure indexes/constraints use existing serialized provisioning;
  ontology, prompt, extraction schema, cache and old assertion stamps are unchanged.

Verification boundaries: automated suites mock paid/provider transports and use
fixture-owned graph/runtime containers. No production acquisition, deployment,
paid evaluation, representative resource measurement or reference-platform/manual
acceptance is inferred. Existing DC-14/OI-11/18 map-policy and guard issues remain
on the old map; the new coordinate-only pane requests no external tiles. BE-45
retains operational/model/hosted required-status qualification and missing review
trail obligations. Source corpus fixtures are test helpers, with no new standalone
fixture dataset, ontology artifact or ontology edits. Runtime configuration adds only the read-only API archive
mount. Generated ARCHITECTURE changes come from `tools/generate_runtime_docs.py`.

### Change accounting and handoff

All five ROADMAP acceptance items pass locally. New tests cover eight backend
unit cases, three desktop cases and one graph/API/desktop scenario (12 cases);
existing runtime-stack coverage additionally verifies archive visibility/write
denial. Counts are distinct additions, not a delivery quota or cumulative quality
claim. Inline behavioral fixtures are included in tests/helpers; no standalone
fixture files or ontology artifacts are added. The accepted candidate is prepared
for the subsequently requested PR publication; merge and deployment remain separate.

| Category | Added lines | Deleted lines | Net lines |
|---|---:|---:|---:|
| Handwritten implementation | 899 | 10 | 889 |
| Tests/helpers | 493 | 0 | 493 |
| Runtime configuration | 1 | 0 | 1 |
| Documentation renderer | 4 | 1 | 3 |
| Generated documentation | 4 | 1 | 3 |
| Handwritten documentation | 313 | 17 | 296 |

No runtime/fixture source changed after the final fingerprint was captured.
Ruff, mypy, documentation C1–C9, generated-document drift and whitespace were
rechecked at handoff; final source fingerprint still matches. The three-delivery
workflow review is recorded in ROADMAP; engineering effort and merge waiting
remain unmeasured. No production/paid run or historical issue closure is claimed.

## 2026-10-28 — BE-43/DC-15 local implementation acceptance

Complete parent: dynamic investigation-driven news acquisition and qualified
reporting, including its paired desktop consumer. Branch
`codex/be-43-dynamic-news`; live-fetched main `b1afc86ab283`. After local acceptance, the user explicitly requested preparing and opening a PR,
authorizing commit and push. The checked acceptance/handoff is in ROADMAP; D-82 records the
user's confirmed tracking contract. A supplied provider/subscription or pre-existing
corpus is not an implementation prerequisite.

### Final verification

Final runtime/test/ontology/tool/CI source manifest SHA-256:
`448c9d1b63718ca29a50ba585f3ad19c0c1e49b759aeb5ce5b71a3f488f05e29`.
It hashes sorted unique paths plus NUL, bytes plus NUL from `git ls-files -co
--exclude-standard src desktop/src tests desktop/tests tools ontology docker
pyproject.toml uv.lock .github/workflows/ci.yml`. Local logs, XML and the manifest
are retained under ignored `work/be43/candidate/`. Documentation handoff edits
follow validation; the source manifest is rechecked after them.

| Suite | Final result | JUnit file |
|---|---|---|
| unit-final | 823 passed; 134.45s | `unit-final.xml` |
| desktop-final | 137 passed; 4.48s | `desktop-final.xml` |
| integration-final | 170 passed; 277.20s | `integration-final.xml` |
| acceptance-final | 85 passed; 34.94s | `acceptance-final.xml` |
| desktop-integration-final | 2 passed; 19.27s | `desktop-integration-final.xml` |

Commands use `venv/bin/python -m pytest PATHS -q --tb=short --junitxml=FILE`.
Paths, respectively: `tests/unit`; `desktop/tests/unit desktop/tests/contract`;
`tests/integration`; `tests/acceptance`; `desktop/tests/integration`. Qt uses
`QT_QPA_PLATFORM=offscreen` and
`QTWEBENGINE_CHROMIUM_FLAGS='--no-sandbox --disable-gpu'`.
`BUILDX_CONFIG` points to ignored `work/be43/buildx` for disposable image builds.
All provider/model transports in automated suites are mocked; graph, backup and
runtime tests own disposable containers/volumes. No production graph is selected.

Ruff over src/tests/desktop, strict mypy (156 files), documentation C1–C9,
generated-document drift and whitespace checks pass. The bounded main smoke
command (config/news/runtime-doc units, plugin autoload disabled) passes 33 cases.
The CI aggregate was locally exercised with success, failure, skipped and cancelled
lane results: required lanes fail closed. Hosted GitHub execution and required-check
configuration were not inspected or claimed; OI-23 retains that evidence obligation.

The environment connection was reset during an earlier run: partial unit/graph
logs without completed JUnit are not counted as results. Only fixture-owned
containers/project volumes were cleaned up. The next complete graph run had 168
passes and two stale source-selection expectations; those tests now explicitly
exclude investigation-only news from global ingest/reextract. The entire graph
suite then passed as above. Backend units ran again after queued-request schema
compatibility was repaired; desktop units/contracts ran after selectable relation
wiring and late-reply evidence protection. Repetition was caused by these actual
changes/failures and the interrupted environment, not a test quota. Durations are
validation measurements; implementation effort and merge latency are unmeasured.

### Acceptance evidence and boundaries

- Tracking lifecycle, current graph label/alias and relation endpoint discovery,
  persistent scheduling, queue backpressure, failed/interrupted manual replay,
  publication versus update times and optional-field job migration:
  `tests/unit/test_news.py` and `news/store.py`, `news/targets.py`, `sources/news.py`.
- Independently captured RSS transport fixture, byte/text/target bounds, raw feed
  and entry identity, unchanged-report deduplication and visible partial failure:
  fixture README plus upstream-format news units. One successful public response
  (53,216 bytes; source SHA-256 recorded in the fixture README) was inspected
  read-only. Identity encoding resolved the first decoding failure. This is
  bounded source-format qualification, not production ingestion or full coverage.
- Bilingual proposal/denial/reporting/completion/cancellation/conditional/unknown
  precision fixtures cover qualification preservation and rejection. They are
  independently authored synthetic behavioral labels, not measured model quality.
  Acquired documents enter an unreviewed evaluation pool; operator annotations
  can grow it during investigation. Automated extraction is never its own gold.
- `tests/integration/test_news_pipeline.py` exercises real composition, gate,
  schema-2 extraction parsing, shared resolution, loader, archive and authenticated
  API against disposable Neo4j. Proposed/denied reports retain contradictions and
  exact evidence, never create unqualified positive edges, share dependent dispatch
  identity, preserve source versions and unknown dates, replay without paid calls,
  survive failed replacement, and retract only their own archived document after
  successful empty replacement. Other source/channel history is untouched.
- Five new desktop regressions cover tracking/pause/manual replay, qualified
  denial and prior-version evidence, unknown event-time/network semantics,
  selectable relation evidence from the shell, and stale asynchronous replies.
  API mirrors have field parity; ontology literals remain out of desktop views.
  Existing desktop integration flows also pass. DC-14's unrelated map-policy and
  reference-platform/manual-performance obligations are not inferred complete.

Ontology 1.1.0 is additive: historical stamps/assertions remain unchanged. Legacy
schema/prompt/cache behavior remains available; news uses 2.0.0 with qualifiers.
Claims are ontology-visible artifacts with separate source trust, extraction
confidence and unassessed assessment; event descriptions remain unresolved
candidates. Canonical original-agency identity, correction metadata and full
article text are unknown where public RSS does not supply them. Headlines/snippets
are never described as licensed agency full text or independent corroboration.
Representative paid quality, production ingestion/deployment/resource/recovery
qualification and broader licensed sources remain unclaimed. No staging, commit,
push, PR, deployment or paid provider evaluation occurred.

## Historical BE-41 documentation candidate

Reviewed 2026-10-27 on `codex/core-news-design`; live-fetched base main
`3f1effd01bd9`. Product implementation was not changed. The delivery changes are
specifications, documentation organization, renderer text and documentation guards.
This is a documentation candidate, not a production/release qualification.

## Current executed checks

| Check | Command | Result and boundary |
|---|---|---|
| Live baseline | `python3 tools/check_git_baseline.py` with network access | Passed against 3f1effd; preserves merged PR #6 |
| Historical packages | `git show 37a8989^:docs/LIMES_Implementation_Roadmap_v2.1.0.md`; `git merge-base --is-ancestor COMMIT origin/main`; introducing diffs/current files | Backend 01–40 plus 25a and desktop 01–13 implementation ancestry/artifacts checked; acceptance not inferred |
| Root existing units | `venv/bin/python -m pytest tests/unit -q --junitxml=work/reconciliation/limes-reconciliation-unit.xml` with network-enabled local execution | 779 passed in 137.21s before adding two documentation-regression tests; 3 existing warnings |
| Desktop units/contracts | `QT_QPA_PLATFORM=offscreen QTWEBENGINE_CHROMIUM_FLAGS='--no-sandbox --disable-gpu' venv/bin/python -m pytest desktop/tests/unit desktop/tests/contract -q --junitxml=work/reconciliation/limes-reconciliation-desktop.xml` | 132 passed in 4.58s; no current graph/manual/deployed workflow inferred |

Both runs used a 180-second command timeout; the timeout did not fire. Network
access allowed local test sockets; tests mock paid inference. JUnit files are
retained locally under ignored work/reconciliation, with the exact commands/results
above tracked here. An earlier sandboxed root-unit run stalled and was stopped
without a result (143); it is not counted as a test failure or passing evidence.
No test quota or cumulative-pass delivery target is used.

The two new document-guard tests cover distinct regressions: a missing package
definition in a sequence and a broken active document link. They protect the
specific organizational failures this repair addresses, not runtime behavior.
Their focused validation and the shared runtime-doc guards passed as recorded below,
alongside C1–C9, renderer lint, generated drift, archive preservation and whitespace. No new fixture data or production source is added.

## Evidence that remains explicitly unclaimed

- Current full integration/acceptance/desktop integration suite execution. The
  October 7 results in OPEN_ISSUES are historical, not fresh results here.
- Working live GDELT ingestion: OI-19..22 are reproduced open defects, assigned to
  BE-42. Mocked adapter/acceptance fixtures cannot certify upstream compatibility.
- Agency provider access, representative annotated corpus, qualified claim/event
  schema/migration and measured paid-model quality: BE-43/DC-15 prerequisites.
- Desktop map policy/network enforcement, builder semantics, reference X11/Wayland
  behavior, ≤3s startup, manual selection/time-sync/degradation/confirmation flows:
  DC-14. API-only networking remains a requirement with a known violation.
- Representative full-workload memory/storage, current production revision/images,
  deployment smoke and actual operator recovery evidence: BE-45/OI-01/03/09/24.
- Recovery of the original ignored 18-finding review trail: OI-05. Current code,
  an archived summary and fresh tests cannot reconstruct absent original evidence.
- Hosted candidate checks, required-status configuration and merge latency. CI
  lanes exist on separate runners; OI-23 records trigger/gate qualification gaps.

The repository can have a precise documentation baseline with these known gaps;
it cannot honestly be labeled fully accepted, live-validated or release-ready.
Roadmap H/R/S states retain these distinctions. The BE-41 handoff closes only its
specified documentation acceptance, not any future implementation package.

## Documentation candidate results

| Check | Result |
|---|---|
| `venv/bin/python -m pytest tests/unit/test_document_organization.py tests/unit/test_runtime_docs.py -q` | 8 passed (2 new organizational regressions, 6 existing runtime-doc guards); latest run 0.11s |
| `python3 tools/check_docs.py docs/` | C1–C9 passed, including complete BE/DC definitions, preserved inserted package mapping, defined roadmap references and active relative links |
| `python3 tools/generate_runtime_docs.py --check` | Passed; README/runtime/testing match their renderer and runtime contract |
| `venv/bin/ruff check tools/check_docs.py tools/generate_runtime_docs.py tests/unit/test_document_organization.py` | Passed |
| `git diff --check` | Passed |
| Archive preservation | Backend archive matches its original Git body; desktop archive preserves its body except two normalized recipe indentation lines, after explicit historical notices |
| Runtime scope | No changes under src/, desktop/src/, ontology/, docker/ or tests/fixtures/ |

The focused checks were repeated only after relevant documentation-guard edits;
the expensive root/desktop suites were not rerun without an implementation reason.
Junit documentation-guards.xml under work/reconciliation retains the initial
focused run; later 0.11s result is recorded above. This is not hosted CI evidence.
BE-41's documentation acceptance passes; the user explicitly requested PR
publication. Merge remains a separate user action. Implementation remains unstarted, with precise next packages and
external blockers in both registers. Implementation effort and merge latency were
not measured; test durations above are validation measurements only.

## Change accounting

Counts below include tracked edits and new files before publication; archived
original plans are kept separate from new documentation and from implementation.
They are line additions/deletions, not engineering effort or acceptance metrics.

| Category | Added lines | Deleted lines | Net lines |
|---|---:|---:|---:|
| Handwritten product implementation | 0 | 0 | 0 |
| Documentation renderer/checker | 103 | 33 | 70 |
| Tests/helpers (2 new regression tests) | 33 | 0 | 33 |
| Fixture data | 6 | 3 | 3 |
| Generated documents | 24 | 16 | 8 |
| Handwritten documentation | 273 | 20 | 253 |
| Archived original plans with notices | 3445 | 0 | 3445 |


## 2026-10-28 — BE-46 planning documentation verification

Documentation-only update prepared on `work`, published for review from
`codex/entity-enrichment-design` at base `b9d940a`. GitHub main was first confirmed
through the connector. The initial sandboxed baseline fetch could not reach the
proxy; the network-enabled `python3 tools/check_git_baseline.py` passed against
`b9d940a` before publication. The user subsequently authorized a PR. No runtime
implementation occurred. D-80 records the approved scope/provider;
ROADMAP records the documentation checklist, while BE-46 implementation acceptance
remains planned and unchecked in BACKEND_ROADMAP.

Validation for this update: `python3 tools/check_docs.py docs/` (C1–C9),
`python3 tools/generate_runtime_docs.py --check`, the existing
`tests/unit/test_document_organization.py` and `tests/unit/test_runtime_docs.py`
suites (8 passed), renderer lint and `git diff --check`. No new tests, runtime
adapters, ontology migration, provider data fixtures or live ingestion were added.
These checks establish document consistency, not Yahoo Finance or Wikipedia live
availability, completeness or adapter acceptance. Existing release/operator gaps
above remain open.

## 2026-10-28 — BE-42 candidate acceptance

Selected package/branch/prerequisites and completed checklist: ROADMAP. Base main
`b093599d3667` was fetched, fast-forwarded and rechecked before implementation.
Validation preceded publication; the source/test/tool manifest SHA-256 is
`b1ae0e751124f1a606a2959bb577b6ed75cb04840d2ce6b55672126e87ebd1d5`.
It hashes sorted unique repository-relative paths plus NUL, bytes plus NUL for
existing files returned by `git ls-files -co --exclude-standard src desktop/src
tests desktop/tests tools ontology docker pyproject.toml uv.lock`. The digest and
JUnit/logs are retained in ignored work/be42/candidate. Documentation-only status
updates follow runtime verification; no runtime changes follow the final run.

| Check | Final result |
|---|---|
| `unit-final` pytest suite | 808 passed, 136.33s; JUnit `unit-final.xml` |
| `desktop` pytest suite | 132 passed, 3.60s; JUnit `desktop.xml` |
| `integration-final` pytest suite | 169 passed, 273.75s; JUnit `integration-final.xml` |
| `acceptance` pytest suite | 85 passed, 32.10s; JUnit `acceptance.xml` |
| `desktop-integration` pytest suite | 2 passed, 26.88s; JUnit `desktop-integration.xml` |
| Ruff over src/tests/desktop and renderer | Passed |
| mypy | Passed, 148 source files |
| Documentation C1–C9, generation drift, whitespace | Passed |

The original full graph run had 166 passes plus one invalid-fixture failure and
two Docker build metadata failures. Corrected GISCO input and workspace
BUILDX_CONFIG resolved those causes; four focused checks passed (221.27s), then
the entire graph suite passed. Backend units were repeated after distinct
row-limit/report-identity and UTC-offset regression cases were added; this is the final suite count, not a quota.
Other complete suites passed without changes requiring repetition. Timings are
validation latency, not implementation effort; no merge/hosted CI latency exists.

Direct evidence mapping: OI-19 official URL/map/ZIP bounds and upstream-to-graph;
OI-20 mixed gate/cache/empty/load failure/retry/reextract ownership; OI-21 exact
archive/member/row/report/time metadata through authenticated API; OI-22 independent
country/geography/fractional-slot expectations and explicit work bounds. The source
fixture README identifies the upstream URL/hash and GeoNames attribution. Paid
transports are mocked; all graphs/volumes belong to disposable test fixtures.

BE-42 implementation/local acceptance is complete. Mentions coverage is explicitly
not required; only export SOURCEURL associations are claimed. Article text remains
unavailable, never synthesized. Caps are safety bounds, not measured performance.
No production acquisition, deployment, paid quality, hosted required-check status,
review-trail recovery or other BE-43/45 evidence is inferred. Implementation verification did not stage, commit, push or open a PR. The user
subsequently requested PR publication; merge and deployment remain outside scope.

### BE-42 change accounting

Line changes include untracked delivery files and compare with origin/main.
They distinguish additions/deletions from net growth, not engineering effort.
The generated country crosswalk is source data, separate from handwritten logic;
fixture metadata/attribution is documentation. The new tests add 32 parameterized
cases (25 upstream/format/geography/window, two checkpoints, four mixed-channel
and one upstream graph/API scenario); suite totals above include pre-existing tests.

| Category | Added | Deleted | Net |
|---|---:|---:|---:|
| Handwritten documentation | 273 | 20 | 253 |
| Handwritten implementation | 259 | 148 | 111 |
| Generated documents | 24 | 16 | 8 |
| Tests/helpers | 449 | 33 | 416 |
| Fixture data | 6 | 3 | 3 |
| Documentation renderer | 24 | 16 | 8 |
| Generated country crosswalk | 258 | 0 | 258 |

Publication preparation rechecked live main, documentation guards and staged
whitespace. The synthetic TSV fixture now has explicit DATEADDED and example.org
report URLs instead of empty trailing columns, preserving all 61 fields without
whitespace exceptions. Affected adapter/upstream unit checks and the complete
AC-04 adapter acceptance file passed again; runtime and the independent upstream
fixture are unchanged. The source manifest above includes this fixture update.
### BE-43 change accounting

Counts compare tracked edits and delivery files with live base main. They are
line additions/deletions/net growth, not engineering effort. Fifteen new backend
unit cases (including six bilingual parameter cases), five desktop cases and one
disposable graph scenario cover distinct regressions; suite totals above include
existing tests and are not a quota. Ontology/prompt/schema versions are explicit.

| Category | Added | Deleted | Net |
|---|---:|---:|---:|
| Documentation/CI tooling | 61 | 11 | 50 |
| Fixture data | 10 | 0 | 10 |
| Generated documents | 23 | 11 | 12 |
| Handwritten documentation | 422 | 47 | 375 |
| Handwritten implementation and prompts | 1488 | 31 | 1457 |
| Tests/helpers | 683 | 31 | 652 |
| Versioned ontology | 55 | 1 | 54 |
