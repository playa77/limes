# Verification and acceptance evidence

## 2026-11-09 — DC-17 ReUI web desktop: implementation and full candidate pass

The complete DC-17 package (D-99) is implemented on
`dc-17-reui-web-desktop` from live main `3896e91`
(the per-session record lives in the ignored `work/dc17/SESSION.md`). The
PySide6/QWebEngine desktop
is retired for the React 19 + Tailwind v4 + ReUI SPA (`desktop/web/`) and a
FastAPI launcher (`limes_desktop.webapp.py`: static serve, `/api` bearer proxy
with credential injection and bounded same-origin redirects, XDG profile
store, flock single-instance guard). Contract machinery generates the
committed `openapi.json`/`schema.ts` from the live API app
(`tools/export_openapi.py`, `desktop/web/tools/gen-api.mjs`) with pytest-only
freshness and TS-client-surface parity tests; the ontology-literal guard
extends to `desktop/web/src`. Vitest pins the pure modules (builder refill,
temporal filtering, viz payloads). Two backend integration tests whose desktop
halves imported the retired Python client were rewritten to the same payload
surface the web client consumes; the retired Qt widget render assertions are
superseded by payload-plus-contract evidence with the remaining browser-level
display evidence named under OI-34 and the DC-17 roadmap row. A secondary
agent session executed part of this package concurrently on the same checkout;
the user parked it while this session held the delivery contract, and its work
is incorporated and reviewed (details in the session record).

### Change accounting against live main (untracked files included)

| Category | Files | Added | Deleted | Net |
|---|---:|---:|---:|---:|
| Web SPA (React/TS sources, 3 generated contract files, tooling, committed lockfile) | 97 | 34,167 | 0 | +34,167 |
| Desktop Python launcher (3 modified, 1 new, 37 retired-stack deletions) | 41 | 507 | 10,697 | −10,190 |
| Desktop pytest suites (4 modified, 3 new, 21 retired deletions) | 28 | 881 | 3,712 | −2,831 |
| Root integration tests (2 modified: retired-client blocks → consumable surface) | 2 | 38 | 60 | −22 |
| Tooling (2 tools modified, `export_openapi.py` new, Makefile, CI) | 5 | 156 | 35 | +121 |
| Dependencies (root pyproject + uv.lock; PySide6/pytest-qt/shiboken out) | 2 | 425 | 94 | +331 |
| Handwritten documentation (requirements/architecture v1.1.0, roadmaps, ledgers, READMEs) | 10 | 510 | 207 | +303 |
| Generated documentation (root README, docs/TESTING_PHASE) | 2 | 39 | 13 | +26 |

Counts are text lines including untracked new files; fixture data, generated
SPA artifacts (`dist/`, node_modules) and the ignored work/ evidence are not
part of the manifest. No existing secret file was read or changed.

### Candidate

After the first pass (`candidate-final-5`, revision `3896e91` + working tree,
source SHA `35288c81…99a56`, 939.8 s, all lanes passing), one
publication-blocking defect was found in the SPA packaging:
`desktop/web/.gitignore` excluded `src/api/openapi.json`, so a fresh clone
would lack the committed contract file that the freshness contract reads.
The rule was removed, the generated file is tracked, and the publication
commit `06cb16f` was requalified end to end.

Authoritative command: `venv/bin/python tools/qualify.py --output
work/dc17/candidate-final-6`; status **passed**; revision
`06cb16fffe7a9c649df6835a6bb841ee4259fef9` (the complete publication commit),
source manifest SHA-256
`295a4d6513488b6db438ba8f3ecad394f1cbf6e40fa4e162ab2deb169e8076b6`,
validation wall time **511.201 s**. `-5` is retained as superseded
evidence (the only deltas are the gitignore rule and the tracked contract
file; no behavior). Report, source.json, JUnit and logs are in the ignored
directories.

| Lane | Result | Case count | Elapsed |
|---|---|---:|---:|
| baseline/lint/tools-lint/types/docs/generated/guards/whitespace | passed | — | ≈1.9 s |
| web (pnpm: install, tsc -b, vitest 29, eslint, build) | passed | 29 vitest cases | 10.4 s |
| unit | passed | 1,012 | 157.9 s |
| desktop (unit + contract) | passed | 42 | 2.9 s |
| integration | passed | 185 | 198.3 s |
| acceptance | passed | 85 | 37.0 s |
| desktop-integration (launcher + real API + disposable graph) | passed | 2 | 21.2 s |
| runtime-stack | passed | 1 | 82.6 s |

Total 1,327 pytest cases, zero failures/errors/skips, no source drift. The
web lane runs the committed pnpm toolchain with no test-time network beyond
standard registry installs. The runtime-stack lane passes on this executor
(292 GB free) — it does not claim deployed behavior.

Earlier candidate attempts on this package are retained as non-evidence:
`work/dc17/candidate-final` (and `-2`) crashed at the runner's source
fingerprint because tracked-but-deleted file paths carried no bytes while
still uncommitted — the runner was corrected to fingerprint bytes on disk (a
path appearing, disappearing or changing during a run still fails the drift
check); `-3` failed the strengthened ontology-literal guard on a vitest
fixture using real ontology names (`Corporation`/`SUBSIDIARY_OF` were in the
ontology 1.4 name set — the fixture schema is now invented); `-4` failed the
two retired-client integration tests. No failed assertion was waived or
weakened on the way to the passing candidate; the guard's violation was a
test-fixture defect, and the integration rewires preserve the underlying
asserted values with the payload surface the web client consumes.
At qualification time no staging, commit, push or PR was requested or
performed; only the documentation above changed after the freeze, checked by
`tools/check_docs.py`, generated-document drift and whitespace guards, and the
frozen source manifest was recomputed unchanged.

Publication update (2026-11-09): the user requests preparing and opening the
PR for this session's implementation. Live main is rechecked at `3896e91`
(tokens/checkout unchanged) and the declared source fingerprint still matches
the tested candidate: staging, commit, push and PR creation are now
authorized. The PR is a normal review candidate, not a draft; merge and
deployment remain separate actions.

## 2026-11-07 — BE-56 implementation; full qualification blocked by executor storage

Implemented on `codex/be-56-german-parliament-members`. Fetched live GitHub before
coding and fast-forwarded the clean checkout from `7c7be13` to main
`d967bae244dcbe221307eebae903f14042479166`; baseline checks passed again at the
latest candidate. The canonical `venv/` was synchronized from the frozen
all-packages lock. Scope, completion A1–A8, prerequisites and branch were recorded
before coding in `work/be56/SESSION.md`; D-98 records implementation.

All 21 source mappings are implemented: Bundestag, all 16 state parliaments,
both BVerfG Senates, Bundesrat regular/deputy membership and the presidency.
[Source qualification](BE56_SOURCES.md) records exact original responses, hashes,
URLs, retrieval times, term evidence, fields and access/retention limits. The 350
new fixture files comprise 327 compressed original responses, 22 JSON manifests
and one README. Counts are dated fixture observations, not legal quotas or deployed
population. Public DIP-key discovery and HTTP 200 validation are documented with
the public source and stated expiry; its 840 period-person records are not a
serving roster. No existing operator secret file was read/changed or key committed.

**Acceptance disposition:** A1–A6 and A8 have direct local implementation evidence;
A7 remains open. This is not a fully accepted package or a passing full candidate.
No required suite has been waived. The remaining blocker is concrete: Docker’s
VFS images plus container copies exhaust this executor’s 8 GB filesystem. A larger
filesystem is required to finish qualification; the current environment exposes
no storage-resize action to this session.

| Acceptance | Delivered behavior and direct evidence |
|---|---|
| A1 | All 21 official mappings and complete original fixtures; shared parameterized qualification, including city states, both court Senates and both Bundesrat classes. |
| A2 | Scoped identifiers, exact canonical reuse and visible name candidates; graph tests cover same-name company people, local-ID collisions and audited canonical review without name-only merging. |
| A3 | Ontology 1.4 institutions/offices/groups/roster artifacts; legacy DIP IDs/history retained through source-isolated, idempotent repair and bounded rollback tested on disposable Neo4j. |
| A4 | Actual/unknown service dates, observation/recording/belief times and evidence survive normalization/persistence/API; real replacement/departure/name-change/profile fixtures and temporal graph regressions. |
| A5 | Bounded page/byte/time/retry acquisition, durable archived-page resume, fresh consistency recheck, cycle/count/empty/overflow failures and no failed coverage checkpoint advancement. |
| A6 | Authenticated coverage/member reads report missing/failed/partial/unverified/stale scopes and exact persisted sets; generic desktop HTTP coverage/evidence navigation and late-reply handling tested. |
| A7 — OPEN | Static guards and five complete lanes pass (1,397 tests); runtime-stack fails during fixture startup because the disk is full. Requires a complete new passing frozen candidate on sufficient storage. |
| A8 | Maintained design/specifications/roadmaps, generated operations/runtime docs, config example, source register and migration/identity-review/operator handoff reconciled; limits explicit. |

Latest full candidate command: `venv/bin/python tools/qualify.py --output
work/be56/candidate-qualified`. Report, source map, JUnit and logs remain in that
ignored directory; report status is **failed**. Revision is the base; working-tree
content is identified by source SHA-256
**`dcf95004dd76338ca9e6bdbd6f36108420ae53e0e8a589775ba8a2baca0a69a7`** over the runner’s declared paths, including untracked
code/tests/fixtures. A separate post-run comparison against `source.json` confirmed
that source remained unchanged; the runner itself exits on the failed lane before
its final source comparison.

Started `2026-11-07T19:24:46.247786+00:00`; finished `2026-11-07T19:35:00.760801+00:00`;
validation wall time **614.511 seconds**. Baseline, runtime/tool
lint, mypy, documentation consistency, generated docs, architecture/security guards
and whitespace checks all pass. Each passing lane has zero failures/errors/skips.
The table describes this candidate only, not cumulative development passes.

| Lane | Tests | Result | Runner wall seconds |
|---|---:|---|---:|
| unit | 977 | passed | 161.284 |
| desktop | 149 | passed | 7.455 |
| integration | 183 | passed | 295.914 |
| acceptance | 85 | passed | 51.556 |
| desktop-integration | 3 | passed | 29.019 |
| runtime-stack | 1 failed | failed | 67.643 |

Runtime failure: `docker compose … up --wait` could not initialize the disposable
three-service stack. A bounded reproduction using its generated Compose fixture
failed while creating the models volume with the daemon error **`no space left on
device`**. Diagnostic: `work/be56/runtime-storage-diagnosis.log`. `df` showed the
7.9 GiB filesystem at 100% with zero available space. Unused build-cache cleanup
alone was insufficient; removing only the failed fixture’s unused API/worker test
images restored 6.2 GiB free. Configured application containers/images were retained.
Rebuilding those VFS images would recreate the peak storage requirement. No daemon
replacement, storage-driver change, production operation or test bypass was attempted.

Earlier attempts remain distinct and preserved: `candidate-authoritative` was
interrupted to correct a later-replay/belief-time status defect (graph regression
passes). `candidate-final` was interrupted after obsolete ontology/registry test
expectations were found; affected API preflight (7 tests) and separate acceptance
preflight (85 tests) then passed. `candidate-complete` had 182 passing integration
tests and a backup HTTP 503 while abandoned disposable containers from the earlier
interruption remained. Ownership was verified and only those fixtures were removed.
The unchanged isolated backup/restore diagnostic passed, recovering the original
marker and 1,000 workload rows; the latest candidate subsequently passed all 183
integration tests including physical backup/restore. This does not establish a
unique root cause for the earlier 503. An early combined integration/acceptance
preflight hit their known duplicate-plugin conflict; canonical lanes run separately.
Existing library deprecation warnings remain in logs. Failed reports are not
relabeled successful and earlier passes do not substitute for A7.

### Change accounting against live main

| Category | Files | Added text lines | Deleted text lines | Net text lines | New compressed bytes |
|---|---:|---:|---:|---:|---:|
| handwritten documentation | 12 | 480 | 66 | 414 | 0 |
| handwritten implementation/configuration/ontology/renderer | 39 | 2562 | 188 | 2374 | 0 |
| tests/helpers | 25 | 862 | 187 | 675 | 0 |
| generated documentation | 2 | 26 | 0 | 26 | 0 |
| source fixtures | 350 | 4262 | 0 | 4262 | 4060857 |

There are 15 net additional test functions and four rewritten DIP contract tests.
Parametrized official-source cases share invariant coverage rather than copying
21 suites. Compressed source bytes and fixture metadata are separate from code.
Implementation effort was not independently timed; timings above measure validation
only. At qualification time, no staging, commit, push or PR was requested or
performed; publication is authorized by the subsequent request below.

### Operator and measurement boundary

No production ingestion, migration, paid inference or deployment was run. Coverage
reads never acquire data. Production requires explicit backup, 1.4/DIP data repair,
configured DIP key and NL prompt 1.1.0, then separately submitted source jobs and
dated per-scope reconciliation. Unknown dates remain unknown; a directory without
an independent serving count remains unverified. Missing/stale/unresolved/failed
scopes prevent a reconciled national claim. OPEN_ISSUES retains unrelated external
obligations and records the current storage blocker. Resume on sufficient storage
with a fresh live-main check, preserve this diff and run the complete canonical
qualification command; only then close A7 and claim full local acceptance.

Publication update: the user requests preparing and opening a PR for this full
session’s implementation. Staging, commit, push and draft PR creation are now
authorized. Rechecked live main at `d967bae244dc`; the declared source fingerprint
still matches the tested candidate. Only publication/disposition documentation
changed afterward, checked with documentation/generated/whitespace guards. The
user confirms larger storage is unavailable; A7 remains open with no acceptance
waiver. Production actions and merge remain outside this request.

## 2026-11-07 — BE-56 parliamentary/federal-officeholder planning documentation

Documentation-only delivery on checkout branch `work`, based on live-fetched main
`7c7be13dc74d4c8613f4507ec8b8b8f708c83955`. `python3 tools/check_git_baseline.py`
passed before edits; publication guard was already configured as `.githooks`.
[Next-session implementation plan](GERMAN_PARLIAMENT_MEMBERS.md) defines the full
BE-56 package and eight uncompleted implementation acceptance items. Design and
technical scope, both roadmaps, delivery/index navigation, D-97 and CHANGELOG
are reconciled. The source-discovery matrix includes Bundestag, all 16 states,
both Bundesverfassungsgericht Senates, Bundesrat regular/deputy members and the
serving Bundespräsident/Bundespräsidentin (21 coverage scopes);
city-state coverage, canonical identity reuse, mandate dates, party/group semantics,
legacy DIP migration and per-scope completeness are explicit. The requested scope
extension preserves judicial Senate assignment, represented Land/member class and
presidential tenure without imposing parliamentary terms on other institutions.

Validation: `python3 tools/check_docs.py docs/`,
`python3 tools/generate_runtime_docs.py --check` and `git diff --check` pass.
Reviewed the change against the fetched baseline and the existing DIP/ontology
contracts. All changed files are handwritten documentation; no runtime, test,
fixture or generated-file change. Runtime suites were not needed for this scope.
Source portals are discovery references, not tested roster endpoints. No member
acquisition, loaded-roster completeness, implementation, migration, deployment or
paid-quality result is claimed. Implementation is reserved for the next session.

Publication update: the user requests a PR for this session's documentation.
Publication branch `codex/be-56-public-officeholder-planning` is created after a
fresh successful baseline fetch at the same main revision. Recheck documentation,
generated-document consistency and whitespace before committing; retain the live
pre-push baseline hook. Staging, commit, push and PR creation are now authorized;
runtime implementation, roster acquisition, deployment and merge remain separate.

## 2026-11-05 — PR #24 conflict reconciliation

Reconciled BE-55 with live main `66aecffae9ee` (merged BE-54 / PR #23).
Preserved both packages' changelog, decisions, issue dispositions, roadmap and
original frozen verification records; replaced the stale BE-54 roadmap placeholder.
Runtime and test files merge without conflicts. This reconciliation passes docs
C1–C9, generated-doc drift, shared G1–G4 guards and whitespace checks.
Focused window/OSM/schema tests: 59 passed; extractor/pipeline tests: 44 passed.
These 103 unit passes validate the combined branch's affected behavior; they are
not a new full frozen candidate or evidence of live source coverage. No deployment,
production acquisition or paid call was performed. The user authorizes committing
and pushing this reconciliation to PR #24's existing branch.

## 2026-11-04 — BE-55 authoritative frozen candidate

[Acceptance checklist, cursor contract and operator handoff](GDELT_BACKLOG_OSM_LEAVES.md).
Branch `codex/be-55-gdelt-backlog-and-osm-leaves`, live base `029f2fceea1d`.
Report `work/be55/candidate-authoritative/report.json`: passed. Source SHA-256
`2be5d9079f8efbd5ff2f87b47bc6b34306997d76de62959d374e070f38a29d73`.
Source stability passes after every lane; subsequent changes are handwritten docs.

| Lane | Passing cases | Elapsed seconds |
|---|---:|---:|
| unit | 942 | 160.6 |
| desktop | 147 | 11.383 |
| integration | 177 | 356.149 |
| acceptance | 85 | 83.821 |
| desktop-integration | 3 | 36.146 |
| runtime-stack | 1 | 103.702 |

All 1,355 cumulative cases pass with zero failures/errors/skips. Seven new cases;
no copied suites or new CI lanes. Shared baseline/lint/tools-lint/types/docs/
generated/G1–G4/whitespace guards pass. Validation elapsed 754.095 seconds;
implementation effort and merge latency are not inferred. Affected checks before
freeze: 79 units, 8 graph integration cases. The new GDELT fixture initially used
an invalid ZIP member name; corrected to the official timestamp filename. Initial
unit startup lacked libEGL; existing ignored Qt libraries resolved it. No failed
check was skipped. `work/be55/candidate-final/report.json` remains a failed
preflight (renderer line length, before test lanes); wrapping/regeneration preceded
the authoritative freeze. Exact invocation and environment are in the handoff.
Live main remained unchanged at final recheck. Tests use mocked source/model
transports and fixture-owned disposable graphs/runtime. No live acquisition, paid
call, operator graph write, deployment or push. Existing deployed GDELT lost-anchor
and upstream OSM capacity obligations remain explicit; local success is not
historical coverage or live source qualification.

## 2026-11-04 — BE-54 extraction span geometry, iteration two

Complete local implementation acceptance and full frozen candidate pass on
`codex/be-54-extraction-span-geometry`, verified live main `029f2fceea1d`.
[Acceptance mapping, diagnosis and operator obligations](EXTRACTION_SPAN_GEOMETRY.md).
The operator poll file resides at the report root rather than evidence/; its
11 concatenated snapshots show four copies of one unique second-item rejection,
not independently evidenced failures across documents.

Authoritative report: `work/be54/candidate-final/report.json`, status passed.
Exact source manifest: `work/be54/candidate-final/source.json`, SHA-256
`d1856c62694cef500c05e2e4d63ffbe1d77b81ed2320de2d17454b61d750393b`.
All 444 manifest files match the review checkout before/after qualification;
subsequent edits are handwritten documentation only. Public settings-example hash
(outside the runner manifest):
`fd3b00bf863032f37cbda5194ff1b7de54369a26924a189dab863130485e82c5`.

| Lane | Passed cases | Lane elapsed seconds |
|---|---:|---:|
| unit | 938 | 163.646 |
| desktop | 147 | 11.020 |
| integration | 176 | 384.717 |
| acceptance | 85 | 91.715 |
| desktop-integration | 3 | 48.570 |
| runtime-stack | 1 | 126.220 |

All **1,350 cumulative cases** pass with zero failures/errors/skips. Two new tests
cover the observed overflow and shared Unicode/batch geometry; existing archive
and provenance cases are updated. Baseline, lint/types, docs/generated drift,
C1–C9/G1–G4, whitespace and final source stability pass. Full candidate validation
latency: **828.681 seconds**; implementation effort and merge delay
are not inferred. Existing deprecation/runpy warnings remain visible in logs.

Affected development checks: 58 unit cases (36.03 s), nine disposable feeds graph
cases (50.00 s), shared guards, lint and types passed before final qualification.
The candidate began its static/unit lanes while the affected graph run finished;
its own graph lane ran later, sequentially with the remaining full suites.
Earlier development attempts stopped before collection for missing libEGL, then
failed one new fixture's incorrect 44-character expectation; corrected to the
independently counted 43 before freeze. The ignored BE-53 Qt library bundle and
canonical frozen venv were reused; see the handoff for invocation.

Change accounting against main (additions/deletions/net): handwritten runtime
Python **44/15/+29**; versioned handwritten prompt **58/0/+58**; tests/helpers
**76/6/+70**; public configuration example **2/2/0**. Other changes are handwritten
documentation. No generated files, fixture data, ontology, dependency, model pin,
reasoning setting, CI workflow or existing settings/secrets file changed.
No paid provider call, source acquisition, production data mutation, deployment,
push or merge occurred. Prompt/schema 1.2.0 is locally qualified; live rejection
rates remain OI-32/operator evidence, requiring explicit pins and redeployment.


## 2026-11-04 — BE-53 authoritative integrated candidate

Complete local acceptance and qualification pass after reconciliation onto live
main `06bbfb47134e` (PR #21 merged during standalone verification). The original
`4ef67c8` standalone result below proves no BE-52 implementation dependency.
[Handoff and cursor/merge implications](OSM_TRANSPORT_POLICY.md).

Report: `work/be53/candidate-integrated-final/report.json`, status passed.
Manifest SHA-256:
`1b0114367718110e68c541fa6e3748e78b8f28a46db0df4eb46e579465bcdbbb`.
Source unchanged after all lanes; subsequent edits are handwritten documentation.
Public settings-example SHA-256:
`d839019401ba227345bb83d7900edf46c4495644750abe6ab7a617b859d0c2d8`.

| Lane | Passed cases | Lane elapsed seconds |
|---|---:|---:|
| Backend unit | 936 | 159.617 |
| Desktop unit/contract | 147 | 10.646 |
| Disposable graph integration | 176 | 390.886 |
| Acceptance | 85 | 84.473 |
| Desktop integration | 3 | 42.334 |
| Isolated three-service runtime | 1 | 123.339 |

1,348 cumulative passes, zero failures/errors/skips; 11 new BE-53 cases.
All baseline/lint/types/docs/generated/G1–G4/whitespace/source-stability guards pass.
Final validation latency 813.700 seconds, separate from implementation and merge.
Earlier integrated report stopped at 175 graph passes/one failure because the
BE-52 fixture loaded a local 1.0.0 pin but expected 1.1.0. Its factory now disables
env-file loading; 9 affected cases passed before final freeze. The failed report
remains retained; no assertion, runtime pin or provider default was weakened.
The original standalone run and its earlier env-file failures remain below.
Requalification was necessary because main advanced and then fixture isolation
changed. No production acquisition, paid call, deployment, push or merge occurred.

## 2026-11-04 — BE-53 standalone qualification before main advanced

[Full acceptance, operator policy and PR #21 overlap](OSM_TRANSPORT_POLICY.md).
Live base `4ef67c89ae67`, branch `codex/be-53-feed-and-osm-transport`.
Standalone `work/be53/candidate-final/report.json` passes, source SHA-256
`463d4e2234cc5c513bd119dbb6c8fb708a2bfe862436d1ae53d9d1fdac1ecc4a`.
Manifest unchanged after all checks; subsequent edits are handwritten documentation.

| Lane | Passed cases | Lane elapsed seconds |
|---|---:|---:|
| Backend unit | 927 | 161.957 |
| Desktop unit/contract | 147 | 11.817 |
| Disposable graph integration | 176 | 420.653 |
| Acceptance | 85 | 103.971 |
| Desktop integration | 3 | 39.355 |
| Isolated three-service runtime | 1 | 119.718 |

All 1,339 cumulative cases pass without failures/errors/skips. Eleven new mocked
transport/configuration cases cover distinct policy paths; existing acquisition
coverage protects locks, complete-before-load and graph replay. Lint/types,
docs/generated-doc drift, G1–G4, baseline, whitespace and source stability pass.
Total validation latency: 859.134 seconds, not implementation or merge effort.
No live source/model acquisition, production change, push or deployment.
This candidate qualifies on the larger overlayfs executor; earlier candidate disk
failures remain historical evidence, not retroactively passed runs.

Initial candidate stopped with 925 unit passes and two unrelated failures caused
by test factories loading local env files. Explicit `_env_file=None` isolation
corrected them; focused recheck passed 39 cases before final freeze. Missing Qt
libraries were extracted to ignored work/ and supplied via LD_LIBRARY_PATH.
Exact invocation/environment, affected checks and retained reports are in the
linked handoff. Full manual/operator coverage and upstream capacity remain separate.

BE-52 merged as `06bbfb47134e` during final baseline verification. The branch was
fast-forwarded and overlaps reconciled under the standing live-main contract.
Integrated qualification now passes as recorded above; standalone evidence is preserved.

## 2026-11-04 — BE-52 ingest source repair

Complete local implementation acceptance and full disposable qualification pass.
Live base `4ef67c89ae67`, branch `codex/be-52-ingest-source-repair`.
[Acceptance mapping and operator handoff](INGEST_SOURCE_REPAIR.md) covers the full
parent: partial feeds/checkpoints, ontology-constrained versioned extraction with
preserved rejection archives, and bounded TED/FSD transport diagnostics.

Authoritative frozen candidate: `work/be52/candidate-3/report.json`, exact manifest
`work/be52/candidate-3/source.json`, SHA-256
`5a339c1e64b9dd0f5f671a69ef23ee90f104bcf640b59b22483c5b61b4eb9c43`.
All 442 implementation/verification files matched the review checkout before and
after qualification. The configuration example (outside the runner's normal
manifest paths) also matched exactly, SHA-256
`c1cfe37144dd5339fce33f5badc318aa02241dfd895323af02bedbfabf7901e0`.
Only handoff/specification/ledger documentation changes followed the final freeze.

| Candidate lane | Result | Check elapsed |
|---|---|---|
| Live baseline, runtime/tool lint, types, docs/generated docs, shared guards, whitespace | Passed | Individual times in report |
| Backend unit | 925 passed | 157.234 s |
| Desktop unit/contract | 147 passed | 10.373 s |
| Graph integration | 176 passed | 385.426 s |
| Acceptance (separate collection) | 85 passed | 87.389 s |
| Desktop integration | 3 passed | 42.109 s |
| Three-service runtime stack | 1 passed | 129.813 s |

Total: **1,337 cases, no failures/errors/skips**. Final candidate validation took
813.981 seconds; this is not implementation effort or merge latency. Implementation
effort was not separately timed; no push/PR/merge/deployment was requested or done.
The candidate used the canonical `venv/`, disposable graphs and mocked model/source
transports. Existing co-tenant services/data were not selected by graph tests.
Fixture containers/volumes were removed by their own teardowns. The larger executor
had about 42 GB free with overlayfs, unlike the historical 7.9 GB vfs executor.
This current descendant candidate passes runtime qualification; older BE-48/49/50/51
failed reports remain failed historical evidence, not retroactively green runs.

Development evidence: 137 affected unit cases passed (36.26 s); lint, mypy and
shared C1–C9/G1–G4 guards passed. The focused clean recheck of prior failing unit
cases/shared transport coverage passed 20 cases (2.28 s), and the default-version
feeds graph scenario passed (28.10 s). These are separate checks, not added to the
final candidate total. Nine new parameterized unit cases cover distinct behaviors;
existing rejection-archive coverage now checks the observed ontology/span reasons,
and the existing end-to-end feeds graph assertion expects provenance 1.1.0.

Earlier attempts are retained, not accepted: candidate 1 stopped at backend unit
with four failures (162.934 s). Two came from default Settings reading ignored local
configuration (missing-backup-credential and optional-inference-default cases);
the unexpected backup connection attempt failed to connect. The other two were
new log-capture assertions affected by cached loggers after CLI initialization.
Their capture now binds a fresh logger. Candidate 2 used an isolated detached
checkout with no local configuration files and passed units/desktop, but stopped
at graph integration because an existing test expected provenance 1.0.0 instead
of the new default 1.1.0 (580.118 s). Only that fixture expectation/comment changed
before candidate 3; numerical expectations and behavioral checks were preserved.
No paid call or live source ingestion was executed. No configuration/secret/model
pin files were edited or their contents printed.

The authoritative run used `/tmp/limes-be52-qualification` (exact source diff
verified against the review workspace); reports/manifests/logs/JUnit were copied
back to `work/be52/`. Both checkouts were synced with
`UV_PROJECT_ENVIRONMENT=venv uv sync --frozen --all-packages`. Qt initially lacked
system libraries, and sudo installation was unavailable. CI's library packages
were downloaded/extracted under `/tmp/be52-qt-libs`; the run inherited
`LD_LIBRARY_PATH=/tmp/be52-qt-libs/root/usr/lib/x86_64-linux-gnu` plus headless Qt
and Chromium flags from the existing runner. No missing-library check was skipped.

Workflow correction: begin future qualification in a clean checkout, and test new
structured-log assertions after CLI logger setup before freezing. Search fixed
provenance expectations when changing defaults. These repeated corrections are
recorded within BE-52, without splitting its delivery boundary or adding CI lanes,
fixed quotas or duplicate test suites. Existing independent CI lanes and the stable
fail-closed required status remain unchanged; hosted execution is not claimed.

Change accounting against live main (additions/deletions/net): handwritten Python
runtime **69/24/+45**; versioned prompt assets **111/0/+111**; tests/helpers
**139/12/+127**; configuration example **2/2/0**. Handwritten documentation **301/4/+297**.
No fixture data, generated artifacts, dependencies, ontology, endpoints, credentials,
service topology or production model pins changed. Full-runtime acceptance does
not establish deployed feed success, reduced live rejection rates, TED/FSD recovery,
OSM capacity/timeout policy or historical corpus completeness. Existing explicitly
pinned deployments must opt into paired extraction versions 1.1.0; URL disposition
remains with the operator/owner. OI-26/28/30 retain the appropriate external gaps.


## 2026-11-04 — BE-51 dedicated embedding credential

Implementation and affected verification pass; **full runtime qualification is
blocked by executor disk capacity**. Live base `6f77a00ec9b4`, branch
`codex/be-51-dedicated-embedding-credential`. [Acceptance and operator handoff](EMBEDDING_CREDENTIALS.md)
map dedicated secret parsing/masking, no credential fallback, per-role HTTP
routing, embedding catalogue pricing/cache isolation and bounded guardrail errors.
The default logging redactor explicitly includes the new credential name.

Frozen candidate: `work/be51/candidate-4/report.json`, source manifest
`work/be51/candidate-4/source.json`, SHA-256
`ab7bbac034fb56e92fb9897fa47f79f51e58d24a0cdd469f4ff1b14dbb4df38a`.
The complete manifest was rechecked unchanged after the failed runtime lane.
Only handoff documentation changed after this freeze.

| Candidate lane | Result | Check elapsed |
|---|---|---|
| Live baseline, lint, types, docs/generated docs, guards, whitespace | Passed | Individual times in report |
| Backend unit | 916 passed, no failures/errors/skips | 151.158 s |
| Desktop unit/contract | 147 passed, no failures/errors/skips | 7.940 s |
| Graph integration | 176 passed, no failures/errors/skips | 248.342 s |
| Acceptance | 85 passed, no failures/errors/skips | 51.079 s |
| Desktop integration | 3 passed, no failures/errors/skips | 28.880 s |
| Three-service runtime stack | Failed during container creation | 188.468 s |

Total: **1,327 passing cases and one failed runtime-stack case**. Candidate
validation took 678.702 seconds, not implementation or merge latency. A direct
repeat of the fixture's Compose startup captured
`Error response from daemon: no space left on device` creating its Neo4j
container (`work/be51/runtime-diagnostic.log`). Images built successfully, but
container filesystems exceed this 7.9-GB executor with the `vfs` storage driver.
The fixture project and reproduction containers/volumes were removed. Only the
three test image tags and unused build cache were cleaned; free space recovered
to 5.8 GB. The CLI cache cleanup itself could not create its config directory
on the full filesystem; the equivalent local daemon build-prune operation
completed cleanup. Storage driver and production resources were not changed.
Repeat the full frozen candidate on an adequately sized executor; no runtime
acceptance or deployed-success claim is made.

Earlier reports remain retained: candidate 1 exposed 12 integration failures
from old shared-key fixtures; candidate 2 passed graph integration but exposed
four acceptance failures from catalogue mocks embedded in subprocess scripts.
Those fixtures now use separate fake credentials and mock `/embeddings/models`;
no acceptance assertion or guard was relaxed. The affected integration recheck
passes 16 cases; the complete acceptance recheck passes 85. Candidate 3 was
explicitly interrupted before adding the new name to the default secret redactor;
its report is not accepted evidence. The final candidate includes that correction.

Change accounting against live main (additions/deletions/net): handwritten runtime
**73/16/+57**; tests/helpers **129/5/+124**; handwritten runtime-doc renderer
**14/1/+13**; generated operations documentation **14/1/+13**. Six new
unit cases cover distinct credential/configuration, role-pricing and policy-error
behaviors; the existing logging test now checks the new secret name and nested
field. Existing integration/acceptance transport fixtures were updated, without
adding repeated behavior suites. Other changes are configuration-example and
handwritten documentation. No fixture data, dependency, ontology, model pin,
vector index, ER threshold, node stamp or ledger schema changed.

No provider call, production ingestion, VPS secret edit, staging, commit, push,
PR, merge or deployment occurred. The operator must create/supply the dedicated
workspace key and separately authorize the production embedding/ledger probe.
OI-29 retains full-runtime qualification and live embedding/feeds evidence.


Publication update (2026-11-04): the user authorized preparing and opening the
session PR, including staging, commit and push. The reviewed runtime/test source
still matches candidate 4's manifest. Publish as a draft with the runtime-stack
failure retained; publication is not full acceptance or deployment evidence.


## 2026-10-31 — BE-50 adaptive OSM acquisition

Live base `54c6a1a3efa2`, branch `codex/be-50-adaptive-osm-acquisition`.
[Acceptance mapping](OSM_ADAPTIVE_ACQUISITION.md) defines the complete package.
Affected development checks: 43 adapter/pipeline unit cases and two disposable
Neo4j acquisition lifecycle cases pass; lint and types pass. Five new unit cases
and one new graph case cover distinct adaptive behavior. Two earlier incomplete
response regressions initially failed because their dummy query could not split;
the fixtures now use a real bbox with subdivision disabled to test terminal
failure separately. The source classification does not relax payload validation.

Frozen candidate `work/be50/candidate-1/report.json` failed only its isolated
runtime-stack lane. Source manifest SHA-256:
`cf2423403980a624ba21be7a3f42079b2e86f42541c8b687aaa3210256e6c818`.
No production data, paid inference, staging, commit, publication or deployment.


| Candidate check | Result | Duration |
|---|---|---|
| Baseline, lint, types, docs, generated docs, guards, whitespace | Passed | Individual times in report |
| Backend unit | 910 passed | 149.583 s |
| Desktop unit/contract | 147 passed | 8.863 s |
| Graph integration | 176 passed | 229.573 s |
| Acceptance | 85 passed | 44.624 s |
| Desktop integration | 3 passed | 24.442 s |
| Three-service runtime stack | Failed creating container filesystem | 65.738 s |

Total: 1,321 passing cases and one failed runtime-stack case; 524.298 seconds
candidate validation, not implementation/merge latency. Exact source manifest was
rechecked unchanged after the failure. A separate reproduction saved Compose stderr
in `work/be50/runtime-diagnostic.log`: `Error response from daemon: no space left
on device` creating the disposable Neo4j container. Disk reached 100% of 7.9 GB.
Test project containers/volumes, three test image tags and unused build cache were
removed; free space recovered to 5.8 GB. No storage driver or production resources
were changed. Full qualification requires an adequately sized executor.

Runtime additions/deletions/net: 83/16/+67 lines. Tests: 131/3/+128 lines,
including five new parameterized unit cases and one graph case; other changes are
handwritten documentation. No fixture data, generated files, dependency, ontology,
Dockerfile, service, config key or deployment changes. OI-28 remains open for full
runtime qualification and live deployment/capacity evidence.


## 2026-10-31 — BE-49 third-ingest repair

Implementation and affected source/graph checks pass; **full runtime qualification
remains blocked by executor storage**. Branch `codex/be-49-third-ingest-repair`,
verified live-main `d5abd10fc055`. [Acceptance mapping](INGEST_THIRD_RUN_REPAIR.md)
covers the complete requested repair and its external evidence boundaries.

Final frozen candidate: `work/be49/candidate-2/report.json`, source manifest
`work/be49/candidate-2/source.json`, SHA-256
`a4608e6d217319d55968fa15b21d99450f7b92a0988f585c8fe022ccfc0cf4a0`.
No runtime/test source edits followed this candidate. The full attempt took
508.580 seconds; implementation and merge latency are not measured by that time.

| Check | Result | Duration |
|---|---|---|
| Live baseline, runtime/tool lint, types, docs, generated docs, shared guards, whitespace | Passed | Recorded individually in candidate report |
| Backend unit | 905 passed, no failures/errors/skips | 138.596 s |
| Desktop unit/contract | 147 passed, no failures/errors/skips | 7.350 s |
| Graph integration (separate from runtime-stack) | 175 passed, no failures/errors/skips | 225.818 s |
| Acceptance | 85 passed, no failures/errors/skips | 48.588 s |
| Desktop integration | 3 passed, no failures/errors/skips | 25.014 s |
| Isolated three-service runtime stack | Failed during Compose container creation | 62.118 s |

This is **1,315 passing cases plus one failed runtime-stack case**, not a green full
candidate. Candidate 1 was deliberately interrupted during the unit lane to fix
the cursor-retirement crash window; its failed report is retained. Earlier affected
checks passed 60 unit cases and 10 graph/composition cases. The first combined
graph development check exposed missing teardown in the new test; that fixture was
repaired before final qualification. No failures are hidden by cumulative counts.

The short pytest output did not expose Compose stderr. Repeating the exact
fixture Compose startup showed:

```text
Container limes-runtime-test-fa1cb9570f92-api-1  Error response from daemon: no space left on device
Error response from daemon: no space left on device
```

Docker reports `storage_driver=vfs`; the executor filesystem is 7.9 GB. Before
runtime builds it had approximately 6.1 GB free; after the test images were built,
about 950 MB remained, and creating the three container filesystems exhausted it.
The fixture containers/volumes were removed. Retired test images and unused build
cache were cleaned; clearing unused cache alone did not provide the needed space.
The newly built API/worker test images were then removed to recover workspace
capacity. The storage driver was not changed. Run the complete frozen candidate on
an adequately sized executor; no passing runtime/deployment claim is made here.

Change accounting against live main (additions/deletions/net): handwritten runtime
**308/38/+270**, tests/helpers **343/20/+323**. There are 16 added parameterized
unit cases and one new end-to-end graph case; existing request fixtures and shared
constructor coverage are corrected/extended. No fixture data, generated artifacts,
ontology schema, Dockerfile, dependency, config key or CI lane changed.
Documentation records the selected parent, supplied operator evidence, acceptance
mapping, verification and remaining blockers separately from handwritten runtime.

No paid inference, production source run, operator graph/config mutation, staging,
commit, push, PR, merge or deployment occurred. Operator-reported BE-48 deployment
and Transparency success remain supplied evidence; TED/FSD availability, nationwide
OSM capacity, GDELT backlog and any legacy numeric OSM identity migration are not
certified by these fixtures. OI-27/OI-28 retain full qualification blockers.



Publication update (2026-10-31): the user authorized preparing and opening the
session PR. The reviewed runtime/test source still matches the frozen manifest.
The draft PR preserves the runtime-stack failure; staging, commit and push do not
turn this candidate into full passing qualification.

## 2026-10-31 — BE-48 second full-ingest repair

Implementation verified locally; **full runtime qualification remains blocked**.
Branch `codex/be-48-ingest-rerun-repair`, live-main base `a0ec26f92c7e`.
[Acceptance mapping and limitations](INGEST_RERUN_REPAIR.md) cover the whole parent.
Final source digest: `aeb3b835d3276c98a6ab991f27d96567b9ce1346b8f21a0a63b76e77c04d2586`; final source manifest is unchanged
from `work/be48/candidate-3/source.json`.

- Static/type/docs/generated/shared guards pass.
- Backend unit: 889 passed; desktop unit/contract: 147 passed.
- Graph integration: 173 passed, with one backup test failing under storage
  pressure. That same backup/recovery test subsequently passed in isolation
  (`work/be48/backup-final.xml`, 120.50 s) after test-image cleanup.
- Acceptance: 85 passed (`work/be48/acceptance.xml`); desktop integration:
  3 passed (`work/be48/desktop-integration.xml`).
- Mandatory runtime-stack recheck fails during worker dependency installation:
  language-model wheel extraction reports `No space left on device (os error 28)`
  (`work/be48/runtime-isolated.log`). Earlier Neo4j startup and backup restore
  failures independently report the same storage exhaustion. These are not a
  green full candidate. Retain all three failed candidate reports and isolated
  rechecks; repeat the complete candidate on an executor with enough free disk.

Change accounting against live main (additions/deletions/net): handwritten
runtime **132/13/+119**; unit regressions **129/4/+125**; integration helpers
**14/1/+13**; qualification runner **4/1/+3**; CI **3/1/+2**; feed configuration
**1/1/0**. No fixture data or generated artifacts changed. Documentation separately
records the acceptance mapping, issue disposition, decision and validation evidence.
These line counts describe change size, not engineering time or acceptance.

Ten added regression cases cover distinct wire-schema, feed-continuation,
server-cooldown and XML-integrity behaviors. Existing parser/ontology/evidence,
cache/checkpoint and graph suites remain in force. No paid inference, operator
source ingestion, production graph/config write, staging, commit, push or
publication occurred. FSD/OSM availability and full operator law coverage remain
external evidence; the operator identifies OpenCode Go as inference provider.


Publication update (2026-10-31): the user authorized preparing and opening the
session PR. Runtime/test/CI source still matches the recorded candidate manifest;
publication does not turn the disk-blocked runtime check into passing evidence.

## 2026-10-29 — DC-14 desktop correctness and local qualification

The complete DC-14 implementation and bounded local qualification are accepted.
OI-10/11/18 close with direct behavior evidence and D-86's conforming local-map
policy. [DESKTOP_QUALIFICATION](DESKTOP_QUALIFICATION.md) records the current
source re-review and every grouped functional requirement, NFR and AC disposition.
External Ubuntu reference/manual deployment evidence and the absent original
review log remain REF-DC-1, DEP-DC-1 and HIST-DC-1; they are not claimed or waived.

Branch `codex/dc-14-desktop-qualification`, live-fetched and fast-forwarded base
`a434adc0fe4b195338a1a772ccafc89e24469a9b`. The required baseline check and local
publication hook were installed before coding. Canonical frozen all-package venv
was synchronized. No staging, commit, push, PR, production ingestion, paid model
run or deployment is requested/performed by this implementation delivery.

Authoritative final command: `venv/bin/python tools/qualify.py --output work/dc14/final-2`.
It passed in **958.171s** with all five suites, zero failures,
errors or skips, and no source drift. The report, exact commands, logs, durations,
JUnit and complete source mappings are in ignored `work/dc14/final-2/`.
Source manifest SHA-256: `446d8b41c3cb31505b3ebdf7bba3027a394022a7d25062d4adb36ed411328fbe`.
The manifest includes tracked and untracked runtime, tests, assets, tools, CI,
fixtures, ontology and dependency/runtime files. Handoff-only documentation changes
follow the source freeze; qualified runtime/test/tool sources remain unchanged.

| Suite | Result | Command elapsed | JUnit under work/dc14/final-2 |
|---|---:|---:|---|
| unit | 857 passed | 164.999s | unit.xml |
| desktop | 147 passed | 18.281s | desktop.xml |
| integration | 173 passed | 642.129s | integration.xml |
| acceptance | 85 passed | 83.571s | acceptance.xml |
| desktop-integration | 3 passed | 46.918s | desktop-integration.xml |

The total 1,265 passes is cumulative evidence, not a quota. Shared runtime/tools
Ruff, strict mypy (169 source files), C1–C9 docs, generated-document consistency,
static runtime guards, live baseline and whitespace also pass. Existing backend
unit warnings (3) and Starlette deprecation warnings remain. The desktop lane adds
one pytest warning about record_property/xunit2 compatibility; its actual startup
property is present in the retained XML and was checked directly.

### Acceptance mapping

- Builder refill now preserves valid relation/direction/target choices, resets
  invalid choices deterministically and propagates every upstream change through
  all later hops. Submission rechecks the entire chain. The invented self-both and
  multi-hop regression complements independent exact schema/supertype expectations.
- The actual Leaflet map uses finite correctly ordered LatLng points and selected
  relations, with explicit no-basemap/missing-geometry labels. No tile provider is
  registered. Each off-the-record WebEngine profile installs its bundled-resource
  guard before first page load. Real shipped network/map/timeline pages render,
  call registered Qt slots and reject a deliberate external resource even when
  Qt's separate remote-content restriction is relaxed by the test. HTTP client
  redirects stay within the configured origin, including tokenless requests.
- Shared selection and independent validity/belief filters redraw retained original
  results without mutating history. Validity intervals, UTC offsets, belief
  retraction and unknown dates are distinct. Incremental expansion retains prior
  data and coverage. Cold shell imports-to-typed-search measured **0.807026s**
  in a fresh process on **Debian 13/offscreen**, with WebEngine core/widgets still
  absent. Slow and old-profile probes exercise responsiveness and recovery.
  This measurement does not certify the Ubuntu reference-machine ≤3s requirement.
- Existing views are reachable from navigation; saved-query capture retains the
  last query surface across library navigation. Actual widgets exercise search,
  entity/assertion provenance, expansion, NLQ/editable re-run, builder, console,
  manual save/delete and empty diagnosis through the authenticated API and
  disposable graph. Repeating the same NL question succeeds twice and records
  two execution-history entries; manual duplicate-save protection remains intact.
- Backup starts disabled until capability/connection evidence permits it. Visible
  consequences precede the single deliberate UUID submission; output, job ID/dump
  and actual post-backup health are retained. A degraded response is not labeled
  healthy. No failed operation is automatically replayed. Existing full-suite
  physical recovery still verifies restored synthetic graph contents independently
  of the mocked desktop job runner. Actual administrator-deployment/desktop backup
  observation remains DEP-DC-1, not inferred from those fixtures.

### Failed candidate and workflow review

The first full candidate `work/dc14/final/` failed closed after its four earlier
lanes passed and the new real-widget scenario reused an earlier scenario's NL
question/Cypher. Automatic history called the manual duplicate guard and raised
DuplicateSavedQuery, a real repeat-query defect. This is not accepted evidence
for the final source. The failure report/logs and original source manifest remain
retained (source SHA-256 `de7f309f428c403632f08b26dd3ab7d522ce2f6d5d63f4bc09971fc3cd64460b`).
The correction preserves the existing per-execution history contract: automatic
history permits repeated pairs, while manual creation still rejects duplicates.
The widget uses a distinct scenario question and explicitly executes it twice.
Affected desktop integration plus manual saved-query integration passed (6 cases)
before the final freeze. Only query.py, saved_queries.py and the widget integration
source differ between the failed and passing candidate manifests.

Eight new cases cover distinct behaviors: six desktop qualification regressions,
one confirmation/job-result regression, and one actual-widget graph/API scenario.
Existing tests are updated for corrected coordinates, async probes, origin policy
and fresh-process startup evidence. No copied backend suite or fixed count target
is introduced. Existing independent CI lanes and required candidate gate remain
unchanged. The prior BE-45/46 final runner durations were 588.812/588.520s; this
candidate's 958.171s includes 642.129s
for the same 173 graph cases and 18.281s for
147 desktop cases. Different build/fixture/cache conditions do not establish
sustained hosted CI growth. The failed 958.050s run and focused repair validation
are recorded separately, not folded into successful implementation effort.
Active implementation effort was not measured; merge delay is unavailable because
publication was not requested. The complete parent remains one branch/delivery.

### Change accounting against live main

Counts include new untracked source files, with additions/deletions separate from
net growth. No fixture-data, generated-document, dependency, ontology or CI changes.

| Category | Added | Deleted | Net |
|---|---:|---:|---:|
| Handwritten runtime (desktop plus supporting history fix) | 588 | 165 | 423 |
| Tests/helpers | 402 | 15 | 387 |
| Handwritten documentation | 403 | 36 | 367 |

Publication update: the user subsequently requested preparing and opening the
DC-14 PR, authorizing staging, commit and push. The exact qualified source manifest
was rechecked before publication; only handoff documentation changed afterward.
Merge and deployment are not requested.

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

## 2026-10-29 — BE-47 first full-ingest repair candidate

Branch `codex/be-47-ingest-repair`, baseline live main `f1e773812baf`.
Parent acceptance is **incomplete**: see [INGEST_RUN_DIAGNOSIS](INGEST_RUN_DIAGNOSIS.md)
and OI-25 for GLEIF consolidation mapping, TED eForms/pagination, unavailable
compatible OffeneRegister vintage metadata and Transparency export obligations.
No operator full-ingest success, paid provider verification or deployment is claimed.

| Check | Result and retained evidence |
|---|---|
| Affected adapters/config/CLI/extraction | 127 passed, 7.44 s; `work/be47/affected.xml` |
| Broader backend unit suite | 867 passed, zero failures/errors/skips, 192.15 s; `work/be47/final-unit.xml` |
| Final pipeline/failure regressions | 21 passed, 50.73 s; `work/be47/final-regressions.xml` |
| Final broadened TED UBL guard + repair tests | 34 passed, 3.84 s; `work/be47/final-ted.xml` |
| Disposable graph composition/ingest/structured/unstructured | 27 passed, 128.66 s; `work/be47/integration.xml` |
| Shared checks | Ruff, strict mypy (169 source files), documentation, generated docs, G1–G4 runtime guards and whitespace pass |

The unit suite tested the revision immediately before broadening TED's unsupported
UBL guard from award notices to all UBL notice types. The final 34-test run covers
that delta (award, contract and prior-information documents); do not add these
counts together or call them a full frozen final pre-merge qualification.
The final source manifest is `work/be47/final-source.json`, digest
`45b415dbc4eff1d1ec63d87d7b7260d77da2e0068a299f56bcbd8df3813806ed`.
The preceding unit-tested source digest was
`3c7975fae354853b3505b5cb3f5b77456df2f22ce936c5c9a3cdfa8542ce8c0d`.
Graph checks preceded the final fetch-parse closure addition, which has a direct
passing unit regression in both the 21-test and broader unit runs.

Commands: `venv/bin/python -m pytest tests/unit -q -o faulthandler_timeout=60`,
`venv/bin/python -m pytest tests/unit/test_pipeline_run.py tests/unit/test_ingest_repairs.py -q`,
`venv/bin/python -m pytest tests/unit/test_ingest_repairs.py tests/unit/test_ted_adapter.py -q`,
and `venv/bin/python -m pytest tests/integration/test_composition_root.py tests/integration/test_cli_ingest.py tests/integration/test_pipeline_run_structured.py tests/integration/test_pipeline_run_unstructured.py -q`.
JUnit arguments target the files above. All test model/source transports are mocks;
graph containers are fixture-owned and disposable. No desktop source was changed;
desktop and full acceptance/release suites were not rerun for this local candidate.

An initial sandboxed unit execution stalled without producing results and was
terminated; a collection-only check collected 867 tests successfully. Retrying with
local IPC available completed the broader suite above. The virtual environment
was refreshed with frozen main dependencies after initial focused collection found
missing `curl_cffi`/`yfinance`; no dependency versions were changed. Existing
Starlette/runpy warnings remain. An automatic review rejected one proposed probe
that embedded the DIP key in its script; the subsequent date-filter probe used the
normal masked application settings loader and succeeded. No action remains blocked
by that rejection. The user key resides only in ignored local secrets, not this diff.

Bounded live probes verified DIP header auth/date filtering, GLEIF publication URLs
and 64-KiB archive prefixes, TED one-result search syntax and official download
pages. No full bulk archives, production graph operations or paid calls occurred.
No commit, staging, push or PR was requested or performed. Implementation time,
validation time and merge latency are not equated; there was no publication/merge.

## 2026-10-29 — BE-47 complete local acceptance, final frozen candidate

This supersedes the earlier partial BE-47 candidate disposition. The user
explicitly requested finishing this parent on its existing branch before another
full ingest. All acceptance items in INGEST_RUN_DIAGNOSIS pass under the scoped
current-source/explicit-availability-failure contract. OI-25 closes locally;
OI-26 retains observed external availability limits. No successful production
full ingest, deployment or paid-model quality is claimed.

Branch: codex/be-47-ingest-repair. Live-fetched baseline/HEAD:
f1e773812baf1870a7a667d7d49006619384d4ee. The working tree includes uncommitted
implementation and fixtures; HEAD alone is not the candidate identity.
Authoritative report: work/be47/candidate-3/report.json, status passed.
Frozen source manifest: work/be47/candidate-3/source.json; SHA-256:
9381ee7d65ba80c6b7423cb20ab978d1dd4416a99c2ae025730030f18f9564a6.
The runner confirms the same source fingerprint before and after the complete run.

| Lane | Cumulative tests | Failures/errors/skips | Captured lane seconds |
|---|---:|---|---:|
| Backend unit | 879 | 0 / 0 / 0 | 198.947 |
| Desktop unit/contract | 147 | 0 / 0 / 0 | 10.540 |
| Disposable graph integration | 175 | 0 / 0 / 0 | 600.388 |
| Acceptance (separate collection) | 85 | 0 / 0 / 0 | 124.647 |
| Desktop integration | 3 | 0 / 0 / 0 | 48.739 |

Total: 1,289 cumulative passes. New cases relative to main: 22 backend unit and
2 graph integration (24), covering distinct reported behaviors/invariants. These
are not 1,289 new tests, copied pair registrations or an acceptance quota. Backend
and runtime/desktop checks passed together on that frozen source; the publication
addendum below records subsequent formatting-only normalization. Existing Starlette/runpy warnings remain.

Shared guards pass: live-main baseline, runtime/test and tool Ruff checks, strict
mypy (172 source files), docs consistency, generated-doc check, G1–G4 runtime
invariants, whitespace and final source-drift check. Runtime remains three services
with existing auth/privilege and schema-transaction constraints. Additive ontology
1.3.0 needs no destructive rewrite; older evidence retains its original stamps.

Exact command: `venv/bin/python tools/qualify.py --output work/be47/candidate-3`.
To repeat, choose a new output directory under work/; reuse is rejected. The report
records every exact child command/exit code and JUnit/log path. All model transports
are mocks, graph services are fixture-owned Docker containers, Qt is headless, and
no test points at operator data. Final validation took 987.387 seconds; that is
validation latency, not implementation effort or merge latency. No merge or PR
was performed.

Candidate-1's supervisor was interrupted by an environment transition after unit
and desktop checks; its orphan integration output cannot establish a complete
candidate result. Candidate-2 was superseded after final identity review found
ISO3/ISO2 buyer/address divergence. Both retained reports are failed/incomplete
and are not added into final pass counts. Candidate-3 includes the reference-backed
identity fix and regression before its freeze. Workflow correction: verify
cross-format identity and source semantics before the expensive final graph lane;
retain one full parent delivery instead of creating smaller packages after findings.

Fixture attribution/reductions and authoritative source links are in
`tests/fixtures/ingest47/README.md`. They cover actual publication metadata, two
range-limited GLEIF prefixes, OffeneRegister historical rows, the daily TR export,
public UBL and SDK-checked synthetic award joins, and a real two-binding EUR-Lex
response. Bounded live FSD/Overpass/TED failures remain OI-26, never silently marked
available. The DIP key is in ignored split secrets; tracked examples contain no key.

Change accounting for the complete branch diff (additions/deletions, not net
growth) is retained in work/be47/complete-change-accounting.json. Categories keep
handwritten runtime/API/model changes separate from tests/helpers, fixture data
and attribution, generated runtime docs and the generated country reference.

| Complete branch category | Additions | Deletions |
|---|---:|---:|
| Handwritten runtime/API/models | 976 | 247 |
| Tests/helpers | 742 | 45 |
| Fixture data/attribution | 520 | 0 |
| Country reference data | 261 | 0 |
| Generated runtime docs | 18 | 3 |
| Tool renderer | 21 | 4 |
| Config examples | 3 | 0 |
| Hand-maintained documentation | 409 | 8 |

Publication authorization (2026-10-29): after complete local BE-47 acceptance,
the user explicitly requested preparing and opening a PR for this session's work,
authorizing staging, commit and push. The qualified runtime/test/tool/reference
source fingerprint is unchanged. Merge, deployment and live ingestion remain separate.

Publication formatting addendum: staging exposed CSV CRLF line endings and extra
blank test-file EOF lines that the earlier unstaged whitespace check had not seen.
The CSV is normalized to LF and the test EOF is trimmed; runtime, tool, ontology,
reference and test logic are unchanged. The affected current-source, ingest-repair
and GLEIF suites passed 38 tests (work/be47/publication-regressions.xml); Ruff,
docs, generation and staged whitespace checks pass. Publication source digest:
11be7926b618bb8e4917c682e252df3db3fdec2f074b0545a1c29e64c61795fb.
Comparing with candidate-3/source.json confirms only those two formatting changes.
The full 1,289-test run remains evidence for identical runtime behavior, not a
claim that its original byte fingerprint equals this normalized publication tree.


## BE-50 publication authorization — 2026-10-31

The user authorized preparing and opening the session PR. Staging, commit and
push preserve the frozen candidate source and its runtime-stack blocker; no
merge, deployment or production acquisition is included.
