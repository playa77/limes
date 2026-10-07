# AGENTS.md — LIMES testing phase

Read the newest five entries in `DECISIONS.md`, the current contract in
`docs/TESTING_PHASE.md`, and `OPEN_ISSUES.md` on re-entry. Older design/specification
files describe the initial implementation; the testing-phase contract supersedes
changed behavior. Runtime currently has three services: Neo4j, API and worker.

## Repository baseline — before any implementation or publication

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

Model and prompt changes need normal implementation review and meaningful tests,
not an operator budget envelope or a work-package ceremony. Model identifiers are
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
remain supported for migration; Compose mounts only the split config directory.

Every API surface requires `LIMES_API_TOKEN`, including docs and health. Desktop
credentials are session-only; use HTTPS remotely or a loopback SSH tunnel. Starting
the stack is an administrator action; using the HTTP API needs no Docker membership.

Remaining privilege defects are tracked, not endorsed: the worker is still an idle
exec container with a Docker socket, and physical backup still uses it. Do not
expand that privilege surface. Finish the worker/backup redesign before claiming
rootless operations. No agent staging, commits, pushes, deployment or merges unless
explicitly requested. Changes to production data and co-tenant services are outside
an implementation request.
