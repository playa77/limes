# LIMES testing-phase contract — 2026-10-07

This document supersedes the initial design/specification only for behavior changed
in the redesign. Their ontology, type, temporal, coverage and query-validation
contracts remain in force. The attached issues brief is a requirements input;
claims about its old deployment are historical evidence, not deployment commands.

<!-- limes-runtime: {"services":["api","neo4j","worker"],"api_publication":"127.0.0.1:8000:8000","database_published":false,"api_authentication":"bearer","desktop_credentials":"session-only","budget_enforcement":false} -->

| Runtime fact | Current contract |
|---|---|
| Shipped services | api, neo4j, worker |
| API publication | `127.0.0.1:8000:8000` |
| Database publication | None |
| API authentication | Bearer token |
| Desktop credentials | Session memory only |
| Spending enforcement | None |


## Implemented behavior

- R1: CostRecorder only commits usage and accumulates process spend. No budget
  check, monthly ceiling, refusal/queue path or mandatory envelope survives.
  Legacy CLI budget flags are ignored. API/desktop ledger shapes omit remaining
  budget. Run spend uses the recorder delta, independent of concurrent callers.
- A1/A2 and R2 API access: every path, including OpenAPI and health, requires the
  configured bearer token. The API refuses startup with no credential. Compose
  publishes only the API on loopback. Desktop tokens live in session memory,
  scoped to endpoint, never in connection profile files. Remote credentials use
  HTTPS or a loopback tunnel. The operator/user split is complete for graph API
  consumption; operational control is still pending.
- A5: credentials, tunables and model pins have separate files. Empty environment
  strings are unset. Tools never write credential/configuration files. Pin writes
  validate keys/values, serialize concurrent writers and atomically replace the
  file; repeated writes of identical values preserve the file.
- B1: temperature, output limit and reasoning effort are typed optional settings.
  Requests and successful call logs record the parameter payload. Embedding calls
  do not receive chat-only parameters. Omitted parameters use provider defaults.
- B2/B3: model selection validates identifiers against its current catalogue.
  Confirmation is opt-in. Dates are automatic; measured stage requires a complete
  four-role result with finite scores, with a saved evaluation report. The flow is
  exercised offline using mocked inference; live measured model selection remains
  an operator task. Catalogue parameters accept both mapping and current list forms.
- C4: Compose no longer ships Dash. Its legacy sources/tests remain temporarily.
- D1: CI covers the verification loop and retains machine-readable test evidence.
  Existing disposable fixture cleanup is preserved. External test-database reuse
  remains available for hosts without functional Docker port forwarding.
- OI-06/07/08/12/13: guard typo, dead timeout, unused expansion bookkeeping,
  top-level response parity and the duplicated dynamic sys import are fixed.

## Governance and guarded-invariant inventory (R3/D2)

| Initial restriction or guard | Testing-phase treatment | Evidence surface |
|---|---|---|
| Hard monthly governor; G4 mandatory BUDGET | Removed; passive spend replaces ceilings | recorder and OpenRouter tests; AC-14/15 rewritten; smoke G4 |
| G1 no published ports; AC-34 UI-only loopback | API loopback publication; DB stays internal | AC-34 Compose tests; smoke G1 |
| G2 credential-free shipped Dash service | Dash service removed; API token allowed in compatibility HTTP consumer | smoke G2 and Compose guard |
| G3 spaCy models worker-only | Survives while worker architecture is unchanged | smoke G3 |
| Every model/prompt edit needs operator envelope | Removed for implementation; do not start live data/paid runs merely for tests | AGENTS and no-paid-call test convention |
| Provisional confirmation before pinning | Optional `--confirm`; current catalogue validation remains | select-models unit/acceptance tests |
| Per-work-package changelog and version event | Material behavior/schema/provenance changes recorded normally | CHANGELOG and artifact cache keys |
| Guard edits require an R3 one-way-door decision | Update guard with documented requirements and regression evidence | this inventory and D-75 |
| API has exactly three writes; no additional write surfaces | Read-only query invariant survives; dedicated bounded authenticated operational endpoints allowed | AC-18 current writes/corpus retained until operational redesign |
| Ontology literals forbidden in consumers | Survives | desktop contract and legacy UI scans |
| One composition root; structured paths load no inference | Survives | composition tests and AC-40/41 |
| Bitemporality, contradictions, assertion recorded_at | Survives | temporal/loader acceptance tests |
| Empty results require coverage/diagnosis | Survives | API/desktop coverage tests |
| Archive content addressing; clean Neo4j shutdown | Survives | archive and physical-backup tests |
| Model tools write the secret .env; agents cannot iterate pins | Replaced by atomic model-only file; actual secrets remain private | config_files and empty-env regressions |
| Never run ingestion on host; idle exec worker/socket | Existing implementation remains, but the mandate is withdrawn for redesign | next worker/backup work package |
| Four-service topology and remove override to deploy | Three current services; same authenticated loopback API for local/server | runtime contract, docs checker |
| No commits/pushes/merge without instruction | Survives; implementation does not authorize publication | AGENTS |
| No authentication / deployment as explicit non-goals | Removed | current README/security/access contract |

## Remaining redesign work

R2 operational CLI, A3/A4 and R4/C1/C2 are not complete: the worker still runs as an
idle exec carrier with the host Docker socket; API/worker images still lack a
non-root process identity. Physical backup still uses host Docker control.
Replace these together so removing privilege does not leave backup unusable.

C3's Neo4j bootstrap wrapper and application-user provisioning need that same
runtime review. E1's clean, version-stamped release/deploy record is still absent.
E2/E3's old full specification set needs regeneration once the runtime replacement
is implemented; the current override contract prevents its stale access claims
from being presented as current behavior. E4's original ignored 18-item review
trail is not present in this checkout, so the ledger's tracked OI-10..18 rows are
preserved without claiming a reconstructed complete triage. Remaining map-network,
semantic desktop and original deployment-evidence items stay open.
