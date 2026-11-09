# Desktop work-package roadmap

Updated 2026-10-29 for DC-14 local acceptance from live main `a434adc0fe4b`. Canonical prefix **DC-**.
Historical desktop `wp-NN`/Task N maps to DC-NN; it never means BE-NN.
Original tasks and acceptance are preserved in the
[archived plan](archive/desktop-plan-2026-09-09.md); its unticked checkboxes and
“executed in full” banner are not current status. [ROADMAP](ROADMAP.md) coordinates
this sequence with the [backend](BACKEND_ROADMAP.md).

## Exact position

DC-01–13 implementations are in main, merged at `5ab2d4e` on 2026-09-10.
Current runtime auth/backup/lifecycle changes subsequently updated them.
**DC-14 implementation and local qualification are accepted**; DC-15 and DC-16 are
core news consumer work paired with BE-43 and BE-44 respectively. DC-15 merged
with BE-43 in PR #10; DC-16 merged with BE-44 in PR #11 (`44ab4eb`);
DC-14's repairs are implemented on `codex/dc-14-desktop-qualification`; the final
candidate passes all five suites (VERIFICATION). Reference/platform/deployment and original-review evidence
remain explicitly bounded in [DESKTOP_QUALIFICATION](DESKTOP_QUALIFICATION.md). **DC-17
(D-99) replaces the retired PySide6/QWebEngine stack with the ReUI web client
plus launcher; its Qt-era external evidence (REF-DC-1/DEP-DC-1 style platform
and manual deployment observations) binds the retired stack, and the web
client's own qualification status is named in the DC-17 row.** There is no
standalone news UI or ledger iteration. No claim that every desktop acceptance
criterion is currently satisfied is made.

H = historical implementation/evidence, no blanket fresh acceptance; R = known
repair/evidence obligation; S = intentionally superseded behavior; P = planned.
Relevant current tests are linked, not treated as proof of live acceptance.

| Package | Historical alias/scope | Implementation commit | Current artifact | Verification and remaining obligation |
|---|---|---|---|---|
| DC-01 | desktop wp-01: Workspace/profiles | `fb1945c` | [config.py](../desktop/src/limes_desktop/config.py) | [unit test](../desktop/tests/unit/test_config.py); H; profile compose_root is legacy/ignored; session token is not persisted. |
| DC-02 | desktop wp-02: API client/models | `0708212` | [client.py]`client.py` (retired in DC-17) | [unit test]`test_api_client.py` (retired in DC-17); S; bearer auth and operation models added; parity guard includes top-level query/neighbors. |
| DC-03 | desktop wp-03: Ontology literal guard | `ea105cf` | [ontology guard](../desktop/tests/contract/test_no_ontology_literals.py) | H; contract/test_no_ontology_literals.py; OI-06 typo closed. |
| DC-04 | desktop wp-04: SessionState | `625867d` | [state.py]`state.py` (retired in DC-17) | [unit test]`test_state.py` (retired in DC-17); H; signal/state tests; full visual synchronization requires DC-14 qualification. |
| DC-05 | desktop wp-05: Shell/connection/search | `cb6c8fb` | [main_window.py]`main_window.py` (retired in DC-17) | [unit test]`test_search_debounce.py` (retired in DC-17); H; lifecycle fixes merged; startup ≤3s and reference X11/Wayland performance unmeasured. |
| DC-06 | desktop wp-06: Entity/provenance/coverage | `157e0a9` | [entity.py]`entity.py` (retired in DC-17) | [unit test]`test_entity_view.py` (retired in DC-17); H; OI-08 bookkeeping closed; qualified evidence UI belongs to DC-15. |
| DC-07 | desktop wp-07: Query/console/history | `15e355b` | [query_nl.py]`query_nl.py` (retired in DC-17) | [unit test]`test_query_views.py` (retired in DC-17); H; coverage/save wiring fixes merged; no blanket user workflow acceptance. |
| DC-08 | desktop wp-08: Ontology query builder | `015ddc0` | [query_builder.py]`query_builder.py` (retired in DC-17) | [unit test]`test_query_builder_view.py` (retired in DC-17); DC-14 candidate; admissible selections preserved and full suffix recomputed, with self-both regression. |
| DC-09 | desktop wp-09: Network/map/timeline | `a6245ef` | [page.py]`page.py` (retired in DC-17) | [unit test]`test_viz_payload.py` (retired in DC-17); DC-14 candidate; coordinate-only local map, enforced resource guard and real JS/Qt click/render/network tests. Reference display evidence remains external. |
| DC-10 | desktop wp-10: Read-only operations views | `933d253` | [ledger.py]`ledger.py` (retired in DC-17) | [unit test]`test_ops_views.py` (retired in DC-17); S; ledger is passive usage, not budget enforcement. |
| DC-11 | desktop wp-11: Backup orchestration | `a07fc69` | [backup_runner.py]`backup_runner.py` (retired in DC-17) | [unit test]`test_backup_runner.py` (retired in DC-17); S; subprocess replaced by authenticated asynchronous HTTP (9436372); current manual deployment recovery unverified. |
| DC-12 | desktop wp-12: Integration flow/docs | `b66feb5` | [integration flow](../desktop/tests/integration/test_full_flow.py) | H; OI-02/13 closed with recorded 2 integration passes on 2026-10-07; not a new run or deployed smoke. |
| DC-13 | desktop wp-13: Final review/corrections | `1346847` | [main_window.py]`main_window.py` (retired in DC-17) | [unit test]`test_main_window_wiring.py` (retired in DC-17); R; fixes merged but original ignored 18-finding trail absent (OI-05); not blanket review closure. |

Retired-stack paths above are Git history as of DC-17 (D-99); the PySide6 client those artifacts belonged to is retired on this branch.

## Acceptance disposition

| Criterion | Existing evidence | Exact remaining qualification |
|---|---|---|
| AC-DC-1 full workflow | test_full_flow.py; recorded October 7 integration result | Current deployed/manual complete flow not evidenced; DC-14/BE-45 |
| AC-DC-2 bitemporal labels | test_entity_view.py and test_viz_payload.py | Interactive cross-view time interpretation/manual check remains DC-14; news precision DC-15 |
| AC-DC-3 empty diagnosis | query/coverage unit tests plus recorded integration flow | Keep on every new news surface; DC-15/16 |
| AC-DC-4 ontology-free consumers | contract/test_no_ontology_literals.py | Preserve in every consumer change; no ontology constants allowed |
| AC-DC-5 backup | current HTTP runner tests; disposable supervisor/runtime evidence | Administrator deployment/recovery and desktop consequence confirmation at current revision remain unverified |
| AC-DC-6 degraded API state | API/client/ops/shell unit tests | Manual multi-view failure/recovery qualification DC-14 |
| AC-DC-7 model parity | contract/test_model_parity.py (including jobs and top-level query/neighbors) | Update for qualified claims in DC-15; current contract test does not prove all semantic parity |
| NFR-DC-070/071 | single-instance and lazy WebEngine tests | Reference X11/Wayland and measured ≤3s startup evidence absent; DC-14 |
| NFR-DC-072 | DC-14 local coordinate map; WebEngine request interceptor and API origin guard | D-86 preserves API-only policy; deliberate forbidden-resource tests exercise actual pages |
| NFR-DC-073/074 | mocked offline and parity suites exist | Fresh candidate integration remains distinct from offline checks and release evidence |

## Remaining sequence

### BE-56 compatibility — German parliamentary members and federal officeholders

Implemented in the full backend BE-56 candidate; qualification is recorded in
[VERIFICATION](VERIFICATION.md). [Plan and acceptance](GERMAN_PARLIAMENT_MEMBERS.md) require generic entity,
query and evidence views to display people, parliament/term mandates, distinct
party/group information and per-scope freshness/coverage. Include judicial offices
in both Bundesverfassungsgericht Senates, regular/deputy Bundesrat membership with
the represented Land, and the serving Bundespräsident/Bundespräsidentin. Extend API mirrors and
generic views as necessary in that same package; no separate parliamentary app
or desktop delivery sequence is introduced. CoveragePanel now reads all 21 scopes
asynchronously through authenticated HTTP and opens snapshot evidence through the
generic entity flow. Connection changes discard late replies. API mirrors retain
roster time basis and snapshot provenance; no desktop database/provider access is added.

### DC-14 — desktop correctness and explicit acceptance qualification

Implementation and local qualification accepted on `codex/dc-14-desktop-qualification`.
Final candidate `work/dc14/final-2/report.json` passes all five suites and shared
guards with no source drift. OI-10/11/18 close with direct evidence. The exact
requirement/AC matrix, current-source re-review and external evidence obligations
are in [DESKTOP_QUALIFICATION](DESKTOP_QUALIFICATION.md).

D-86 preserves API-only networking with a conforming coordinate-only Leaflet map
and an enforced bundled-resource WebEngine policy. Builder choices/refills and
full suffix validation are repaired. Actual Qt/JS rendering/selection, independent
validity/belief redraw, geometry, incremental expansion, asynchronous startup and
connection recovery, navigation, saved-query capture and backup confirmation/status
are exercised. The complete widget workflow includes repeated NL execution; its
supporting API history fix preserves each execution and manual duplicate protection.

Acceptance definition is retained: every DC requirement/AC has direct evidence or
a named unresolved external blocker; map policy/correctness cannot remain undecided.
The selected map policy and known correctness obligations are resolved. REF-DC-1
(Ubuntu X11/Wayland reference session/hardware and human interpretation), DEP-DC-1
(current administrator deployment/manual backup observation), and HIST-DC-1 (absent
original review source/OI-05) remain external evidence obligations. No test, BE-45
waiver or current re-review impersonates those facts. Source/model/HTTP guards stay
intact; there is no numerical test quota or duplicate backend suite.

### DC-15 — qualified news evidence and event presentation

Merged with BE-43 in PR #10 (`84c832d`); local implementation acceptance
evidence is retained in VERIFICATION. See ROADMAP and VERIFICATION for the paired checklist,
source/evidence scope and final results. Consumes the versioned API contract. Coordinated delivery parent
BE-43 includes DC-15 in one session/branch/PR; do not ship backend fields while
silently leaving the analyst surface incomplete. Implement API mirrors, query
filters, provenance/entity views and network/timeline payloads for attributed
claims, proposals, denials, event lifecycle, precision, correction/syndication
lineage and evidence gaps. No extraction or database code moves into desktop.

Acceptance: a source dispatch and its correction round-trip to visible evidence;
proposal/denial cannot display as a completed fact; time and confidence/source/
assessment meanings are separate; preserved dependent reports are not displayed
as independent corroboration. Model parity, ontology-free guards and a disposable
end-to-end workflow cover the new contract. Existing unrelated DC-14 blockers
must be visible, with actual dependency on changed views assessed before coding.

### DC-16 — cross-source temporal investigation

Merged and locally accepted with BE-44 in PR #11 (`44ab4eb`).
Paired with BE-44 under parent BE-44, after merged BE-43/DC-15. Deliver analyst
navigation between coded observations, agency evidence and later official records
across network/map/timeline. Preserve alternatives, disputes, gaps and both time
axes. No causal or misconduct inference from timing alone. Acceptance is the
complete BE-44 proposal/denial/agreement/official-record scenario, displayed
through the actual API with evidence navigation and degraded-state handling.

The investigation workspace uses the shared authenticated client and mirrored
models. Network evidence selection and both timeline axes inspect exact source
spans or bounded raw archive previews; independent instant filters reload from the
API. A coordinate-only map uses finite directly supplied graph positions with no
tile requests, preserving missing geometry explicitly. It does not change the
existing map's DC-14/OI-11/18 policy and guard obligations. Late replies are scoped
to the current investigation/request; failures clear result panes and remain
visible. Explicit reviews remain operator-only hypotheses with retained history.

BE-45's D-84 operator-evidence waiver removes those external evidence gates for
that backend delivery. It does not complete DC-14, recover OI-05's review trail,
or claim reference-platform/manual acceptance from offscreen automation.

## BE-46 supporting consumer compatibility

The enrichment backend package updates job/response mirrors and the authenticated
HTTP client without a new dashboard or direct provider access. Ontology-generated
entity properties/neighborhoods expose immutable context, quantities, dates and
evidence; the disposable backend scenario renders revision and attribution/license
properties in the existing EntityView and retrieves archive evidence through HTTP.
Model parity includes EnrichmentResponse and new bounded job selection fields.
This supporting work does not complete DC-14's independent correctness/platform
obligations or change the existing map-network policy.

### DC-17 — ReUI web desktop rebuild (id=`dc-17-reui-web-desktop`)

The complete parent replaces the retired PySide6/QWebEngine/pytest-qt stack
with a React 19 + Tailwind v4 + ReUI SPA (`desktop/web/`) served by a FastAPI
launcher (`desktop/src/limes_desktop/`), per D-99, after the ReUI component
system could not be hosted inside Qt. Stack retirement removes
`views/`, `state.py`, `api/`, `backup_runner.py`, `connection_probe.py`,
`resources/web`, all pytest-qt suites and the PySide6 dependencies from the
workspace; the retired stack's D-14 qualification evidence stays recorded in
[DESKTOP_QUALIFICATION](DESKTOP_QUALIFICATION.md) and binds the retired stack.

Implemented in this package (branch `dc-17-reui-web-desktop`):

- Launcher: static SPA serve with index fallback and traversal guard,
  `/api/*` bearer proxy with verbatim bodies, bounded same-origin redirect
  following, cross-origin refusal and pinned envelopes, `/session` descriptor
  with probe-classified credential kinds, `/profiles` XDG CRUD (name+URL
  only), loopback-only bind, flock process-level single-instance guard,
  validated port override, `--version`. Unit evidence:
  [test_webapp.py](../desktop/tests/unit/test_webapp.py),
  [test_app.py](../desktop/tests/unit/test_app.py),
  [test_cli.py](../desktop/tests/unit/test_cli.py),
  [test_config.py](../desktop/tests/unit/test_config.py).
- SPA: all views (search, entity with distinct VALIDITY/BELIEF provenance,
  NLQ with editable Cypher, builder with DC-14 refill semantics, Cypher
  console with verbatim rejections, saved queries, network/map/timeline with
  shared selection and bitemporal filtering, news claims/investigations/
  developments/documents with separate modality/assessment/lifecycle/precision,
  ingest auto-refresh, passive ledger, references, public offices, backup
  with consequence dialog and no auto-retry), shared coverage/diagnosis
  panel, connection dialog, health polling, capability gating.
- Contract machinery: `tools/export_openapi.py` and `desktop/web/tools/gen-api.mjs`
  generate the committed `openapi.json`/`schema.ts`; contract tests recompute
  the schema, pin the TS endpoint surface (required/allowed-residual sets)
  ([test_openapi_surface.py](../desktop/tests/contract/test_openapi_surface.py))
  and extend the ontology-literal guard over `desktop/web/src`
  ([test_no_ontology_literals.py](../desktop/tests/contract/test_no_ontology_literals.py)).
  Superseded: the Python model-mirror parity (`test_model_parity.py`,
  AC-DC-7's v1.0.0 mechanism) — the generated-schema mechanism replaces it.
- Integration: [test_full_flow.py](../desktop/tests/integration/test_full_flow.py)
  drives the launcher hosting the real API app over a disposable graph.
- Infra: Makefile `desktop-*`/`web-check` targets, CI `web` job (pnpm lane)
  without the retired Qt libraries, new `web` lane in
  [tools/qualify.py](../tools/qualify.py), vitest pins for the pure modules
  (builder refill, temporal filtering, viz payloads).

Remaining obligations for this package:

- Local AC mapping (A1–A15 of the session record) and full five-lane+web
  candidate evidence are recorded in VERIFICATION when the qualification run
  completes; a candidate that has not run yet is not evidence.
- Interactive browser-level SPA behavior is covered by tsc/eslint/vitest and
  the in-process integration flow; a manual browser session against a live
  stack (real click-through, network/map/timeline rendering on reference
  hardware, launcher-to-interactive-search latency) remains named external
  evidence, like REF-DC-1 for the retired stack.
- AC-DC-5's physical dump/health verification and DEP-DC-1-style
  administrator deployment observation remain external for the web client.
- Packaging (.deb / bundled dist) and multi-user accounts stay deferred in
  [LIMES_Desktop_Client_Requirements_v1.0.0.md](LIMES_Desktop_Client_Requirements_v1.0.0.md).

## DC-14 local acceptance disposition

D-86 selects a conforming local coordinate map without external tiles. Builder
refill, geometry, Qt slots, selection/temporal redraw, retained expansion, startup
and connection recovery, navigation and backup UX repairs are implemented.
Offline, real web-page, actual-widget and all five final candidate suites pass.
OI-05's original source remains absent (HIST-DC-1). Ubuntu X11/Wayland reference
hardware/session (REF-DC-1) and a specified administrator deployment (DEP-DC-1)
remain unavailable; no offscreen test or BE-45 waiver is relabeled as that evidence.

## Deferred

Packaging as .deb, platform-specific polish, multi-user account UX and ledger
writes require explicit need/scope. Bearer authentication and HTTP backup are
already implemented and are not deferred features. External map networking remains
an unresolved policy/correctness issue, not a silently accepted exception.
