# OPEN_ISSUES.md — LIMES evidenced open-issue ledger

Ledger mechanics: append-only; ids are never renumbered; an item leaves only
through a `Closed` section carrying a re-runnable evidence line. "Resolved"
means evidenced, not asserted — a bare "done" is not a closure. Design-level
deferrals stay in the roadmap with revisit triggers; this file is the
operational list and is expected to reach zero.

Current testing-phase constraints are in `AGENTS.md` and `docs/TESTING_PHASE.md`.
They supersede the initial operator-envelope/no-model-id restrictions. Tests never
make paid calls; existing secrets remain private. No staging, commits, pushes,
merges or deployment without explicit instruction. Production/co-tenant operations
are outside implementation scope. Snapshot and issue rows below are historical
records; subsequent evidence/closures are appended without erasing them.

## Current disposition — 2026-10-28 (BE-42 candidate)

This index supersedes the status wording in the historical inventory below, without
erasing its evidence. Package placement: [backend](docs/BACKEND_ROADMAP.md),
[desktop](docs/DESKTOP_ROADMAP.md). “Closed” requires the evidence in the dated
closure sections; “open” is not a statement that every old symptom still exists.

| Issue | Current state | Owner/package | Remaining obligation or closure evidence |
|---|---|---|---|
| OI-01 | Open evidence gap; current topology docs corrected | Operator + BE-45 | Observe actual deployed revision/configuration; do not infer it from new deployment tooling |
| OI-02 | Closed | DC-12 | 2026-10-07 Closed with evidence: 2 integration cases; no new deployed smoke claim |
| OI-03 | Open production-smoke evidence | Operator + BE-45 | Actual deployed-candidate smoke and record; old idle-worker implementation has been replaced |
| OI-04 | Closed | BE-37/38 superseding runtime | 2026-10-07 Closed with evidence; loopback/HTTPS/tunnel docs and drift checks |
| OI-05 | Open missing original review trail | Agent + BE-45/DC-13 | Recover source or explicit bounded re-review; do not invent closure of unknown 18 findings |
| OI-06 | Closed | DC-03 | 2026-10-07 contract-suite evidence: keyword typo corrected |
| OI-07 | Closed | DC-02 | 2026-10-07 unit evidence: dead timeout removed |
| OI-08 | Closed | DC-06/09 | 2026-10-07 unit evidence: unused expansion bookkeeping removed |
| OI-09 | Open deployed-revision evidence | Operator + BE-45 | Real revision/image record and observation; zero tags is not itself an implementation defect |
| OI-10 | Open semantic decision/repair | Agent + DC-14 | Verify and document direction/refill policy with behavior coverage, not a closure by prose alone |
| OI-11 | Open requirement/policy conflict | Operator decision + agent DC-14 | API-only requirement conflicts with external OSM tiles; select policy/conforming map behavior explicitly |
| OI-12 | Closed | DC-02 | 2026-10-07 parity evidence; current test covers top-level query/neighbors |
| OI-13 | Closed | DC-12 | 2026-10-07 integration evidence: dynamic sys import corrected |
| OI-14 | Closed implementation; hosted status separate | BE-37/39, BE-45 | CI workflow exists; historical no-CI statement is obsolete, configured required-status evidence remains OI-23 |
| OI-15 | Closed | BE-01 | Canonical venv documented and commands executed; 2026-10-07 closure |
| OI-16 | Closed in BE-41 | Agent/documentation | Original desktop plan archived, old path becomes a pointer, desktop roadmap is authoritative; source preserved |
| OI-17 | Closed | BE-37/38 | C8/runtime-doc guards reject publication/auth/configuration drift; 2026-10-07 evidence |
| OI-18 | Open missing network guard | Agent + DC-14 | Guard and deliberate forbidden-URL failure tied to OI-11's decided policy |
| OI-19 | Closed in BE-42 candidate | Agent + BE-42 | 2026-10-28 direct closure below: Official URL/ZIP/61-column TSV with compressed/expanded/member/row bounds; upstream fixture and real graph/API test |
| OI-20 | Closed in BE-42 candidate | Agent + BE-42 | 2026-10-28 direct closure below: Independent channels, collision-free identity, gate/cache/empty/failure/retry/reextract graph scenarios |
| OI-21 | Closed in BE-42 candidate | Agent + BE-42 | 2026-10-28 direct closure below: Archive/member/row/event/export/report/time provenance survives graph/API; no synthetic document; text explicitly unavailable |
| OI-22 | Closed in BE-42 candidate | Agent + BE-42 | 2026-10-28 direct closure below: GeoNames FIPS conversion, types 1–5, finite coordinate bounds, fractional slot ceiling and explicit workload limits |
| OI-23 | Open workflow/configuration gap | Agent + BE-45 | Full suites currently run on main pushes as well as PRs; document/configure bounded main smoke and authoritative candidate status; hosted required-check configuration unverified |
| OI-24 | Open measurement/acceptance gaps | Agent/operator + DC-14/BE-45 | Reference-platform startup/visual time-sync/manual workflows, representative memory/storage and current live/model/recovery evidence lack current qualification |

The documentation reconciliation can close while these implementation/operator
obligations remain open. It cannot close them by changing labels or accepting
unmeasured goals. Actual coding remains gated by BE-41's documentation acceptance.

## Historical inventory and evidence

Snapshot (every row from the command that produced it; run 2026-09-16):

| Fact | Command | Value |
|---|---|---|
| Local HEAD | `git log --oneline -1` | `ad42871` "docs sweep" (2026-09-10) |
| HEAD vs origin/main | `git rev-parse HEAD origin/main` (local refs only, no network) | equal — `ad428713a75d…` on both; local `main` tracks `origin/main` (`git config branch.main.remote` = origin), so this is last-fetched state |
| Working tree | `git status --porcelain` | clean — no modified, no untracked files (git-ignored caches only: `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `.superpowers/sdd/…`, `venv/`, `.venv/`) |
| Tags | `git tag -l \| wc -l` | 0 — no tags exist in this repo |
| CI | `ls .github` | no `.github/` directory — no CI workflows at all |
| Compose vs repo state | `git log -1 -- docker-compose.yml docker-compose.override.yml` | both last touched `b38a5df` 2026-08-03 (WP-37/38); `worker.Dockerfile` last touched `1d7ab44` 2026-09-07 |
| Deployed revision | operator-run check | see OI-01 — the command is provided as a row there; agent does not SSH |
| Remote URL (local config) | `git remote -v` | `origin` = https://github.com/playa77/limes (HTTPS only; no `vps` remote configured in this repo) |

---

## Open items

### 1. Contract/correctness

- **OI-01** — The docs' deployment story (local-only, override file removed to
  "promote to a server") has never described the actual deployment, which runs
  on the shared VPS at `/opt/limes` via compose with boot-persistence — and the
  operator ruled 2026-09-15 that the deployment is intentional and the docs are
  the stale side. Evidence: `docker-compose.override.yml:1-6` ("loopback
  publication … Promotion to a server is removal of this file (§13.5)");
  `README.md:13` "not operated as a service … Single operator, local machine";
  `README.md:107` "promotion to a server is removal of the override";
  `docs/LIMES_Design_Document_v2.0.0.md:475` (same claim). The repo contains no
  VPS/deploy docs at all (`grep -rn 'sshpass\|/opt/limes' --include='*.md'`
  → no tracked hits). Repair path: after the operator supplies the deploy
  parameters (path, service unit, deploy date), amend Doc 1 §13.5 + README
  §Operations to describe the actual deployment instead of the override-removal
  fiction, and record the ruling as a DECISIONS.md entry. **Owner: operator**
  (supplies deployment facts), then agent (doc amendment).
- **OI-02** — `desktop/tests/integration/test_full_flow.py` (the desktop
  client's integration flow, AC-DC-1/3) has never been executed: it was written
  in wp-12 and blocked by a sandbox Docker NAT failure that pre-existed on the
  root suite at unmodified HEAD. Evidence: `.superpowers/sdd/2026-09-09-desktop-client/progress.md:81`
  "Integration test written to convention but not executed … must run on
  healthy host"; file last touched at `b66feb5` 2026-09-10
  (`git log -1 -- desktop/tests/integration/test_full_flow.py`); no tracked
  doc records a later green run. Repair path: one operator-authorized run on
  the healthy host — `./venv/bin/python -m pytest desktop/tests/integration -q`
  — and record the result in the ledger's Closed section. **Owner: verify**

### 2. Never-verified behaviour

- **OI-03** — The live/smoke behaviour of the compose stack against the
  deployed VPS revision has never been evidenced inside this repo: the tracked
  docs name `tools/smoke_test.py` as the clean-host bootstrap check
  (`AGENTS.md:38`, `README.md:131`), but no tracked file records a smoke run
  against the deployed revision, and the runtime behaviour of
  `worker.Dockerfile:48` `CMD ["sleep", "infinity"]` idle-container pattern on
  the VPS (post-2026-09-07 deploy, boot-persistent via `limes.service`) is
  asserted only in session notes, not in any tracked artifact. Repair path:
  operator runs the deployed-revision check (OI-01's command) plus one
  documented smoke pass against `/opt/limes`; record both in the ledger's
  Closed section with the command outputs. **Owner: verify**

### 3. Docs/ledger drift

- **OI-04** — `README.md` and the compose override still describe server
  promotion as "removal of the override file", which contradicts the actual
  deployment model ruled intentional on 2026-09-15 (see OI-01); this row stays
  until the doc amendment lands, because the wrong claim appears in two
  independent surfaces that a fresh session reads first. Evidence: same lines
  as OI-01 (`README.md:13,107`; `docker-compose.override.yml:1-6`).
  Repair path: same amendment as OI-01; this row is the tracked-tree marker
  that the amendment is the fix, closed only when both files are edited.
  **Owner: agent** (after operator facts arrive).
- **OI-05** — The workspace ledger `.superpowers/sdd/2026-09-09-desktop-client/progress.md`
  (git-ignored) records the desktop branch "MERGED to main (5ab2d4e) and pushed
  to origin at operator instruction" and 18 `minor (deferred)` review findings
  that live only in the ignored tree — invisible to every future session and
  unclosed in any tracked file. Evidence: `grep -c 'minor (deferred)'
  .superpowers/sdd/2026-09-09-desktop-client/progress.md` → 18; the merge line
  is at the file tail (`## 2026-09-10 — MERGED to main (5ab2d4e) and pushed`).
  Repair path: triage the 18 deferred minors into tracked rows or explicit
  won't-fix notes (the individually evidenced ones are OI-06..OI-09 below);
  do not delete the trail. **Owner: agent**
- **OI-06** — `desktop/tests/contract/test_no_ontology_literals.py:21` pins a
  constant misspelled `CYIPHER_KEYWORDS` (typo inherited from the wp-03 brief,
  cosmetic but now guard-adjacent — renaming it touches a guard test).
  Evidence: file line 21 `CYIPHER_KEYWORDS = (`, used at line 47.
  Repair path: rename to `CYPHER_KEYWORDS` in the same commit that runs the
  contract suite (`make desktop-test`) to prove the guard still holds.
  **Owner: agent**
- **OI-07** — `desktop/src/limes_desktop/api/client.py:31` declares
  `_TIMEOUT = httpx.Timeout(30.0)` which is dead — `__init__` builds its own
  `httpx.Timeout(timeout_s)` at line 42, so the module constant misleads a
  reader about where the timeout comes from. Evidence: lines 31 vs 42 as cited.
  Repair path: delete line 31 in a commit that keeps `pytest
  desktop/tests/unit -q` green. **Owner: agent**
- **OI-08** — `desktop/src/limes_desktop/views/viz/network.py:20,25` maintain
  `self._expanded_ids` which nothing reads — the expansion-merge in
  `apply_neighbors` (lines 30-50) rebuilds the payload from history, so the
  set is bookkeeping with no consumer. Evidence: only two occurrences in the
  file, both writes (`grep -n '_expanded_ids' network.py` → 20, 25); the merge
  path at lines 38-47 never consults it. Repair path: delete the attribute and
  its write, re-run the viz unit tests. **Owner: agent**

### 4. Ops/deploy

- **OI-09** — The deployed revision on the VPS is unknown to this repo — no
  tracked deploy record, tag, or version stamp ties the running stack to a
  commit, and the operator-ruled check has not been run. The exact operator-run
  command (password read from the repo-adjacent access doc, never echoed;
  scoped so co-tenants are untouched):

  ```bash
  # operator-run, from the dev machine; sshpass is MANDATORY (no interactive prompt):
  SSHPASS="$(awk '/limes \(SSH/ {print $NF}' <access-doc>.md)" \
    sshpass -e ssh <limes-user>@<limes-host> \
    'cd /opt/limes && git log --oneline -1 && docker compose ps --format json | head -5 && systemctl is-enabled limes.service'
  ```

  (operator substitutes the real access-doc filename, user and host — the
  agent neither knows nor looks them up). Evidence: this repo has 0 tags
  (`git tag -l | wc -l`), no deploy docs (`git ls-files` has no
  deploy/VPS file), and no tracked deployment record; the deployment claim
  (deployed 2026-09-07 at `/opt/limes`, boot-persistent `limes.service`)
  exists only in operator session context, not in any tracked file.
  Repair path: operator runs the command, pastes the output into this
  ledger's Closed section; agent then records the deployed SHA in the
  snapshot table above. **Owner: operator**

### 5. Parked minors (copied out of the git-ignored work trail)

- **OI-10** — `desktop/src/limes_desktop/views/query_builder.py:211-214`
  refills the relation combo with `refill_relation=False` on text change, so
  selecting a "self-both" relation whose admissible direction set depends on
  the relation (not just the type) can leave a stale selection in the
  direction combo — the wp-08 reviewer flagged it as a defensible seam, not a
  defect, and it was parked rather than ruled on. Evidence: `.superpowers/…/progress.md`
  Task 8 line "self-both relation resets user's selection; suggest
  refill_relation=False"; code at lines 211-214 (`refill_relation=False`) and
  247-262 (`_refresh_hop` refills direction unconditionally).
  Repair path: either add a one-line comment pinning the current semantics as
  intended (cheapest), or implement the suggested `refill_relation` conditional
  — either way, close this row so the park does not dangle. **Owner: agent**
- **OI-11** — `desktop/src/limes_desktop/resources/web/map.html:19` fetches OSM
  tiles at runtime, so offline use shows a blank map — parked at wp-09 as
  "defensible", but NFR-DC-072 ("no network calls beyond the configured API",
  Requirements doc line 165) is arguably contradicted, not just uncovered.
  Evidence: `map.html:19` `L.tileLayer('https://tile.openstreetmap.org/…')`;
  `docs/LIMES_Desktop_Client_Requirements_v1.0.0.md:165` NFR-DC-072 wording.
  Repair path: operator decides — either amend NFR-DC-072 to carve out map
  tiles (one sentence), or vendor a small offline tile set; then close with a
  pointer to the decision. **Owner: operator** (decision), agent (edit).
- **OI-12** — `desktop/tests/contract/test_model_parity.py` pins nested model
  members only for `QueryResponse`/`NeighborResponse`, not the top-level fields
  (parked at wp-02) — so a top-level field added to either API model can ship
  without a desktop mirror. Evidence: `.superpowers/…/progress.md` Task 2 line;
  the parity test's own comment at line 19 ("core models by name for the
  parity message") and `model_fields` use at line 40 show the mechanism exists
  but was not extended to those two models' top-level fields.
  Repair path: add the two model names to the parity list in
  `test_field_parity()` and run `make desktop-test`. **Owner: agent**
- **OI-13** — `desktop/tests/integration/test_full_flow.py:33-34` bootstraps
  the root `tests/` package by absolute `sys.path.insert`, and the Task 12
  review's deferred note about `__import__('sys')` + duplicated path insertion
  was ruled cosmetic — recorded here so the seam is visible outside the
  ignored trail. Evidence: lines 33-34 as cited (`if _TESTS_PKG not in
  __import__("sys").path: sys.path.insert(0, _TESTS_PKG)`).
  Repair path: none required now — replace `__import__("sys")` with the
  already-imported `sys` in the next touch of that file. **Owner: agent**

### 6. Tooling/hygiene

- **OI-14** — The repo has no CI at all: no `.github/` directory, so the docs
  guard `tools/check_docs.py`, the lint gates, and the offline suites run only
  when an agent remembers to. Evidence: `ls .github` → "No such file or
  directory"; `git ls-files | grep -c .` = 359 tracked files with zero
  workflow files. Repair path: operator decision — add a minimal GitHub
  Actions workflow running the AGENTS.md verification loop's offline subset
  (`ruff`, `mypy`, `tests/unit`, `desktop/tests`), or record that single-
  operator no-CI is deliberate. **Owner: operator** (decision), agent (file).
- **OI-15** — `venv/` and `.venv/` both exist on disk and both are ignored, but
  the AGENTS.md verification loop hardcodes `./venv/bin/…` while wp-01 used
  `uv sync` (which creates `.venv/`) — a fresh session following the docs gets
  command-not-found against whichever directory it does not have. Evidence:
  `ls -d venv .venv` → both exist; `.gitignore:48-49` ignores both; AGENTS.md
  "Verification loop" block uses `./venv/bin/ruff check …` throughout;
  `Makefile:94,97` also uses `./venv/bin/`. Repair path: one sentence in
  AGENTS.md/README naming the canonical directory and the command that creates
  it (`uv venv venv` vs `uv sync`), then verify the loop runs unchanged.
  **Owner: agent**
- **OI-16** — `docs/superpowers/plans/2026-09-09-desktop-client.md` is a
  committed planning artifact inside `docs/` — a work-trail document living in
  the tracked docs tree, distinct from the tracked work trail the repo keeps
  nowhere else. Evidence: `git ls-files | grep superpowers` → this one file;
  the rest of the SDD trail (`.superpowers/sdd/…`) is git-ignored.
  Repair path: operator decision — keep (it is referenced as plan context in
  the progress ledger) or move it to `.superpowers/` with the rest of the
  trail; either is fine, the inconsistency is the item. **Owner: operator**

### 7. Missing guards

- **OI-17** — Nothing enforces the deployment-doc contract mechanically: the
  repo carries `tools/check_docs.py` (type closure, AC numbering, seam
  coverage), but no check pins the deployment story (README §Operations vs
  compose topology vs the actual deployment), which is exactly the class of
  drift OI-01/OI-04 instantiate — the docs claimed local-only while the stack
  ran on the VPS, and no gate would have caught it. Evidence: `grep -n
  'deploy' tools/check_docs.py` → no deployment-related check (file's own
  header, lines 1-22, lists only type-closure/AC/seam checks); OI-01's
  evidence lines show the drift shipped unnoticed.
  Repair path: after OI-01's amendment lands, add a check_docs rule (or a
  guard test) asserting the deployment paragraph in README matches a single
  canonical deployment statement, and prove it fails on a deliberate drift
  before trusting it. **Owner: agent**
- **OI-18** — The desktop client's no-network guarantee (NFR-DC-072) has no
  mechanical check: `desktop/tests/contract/` pins ontology literals and model
  parity, but nothing greps the vendored/runtime web assets for outbound URLs,
  so OI-11's tile fetch sits undetected. Evidence: `ls
  desktop/tests/contract/` → `test_model_parity.py`,
  `test_no_ontology_literals.py` only; `map.html:19` shows the unguarded
  outbound URL. Repair path: add a contract test asserting the only outbound
  hosts in `resources/web/` are the configured API (extend as needed once
  OI-11 is decided); verify it fails against the current `map.html` before the
  decision, so the guard documents the gap. **Owner: agent**

---

## Closing sequence (ordered)

1. **Operator batch first** — OI-01/OI-04 facts, OI-09 deployed-revision check,
   OI-11 and OI-14/OI-16 decisions. These unblock every agent row below.
2. **Verify rows with real runs** — OI-02 (desktop integration on the healthy
   host), OI-03 (smoke pass against the deployed revision). Evidence into the
   Closed section, never asserted.
3. **Agent fixes in dependency order** — OI-05 triage, then the code minors
   OI-06/OI-07/OI-08/OI-13, then OI-10 and OI-12; each closed with the suite
   that guards its file.
4. **Docs amendment + guard** — the OI-01/OI-04 edit lands after any behaviour
   rows it references, then OI-17's mechanical guard is installed and proven
   to fail on a deliberate drift; OI-18's network guard alongside it.
5. **Release mechanics last** — OI-15 (environment canonicalization) plus any
   tag/deploy steps only on explicit operator instruction, per the standing
   constraints above.

**Definition of done:** every row above is in `Closed` with a re-runnable
evidence line; the OI-17/OI-18 guards are green and proven to fail on
deliberate drift; the operator-gated items (OI-01, OI-09, OI-11, OI-14, OI-16)
are decided in the operator's own words, not merely acknowledged. An empty
ledger proves nothing — this one is not empty, and the guards, not the list,
are what keep it empty afterwards.

## 2026-10-07 — Redesign implementation and verification evidence

D-75 and `docs/TESTING_PHASE.md` define the implemented tranche. This is repo-side
work against HEAD `0aa9d67`; no staging, commits, pushes, production data runs,
deployment or real paid inference occurred. R1, A1/A2's API/desktop access, A5,
B1, selector/pin improvements, C4 and the R3/D2 inventory are implemented. R2's
operational CLI and A3/A4/R4/C1/C2 remain open together; C3 and E1 are still pending.
Live model measurement (B2) remains an operator data run; mocked evaluation exercises
the complete scoring/report/pinning path. CI is configured but no remote CI run is
claimed. The initial full spec regeneration awaits the runtime redesign.

Local evidence (2026-10-07, managed cloud host):

| Re-runnable command | Result |
|---|---|
| `venv/bin/ruff check src tests desktop/src desktop/tests` | Passed |
| `venv/bin/mypy` | Passed, 140 source files |
| `venv/bin/python tools/check_docs.py docs/` | Passed C1–C8; includes visible topology/access/accounting claims |
| `docker compose --env-file config/secrets.env.example config --quiet` | Passed without printing configuration/secrets |
| `venv/bin/python -m pytest tests/unit -q` | 737 passed; then 26 API-auth cases passed after the bearer-scheme case regression expanded the suite |
| `QTWEBENGINE_CHROMIUM_FLAGS='--no-sandbox --disable-gpu' venv/bin/python -m pytest desktop/tests/unit desktop/tests/contract -q` | 138 passed |
| `venv/bin/python -m pytest tests/integration -q` | 163 passed |
| `venv/bin/python -m pytest tests/acceptance -q` | 85 passed |
| `venv/bin/python -m pytest desktop/tests/integration -q` | 2 passed, including the previously unexecuted end-to-end flow |
| `venv/bin/python -m pytest tests/unit/test_runtime_docs.py -q` | 3 passed; deliberately changing publication or visible authentication prose is rejected |
| `git diff --check` | Passed |

Local sockets, the Docker daemon and Qt process creation required the managed
sandbox's reviewed execution access. No test invariant was skipped or weakened to
bypass that environment constraint. Container/volume cleanup used fixture-owned
resources only. Existing Starlette/runpy deprecation warnings remain non-failures.
A production Compose smoke/build/deployment was not run: it would start operational
services and fetch source data. Rendered Compose and all test suites are verified;
production startup still requires administrator deployment validation.

### Closed with evidence

- **OI-02** — Desktop integration is now executed: `venv/bin/python -m pytest
  desktop/tests/integration -q` → 2 passed. No paid calls.
- **OI-04** — README and override no longer describe server promotion as override
  removal. Current loopback API and HTTPS/tunnel access are documented. Evidence:
  `venv/bin/python tools/check_docs.py docs/` plus
  `venv/bin/python -m pytest tests/unit/test_runtime_docs.py -q` → 3 passed.
  OI-01/OI-09's original production-deployment evidence remains open.
- **OI-06 / OI-07 / OI-08** — Guard constant renamed, dead timeout removed and unused
  graph-expansion bookkeeping removed. Evidence: desktop unit/contract command
  above → 138 passed, including visualization tests.
- **OI-12** — `QueryResponse`/`NeighborResponse` top-level fields now have parity
  guards against `QueryOutcome`/`GraphNeighbors`. Evidence: desktop contract suite.
- **OI-13** — Dynamic `__import__('sys')` replaced by the existing `sys` import.
  Evidence: desktop integration → 2 passed.
- **OI-14** — GitHub Actions verification workflow added, with offline and graph
  jobs and JUnit artifacts. Its commands are evidenced locally above; remote CI
  execution is pending publication and is not a closure claim about a CI run.
- **OI-15** — Canonical environment is documented as `venv/` created by
  `UV_PROJECT_ENVIRONMENT=venv uv sync --frozen --all-packages`. Make lint/test
  commands use that path and the verification commands above execute successfully.
- **OI-17** — C8 checks the canonical runtime JSON against both Compose files and
  current README/contract snapshots and visible fact tables. Deliberate port and
  authentication-summary drift tests fail the checker as intended.

OI-05/E4 cannot be fully closed: the original ignored
`.superpowers/sdd/2026-09-09-desktop-client/progress.md` is absent in this checkout
(`test -f ...` → absent). Tracked OI-10..18 findings remain available, but the
missing 18-finding source is not reconstructed or declared complete. OI-03's
original deployed smoke behavior, OI-09 deployment stamp, map-network and remaining
semantic desktop items stay open. The old closing sequence is historical; current
remaining work is governed by the testing-phase contract rather than initial gates.

## 2026-10-07 — Repository runtime redesign verification

Implemented the remaining repo-side redesign: three unprivileged services,
operator-only durable HTTP jobs, remote CLI/desktop backup, private Neo4j
lifecycle supervision, mutable model-pin refresh, immutable-image deployment
records, and generated current architecture/operations/testing documents. No
Docker socket or Docker CLI is available to application services. Private backup
HTTP explicitly bypasses egress proxies; job failure diagnostics expose only
exception type or status, never credentials or response bodies.

Live `main` was explicitly pulled before implementation; the baseline checker
also passed after implementation at `e440b74a9e49`. Nothing was committed,
published or deployed. Existing operator configuration and production data were
not changed. Tests use disposable databases/volumes and mocked paid transports.

| Re-runnable command | Result |
|---|---|
| `venv/bin/ruff check src tests desktop/src desktop/tests` | Passed; new deployment/context/config/docs/supervisor tools also checked |
| `venv/bin/mypy` | Passed, 147 source files |
| `venv/bin/python tools/check_docs.py docs/` | Passed C1–C8, including generated-doc and privilege drift guards |
| `venv/bin/python -m pytest tests/unit -q` | 779 passed; subsequent private-HTTP/docs guard verification recorded separately |
| `QT_QPA_PLATFORM=offscreen QTWEBENGINE_CHROMIUM_FLAGS='--no-sandbox --disable-gpu' venv/bin/python -m pytest desktop/tests/unit desktop/tests/contract -q` | 132 passed |
| `venv/bin/python -m pytest tests/integration -q` | 163 existing integration cases passed; new runtime test verification recorded below |
| `venv/bin/python -m pytest tests/acceptance -q` | 85 passed |
| `QT_QPA_PLATFORM=offscreen QTWEBENGINE_CHROMIUM_FLAGS='--no-sandbox --disable-gpu' venv/bin/python -m pytest desktop/tests/integration -q` | 2 passed |
| `venv/bin/python -m pytest tests/integration/test_cli_backup.py -q` | 1 passed, real clean physical dump and recovered database |
| `venv/bin/python -m pytest tests/unit/test_cli_commands.py tests/unit/test_runtime_docs.py -q` | 15 passed after final proxy/diagnostic changes |

The initial new runtime test exposed unreadable packaged ontology artifacts and
private traffic passing through an inherited egress proxy. Those failures were
fixed in the image and private transport; neither guard was weakened. Test cleanup
is scoped to fixture-owned projects. Historical production smoke/stamp claims
(OI-01/OI-03/OI-09) still require an actual administrator deployment; disposable
runtime evidence does not rewrite that history.

E4/OI-05 still lacks the original ignored 18-finding progress log. Its absence
prevents claiming every original finding has been reconciled; tracked OI-10..18
remain available and existing unresolved semantic/map-network items remain open.

`venv/bin/python -m pytest tests/integration/test_runtime_stack.py -q` → **1
passed**. This builds all three images from allowlisted source, starts immutable
image IDs in a disposable project, verifies UID 7474, worker-only spaCy models,
bearer boundaries, command rejection, idempotent backup submission, available
job/version observation during downtime, one nonempty dump, and recovered health.
No production credentials, source ingestion or paid provider requests are used.

Final whole integration command (with headless Qt flags above) → **164 passed**,
including the new runtime case. A preceding repeated build run hit a database
write failure under accumulated managed-Docker VFS storage pressure; removing
only task-created build cache/untagged images restored 23 GB free and the complete
rerun passed without relaxing guards. JUnit evidence is retained in `work/`.
`git diff --check`, generated-doc checks, lint and type checking pass.

## 2026-10-27 — News review investigation: open ingestion defects

WP-NEWS-DESIGN (D-78) investigated the supplied ChatGPT review against `5295cab`.
Full evidence, pinned public source/hash and reproduction instructions are in
[NEWS_REVIEW](docs/NEWS_REVIEW.md). These are new **open** rows; investigation
does not close them. Owner: agent for WP-NEWS-INGEST implementation and evidence.
Existing historical closures and unresolved operator/desktop rows remain intact.

| ID | Confirmed behavior | Repair and closure condition |
|---|---|---|
| OI-19 | GDELT URL has wrong directory/suffix and extra seconds; parser expects plain comma CSV and 55 fields versus published ZIP/TSV with 61 | Complete upstream transport/field-map repair, bounded ZIP parsing and independent format fixture; prove source-to-loader behavior |
| OI-20 | GDELT returns document-kind output with structured assertions; real routing bypasses the structured handler (5 fixture assertions, 0 structured calls) | Explicit mixed-channel handling with gate/cache/retry/reextract ownership and disposable graph evidence for both channels |
| OI-21 | Export-wide synthetic summaries replace per-report evidence; SOURCEURL/DATEADDED are not retained in normalized provenance; event date is labeled publication time | Preserve export/row/report identity, honest dates and separate dispatch versions; prove evidence retrieval without fabricated article text |
| OI-22 | Geography assumes FIPS codes are ISO2, excludes non-US Geo_Type 4/5; slot rounding includes a boundary earlier than fractional `since`; docstrings claim ignored budgets bound work | Correct code mappings, supported geography and inclusive boundary rounding with independent expectations; remove misleading cost-limit claims |

Public inspection downloaded one 76,729-byte export only, without graph writes,
production ingestion, inference or agency access. All 1,178 rows had 61 fields;
the current normalizer rejected the ZIP with `SourceParseError`. The routing probe
mocked handlers, not the routing decision. Existing unit suites describe current
behavior, not upstream compatibility. [ROADMAP](docs/ROADMAP.md) defines complete
repair acceptance and the source/corpus prerequisites for integrated extraction.

## 2026-10-27 — BE-41 documentation reconciliation evidence and new dispositions

OI-16 is closed as a documentation organization decision explicitly authorized by
the user's request to repair the complete repo documentation. The historical
source is preserved in docs/archive/desktop-plan-2026-09-09.md; the original
superpowers path is a compatibility pointer. Current status/sequence belongs to
DESKTOP_ROADMAP.md. Verification: file-preservation comparison against base main,
relative-link checks and the C9 documentation organization guard.

OI-23 is **open**. .github/workflows/ci.yml has offline and graph lanes on separate
runners and triggers both push and pull_request. Full suite commands therefore run
for routine main pushes too. No aggregate candidate gate is defined in that file;
GitHub branch protection/required-check configuration was not inspected. This is
not a claim that remote checks are absent or green. BE-45 must reconcile it with
the delivery contract before its next implementation candidate is accepted.

OI-24 is **open**. Test presence, Compose limits and historical pass counts do not
satisfy measured resource/latency/platform or live deployment/model requirements.
The desktop acceptance matrix and VERIFICATION.md list the exact unclaimed areas.
No code repair, map-policy decision, production operation or paid call occurred.

## 2026-10-28 — BE-42 Closed with direct evidence (OI-19..OI-22)

These are local implementation/acceptance closures on codex/be-42-ingestion-repair,
base live main b093599d3667. The user subsequently requested PR publication; historical rows
remain intact. VERIFICATION records candidate identity, full suites and limits.

- **OI-19 closed:** `tests/unit/test_gdelt_upstream.py` checks a literal official
  URL and unchanged upstream 61-field rows plus corrupt/unsafe/multiple-member,
  compressed/expanded/row limits and schema drift. `test_gdelt_pipeline.py` proves
  production fetch→archive→normalize→loader→authenticated API with a disposable graph.
- **OI-20 closed:** `test_pipeline_run_unstructured.py::test_mixed_channels_survive_document_gate_empty_and_cache`
  proves both deterministic and extracted evidence survive independently, including
  identical relation semantics. `test_mixed_failure_retry_and_reextract_ownership`
  injects initial/replacement load failures, proves replay and no premature cache,
  checkpoint or retraction, then proves empty reextract retracts extracted only.
  Interval closure respects channel; legacy extracted ownership uses extractor_model.
- **OI-21 closed:** independent upstream field positions 0/1/59/60 and row ordinal
  check event/SQLDATE/DATEADDED/SOURCEURL. The graph/API test retrieves exact archived
  bytes by hash and row/member locator and checks missing-text metadata. A separate
  report test proves distinct reports do not collapse. GDELT emits no document;
  no synthetic summaries or assumed article publication time remain.
- **OI-22 closed:** independent country expectations GM→DE, UK→GB, CH→CN, SZ→CH;
  all coordinate geography types, invalid coordinates and exact/second/microsecond
  slot boundaries are checked. A literal endpoint test and bounded-window failure
  prove slot requests/limits. Budget flags remain ignored; no budget-limit claim.

Re-run `venv/bin/python -m pytest tests/unit/test_gdelt_adapter.py tests/unit/test_gdelt_upstream.py tests/unit/test_pipeline_run.py -q`
and `venv/bin/python -m pytest tests/integration/test_gdelt_pipeline.py tests/integration/test_pipeline_run_unstructured.py -q`
with disposable Docker access. Full inventory/results are in VERIFICATION.

The first full integration run exposed an invalid GISCO fixture that previously
advanced last_success_at despite a parse error. It now uses the existing valid
GISCO fixture, preserving the stricter no-error checkpoint rule. Docker buildx
metadata initially hit read-only ~/.docker; setting BUILDX_CONFIG to ignored
workspace work/be42/buildx fixed the environment without changing credentials.
The four affected checks and the final full graph suite passed. No guard was skipped.

Mentions, article acquisition, paid agency quality, representative resource
measurement, hosted required statuses and production deployment remain unclaimed
under BE-43/45; unrelated OI-01/03/05/09/10/11/18/23/24 stay open.
