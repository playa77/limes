# Backend work-package roadmap

Reviewed 2026-10-27 against live main `3f1effd`. Canonical prefix **BE-**;
historical backend `WP-NN` maps to `BE-NN`, including the inserted BE-25a.
The original roadmap defined WP-01–39 plus WP-25a (40 packages); WP-40 was a
later coverage exercise. The separate desktop sequence is [DC](DESKTOP_ROADMAP.md).
[ROADMAP](ROADMAP.md) coordinates the two tracks and the active delivery.

## Exact position and status vocabulary

Implementation commits exist in main for **BE-01–40 and BE-25a**. This is not a
claim that all original acceptance conditions are currently met. BE-41 documentation acceptance has passed for the PR candidate; merge is
pending; **BE-42 is the next runtime repair**, with
BE-43 news acquisition/qualified claims following its real data-path dependencies.
News is core scope immediately after the existing implementation, not a phase
waiting for unrelated historical cleanups to finish.

- **H**: historical implementation and repository-reported verification exist;
  no fresh full integration/acceptance or live-source certification in this audit.
- **R**: implemented but a specific current repair/acceptance obligation is open.
- **S**: historical behavior is intentionally superseded by a later requirement.
- **P**: planned, not implemented; **A**: active documentation work.
- Passing unit tests validates their bounded behavior; it cannot upgrade H/R into
  a blanket “complete”. BE-45 owns unmeasured release/operational qualification.

## Implemented package register

Each row names a representative current artifact and introducing commit; every
commit was checked as an ancestor of current main and its file content inspected.
The [recovered original definitions](archive/backend-roadmap-2026-08-01.md)
retain tasks/acceptance as historical source. Requirement changes are recorded in
D-74..D-77; original user conversations are not independently authenticated by
ledger entries. Current code, tests and explicit issues govern status.

| Package | Historical alias/scope | Commit | Current artifact | Verification source | Acceptance/status and remaining action |
|---|---|---|---|---|---|
| BE-01 | WP-01: Repository/tooling | `1a66814` | [pyproject.toml](../pyproject.toml) | [verification source](../tests/unit/test_git_baseline.py) | H — implementation and relevant tests present; no specific open defect found in this audit; full current acceptance remains unclaimed (BE-45).  |
| BE-02 | WP-02: Configuration/types/errors/logging | `2f8886f` | [config.py](../src/limes/config.py) | [verification source](../tests/unit/test_config.py) | H — implementation and relevant tests present; no specific open defect found in this audit; full current acceptance remains unclaimed (BE-45).  |
| BE-03 | WP-03: Ontology | `5476574` | [registry.py](../src/limes/ontology/registry.py) | [verification source](../tests/unit/test_ontology.py) | H — implementation and relevant tests present; no specific open defect found in this audit; full current acceptance remains unclaimed (BE-45).  |
| BE-04 | WP-04: Graph/schema/temporal | `f06bce0` | [driver.py](../src/limes/graph/driver.py) | [verification source](../tests/unit/test_graph_driver.py) | H — implementation and relevant tests present; no specific open defect found in this audit; full current acceptance remains unclaimed (BE-45).  |
| BE-05 | WP-05: Archive | `49fe0cb` | [store.py](../src/limes/archive/store.py) | [verification source](../tests/unit/test_archive.py) | H — implementation and relevant tests present; no specific open defect found in this audit; full current acceptance remains unclaimed (BE-45).  |
| BE-06 | WP-06: Usage ledger/governor | `4411634` | [ledger.py](../src/limes/cost/ledger.py) | [verification source](../tests/unit/test_governor.py) | S — passive recorder replaces governor (94052b4); no spend enforcement; BE-43 work limits. |
| BE-07 | WP-07: Graph loader | `52429d0` | [loader.py](../src/limes/graph/loader.py) | [verification source](../tests/unit/test_loader_logic.py) | H — implementation and relevant tests present; no specific open defect found in this audit; full current acceptance remains unclaimed (BE-45).  |
| BE-08 | WP-08: Graph lookups | `b4db02b` | [lookups.py](../src/limes/graph/lookups.py) | [verification source](../tests/integration/test_lookups_cross_process.py) | H — implementation and relevant tests present; no specific open defect found in this audit; full current acceptance remains unclaimed (BE-45).  |
| BE-09 | WP-09: Sources/normalizer | `416de56` | [registry.py](../src/limes/sources/registry.py) | [verification source](../tests/unit/test_source_registry.py) | H — implementation and relevant tests present; no specific open defect found in this audit; full current acceptance remains unclaimed (BE-45).  |
| BE-10 | WP-10: GISCO/NUTS | `beaa26c` | [gisco_nuts.py](../src/limes/sources/gisco_nuts.py) | [verification source](../tests/unit/test_gisco_nuts_adapter.py) | H — fixture/postcode coverage; real acquisition qualification remains BE-45. |
| BE-11 | WP-11: GLEIF | `f4ad3c8` | [gleif.py](../src/limes/sources/gleif.py) | [verification source](../tests/unit/test_gleif_adapter.py) | H — implementation and relevant tests present; no specific open defect found in this audit; full current acceptance remains unclaimed (BE-45).  |
| BE-12 | WP-12: EUR-Lex | `f4ad3c8` | [eurlex.py](../src/limes/sources/eurlex.py) | [verification source](../tests/unit/test_eurlex_adapter.py) | H — implementation and relevant tests present; no specific open defect found in this audit; full current acceptance remains unclaimed (BE-45).  |
| BE-13 | WP-13: FSD | `f4ad3c8` | [fsd.py](../src/limes/sources/fsd.py) | [verification source](../tests/unit/test_fsd_adapter.py) | H — implementation and relevant tests present; no specific open defect found in this audit; full current acceptance remains unclaimed (BE-45).  |
| BE-14 | WP-14: TED | `0ddacbc` | [ted.py](../src/limes/sources/ted.py) | [verification source](../tests/unit/test_ted_adapter.py) | H — implementation and relevant tests present; no specific open defect found in this audit; full current acceptance remains unclaimed (BE-45).  |
| BE-15 | WP-15: Transparency Register | `0ddacbc` | [transparency_register.py](../src/limes/sources/transparency_register.py) | [verification source](../tests/unit/test_transparency_register_adapter.py) | H — implementation and relevant tests present; no specific open defect found in this audit; full current acceptance remains unclaimed (BE-45).  |
| BE-16 | WP-16: Bundestag DIP | `0ddacbc` | [bundestag_dip.py](../src/limes/sources/bundestag_dip.py) | [verification source](../tests/unit/test_bundestag_dip_adapter.py) | H — implementation and relevant tests present; no specific open defect found in this audit; full current acceptance remains unclaimed (BE-45).  |
| BE-17 | WP-17: Gesetze im Internet | `6cf853c` | [gesetze_im_internet.py](../src/limes/sources/gesetze_im_internet.py) | [verification source](../tests/unit/test_gesetze_im_internet_adapter.py) | H — implementation and relevant tests present; no specific open defect found in this audit; full current acceptance remains unclaimed (BE-45).  |
| BE-18 | WP-18: Wikidata | `6cf853c` | [wikidata.py](../src/limes/sources/wikidata.py) | [verification source](../tests/unit/test_wikidata_adapter.py) | H — implementation and relevant tests present; no specific open defect found in this audit; full current acceptance remains unclaimed (BE-45).  |
| BE-19 | WP-19: OSM | `6cf853c` | [osm.py](../src/limes/sources/osm.py) | [verification source](../tests/unit/test_osm_adapter.py) | H — implementation and relevant tests present; no specific open defect found in this audit; full current acceptance remains unclaimed (BE-45).  |
| BE-20 | WP-20: OffeneRegister | `085e43c` | [offeneregister.py](../src/limes/sources/offeneregister.py) | [verification source](../tests/unit/test_offeneregister_adapter.py) | H — implementation and relevant tests present; no specific open defect found in this audit; full current acceptance remains unclaimed (BE-45).  |
| BE-21 | WP-21: GDELT/feeds | `cfe157a` | [gdelt.py](../src/limes/sources/gdelt.py) | [verification source](../tests/unit/test_gdelt_adapter.py) | R — OI-19/21/22 format, evidence, geography/window defects; repair in BE-42. |
| BE-22 | WP-22: Extraction | `40d968e` | [schema.py](../src/limes/extraction/schema.py) | [verification source](../tests/unit/test_extraction_schema.py) | H — strict text schema exists; qualified claims absent, BE-43 extends it. |
| BE-23 | WP-23: Extraction cache | `031c0a0` | [cache.py](../src/limes/extraction/cache.py) | [verification source](../tests/unit/test_extraction_cache.py) | H — implementation and relevant tests present; no specific open defect found in this audit; full current acceptance remains unclaimed (BE-45).  |
| BE-24 | WP-24: Gate/passages | `73a9a49` | [gate.py](../src/limes/pipeline/gate.py) | [verification source](../tests/unit/test_gate.py) | H — implementation and relevant tests present; no specific open defect found in this audit; full current acceptance remains unclaimed (BE-45).  |
| BE-25 | WP-25: Entity resolution | `d51f01a` | [resolve.py](../src/limes/resolution/resolve.py) | [verification source](../tests/unit/test_resolution_resolve.py) | H — entity resolution exists; cross-source event matching remains BE-43/44. |
| BE-25a | WP-25a: Embedding stamp/backfill | `10ef4b6` | [embeddings.py](../src/limes/graph/embeddings.py) | [verification source](../tests/unit/test_graph_embeddings.py) | H — implementation and relevant tests present; no specific open defect found in this audit; full current acceptance remains unclaimed (BE-45).  |
| BE-26 | WP-26: Composition | `cce322d` | [composition.py](../src/limes/composition.py) | [verification source](../tests/unit/test_composition.py) | H — implementation and relevant tests present; no specific open defect found in this audit; full current acceptance remains unclaimed (BE-45).  |
| BE-27 | WP-27: Pipeline/window | `cce322d` | [run.py](../src/limes/pipeline/run.py) | [verification source](../tests/unit/test_pipeline_run.py) | R — OI-20 mixed-channel loss; BE-42 must prove both channels survive gating/retry. |
| BE-28 | WP-28: CLI core | `d8e6370` | [ingest.py](../src/limes/cli/ingest.py) | [verification source](../tests/unit/test_cli_commands.py) | S — operator HTTP jobs/remote CLI replace host-controlled operations (9436372); BE-45 live qualification. |
| BE-29 | WP-29: Model selection | `d8e6370` | [select_models.py](../src/limes/cli/select_models.py) | [verification source](../tests/unit/test_select_models.py) | H — catalogue/pin/report flow; mocked evaluation exists, live measured models remain BE-45 operator evidence. |
| BE-30 | WP-30: Evaluation | `d8e6370` | [evaluate.py](../src/limes/cli/evaluate.py) | [verification source](../tests/unit/test_evaluate.py) | H — evaluation harness exists; representative agency corpus and paid quality evidence absent (BE-43/45). |
| BE-31 | WP-31: Migration | `d8e6370` | [migrate.py](../src/limes/cli/migrate.py) | [verification source](../tests/unit/test_migrate.py) | H — implementation and relevant tests present; no specific open defect found in this audit; full current acceptance remains unclaimed (BE-45).  |
| BE-32 | WP-32: API foundation | `ef749e4` | [main.py](../src/limes/api/main.py) | [verification source](../tests/unit/test_api_auth.py) | S — bearer auth and operator queue added by 94052b4/9436372; API startup is composition exception. |
| BE-33 | WP-33: NL-to-Cypher | `99146e6` | [service.py](../src/limes/nlq/service.py) | [verification source](../tests/unit/test_nlq_validate.py) | H — implementation and relevant tests present; no specific open defect found in this audit; full current acceptance remains unclaimed (BE-45).  |
| BE-34 | WP-34: Coverage/diagnosis | `4400d1f` | [report.py](../src/limes/coverage/report.py) | [verification source](../tests/unit/test_coverage_diagnose.py) | H — implementation and relevant tests present; no specific open defect found in this audit; full current acceptance remains unclaimed (BE-45).  |
| BE-35 | WP-35: Query routes/builder | `178bdbb` | [query.py](../src/limes/api/routers/query.py) | [verification source](../tests/unit/test_api_builder.py) | H — query/builder/saved routes; qualified claim/evidence responses require BE-43. |
| BE-36 | WP-36: Dash UI (superseded as shipped UI) | `48556d3` | [app.py](../src/limes/ui/app.py) | [verification source](../tests/unit/test_ui_components.py) | S — Dash compatibility code retained; native desktop is shipped, not a UI container. |
| BE-37 | WP-37: Images/Compose | `b38a5df` | [docker-compose.yml](../docker-compose.yml) | [verification source](../tests/integration/test_runtime_stack.py) | S — three non-root services replace old topology (9436372); OI-01/03/09 production evidence missing. |
| BE-38 | WP-38: Make/bootstrap | `b38a5df` | [Makefile](../Makefile) | [verification source](../tests/unit/test_deployment.py) | S — HTTP operational Make targets and immutable deployment replace bootstrap/shell backup; BE-45 qualification. |
| BE-39 | WP-39: Acceptance suite | `228d913` | [conftest.py](../tests/acceptance/conftest.py) | [verification source](../tests/acceptance) | H — acceptance suite exists; historical tests are not proof of every current requirement; GDELT escapes fixture coverage. |
| BE-40 | WP-40: Later coverage exercise | `d22f486` | [test_loader_logic.py](../tests/unit/test_loader_logic.py) | [verification source](../tests/unit) | H — historical coverage exercise; no current 100% coverage or quota target; no replay required. |

## Subsequent changes already merged (not a second backend sequence)

| Change | Evidence | Current disposition |
|---|---|---|
| Architecture consolidation and serialized provisioning | 9b4d4cd, b95b193; D-66..D-71 | Implemented; keep one-DDL-per-transaction and advisory locking |
| Runtime packaging fixes | 1d7ab44 | Implemented; no deployed-version claim |
| Cloud/Qt lifecycle repairs | cfcab1a / PR #1 | Implemented; desktop effects mapped in DC register |
| Testing-phase auth/accounting/config/pins | 94052b4, e440b74 / PR #2/#3 | Implemented; supersedes old monetary/unauthenticated requirements |
| Unprivileged runtime, jobs and backup | 9436372 / PR #4 | Implemented; disposable evidence in OPEN_ISSUES; operator deployment evidence absent |
| Delivery contract and news review | PR #6, 3f1effd | Documentation/review merged; not news runtime delivery |

## Remaining sequence and acceptance

### BE-41 — reconcile repository architecture, status and documentation

Documentation acceptance passed; prepared for PR review, merge pending. The checklist and handoff are in ROADMAP. Prerequisites: recovered history,
current source and issue evidence. Delivers both authoritative sequences, reconciled
core/desktop specifications and a finished-product README. No runtime coding.

### BE-42 — correct coded-source ingestion and mixed-channel evidence

Status P. Depends on BE-09/21–27 implementations; specifically repairs their
open gaps OI-19..OI-22. No unrelated desktop issue or live production deployment
is a prerequisite. Deliver the full transport/routing/evidence repair together.

Acceptance: official GDELT ZIP/61-column TSV filename/map with bounded input and
decompression; correct country-code/geography handling and fractional slot
rounding; preserved event/export/row/report identity and honest times; no synthetic
summary presented as article text. Structured and document channels survive cache,
gate, empty extraction, partial failure and retry independently. Checkpoint and
reextract ownership prevent loss or cross-channel retraction. Specify whether
Mentions coverage is required; missing article text remains a visible gap.

Use independently derived upstream fixtures and a real pipeline-to-disposable-graph
scenario; run affected/shared checks and one full pre-merge candidate. Close each
OI only with direct evidence for its defect, not cumulative passes. Prerequisites:
pinned upstream reference/fixture and mixed-output interface decision before coding.

### BE-43 — agency acquisition and qualified claim/event pipeline

Status P. Depends on BE-42. Select provider access/retention/display terms, format,
representative independently annotated DE/EN corpus and justified quality thresholds
before coding. Provider/corpus and enum/migration choices are unresolved prerequisites.
This is an integrated LIMES worker capability using core design §§3–6 and technical
specification §§5–9/15; no standalone extractor, ledger application or vector store.

Deliver source/version/correction/syndication lineage, typed attribution/modality/
assessment/event lifecycle/time precision, non-destructive event candidates,
resolver/loader migration, API serialization, filtering and explicit work limits.
Denial/proposal cannot become an unqualified completed edge; extraction confidence,
source trust and corroboration are distinct. Missing old qualifiers remain unknown.
Schema/prompt/cache/ontology and consumer contracts evolve together; retain the old
reported-speech safeguard until the qualified path works. Source checkpoints,
bounded authenticated jobs and manual failed-job replay precede external timers.

Acceptance: annotated corpus measures each behavior separately; qualified claims
round-trip source→archive→graph→API with independently checkable evidence and
replay/migration semantics. Mock paid transports in automated tests. DC-15 supplies
analyst-facing consumer acceptance; do not call the integrated feature complete
until that paired obligation is delivered. The coordinated parent delivery is
BE-43 with DC-15 in the same work session/branch/PR; they are cross-track entries,
not permission for a partial backend-only handoff. A paid evaluation requires an
explicit operator run and is reported separately from mocked verification.

### BE-44 — cross-source developments and temporal investigation

Status P. Depends on BE-43/DC-15 and useful registry/news overlap, not completion
of every unrelated backlog item. Deliver cross-source query/evidence assessment
and event candidate workflows. Acceptance: follow proposal→denial→agreement→later
official award/registry evidence across validity and recorded time; preserve
contradictions, dependent reporting and unresolved event matches. Chronology
cannot imply causation or misconduct. Coordinated parent BE-44 includes DC-16
network/timeline UX and end-to-end acceptance in the same session/branch/PR.

### BE-45 — current candidate and operator qualification

Status P/blocked on external evidence for production portions. Depends on the
specific behavior being qualified, not a condition that delays BE-42/43. Preserve
manual/release checks, exact candidate revision and one stable fail-closed required
status. Full candidate suites run once; independent CI lanes use separate runners;
routine main pushes use bounded smoke. Current workflow runs suites on both pushes
and PRs and has no aggregate status: OI-23 tracks the process gap.

Acceptance: full disposable suites, measured memory/storage under representative
workload, model-quality/usage evidence, archive/dump recovery validation, revision/
image deployment record and observed production smoke. OI-01/03/09 are operator
evidence gaps; OI-05's missing review trail stays unresolved unless recovered or
explicitly replaced by an authorized review with bounded claims. No deployment,
paid run or historical closure is inferred from this documentation repair.

## Deferred work and revisit triggers

Multi-user accounts, retention/pseudonymization, polygon processing, internal
scheduler, alerts and additional vector stores need a measured need and explicit
package scope; they have no assigned implementation slots. News acquisition,
qualified claims and cross-source analysis are already in core scope above.
