# Desktop work-package roadmap

Reviewed 2026-10-27 against live main `3f1effd`. Canonical prefix **DC-**.
Historical desktop `wp-NN`/Task N maps to DC-NN; it never means BE-NN.
Original tasks and acceptance are preserved in the
[archived plan](archive/desktop-plan-2026-09-09.md); its unticked checkboxes and
“executed in full” banner are not current status. [ROADMAP](ROADMAP.md) coordinates
this sequence with the [backend](BACKEND_ROADMAP.md).

## Exact position

DC-01–13 implementations are in main, merged at `5ab2d4e` on 2026-09-10.
Current runtime auth/backup/lifecycle changes subsequently updated them.
**DC-14 is the next desktop repair/qualification package**; DC-15 and DC-16 are
core news consumer work paired with BE-43 and BE-44 respectively. There is no
standalone news UI or ledger iteration. No claim that every desktop acceptance
criterion is currently satisfied is made.

H = historical implementation/evidence, no blanket fresh acceptance; R = known
repair/evidence obligation; S = intentionally superseded behavior; P = planned.
Relevant current tests are linked, not treated as proof of live acceptance.

| Package | Historical alias/scope | Implementation commit | Current artifact | Verification and remaining obligation |
|---|---|---|---|---|
| DC-01 | desktop wp-01: Workspace/profiles | `fb1945c` | [config.py](../desktop/src/limes_desktop/config.py) | [unit test](../desktop/tests/unit/test_config.py); H; profile compose_root is legacy/ignored; session token is not persisted. |
| DC-02 | desktop wp-02: API client/models | `0708212` | [client.py](../desktop/src/limes_desktop/api/client.py) | [unit test](../desktop/tests/unit/test_api_client.py); S; bearer auth and operation models added; parity guard includes top-level query/neighbors. |
| DC-03 | desktop wp-03: Ontology literal guard | `ea105cf` | [ontology guard](../desktop/tests/contract/test_no_ontology_literals.py) | H; contract/test_no_ontology_literals.py; OI-06 typo closed. |
| DC-04 | desktop wp-04: SessionState | `625867d` | [state.py](../desktop/src/limes_desktop/state.py) | [unit test](../desktop/tests/unit/test_state.py); H; signal/state tests; full visual synchronization requires DC-14 qualification. |
| DC-05 | desktop wp-05: Shell/connection/search | `cb6c8fb` | [main_window.py](../desktop/src/limes_desktop/views/main_window.py) | [unit test](../desktop/tests/unit/test_search_debounce.py); H; lifecycle fixes merged; startup ≤3s and reference X11/Wayland performance unmeasured. |
| DC-06 | desktop wp-06: Entity/provenance/coverage | `157e0a9` | [entity.py](../desktop/src/limes_desktop/views/entity.py) | [unit test](../desktop/tests/unit/test_entity_view.py); H; OI-08 bookkeeping closed; qualified evidence UI belongs to DC-15. |
| DC-07 | desktop wp-07: Query/console/history | `15e355b` | [query_nl.py](../desktop/src/limes_desktop/views/query_nl.py) | [unit test](../desktop/tests/unit/test_query_views.py); H; coverage/save wiring fixes merged; no blanket user workflow acceptance. |
| DC-08 | desktop wp-08: Ontology query builder | `015ddc0` | [query_builder.py](../desktop/src/limes_desktop/views/query_builder.py) | [unit test](../desktop/tests/unit/test_query_builder_view.py); R; OI-10 direction/refill semantics unresolved, DC-14. |
| DC-09 | desktop wp-09: Network/map/timeline | `a6245ef` | [page.py](../desktop/src/limes_desktop/views/viz/page.py) | [unit test](../desktop/tests/unit/test_viz_payload.py); R; OI-11 external map tiles conflict with API-only rule, OI-18 no network guard; DC-14. WebEngine lifecycle repaired separately. |
| DC-10 | desktop wp-10: Read-only operations views | `933d253` | [ledger.py](../desktop/src/limes_desktop/views/ops/ledger.py) | [unit test](../desktop/tests/unit/test_ops_views.py); S; ledger is passive usage, not budget enforcement. |
| DC-11 | desktop wp-11: Backup orchestration | `a07fc69` | [backup_runner.py](../desktop/src/limes_desktop/backup_runner.py) | [unit test](../desktop/tests/unit/test_backup_runner.py); S; subprocess replaced by authenticated asynchronous HTTP (9436372); current manual deployment recovery unverified. |
| DC-12 | desktop wp-12: Integration flow/docs | `b66feb5` | [integration flow](../desktop/tests/integration/test_full_flow.py) | H; OI-02/13 closed with recorded 2 integration passes on 2026-10-07; not a new run or deployed smoke. |
| DC-13 | desktop wp-13: Final review/corrections | `1346847` | [main_window.py](../desktop/src/limes_desktop/views/main_window.py) | [unit test](../desktop/tests/unit/test_main_window_wiring.py); R; fixes merged but original ignored 18-finding trail absent (OI-05); not blanket review closure. |

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
| NFR-DC-072 | map.html calls tile.openstreetmap.org | Known violation/decision gap OI-11; no outbound URL guard OI-18; DC-14 |
| NFR-DC-073/074 | mocked offline and parity suites exist | Fresh candidate integration remains distinct from offline checks and release evidence |

## Remaining sequence

### DC-14 — desktop correctness and explicit acceptance qualification

Status P; depends on DC-01–13 implementations and current authenticated API.
Part of the ordinary desktop sequence, not a prerequisite for BE-42 ingestion.
Resolve OI-10 direction/refill semantics with a documented decision and evidence.
For OI-11, the API-only network requirement remains in force: an operator decision
must select an explicit tile policy or a conforming map solution. Do not silently
weaken the requirement. Implement OI-18's network guard against the decided policy
and prove it detects a forbidden URL. Qualify startup/reference platforms,
selection/time sync, API degradation and confirmation/backup UX with exact
candidate evidence. Link operator-only deployment evidence to BE-45 instead of
claiming it from mocks. Missing original review trail OI-05 remains an evidence
gap; inventory and explicit re-review cannot impersonate the original trail.

Acceptance: all DC requirements/ACs have direct evidence or a named unresolved
external blocker; the package cannot be called complete while its selected map
policy or correctness obligations remain undecided. Source/model/HTTP guards
must stay intact. No fixed test quotas or duplicate backend numerical suites.

### DC-15 — qualified news evidence and event presentation

Status P; depends on BE-43's versioned API contract. Coordinated delivery parent
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

Status P; paired with BE-44 under parent BE-44, after BE-43/DC-15. Deliver analyst
navigation between coded observations, agency evidence and later official records
across network/map/timeline. Preserve alternatives, disputes, gaps and both time
axes. No causal or misconduct inference from timing alone. Acceptance is the
complete BE-44 proposal/denial/agreement/official-record scenario, displayed
through the actual API with evidence navigation and degraded-state handling.

## Deferred

Packaging as .deb, platform-specific polish, multi-user account UX and ledger
writes require explicit need/scope. Bearer authentication and HTTP backup are
already implemented and are not deferred features. External map networking remains
an unresolved policy/correctness issue, not a silently accepted exception.
