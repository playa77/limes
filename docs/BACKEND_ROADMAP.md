# Backend work-package roadmap

Updated 2026-10-29 on `codex/be-47-ingest-repair`, based on live-fetched main `f1e773812baf`. Canonical prefix **BE-**;
historical backend `WP-NN` maps to `BE-NN`, including the inserted BE-25a.
The original roadmap defined WP-01–39 plus WP-25a (40 packages); WP-40 was a
later coverage exercise. The separate desktop sequence is [DC](DESKTOP_ROADMAP.md).
[ROADMAP](ROADMAP.md) coordinates the two tracks and the active delivery.

## Exact position and status vocabulary

Implementation commits exist in main for **BE-01–40 and BE-25a**. This is not a
claim that all original acceptance conditions are currently met. BE-41 was merged
in PR #7 and BE-42 in PR #9 (`b1afc86`). **BE-43/DC-15 merged in PR #10** (`84c832d`), under the dynamic tracking
contract confirmed in D-82. BE-44/DC-16 merged in PR #11 (`44ab4eb`).
BE-45 merged in PR #12 (`b892875`) under the explicit D-84 evidence waiver;
BE-46 merged in PR #13; BE-47 repairs the first full-ingest source contracts.
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
| BE-21 | WP-21: GDELT/feeds | `cfe157a` | [gdelt.py](../src/limes/sources/gdelt.py) | [verification source](../tests/unit/test_gdelt_adapter.py) | BE-42 candidate — OI-19/21/22 repaired with upstream/disposable evidence; no production qualification. |
| BE-22 | WP-22: Extraction | `40d968e` | [schema.py](../src/limes/extraction/schema.py) | [verification source](../tests/unit/test_extraction_schema.py) | H — strict text schema exists; qualified claims absent, BE-43 extends it. |
| BE-23 | WP-23: Extraction cache | `031c0a0` | [cache.py](../src/limes/extraction/cache.py) | [verification source](../tests/unit/test_extraction_cache.py) | H — implementation and relevant tests present; no specific open defect found in this audit; full current acceptance remains unclaimed (BE-45).  |
| BE-24 | WP-24: Gate/passages | `73a9a49` | [gate.py](../src/limes/pipeline/gate.py) | [verification source](../tests/unit/test_gate.py) | H — implementation and relevant tests present; no specific open defect found in this audit; full current acceptance remains unclaimed (BE-45).  |
| BE-25 | WP-25: Entity resolution | `d51f01a` | [resolve.py](../src/limes/resolution/resolve.py) | [verification source](../tests/unit/test_resolution_resolve.py) | H — entity resolution exists; cross-source event matching remains BE-43/44. |
| BE-25a | WP-25a: Embedding stamp/backfill | `10ef4b6` | [embeddings.py](../src/limes/graph/embeddings.py) | [verification source](../tests/unit/test_graph_embeddings.py) | H — implementation and relevant tests present; no specific open defect found in this audit; full current acceptance remains unclaimed (BE-45).  |
| BE-26 | WP-26: Composition | `cce322d` | [composition.py](../src/limes/composition.py) | [verification source](../tests/unit/test_composition.py) | H — implementation and relevant tests present; no specific open defect found in this audit; full current acceptance remains unclaimed (BE-45).  |
| BE-27 | WP-27: Pipeline/window | `cce322d` | [run.py](../src/limes/pipeline/run.py) | [verification source](../tests/unit/test_pipeline_run.py) | BE-42 candidate — OI-20 repaired; graph tests prove both channels survive gate/cache/empty/failure/retry and reextract. |
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
| BE-39 | WP-39: Acceptance suite | `228d913` | [conftest.py](../tests/acceptance/conftest.py) | [verification source](../tests/acceptance) | H — acceptance suite exists; historical tests are not proof of every requirement; BE-42 adds independent GDELT format and graph/API coverage. |
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

Documentation acceptance passed; merged in PR #7 (`b9d940a`). The checklist and handoff are in ROADMAP. Prerequisites: recovered history,
current source and issue evidence. Delivers both authoritative sequences, reconciled
core/desktop specifications and a finished-product README. No runtime coding.

### BE-42 — correct coded-source ingestion and mixed-channel evidence

Implementation and local acceptance pass in this PR candidate. Depends on BE-09/21–27 implementations; specifically repairs their
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

All BE-42 checklist items in ROADMAP are satisfied. VERIFICATION records the exact
source fingerprint, full suites, correction and evidence boundaries; OPEN_ISSUES
closes OI-19..22 directly. Official exports yield coded observations only; article
text is visibly missing and only SOURCEURL associations are covered. Mentions is
not required for this repair and remains future acquisition scope. Requests are
bounded to 96 slots; larger windows must be split. Hosted checks, paid quality and
production qualification remain BE-45. No publication or deployment is implied.

### BE-43 — investigation-driven news acquisition and qualified reporting

Merged in PR #10 (`84c832d`), paired with DC-15; local acceptance evidence
is retained in VERIFICATION. Evidence: VERIFICATION and the checked
ROADMAP acceptance checklist. Depends
on merged BE-42. D-82 records the user's confirmed meaning: tracked entities and
relations belong to an ongoing investigation that LIMES actively keeps informed
about. LIMES dynamically discovers, sets up and acquires relevant feeds itself.
Provider setup and growing evaluation material are implementation responsibilities;
a user-supplied subscription or pre-existing corpus is not a coding prerequisite.

Acceptance is the complete checklist in ROADMAP: persistent tracking lifecycle,
current graph identity/alias-based DE/EN discovery, bounded automatic acquisition
in the existing worker, archive-linked versions and per-investigation checkpoints,
visible partial failures/manual replay, typed qualifications, safe persistence,
authenticated APIs/filtering, additive migrations and paired desktop evidence.
The initial acquisition surface is public search RSS with publisher/report links
and supplied headlines/snippets. Full article text, licensed agency access and
independent corroboration must never be inferred from an index response. Acquired
reports enter an unreviewed evaluation pool; annotation develops during use.

Qualified reports are NewsClaim artifacts, not positive factual relations. Denial,
proposal, attribution, assessment, lifecycle and unknown precision round-trip
through extraction, resolution, graph and API. Event descriptions are unresolved
candidates. Corrections/versions coexist with prior evidence and shared dispatches
remain dependent reporting. Existing assertions keep their historical stamps;
missing qualifiers stay unknown. Old unqualified extraction retains its safeguard.

Automated checks mock provider/model calls. Independent upstream-format and
bilingual behavioral fixtures plus disposable graph/API and desktop scenarios
supply implementation acceptance; no representative paid quality score, production
acquisition or deployment is implied. The coordinated parent includes DC-15 in
the same session/branch; BE-44 owns subsequent cross-source event matching.

### BE-44 — cross-source developments and temporal investigation

Implemented and locally accepted in the current
`codex/be-44-temporal-investigation` candidate. Depends on BE-43/DC-15 and useful registry/news overlap, not completion
of every unrelated backlog item. Deliver cross-source query/evidence assessment
and event candidate workflows. Acceptance: follow proposal→denial→agreement→later
official award/registry evidence across validity and recorded time; preserve
contradictions, dependent reporting and unresolved event matches. Chronology
cannot imply causation or misconduct. Coordinated parent BE-44 includes DC-16
network/timeline UX and end-to-end acceptance in the same session/branch/PR.

Implementation: `news/developments.py`, authenticated news routes, additive
EventMatchReview infrastructure records and `views/developments.py`. Per-channel
bounded evidence queries use independent temporal filters, target-hop coverage and
missing/truncated diagnosis. Directed participant/predicate matches remain
unresolved; explicit operator reviews preserve event-match, assessment and
independence labels separately with immutable recorded-time history. No graph
identity or source claim is rewritten. The paired desktop offers network,
coordinate-only map, both timeline axes and source span/archive-preview navigation.
See the active ROADMAP checklist and VERIFICATION for final acceptance evidence.
No production acquisition, paid quality or platform qualification is implied.

### BE-45 — current candidate and operator qualification

Candidate acceptance passed under D-84: the user waived operator-evidence and separate
production/paid-run authorization requirements. Unmeasured behavior is not verified
by that waiver; production/model/platform claims stay explicitly bounded. Depends on the
specific behavior being qualified, not a condition that delays BE-42/43. Preserve
manual/release checks, exact candidate revision and one stable fail-closed required
status. Full candidate suites run once; independent CI lanes use separate runners;
routine main pushes use bounded smoke. BE-43 separates bounded main smoke from full PR/manual lanes and adds a fail-closed
candidate-check aggregate. OI-23 retains hosted execution/required-status evidence.

Acceptance: full disposable suites, measured memory/storage under representative
workload, model-quality/usage evidence, archive/dump recovery validation, revision/
image deployment record and observed production smoke. OI-01/03/09 are operator
evidence gaps; OI-05's missing review trail stays unresolved unless recovered or
explicitly replaced by an authorized review with bounded claims. No deployment,
paid run or historical closure is inferred from candidate verification. The waiver
removes external evidence as a BE-45 delivery gate; it does not erase DC-14 defects
or recover OI-05's missing historical review. `tools/qualify.py` records the exact
source manifest, fail-closed check results and JUnit. Physical recovery checks
restore known graph content and retain bounded synthetic resource observations.

### BE-46 — Wikipedia context and Yahoo Finance company/shareholder enrichment

Status: full local implementation acceptance passed; provider/scope approved in D-80. Both adapters and supporting
identity/model/persistence/API changes are delivered as one complete backend package. Dependencies:
BE-09/18/25–27 and BE-31–35 implementations and BE-42's reliable mixed-channel path.
It does not require unrelated desktop polish, agency procurement, production
qualification BE-45 or comprehensive EU-27 coverage. BE-42 is verified in the current candidate; BE-46 can follow it without
waiting for BE-43/44. If qualified news
schema changes have landed, integrate with them; otherwise preserve compatibility
and the existing extraction safeguard without assuming future BE-43 fields.

Prerequisites before coding: representative DE/EN Wikipedia revisions and Yahoo
Finance payloads for relevant German/European issuers, dual listings/share classes,
non-German holders and unsupported/unlisted cases; provider field/access/retention
review; explicit trust ranks and identity mapping; versioned ontology/assertion/
loader/API migration and source-section completeness rules. Yahoo Finance is the
selected provider, not an open provider-selection question. Freeze exact model
names only after checking supplied fields; never invent missing board/holder data.

Acceptance checklist:

- [x] Register `wikipedia` and `yahoo_finance` through composition and bounded
  operator jobs; retain all original payloads, idempotent replay, checkpoints,
  backoff/rate limits and visible partial failures. Consumer reads do not fetch.
- [x] Wikipedia retrieves verified DE/EN page revisions with IDs, URLs, dates and
  attribution/license. Missing/ambiguous pages and redirects are handled explicitly;
  context remains retrievable without extraction output. Extracted claims use the
  shared cache/resolver/loader with exact revision/span evidence.
- [x] Verified QID/company/security/listing mappings link existing corporations
  without conflating tickers, share classes or multiple listings. Ambiguous person
  and holder matches stay unresolved; existing registry identity is preserved.
- [x] Yahoo Finance preserves available company profile, executive versus board/
  supervisory roles and membership/structure without representing executives as a
  complete board. Source dates and unknown term dates remain distinguishable.
- [x] Shareholder structure retains named major/institutional/fund holdings and
  separate aggregate ownership ratios, with shares, percentages/basis, value/
  currency, security/share class and as-of dates where supplied. No overlapping-list
  double counting, inferred control/beneficial ownership or assumed completeness.
- [x] Earnings calendars and actual report metadata retain supplied fiscal periods,
  report kinds, dates, status and URLs. Estimated dates are not published reports;
  missing/stale/unsupported sections are not zero holdings or evidence of disposal.
- [x] Version and migrate ontology, assertion/property persistence, loader and API
  together. Quantities, roles and field/row provenance survive archive→graph→API,
  replay and update with both time axes; partial snapshots cannot retract evidence
  from another section/source. Existing GLEIF/OffeneRegister history remains intact.
- [x] Expose source/section availability, freshness, unresolved identity and evidence
  through authenticated APIs and ontology-generated queries; update desktop mirrors
  and verify existing evidence views can consume them. No dedicated new desktop
  dashboard or direct desktop provider access is implied.
- [x] Use independently checkable revision/holdings fixtures, missing-field and
  failure cases plus disposable graph/API round trips. Mock paid calls and providers
  in automated checks; separately record any bounded live source qualification.
  No production ingestion, paid evaluation or deployment is authorized by planning.

Implementation/evidence: registered adapters, `enrichment/` contracts/read service,
shared pipeline/cache/resolver/loader and additive ontology 1.2.0, bounded `enrich`
operator jobs and mirrored desktop HTTP consumers. Wikipedia covers any reviewed
existing ontology entity, including countries; Yahoo remains corporation-only.
The final source manifest and five passing suites (1,256 tests, no skips) are in
VERIFICATION; independent source fixtures, malformed/missing/failure cases and two
real graph/API/shared-pipeline scenarios support every checklist item. Normalized
property drift becomes a durable failed section. Generic ingest/re-extraction
cannot select these adapters implicitly. No staging/commit/publication or production ingestion
was performed. Live probes qualify formats only; source coverage, production,
paid quality and platform evidence are not inferred from implementation acceptance.

Core design §3.6 and technical specification §8.5.3 are the authoritative contract.
Package completion includes both adapters and these supporting changes; parser-only
or one-adapter delivery is not full acceptance. BE-45 qualifies any release
candidate containing BE-46; it is not a prerequisite for developing this package.

## Deferred work and revisit triggers

Comprehensive EU-27 national and multilingual coverage is deferred to a possible
later version. Current scope remains German and European policy.

Multi-user accounts, retention/pseudonymization, polygon processing, internal
scheduler, alerts and additional vector stores need a measured need and explicit
package scope; they have no assigned implementation slots. News acquisition,
qualified claims and cross-source analysis are already in core scope above.

### BE-47 — first full-ingest repair and source-contract qualification

Active on `codex/be-47-ingest-repair`, base `f1e773812baf`.
[Acceptance and evidence](INGEST_RUN_DIAGNOSIS.md) cover DIP/auth/extraction,
transport/error lifecycle, current GLEIF/TED/OffeneRegister/Transparency/EUR-Lex
formats, the laws TOC defect, original bulk archives with bounded chunks and
manifest/API provenance, and checkpointed initial catch-up/failure replay.
Additive ontology 1.3.0 distinguishes direct/ultimate financial consolidation.
Complete local implementation acceptance passes. Final frozen qualification
passed all five suites (1,289 cumulative tests, no failures/errors/skips), shared
guards and source-drift checks; exact evidence is in VERIFICATION.
External availability and unrun production/paid evidence remain explicitly bounded;
no historical claim is silently upgraded to successful operator ingestion.


### BE-48 — second full-ingest repair

Active implementation on `codex/be-48-ingest-rerun-repair`, live-main
`a0ec26f92c7e`. Depends on BE-47 and the supplied five source job records.
[Acceptance mapping](INGEST_RERUN_REPAIR.md) defines the full parent and evidence
limits; VERIFICATION records the candidate result. External FSD/OSM availability,
operator graph coverage and actual OpenCode Go output remain separate evidence.
