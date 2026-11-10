# Current-release readiness — 2026-11-10

Scope: the user requests outstanding current-release implementation and whole-codebase
qualification before comprehensive human testing. GraphRAG/next-version implementation
is explicitly excluded; ingestion is not assumed operationally complete.

## Package and defect audit

- Current BE-01–56 and DC-01–17 have implementations. Historical acceptance,
  external source availability, deployed data coverage and current code are separate.
- PA-1 (historical branch `wp-57-parallel-downloads-cancel`, PR #27, `3896e91`)
  is merged: parallel source jobs, serial graph writes, cancellation, transport/run
  budgets and cross-process host slots. Its placement under `next-version/` does
  not make that merged ingestion repair an unimplemented future feature.
- [DEFECT-PA1-R1](next-version/DEFECT-01_downgrade_guard_test_isolation.md) was
  explicitly routed to Codex. The combined structured-pipeline/composition command
  reproduced **1 failed, 13 passed**, with a retained GISCO source breaking the
  guard test's fresh-graph premise. The same combined command passes **14 tests** after repair. The fixture clears the session-owned
  disposable graph **before** calling composition/provision; production downgrade
  rejection and the existing schema-guard tests remain intact.
- [OPEN_ISSUES](../OPEN_ISSUES.md) retains upstream availability, operator pinning,
  live ingestion/quality/coverage, deployment/recovery and reference-hardware
  obligations. Automated fixture results cannot close those observations.

## Repairs from this pass

- Bind both default browser HTTP transports to the global receiver; native Chromium
  fetch otherwise raises `Illegal invocation` before any health/search/API request.
- Keep search text synchronized with header/URL navigation, with API request debounce.
- Subscribe to Plotly's emitter for timeline selection; stop abandoned asynchronous
  Cytoscape initialization; filter expanded assertions on both temporal axes; retain
  earlier expansion and report errors when a neighbor request fails. New query results
  do not inherit the previous result's expansion. Timeline renderer failures are visible.
- Accept valid empty API free text (queued job output, rejected generated Cypher,
  diagnosis with no failing hop); keep nonempty identifiers and string-type checks.
- Gate backup on confirmed connection and capability, observe one status stream,
  derive the dump filename from the successful response, treat cancellation as
  terminal and retain the request ID across view navigation without replaying POST.
- Publish global connection recovery even when the successful health payload is
  structurally unchanged; clear stale authentication prompts.
- Disable Leaflet asynchronous zoom transitions and animated data fitting so tab/route
  teardown cannot leave a callback accessing the removed map pane. Zoom/pan remain.
- Use readable error text on pale error surfaces.
- Repair supervisor readiness for cold Java CLI startup: a measured successful
  probe took 34.51 seconds, exceeding the old 15-second process cap. Allow up to
  60 seconds per probe, bounded by the unchanged 360-second shared startup window;
  stop launching probes after shutdown is requested. Authentication, application-user
  provisioning and clean physical-dump checks remain enforced.
- Reclaim stale owned Neo4j browser extraction caches before a stopped database is
  relaunched. Captured concurrent-suite logs proved that repeated extraction filled
  the executor disk and caused the subsequent `Path is null` startup failure. Active
  caches, symlinks, foreign-owned directories and persistent data are preserved.
- Bound the recovery test's peak container filesystem copies: inspect the dump in
  the running fixture, remove only the stopped disposable service before the offline
  loader, retain its volumes, and recreate the service after load. Marker/count/byte
  assertions and authentication/clean-stop checks remain unchanged.

- Flatten service runtime filesystems with standard multi-stage Docker builds,
  install the same frozen dependencies/source in one build step, and mount the
  installer only during the build. Place final working-directory creation before
  copying the runtime so VFS does not duplicate a complete tree for an empty layer.
  Non-root identities, model separation, vendor runtime paths, ports and volumes
  are preserved. Full qualification passes on the fixed-size executor.

- Apply read deadlines using Neo4j query metadata rather than a Cypher parameter;
  preserve valid user parameters named `timeout`. The read-mode barrier remains.
  The new regression fails before the repair and passes after it, with a live
  database counterpart. The earlier AC-39 child timeout did not reproduce under
  instrumentation with its original 120-second deadline; no deadline was enlarged.

## Qualification

**The current release passes the complete automated qualification and both browser
gates; the approved local stack is restored and healthy.**

Final candidate: `work/readiness/candidate-final-10/report.json`.
Source SHA-256: `b02928e06b85d9839d58edd8112d534bad2c97d20118eedd18d6ec496cc51a72`.
Live GitHub baseline: `1dd2d8241a84ebb7549768cdffe1029f89a4178b`.
Validation elapsed: 10 November 2026, 09:25:40–09:52:59 CET; 1,638.952 seconds. This is validation time, not implementation effort
or merge latency. Branch: `codex/current-release-readiness`; qualification was
recorded before publication. The later PR authorization is recorded in D-100.

| Lane | Passed |
|---|---:|
| Backend unit | 1,019 |
| Desktop unit/contract | 42 |
| Graph integration | 186 |
| Acceptance | 85 |
| Desktop integration | 2 |
| Three-service runtime | 1 |
| Total pytest cases | 1,335 |
| Web Vitest | 48 |
| Chromium renderer/navigation scenarios | 22 |
| Chromium through real three-service stack | 24 |

All six pytest lanes have zero failures, errors and skips. Frozen web install,
TypeScript, ESLint, production build, Ruff, mypy, documentation/generation,
G1–G4, whitespace and live-baseline checks pass. The runtime lane proves non-root
execution, model separation, authorization, bounded jobs, remote backup, nonempty
physical dump, recovered health and read-only API archive access. Graph integration
restores the marker, 1,000 records and 1,024,000 payload bytes.

The final Chromium fixture uses real Cytoscape, Leaflet and Plotly renderers and
covers selection, header search, all routes and deep-link reload. Its receipt is
`work/readiness/browser-fixture-final-source.json`, with no page errors or external
requests. The separate real-stack flow uses the exact qualified images, a disposable
graph and synthetic credentials: launcher session, read-only Cypher, route API
responses, consequence confirmation, physical backup, navigation away/return with
exactly one POST, actual dump output, recovered API/database health, recovered global
header/action eligibility, credential confinement and reload. Receipts:
`work/readiness/real-browser-results.json` and
`work/readiness/real-browser-stack/success.json`; screenshot:
`work/readiness/real-stack-browser.png`. Its dump is independently verified nonempty.

There are 27 new behavioral regression cases (19 web, 6 supervisor, 1 query-deadline
unit and 1 live reserved-parameter integration). The map teardown regression is
covered by the real-renderer browser gate. These are distinct from cumulative
suite counts. DEFECT-PA1-R1 has exact combined before/after evidence: 1 failed/13
passed before, 14 passed after; final integration passes all 186 cases.

Candidate-8 and candidate-9 retain passing canonical reports for their own source.
Supplemental work caught stale global health after backup in candidate-8, then two
Leaflet callbacks touching a removed pane in candidate-9. Health recovery tests
failed before repair and pass after it; map stack traces and its passing repeated
renderer gate are retained. Candidate-10 qualifies both repairs. Earlier interrupted
or failed reports remain failed. Final-7's 120-second lookup timeout did not reproduce
under instrumentation at the original deadline; the separately reproduced query
metadata bug is fixed, but is not asserted as its sole cause.

Qualification completed on the existing 2-CPU, 8-GB RAM, 7.9-GB disk executor with
rootless Docker VFS. Standard compact multi-stage images, ordinary unused cache/image
cleanup and RAM storage of regenerable dependencies bounded disk use.
An initial local restoration with an on-disk venv exhausted startup disk; its
failed receipt is retained. Moving the exact environment to RAM with a durable
compressed recovery archive supplied the required local-service headroom.
No assertion, authentication barrier, transaction deadline or content check was
waived. Direct relocation of Docker layer directories was rejected and never applied.
The qualification-only wrapper and source manifests are retained under `work/readiness`.

## Approved configuration access and local stack

The original API/worker failed to read configuration. The user explicitly granted
service UID access including secrets and approved their restart. ACLs are unsupported;
equivalent service-group read/traverse access preserves owner and private directory/file
modes 750/640. The service UID/GID is 7474 (rootless host GID 107472). Secret contents
were never printed or manually read. Opaque environment files are passed to Compose.

The local Neo4j, API and worker now run the exact qualified image IDs and report
healthy. Service-UID checks confirm all three configuration files are readable by
both API and worker. Existing data volumes and configuration are preserved;
volume identities are recorded in the restoration receipt. The canonical `venv/`
uses the exact qualified RAM environment with a durable compressed recovery archive
and checksum. The built desktop bundle is retained, and the allowlisted local build
context is updated to the qualified source. Receipt:
`work/readiness/restored-local-environment.json`. RAM recovery command:
`python3 work/readiness/restore_canonical_venv.py`. Regenerable web build dependencies
are pruned after qualification to fit the fixed disk; frozen install recreates them.

This candidate is ready to begin comprehensive human testing. Live acquisition,
ingestion completeness, paid extraction quality, deployed data coverage and
reference-hardware performance retain their explicit obligations in OPEN_ISSUES.
No live paid ingestion, external deployment or publication was performed.

## Change accounting against live main

Untracked source/tests/documentation are included. Build recipes are handwritten
runtime/build changes. Generated contracts, lockfiles and fixture data are unchanged.
Ignored qualification controllers/logs/archives are operational evidence, excluded
from repository source accounting. Additions/deletions are separate from net growth.

| Category | Files | Added | Deleted | Net |
|---|---:|---:|---:|---:|
| Handwritten runtime/build | 15 | 239 | 199 | +40 |
| Tests/helpers | 12 | 511 | 12 | +499 |
| Hand-maintained documentation | 8 | 538 | 0 | +538 |
