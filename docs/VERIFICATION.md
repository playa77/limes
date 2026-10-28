# Verification and acceptance evidence — BE-41

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
| Fixture data | 0 | 0 | 0 |
| Generated documents | 38 | 31 | 7 |
| Handwritten documentation | 1394 | 1283 | 111 |
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
