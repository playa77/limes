# PA-1: Parallel source acquisition, job cancellation and professional source time budgeting

Status: accepted (operator directive, 2026-11-08) · Implemented by: Hermes (explicitly
designated by the user to write this work in-repo, superseding the codex-only default for
this package) · Related: BE-52/BE-53/BE-55 transport policy, `src/limes/operations/*`,
`src/limes/pipeline/run.py`, `src/limes/graph/driver.py`.

## Problem statement (observed 2026-11-08, run `00-deploy-and-continue-ingestion`)

1. The worker executes one operation job at a time (`worker.py` claim→execute loop, single
   worker container). One source's stalled transport (OSM/Overpass, 5.5 h of failed request
   cycles) blocked 23 queued sources: **zero ingestion for hours** while the queue was not
   empty.
2. There is **no cancellation surface**: submit-only API. Stopping a running job requires
   restarting the worker container (which SIGTERMs the whole run and marks it failed).
3. **No wall-clock budget exists for a source run.** The only bound is `LIMES_JOB_TIMEOUT_SECONDS`
   (24 h). A source whose upstream is degraded can burn 24 h inside its own per-request retry
   policy before the worker timeout kills it. A 5+ hour wait before declaring a source NOT
   TIMEABLE is unprofessional; time slots must be declared per source and enforced.
4. Within a source, record fetch is a streaming `for raw in adapter.fetch(...)` loop with
   per-record processing; the whole run's graph writes interleave with network phases, so a
   naive "run two sources concurrently" would make them write to Neo4j at the same time.

## User requirements (verbatim intent, 2026-11-08)

- **Downloading the sources: parallel between sources.** Different sources must acquire
  concurrently.
- **Ingestion into the DB: still serial.** One graph writer at a time, unchanged semantics
  (`§9`: single writer).
- **A source failing again and again must not run any other ingestion while doing so.** A
  stuck/degraded source must degrade alone and fail fast.
- **A real cancel endpoint.** Operator can stop one queued or running job; stopped running
  jobs terminate their subprocess, release locks, and are marked `cancelled` — not silently
  replayed later (`recover()` already refuses replaying interrupted work).
- **Professional time slots per source**: bounded wall-clock acquisition budgets and a
  bounded consecutive transport-failure budget, after which the run aborts cleanly (durable
  record, checkpoint untouched, replayable) — minutes-scale for small sources, not hours.
- **Netiquette**: per-host concurrency is respected across concurrent sources (21
  `public_offices_*` scopes all hit the same host; parallel scopes must not become a
  self-DOS).

## Non-goals (this package)

- No parallel download of leaf cells *within* one source's cursor (BE-53 cursor stays
  sequential and resumable). Per-host slot limits apply to cross-source concurrency, not
  intra-source loops (a source's own adapter keeps its serialized cursor and its own
  endpoint-rotation/backoff policies).
- No change to job submission semantics or `request_id` idempotency; no schema/ontology
  changes; no API auth changes (operator bearer already required for `/operations/*`).
- No change to `TrackingStore` (news) — separate module.

## Architecture

Keep the durable single-worker model. One worker *process* (lifetime `flock` unchanged),
which internally runs a bounded job pool. Job isolation is preserved: each job runs in its
own subprocess (`job.request.argv()`, `start_new_session=True`) exactly as today, so
cancellation = terminate one process group; crash isolation unchanged.

```
worker process (lifetime flock)
├── ThreadPool: ExecuteJob × LIMES_JOB_CONCURRENCY        (R1: parallel ACQUISITION)
│     └── subprocess `limes <command> ...` per job
│           ├── fetch/normalize/gate        (network, CPU)   — runs freely in parallel
│           └── every graph write batch      (R2: serial DB)
├── per-job cancel Event → SIGTERM own process group       (R4: cancel)
└── recovery: running jobs on worker start → failed, no replay (unchanged)
```

### R1 — Worker job pool (parallel between sources)

- `LIMES_JOB_CONCURRENCY` (int, default `4`, range 1–16): how many operation jobs the worker
  executes concurrently. Each concurrent job keeps its own subprocess as today.
- The claim loop (`store.claim()`, SQLite `BEGIN IMMEDIATE`) is already safe for concurrent
  claimers; the worker claims only while a pool slot is free and re-checks the queue as
  slots drain. Heartbeat/scheduling behavior (`TrackingStore.schedule`, heartbeat touch)
  must be moved out of per-job execute into the worker main loop so a long job cannot stall
  the heartbeat (today `execute()` touches the heartbeat inside its poll loop — pool-safe
  version touches it from the manager loop only).
- One advisory lock per source (`§9`, `§8.14`) already refuses a second concurrent run of
  the SAME source; with concurrency the pool must treat that failure as a normal terminal
  failure (it already surfaces as job failed), never as a blocker of other sources.
- Worker startup recovery unchanged: `recover()` marks previously `running` jobs `failed`
  ("never replay'); a `cancelled_request` that arrives while the worker is down resolves to
  `failed` on recovery with the existing interrupted note.

### R2 — Graph write gate (ingestion into the DB stays serial, downloads stay parallel)

- All graph transactions already funnel through `Driver.write_batch` (the single WRITE-mode
  choke point). Wrap it in a cross-process file lock under the worker volume:
  `LIMES_INGEST_WRITE_GATE` (bool, default true) + gate file `/data/write-gate.lock`,
  `fcntl.flock(LOCK_EX)` acquired before `session.execute_write` and released after it —
  per transaction, **never** held across network/inference phases. Crash of any holder
  releases the lock automatically (kernel semantics), which the SQLite/Neo4j node lock diary
  approach would not.
- Effect: concurrent runs interleave freely on fetch/normalize/gate/extract phases; their
  write batches serialize transaction-by-transaction. Neo4j observes one write transaction
  at a time. Idempotent loaders make per-batch interleaving safe (a mid-run kill replays a
  document with "checkpoint unchanged" semantics exactly as today).
- Other writers through the same driver (entity writes, identity reviews, news claims) go
  through the same gate: total write throughput is unchanged by definition of "serial DB
  ingestion"; reads (READ sessions) are never gated.

### R3 — Success-path time slots per source (no more multi-hour stalls)

- New settings keys (§4.2):
  - `LIMES_SOURCE_RUN_BUDGET_SECONDS` (int, default `1800`): wall-clock acquisition budget
    for a single source run measured from run start (not per request).
  - `LIMES_SOURCE_TRANSPORT_BUDGET_ATTEMPTS` (int, default `8`): maximum consecutive failed
    HTTP request attempts across *any* requests in one run (endpoint rotation does not reset
    this) before the run aborts with `SourceFetchError`.
- Enforcement point: `pipeline/run.py` `_execute_run` checks both budgets each iteration of
  the streaming fetch loop and raises a new `SourceRunBudgetExceeded` (subclass of
  `SourceFetchError` so today's abort+`_close_run` behavior is preserved: durable record,
  checkpoint unchanged, replayable by resubmission). Budget exhaustion is logged with the
  budget value and elapsed time. A budget-exhausted run must close in seconds, not hours.
- A per-request retry policy remains (4 attempts with backoff, BE-53 endpoint rotation, per
  request); the new run-level budget is NOT reset by endpoint rotation (R3's key defect fix:
  2026-11-08 saw one source rotate endpoints and burn hours).
- Default budget derived per source where an adapter declares one: structured bulk sources
  (gleif, offeneregister, gisco) may declare `LIMES_SOURCE_RUN_BUDGET_SECONDS_MAX`-style
  per-source override via settings file keys documented in OPERATIONS.md (not per package
  code) — Operators may pin per-source budgets as `LIMES_SOURCE_BUDGET_<ID>_SECONDS`; the
  generic budget applies otherwise. Public-office list (21 scopes) uses the generic budget;
  a scope that cannot finish inside it leaves resumable progress (acquisition already
  archives bounded per-scope state), explicitly resubmittable.

### R4 — Cancellation endpoint (and CLI + client)

- `POST /operations/jobs/{job_id}/cancel` (operator bearer):
  - `queued` → status `cancelled` immediately (exit_code null, output note).
  - `running` → persist a cancel flag in the store; the worker observes it within its poll
    cadence and SIGTERMs the job's process group (the existing graceful-stop path; after
    the 180 s grace, SIGKILL as today), then closes the job as `cancelled`.
  - terminal state → HTTP 409 (no-op), current record returned.
- Store: add boolean column `cancel_requested` (migrate existing DB: `PRAGMA table_info`
  check + `ALTER TABLE ADD COLUMN`). Job model status gains literal `cancelled`; API
  response models pick it up automatically via `Job`.
- `finish()` gains the `cancelled` terminal status path (distinguishable from consumer
  abort/failed). `recover()` treats running-with-cancel_requested same as running (→
  `failed`, no replay).
- Client (`client.py`) gains `cancel(job_id)`; remote CLI gains `limes remote cancel <id>`.
- Cancellation of an ingest run terminates the subprocess mid-run: durable per-source state
  stays consistent by existing semantics (checkpoint advances only on successful complete
  load; stale-lock janitor reclaims `(§8.14) `).

### R5 — Per-host netiquette across concurrent sources

- New cross-process host-slot limiter in `sources/base.py` request path:
  `LIMES_HOST_CONCURRENCY_DEFAULT` (int, default `2`) applies to `every` upstream host; the
  heavier policy hosts get explicit caps: abgeordnetenwatch.de 1 (21 public-office scopes
  share it), ted.europa.eu 1 (429-prone, observed), webgate.ec.europa.eu 1, overpass
  hosts 1 (BE-53 budget already per-request 4-attempt), bundestag.de 1.
- Mechanism: per (host, slot) flock files `/data/host-slots/<host>/<i>.lock`
  (`i < cap`); a request acquires any free slot (blocking, bounded wait `10 s` default,
  `LIMES_HOST_SLOT_WAIT_SECONDS`) before the HTTP call and releases after the response —
  same kernel-release crash semantics as R2. Streaming responses (OSM XML may stream) keep
  the slot until the response body is fully consumed (slot released in `finally` at
  request completion, mirroring today's per-request lifecycle).
- Intra-source loops never violate this: a single cursor run holds at most one slot per
  host at a time (unchanged); 21 scopes × 2 parallel scopes pairs would otherwise hit
  abgeordnetenwatch 14-deep — this limiter is what makes R1 safe with BE-56 scope fan-out.

### R6 — observability and operator surface

- `GET /operations/jobs/{job_id}` unchanged shape (status gains `cancelled`).
- Operator diagnostics: worker logs each claim/finish/fail with `pool_slot`, and any
  budget-exhausted run logs its budget line. `/ingest/status` semantics unchanged
  (`latest-run-per-source` likewise).
- Job submission response stays 202 + Job model; 256-slot queue cap unchanged.

### R7 — tests

- Unit: pool claim/finish-reopen loop; cancel of queued (direct `cancelled`), cancel of
  running (subprocess SIGTerm path, subprocessFinishes as `cancelled`, exit_code -15
  recorded), cancel idempotency/409, store migration of old DB shape (no `cancel_requested`
  column), budget abort (clock faked; abort closes record durable with 1 error, checkpoint
  unchanged), transport-failure budget with endpoint rotation not resetting it, write gate
  (two threads/batches serialized — via a slow fake driver call), host slots (two
  processes contended on same host; different hosts unaffected).
- Integration (disposable graph, pattern of existing integration tests): two sources
  concurrently, one with a hanging fetch (mock sleep heavy), prove the other completes and
  DB writes land; cancel of the hanging job leaves the other unaffected; scope jobs ×2
  respecting abgeordnetenwatch cap=1.
- Regression guard: existing operation tests must pass unchanged (status literal widened is
  additive; `finish()` unchanged for succeeded/failed).

## Rollout/operator notes

- Deploy via `venv/bin/python tools/deploy.py` as usual (immutable images, `record.json`),
  after merging PR to main; existing job DB auto-migrates on worker start (`ALTER TABLE`,
  idempotent `PRAGMA table_info` guard).
- New keys go to `config/settings.env` (documented defaults above); ACL discipline after any
  config edit (drop→`setfacl -m u:7474:r`, chmod BEFORE setfacl, restart api/worker).
- Runtime contract (`docs/OPERATIONS.md` generated) must be regenerated after the change
  (`tools/generate_runtime_docs.py`), including `operations_authentication` unchanged and
  new job-concurrency capabilities block (`limes-runtime` payload gets
  `job_concurrency_default` and `write_gate` fields; VERIFICATION section updated).

## Acceptance criteria

- AC-1: two different sources ingest concurrently (integration test evidence) while a third
  hung fetch is cancelled without affecting the other two.
- AC-2: graph write batches serialize: at no time do two write transactions overlap (unit
  test with instrumented fake driver + fake gate proves mutual exclusion; inspection of
  driver code confirms single choke point).
- AC-3: a degraded source with endpoint rotation aborts its run within its
  `LIMES_SOURCE_TRANSPORT_BUDGET_ATTEMPTS` consecutive failures (unit test, faked clock),
  closing its record durably; the queue proceeds (pool picks the next source).
- AC-4: cancel of queued job → `cancelled` without any subprocess; cancel of running →
  process group SIGTERMed; job status `cancelled`; a cancelled job is NOT replayed on
  worker restart.
- AC-5: parallel public-office scopes against the same provider respect per-host slots
  (unit + integration evidence); no politeness violation when 2+ scopes run concurrently.
- AC-6: heartbeat/news scheduling cadence remains µreserved with N running jobs.
- AC-7: docs regenerated (OPERATIONS.md), settings example updated, all compose/vendor
  behavior unchanged, `pytest` green.

## Implementation slicing (for sessions)

- **IP-1**: store column + Job status literal + cancel flag; API POST cancel; worker pool
  with per-job cancel events; heartbeat de-coupling. Tests (AC-4..6, partial AC-1).
- **IP-2**: write gate in `Driver.write_batch` + settings keys + example env + unit tests
  (AC-2).
- **IP-3**: run budgets + `SourceRunBudgetExceeded` + transport budget + tests (AC-3).
- **IP-4**: host slots limiter + caps + tests (AC-5).
- **IP-5**: docs/OPERATIONS regen, settings example, remote CLI cancel, client cancel,
  CHANGELOG/docs INDEX touch; full `pytest`; final PR branch validation
  (`tools/check_git_baseline.py`, deploy `--check`).

Deployment gate: PR to main only after user approval, per the standing Git workflow
(branch→push→PR→user merges; user merges, then operator pulls and `tools/deploy.py`).
