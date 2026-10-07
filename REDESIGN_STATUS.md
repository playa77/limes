# LIMES redesign — implementation status

Basis: user-supplied `limes-issues-and-fixes.md`, 2026-10-06. This is the
re-entry checklist for continued repo-side implementation. Requirements in that
brief supersede conflicting initial-build process rules; historical deployment
facts are not inferred. No deployed instance was accessed or modified.

## Implemented in this change (D-75)

| Requirement | Behavior | Re-runnable evidence |
|---|---|---|
| R1 | No pre-call spend checks; no required envelopes. Ledger persists reported usage; run totals use process-local spend deltas; remaining budget is null. Legacy budget inputs are inert. | `venv/bin/python -m pytest tests/unit/test_governor.py tests/unit/test_openrouter_client.py tests/unit/test_pipeline_run.py -q`; graph-backed ledger and AC-14/15 tests |
| R3, D2 (inference/process portion) | Routine authorized model/prompt iteration needs no extra envelope; no per-work-package version ceremony. Preserve meaningful cache versions and keep-set guards. `select-models --provisional --yes` supports noninteractive ranking. | AGENTS.md, D-75, G4 dry-run guard; selector unit tests |
| A5 | Read-only legacy secrets file plus separate non-secret `config/limes.env`; empty environment values are unset. Pins/stage/date are atomically replaced and other tuning keys preserved. Directory mount exposes replacement correctly. | Config precedence/empty-shadow tests; interrupted-write/idempotency selector tests |
| B1 | Optional validated temperature, token cap, reasoning effort sent to completions and recorded in per-call structured logs. Empty knobs retain provider defaults. | Completion payload/log tests (mocked transport) |
| B3 | Pin-time catalogue validation; invalid ids excluded; catalogue parameter lists supported. | Selector unit tests |
| B2 (partial) | Measured pins require evaluated winners in all four roles; stage/date are updated together. Measured evaluation is covered offline with stubbed scores. No live measurement or measured production pins claimed. | `tests/unit/test_select_models.py` |
| D1 (partial) | CI runs lint/types/docs/offline and separate graph suites; unit API startup never waits for real database retries. | `.github/workflows/tests.yml`; offline suites. CI execution is still pending until changes are pushed. |
| OI-06/07/08/12 | Correct Cypher constant spelling, remove dead timeout and expansion bookkeeping, test top-level query/neighbors mirrors. | Desktop unit and contract suites |
| OI-15 | Canonical `venv`: `UV_PROJECT_ENVIRONMENT=venv uv sync --all-packages --all-groups`. | AGENTS.md, README, CI |

## Guard inventory and disposition

| Guard/constraint | Disposition | Reason / follow-up |
|---|---|---|
| G1 / AC-34 no API publication | Rewrite with A1/A2 implementation; retained now | Auth must precede a reachable API topology. Never expose the current unauthenticated API remotely. |
| G2 UI holds no DB/model credentials | Keep until Dash removal decision lands | Preserve consumer boundary. |
| G3 spaCy wheels only in worker image | Keep / reevaluate with C2 | Heavy inference dependencies belong in the execution service, not clients. |
| G4 BUDGET refusal / AC-14 / AC-15 | Rewritten | R1 removes enforcement; replacements verify no gate and accounting survives. |
| Exactly three API writes / no new write surfaces | Fixed-count restriction retired for authorized access redesign; current guard retained until routes change | Explicit operational routes may be added; arbitrary query writes stay rejected. |
| Operator envelopes / provisional confirmation / versioned model ceremony | Extra governance retired; interactive prompt remains optional via `--yes` | Routine testing iteration should be cheap; paid live evaluation remains an explicit operator action. |
| No paid calls in tests | Keep | All OpenRouter calls are mocked. |
| Single composition root / no consumer ontology literals / API mirror parity | Keep, extend | Sound ontology and dependency boundaries. |
| Bitemporal assertion identity / contradictions / archive / coverage on empty / read-only query path | Keep | Brief's explicit keep-set. |
| Never read or edit real secrets / no production ingestion without authorization / no unsolicited commit/push/merge | Keep | Repo-side implementation does not require these actions. |
| Host ingestion prohibition / exec-only operations / docker socket mandate | Rewrite with R2/R4/C2/A4; retained implementation pending | The new remote operational interface and privilege model must be implemented together. |
| Re-entry via very large decision history / changelog per WP | Reduced | Use this status file plus latest decisions and evidenced open rows; record material behavior changes. |

## Remaining implementation, in dependency order

1. **R2/R4/A1–A4/C1–C3:** authenticated API and desktop credential storage,
   working client topology, least-privilege remote operational CLI/job interface,
   execution service architecture, backup without host Docker socket, unprivileged
   images/volumes and reviewed database-user provisioning. Current Compose still
   carries the old idle worker/socket/root/access design; this change does not
   claim those P0 requirements complete.
2. **C4:** remove or maintain Dash consistently across packaging, Compose, guards,
   README and design docs. Do not delete historical UI tests ahead of the decision.
3. **B2/D1:** exercise the actual evaluation harness and portable graph suites,
   record measured evidence, and validate CI on GitHub. Live paid measurement is
   not part of offline verification.
4. **E1–E3:** version-stamped reproducible deployment, current access/operations
   design docs and topology/ports/access drift checks after P0 implementation.
   This change updates inference docs and marks the old design as superseded for
   implemented parts; it does not claim a completed operations-doc regeneration.
5. **E4/OI-05:** reconstruct the 18 ignored deferred findings if the source trail
   is available; preserve tracked OI-10–18 and do not pretend the absent trail was
   reviewed. Resolve map-network behavior (OI-11/18), remaining client seams and
   deployment facts with evidence.

## Verification results

Executed evidence is in `OPEN_ISSUES.md`, 2026-10-07 closure section. Lint,
strict types, docs checks, desktop unit/contract and full desktop integration
passed. Main unit, integration and acceptance runs found obsolete assertions;
all failed cases passed after correction in targeted reruns. CI is configured
but has not run on GitHub. Production Compose smoke and deployment are pending.
