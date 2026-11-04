# BE-55 — GDELT backlog addressing and OSM leaf failures

Branch: `codex/be-55-gdelt-backlog-and-osm-leaves`; live base `029f2fceea1d`.
Owner decisions A/A, 2026-11-04. Prerequisites: BE-41 documentation acceptance
passed; merged BE-47/BE-52 bounded checkpoint lifecycle and BE-49/50/53 durable
OSM acquisition, adaptive subdivision and transport policy. No BE-54 dependency.
Operational evidence: `~/limes-ops-reports/2026-11-04/03-deployed-and-validated-be-52-be-53/REPORT.md`.
The deployed GDELT checkpoint already jumped over historical coverage; this change
cannot infer or repair that lost anchor automatically.

## Acceptance checklist (defined before implementation)

- [x] GDELT backfill with checkpoint older than now-days selects the oldest
  unconsumed bounded prefix under the source lock; successful submissions advance
  durably. Fresh-day and other-source explicit-window semantics stay unchanged.
- [x] Preserve 96-slot cap, missing-slot abort, malformed-row blocking and locks.
- [x] Exhausted OSM leaf fetch failures persist durably, then eligible siblings
  continue; incomplete acquisition fails the job before graph loading/checkpoint.
- [x] Explicit resubmission skips acquired leaves, retries failures and pending
  leaves, and clears recovered failures. No automatic replay.
- [x] Old cursors remain readable; new fields, bounds, operator sequence and
  obligations are documented without changing split triggers/depth/200-call cap.
- [x] Affected unit/integration tests and shared guards pass; one authoritative
  frozen full candidate is recorded, with blockers retained honestly.

## Operator sequence and cursor contract

GDELT rolling backfill (`--days N`, no explicit `until`) reads the checkpoint
inside the existing source lock. If older than now-N-days, the run records
`window_from = last_success_at`, bounds `window_to` to at most 96 new slots and
fetches strictly after the covered checkpoint slot. The microsecond offset is
only a fetch-boundary device; the durable checkpoint and recorded window remain
slot endpoints. At aligned checkpoints, 96 new slots advance exactly one day;
at fractional legacy checkpoints the first slot is the next quarter hour.
A successful run checkpoints the covered endpoint; missing slots or malformed
rows retain the prior checkpoint and re-request the same oldest prefix.
Fresh/absent checkpoints retain exactly the previous now-days fetch semantics,
including wider-window rejection. Explicit `until` requests retain their old
semantics. Default ingest is unchanged. No other source shares this change.

For a G-day historical gap anchored by its actual last covered checkpoint, submit
`venv/bin/limes remote run backfill --source gdelt --days 1`, wait for the terminal
result, verify the checkpoint, then submit the next job: ceil(G/1) successful
submissions, oldest to newest. Missing slots can require operator investigation
and resubmission; unsuccessful jobs do not count as progress. The last prefix
is capped by the existing publication lag. A day can pass during a long catch-up,
so measure the remaining gap again rather than treating job count as coverage.
The supplied fresh-day job already advanced its checkpoint: catch-up cannot
reconstruct that anchor. No automatic checkpoint rewind or production mutation
is introduced; any historical anchor repair is a separate reviewed operator action.

OSM `active.json` keeps acquisition_id, plan_hash, started_at, partitions and
splits unchanged and adds optional `failed_leaves: {leaf_key: entry}`. An entry
contains `phase: "fetch"`, `state: "failed"`, aware `failed_at`, diagnostic `error`,
and nullable `content_hash`. The hash points to the archived capacity-error
response, when received; transport exhaustion has no validated payload and stores
null. Each failure is atomically fsynced before requesting a sibling. Acquired
leaves are in partitions; failed leaves are in failed_leaves; pending leaves are
in the derived split topology but absent in both. Unknown keys and overlap are
rejected. A later successful fetch removes the failure in the same atomic write
that adds its acquired partition. A later eligible subdivision removes the failed
parent and durably records the split before children.

Old cursors default the missing map to empty and resume without migration, with
the same root plan hash and cached payloads. Older strict binaries cannot read a
cursor written with this additional field, even when empty: finish the acquisition
or preserve it for separately reviewed rollback handling; never delete failed
state merely to bypass validation. This is forward readability of old cursors,
not a claim of backward readability by old software.

After a leaf cannot subdivide and its fetch fails, including exhausted transport
retries or a depth-limited capacity remark, record it and continue eligible
siblings once each. Permanent fetch errors are also recorded; malformed response
parse errors and cursor/archive errors still abort immediately. The existing
remark triggers, root-only transport triggers, depth limit and 200 logical calls
per run (each at most four physical attempts) are unchanged. At the call cap,
unvisited leaves remain pending; all durable progress survives. Any failed or
pending leaf prevents record yield, graph loading, cursor retirement and source
checkpoint advancement. The pipeline closes the failed ingestion run and the job
fails. No partial success, background retries or automatic resubmission.

After merge, the operator drives GDELT catch-up submissions and explicit OSM
re-runs. No new configuration, service, credentials or cursor migration is needed.
Existing external capacity and historical coverage obligations stay open. No live
GDELT, Overpass, OpenRouter acquisition or production writes were used here.


## Merge and accounting boundaries

BE-54 remains on its independent branch. Its D-95 and OI-32 identifiers are
reserved; BE-55 uses D-96 and OI-33 to avoid ledger collisions. Both branches
edit shared specification/roadmap/ledger files; preserve both additions on merge.
BE-55 does not import BE-54 implementation, prompt/schema changes or acceptance.
No CI lanes or required statuses change; existing qualification remains fail-closed.
Local suites run sequentially on the disposable executor; existing CI isolates
independent lanes on separate runners. The workflow ships the whole parent in one
commit. There are no copied test registrations or new verification lanes; new cases
cover addressing, retry persistence, legacy cursors and invalid cursor states.
Validation time is reported separately from implementation and merge delay; no
merge has occurred, so merge latency cannot be measured here.


## Validation and commit map

Affected development checks: 79 unit cases and 8 disposable integration cases
pass. The integration scenario exercises the actual CLI, source lock, window
selection, bounded adapter, graph run closure and checkpoint. It proves three
successive 96-slot prefixes and unchanged checkpoints after both missing exports
and malformed rows. The first integration attempt rejected the new fixture's
invalid ZIP member name; the corrected fixture uses the official filename shape.
The initial unit invocation could not load Qt's libEGL; the existing ignored
Qt library bundle resolved the executor dependency. Neither failure was skipped.

Frozen invocation: `LD_LIBRARY_PATH=$PWD/work/be53/qt-libs/root/usr/lib/x86_64-linux-gnu
venv/bin/python tools/qualify.py --output work/be55/candidate-authoritative`
(as one shell command). The canonical environment was synced with
`UV_PROJECT_ENVIRONMENT=venv uv sync --frozen --all-packages`. Backend, desktop,
graph, acceptance and runtime suites execute sequentially with fixture-owned
containers; no operator graph is selected. An earlier attempt in
`work/be55/candidate-final/report.json` stopped at tools-lint before tests, because
an edited renderer line exceeded 100 columns; it remains a failed preflight.
The renderer was wrapped and generated operations regenerated before final freeze.

One delivery commit, `BE-55: address GDELT backlog and persist OSM leaf failures`,
maps to all acceptance items: pipeline window/fetch-boundary and CLI reporting
cover GDELT; OSM acquisition model/loop cover leaf durability and fail-closed
coverage; tests cover the distinct regressions; renderer/specification/operator
and ledger updates cover cursor compatibility and operational obligations.
No prompt, ontology, fixture data, dependency, CI or desktop implementation change.
Final frozen results and line accounting are recorded after qualification below.


## Final local acceptance

All six acceptance items pass. No remaining local implementation or qualification
blocker. Authoritative report: `work/be55/candidate-authoritative/report.json`,
status passed. Source manifest SHA-256:
`2be5d9079f8efbd5ff2f87b47bc6b34306997d76de62959d374e070f38a29d73`.
Final validation elapsed 754.095 seconds, separate from implementation effort
and merge delay. All guards pass and source stability is unchanged after all lanes.

| Lane | Passing cases | Elapsed seconds |
|---|---:|---:|
| unit | 942 | 160.6 |
| desktop | 147 | 11.383 |
| integration | 177 | 356.149 |
| acceptance | 85 | 83.821 |
| desktop-integration | 3 | 36.146 |
| runtime-stack | 1 | 103.702 |

1,355 cumulative cases, zero failures/errors/skips. Seven new cases (six unit,
one integration); existing OSM cases were updated for sibling continuation rather
than duplicated. Cumulative passes are not new coverage or a delivery target.
Final edits after freeze are handwritten documentation only. Live baseline was
rechecked at `029f2fceea1d` before commit; the prior branch's work remains intact.
No live acquisition, paid call, push, deployment, PR or merge was performed.
External upstream capacity and corpus coverage remain unmeasured. The already
advanced deployed GDELT checkpoint still needs a separately reviewed historical
anchor decision if that skipped gap must be acquired; code does not alter it.


## Delivery line accounting against live main

| Category | Additions | Deletions | Net |
|---|---:|---:|---:|
| Handwritten documentation | 291 | 2 | 289 |
| Generated operations | 19 | 3 | 16 |
| Handwritten implementation and renderer | 86 | 21 | 65 |
| Tests/helpers | 226 | 7 | 219 |

No fixture data, dependency or other generated-file changes.
