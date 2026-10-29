# Verification and acceptance evidence

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
