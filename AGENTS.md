# AGENTS.md — LIMES testing phase

Read docs/INDEX.md, both docs/BACKEND_ROADMAP.md and docs/DESKTOP_ROADMAP.md,
docs/VERIFICATION.md, the current disposition index in OPEN_ISSUES.md and the
newest five DECISIONS.md entries on re-entry. Core design/technical specification
and desktop requirements/architecture are maintained product contracts; generated
docs/ARCHITECTURE.md, OPERATIONS.md and TESTING_PHASE.md describe the shipped
runtime. Historical plans in docs/archive are inactive. Runtime has three services:
Neo4j, API and worker. Edit tools/generate_runtime_docs.py and regenerate rather
than changing generated documents alone; the checker rejects drift.

Use BE-NN for backend and DC-NN for desktop. Bare historical WP numbers are
ambiguous and require a track qualifier. The package registers distinguish
implementation, acceptance evidence, current defects and superseded requirements;
never equate a merged commit with completed acceptance. BE-41 documentation
acceptance gates further runtime coding. Known implementation/measurement/operator
gaps retain their assigned packages and closure conditions after that gate passes.

## Delivery contract for LIMES

This contract takes precedence over conflicting instructions elsewhere in this
file or in existing project guidance.

1. **Deliver one full work package per session, branch and PR.** Children are
   internal steps and commits. Do not invent smaller delivery packages to fit a
   turn or context window. Continue through compaction and resume the same parent
   after interruption. Partial delivery requires an explicit user instruction.
2. **Define completion before coding.** Record the selected WP, acceptance
   checklist, actual prerequisites and branch. Every handoff maps delivered
   behavior to that checklist. Preserve incomplete obligations and identify
   concrete blockers; never call a child the completed parent. Flag an impractical
   package boundary before beginning instead of silently changing the plan.
3. **Validate proportionately.** During development run affected tests and shared
   invariant checks. Use one authoritative full pre-merge candidate run; routine
   main pushes get bounded smoke. Documentation gets relevant lightweight checks.
   Run independent CI lanes on separate runners. Keep full manual/release checks,
   exact candidate evidence and a stable fail-closed required status.
4. **Require a reason for new verification cost.** New tests cover a distinct
   behavior, regression or failure; shared invariants live in shared coverage.
   Preserve independently derived numerical expectations. Do not use fixed test
   quotas, copied pair suites or cumulative pass counts as a delivery target.
5. **Report behavior and measurements honestly.** Lead with completed acceptance
   and remaining blockers. Separate handwritten implementation, tests/helpers,
   fixture data, generated files and documentation. Separate additions/deletions
   from net growth, and new tests from cumulative passes. Measure validation and
   merge latency separately from implementation effort when evidence permits.
6. **Review the workflow after the first three PRs.** Check that complete WPs are
   shipping and compare implementation, validation and merge delay. Investigate
   sustained CI growth, repeated corrections, copied registrations or repeated
   partial handoffs immediately. Correct the process within the active scope;
   do not respond by creating still smaller PRs.

## Repository baseline — before any implementation or publication

For every session, including Q&A, architecture review, planning, documentation and
study material, verify the live GitHub baseline before substantive work. Never
substitute a supplied checkout or cached remote reference when fetching fails.
Check required sandbox network permissions first; use the configured proxy with
explicit network access when needed. If live access still fails, retry every
120 seconds until it succeeds. Preserve local work, reconcile the checkout with
current main, and inspect the resulting diff before proceeding. Do not waive this
prerequisite or ask the user to repeat it. This is the user's explicit standing
instruction, reaffirmed 2026-10-30.

At session entry inspect `git status` and the current branch. Run
`python3 tools/check_git_baseline.py`: it fetches main and requires the checkout
to contain its current history. If stale, preserve local work, reconcile with
main and review the resulting diff before implementation. A supplied workspace
or cached `origin/main` ref is never evidence that GitHub is current.

Install the repository-local publication guard once per checkout with
`git config --local core.hooksPath .githooks`. Its pre-push hook fetches live main,
checks every pushed commit, and fails closed on stale history or fetch failure.
Do not bypass this hook. It does not merge or overwrite working-tree files.
Inspect `git diff origin/main` before committing/pushing and describe the current
PR diff, not work already merged through an earlier PR. An installed local hook
is not a platform-wide initialization guarantee; fresh clones must install it.

## Verification

The canonical environment is `venv/`: create/update it with
`UV_PROJECT_ENVIRONMENT=venv uv sync --frozen --all-packages`.

Select checks according to the delivery contract above. The commands below are
the full verification inventory, not a requirement to rerun every suite during
each development iteration or documentation change.

```bash
venv/bin/ruff check src tests desktop/src desktop/tests
venv/bin/mypy
venv/bin/python tools/check_docs.py docs/
venv/bin/python -m pytest tests/unit -q
venv/bin/python -m pytest desktop/tests/unit desktop/tests/contract -q
venv/bin/python -m pytest tests/integration -q
venv/bin/python -m pytest tests/acceptance -q
venv/bin/python -m pytest desktop/tests/integration -q
```

Graph suites use disposable Docker containers. A dedicated external test database
may be selected using `LIMES_TEST_NEO4J_URI`; never point this at operator data.
Run acceptance separately because pytest rejects its nested plugin declaration in
whole-tree collection. Headless desktop checks use `QT_QPA_PLATFORM=offscreen`;
WebEngine may need platform-specific test flags in constrained CI environments.
Never skip a failing guard merely to get a green run.

## Surviving invariants

- Tests never make real paid model calls. Mock OpenRouter transports.
- `composition.py` owns infrastructure construction (API startup is its existing
  documented exception). No infrastructure construction inside pipeline consumers.
- Ontology remains the single source of entity/relation types. Consumers derive
  their schema and never embed ontology literals or database access in the desktop.
- Query validation and read-mode sessions remain independent barriers to writes.
  Dedicated operational endpoints may be added with explicit authentication,
  bounded parameters and tests; the initial fixed write count is not a product rule.
- Assertions remain bitemporal. Keep contradictions; use assertion `recorded_at`.
- Empty results include hop-level coverage and diagnosis.
- Content-addressed archive remains the system of record. Preserve clean shutdown
  for physical Neo4j dumps and the 180-second stop grace.
- Neo4j schema provisioning uses one DDL statement per transaction and serializes
  provisioners with the existing advisory lock.

## Routine iteration

Model and prompt changes follow the delivery contract above and need normal
implementation review and meaningful tests, without an operator budget envelope. Model identifiers are
allowed in configuration and examples. Preserve cache/provenance version keys;
record material behavior/schema changes in the changelog. Make testing evidence
and remaining gaps visible in the tracked issue ledger.

There is no cost governor. The passive ledger records provider usage and run spend.
Old `--budget` CLI arguments are optional, accepted for compatibility and ignored.
Do not execute ingestion, backfill, re-extraction or live paid evaluation merely to
verify an implementation; an implementation request does not request a data run.

## Runtime and secrets

`config/secrets.env`, `config/settings.env`, and `config/models.env` separate
credentials, tuning and tool-written pins. Never print/read existing secret files
or commit credentials. Empty environment values are unset. Pin writes validate a
model-only allowlist and use locked atomic replacement. Legacy host `.env` loads
remain supported for migration; Compose mounts split configuration read-only; writable model pins live in the
named models volume and override seed pins. The API reloads atomic model pins before its next NL query.

Every API surface requires `LIMES_API_TOKEN`, including docs and health. Desktop
credentials are session-only; use HTTPS remotely or a loopback SSH tunnel. Starting
the stack is an administrator action; using the HTTP API needs no Docker membership.

All services must run as UID/GID 7474, drop capabilities and disallow new
privileges. Never add a Docker socket, host-control CLI or arbitrary command
execution to a service. Operations use bounded authenticated jobs; backup is the
private Neo4j supervisor action. Interrupted jobs are never automatically replayed. No agent staging, commits, pushes, deployment or merges unless
explicitly requested. Changes to production data and co-tenant services are outside
an implementation request.
