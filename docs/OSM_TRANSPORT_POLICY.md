# BE-53 — dead-feed disposition and OSM transport policy

Branch: `codex/be-53-feed-and-osm-transport`, live base `4ef67c89ae67`.
Prerequisites: merged BE-49 cursor/lock lifecycle and BE-50 adaptive acquisition;
BE-41 documentation acceptance passed. BE-52 / PR #21 was not an implementation prerequisite. It merged during final
verification; the branch was then fast-forwarded to live main `06bbfb47134e`
under the standing baseline contract. Standalone qualification below proves the
implementation did not depend on BE-52. Integrated requalification passes; see final disposition below.
Owner decisions: REMOVE EUobserver; deliver the full OSM transport package.
Evidence: operator report `2026-11-04/02-deployed-and-validated-be-50-be-51`,
sections 5 and 7 (three 502s, then read timeout; zero new progress).

## Acceptance checklist

- [x] Remove only EUobserver; retain all three other feed entries unchanged.
- [x] OSM has a configurable longer read timeout; other sources retain 60 seconds.
- [x] Configurable mirrors rotate on endpoint transport failures with every attempt logged.
- [x] Exhausted 502/503/504 and read timeouts subdivide oversized root cells;
  auth failures, other HTTP statuses and small children do not. Existing explicit
  resource-remark triggers and finite limits remain.
- [x] Cursor durability, lock scope, complete-before-yield and checkpoint semantics
  are unchanged; old cursors resume without migration.
- [x] Affected tests/shared guards and one frozen full candidate are recorded,
  with failed qualification and operational gaps kept explicit.

## Operator configuration and bounds

Set `LIMES_OSM_HTTP_TIMEOUT_SECONDS=180` in settings (range 1–3600 seconds).
180 seconds allows three times the global 60-second read window for loaded
Overpass servers, including queueing, while remaining bounded. This is a socket
read inactivity timeout, not a total request or run deadline. Connect/write/pool
limits retain the shared default. The Overpass query timeout remains 25 seconds.

`LIMES_OSM_OVERPASS_ENDPOINTS` is a JSON array of HTTPS interpreter URLs, e.g.
`["https://overpass-api.de/api/interpreter","https://overpass.kumi.systems/api/interpreter"]`.
Those are the defaults. Each cell starts at the first endpoint. Shared retries
remain four attempts total, with existing backoff. Transient network errors and
5xx rotate through the list; 429 retains its endpoint and cooldown policy;
permanent 4xx fail immediately. Every OSM attempt logs endpoint and attempt number.
Mirrors can observe different replication instants; acquisition already represents
an interval, never an atomic snapshot. No live mirror availability is claimed.

After retries, only final HTTP 502/503/504 or read timeout can split a transport-
failed root (roughly 0.97 by 0.92 degrees). Children never split for transport
failures: a smaller cell provides weak evidence of a size remedy. Explicit
runtime-timeout/OOM remarks retain BE-50's three-level depth rule. The 200 logical
fetch-call limit remains, each call with at most four physical attempts. No job
is replayed automatically.

The cursor schema and canonical root query-plan hash are unchanged, including
when endpoints/timeout change. Existing cached leaves keep their bytes and fetch
instants. New transport splits use the existing `splits` tree, durably persisted
before children. A failed request has no validated response to archive. Raw record
`source_url` remains the canonical Overpass service identifier; attempt logs identify
actual mirrors. The cursor does not store endpoint provenance. Locks, fsync/atomic
writes, complete-leaf coverage, graph replay and retirement are unchanged.

## Scope and merge implications

No feeds adapter/failure handling changes depend on BE-52. Fetched PR #21 overlaps directly in `sources/base.py` at the transport-exception
and retry-status block: combine its attempt-result logging with this branch's
endpoint rotation and typed status metadata, using `attempt_url` for actual mirrors.
Both branches also edit `config.py`, the settings example, changelog, index,
roadmap, verification and issue/decision ledgers. Their additions must be combined.
PR #21 does not edit `feeds.yaml`. Reconciliation now preserves both its feed
failure policy and this branch's minimal deletion. The shared retry block combines
BE-52 result logging with rotation/metadata; result logs use actual `attempt_url`.
The independent colliding ledger IDs were reconciled to D-94 and OI-31 for BE-53. Never replace this branch's base
with the parallel branch. Feed extraction rejections, TED/FSD availability, GDELT
backlog, nationwide OSM capacity and previous qualification gaps remain open.
No live acquisition, paid model call, production mutation, deployment or push.

## Final handoff

All six checklist items pass locally. The single BE-53 delivery commit removes
EUobserver, wires OSM-only timeout/endpoints through composition, rotates the
shared transport within four attempts, preserves typed failure causes for bounded
root subdivision, and adds distinct mocked regressions plus operator documentation.
No dependency on PR #21 is introduced.

Affected adapter/shared transport/configuration/composition/feed units: 101 passed.
Two existing helper factories loaded local environment files, causing unrelated
backup-credential and provider-default failures in the first candidate (925 passed,
2 failed; qualification stopped at units). Their `_env_file=None` isolation fixes
pass 39 affected cases; this is test hygiene, not changed application behavior.
The first report remains at `work/be53/candidate/report.json`, never accepted.

Standalone report before main advanced: `work/be53/candidate-final/report.json`, status passed.
Source SHA-256: `463d4e2234cc5c513bd119dbb6c8fb708a2bfe862436d1ae53d9d1fdac1ecc4a`.
927 backend units, 147 desktop unit/contract, 176 graph integration, 85 acceptance,
3 desktop integration and 1 runtime-stack case pass with zero failures/errors/skips.
These 1,339 cumulative cases include 11 new transport/config cases, not 1,339 new
tests. Existing OSM tests accept the new mocked policy kwargs. All shared guards
pass. Final validation elapsed 859.134 seconds; implementation and merge latency
are not inferred (no merge). Final source manifest was unchanged after the run.
Only handwritten handoff/specification documentation changes follow the freeze.

The executor's missing Qt libraries were extracted from distribution packages
under ignored `work/be53/qt-libs` without a system install; the run used
`LD_LIBRARY_PATH=$PWD/work/be53/qt-libs/root/usr/lib/x86_64-linux-gnu` and
`venv/bin/python tools/qualify.py --output work/be53/candidate-final`.
The canonical environment was synced frozen. Existing deprecation/runpy/JUnit
warnings remain; no check was skipped. Runtime containers/volumes were fixture-owned.

Standalone local implementation/qualification passed. Integrated qualification
after main advanced also passes (final disposition below). External mirror
availability, nationwide coverage, extraction quality and operator ingestion success
remain open; this does not retroactively qualify older frozen candidates. Commit
is authorized; no push, PR creation, merge, deployment or acquisition is performed.

## Authoritative integrated disposition

Live main advanced to `06bbfb47134e` (PR #21) after standalone qualification.
Standing baseline instructions required reconciliation before commit. This branch
was fast-forwarded, preserving independently implemented BE-53 behavior. Shared
retry logging was combined with rotation/status metadata; logs now use the actual
attempt endpoint. BE-52 extraction versions/feed behavior are unchanged in the diff
against current main. Ledger collisions resolve to D-94 and OI-31.

The first integrated attempt stopped with 175 graph passes and one failure:
BE-52's unstructured fixture inherited a local 1.0.0 prompt pin while expecting
1.1.0. Its factory now also uses `_env_file=None`; all 9 affected graph cases pass.
This extends the narrowly scoped test isolation correction, without changing
runtime pins or defaults. Report `work/be53/candidate-integrated/report.json`
remains failed. Investigation identified file-loading fixture factories as the
shared cause; no production setting was changed or assertion weakened.

Authoritative final report: `work/be53/candidate-integrated-final/report.json`.
Source manifest SHA-256:
`1b0114367718110e68c541fa6e3748e78b8f28a46db0df4eb46e579465bcdbbb`.
Public settings-example SHA-256 (outside the normal source manifest):
`d839019401ba227345bb83d7900edf46c4495644750abe6ab7a617b859d0c2d8`.
All shared guards and 1,348 cumulative cases pass: 936 backend, 147 desktop
unit/contract, 176 graph, 85 acceptance, 3 desktop integration, 1 runtime stack.
Zero failures/errors/skips. Eleven new BE-53 cases; all other counts are existing
coverage. Final validation elapsed 813.700 seconds. Standalone validation took
859.134 seconds; those are separate candidate runs, never added as test coverage.
No implementation-effort or merge-latency estimate is inferred. The integrated
manifest is unchanged after qualification; final edits are handwritten documents.
No remaining local implementation/qualification blockers. Operator acquisition,
mirror capacity, live extraction quality and corpus completeness remain unmeasured.

## Delivery accounting against current main

| Category | Additions | Deletions | Net |
|---|---:|---:|---:|
| Handwritten implementation | 76 | 19 | 57 |
| Tests/helpers | 120 | 17 | 103 |
| Ontology feed configuration | 0 | 4 | -4 |
| Configuration example | 4 | 0 | 4 |
| Handwritten documentation | 289 | 6 | 283 |

No generated files, fixture data or dependency changes. Counts measure line
changes, not effort; the new tests are eleven cases, not cumulative suite passes.
