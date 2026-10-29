# DC-14 desktop qualification and current re-review

Candidate branch `codex/dc-14-desktop-qualification`, live-fetched base
`a434adc0fe4b`, 2026-10-29. This is a bounded current-source re-review, not the
absent original 18-finding review log (OI-05). Final candidate identity, commands
and results belong to [VERIFICATION](VERIFICATION.md). The acceptance checklist
was recorded before coding in [ROADMAP](ROADMAP.md).

## Correctness decisions and evidence

- OI-10: relation changes refill admissible directions; direction changes do not
  refill/reset the relation. Every refill retains still-admissible selections,
  chooses the first schema option when a choice becomes invalid, and recomputes
  the entire downstream chain. Submission rechecks every triple. The invented
  self-both/multi-hop scenario in `test_desktop_qualification.py` exercises both
  direction preservation and upstream invalidation; existing builder tests cover
  supertype-expanded target sets and API error/coverage propagation.
- OI-11/18, D-86: the API-only contract remains unchanged. The Leaflet map uses
  bundled assets and actual finite latitude/longitude positions, no tiles or
  geographic inference. The visible notice names the missing basemap and geometry
  count. WebEngine profiles install a deny-by-default request interceptor before
  loading their first page. Only existing files under the resolved bundle root,
  Qt WebChannel's exact resource URL and about:blank are admitted. Arbitrary local
  files, HTTP(S), WebSocket and data URLs are denied. A real attempted external
  image is blocked on each real visualization page, even with Qt's separate remote
  content restriction deliberately relaxed in the test. ApiClient separately
  rejects cross-origin redirects before sending another request, including tokenless
  requests; same-origin redirects remain bounded and supported.
- The re-review found and fixed additional relevant defects: missing Qt slot
  declarations made JS click/zoom calls unavailable; Leaflet LatLng coordinates
  were reversed; nonfinite/malformed coordinates could reach JS; filter changes
  only affected future results; hidden views imported WebEngine eagerly; network
  expansion lost prior deltas/coverage; backup was not initialized by the shell;
  a capability response containing backup=false enabled submission; health checks
  treated a degraded response as recovered; shell startup blocked on network;
  unreachable probes stopped rather than detecting recovery; source profile replies
  could arrive late; typed entity evidence lookup used dict access; changing entity
  could retain stale neighbor rows. The actual-widget scenario also exposed saved
  query capture depending on the currently visible page: the library now retains
  the last query surface while it is visible. The full suite then exposed the
  backend's automatic history path rejecting repeated NL executions. It now keeps
  the existing per-execution recording contract, while manual saved-query duplicate
  protection remains intact; the real-widget regression asks twice and checks two
  history records.
- Shared temporal visibility intersects validity intervals and independently applies
  recorded/retracted belief instants in UTC, including offsets and date-only upper
  bounds. Unknown timestamps remain unknown/visible, never synthesized from another
  axis. Network, map and timeline redraw their retained original result immediately;
  selection and filter changes do not mutate history. Qualified unknown event time
  stays separate from recorded time. Timeline markers label both axes; map/timeline
  clicks and network expansion use actual registered Qt slots. The toolbar offers
  independent validity bounds and belief-as-of, with invalid ranges rejected.

## Requirements and acceptance disposition

Evidence paths below are under `desktop/tests/` unless otherwise stated. Test
presence is not a claim of interactive Ubuntu or administrator-deployment acceptance.
All automated API/model/provider interactions use mocks or disposable fixtures.

| Requirement | Direct bounded evidence | External qualification still needed |
|---|---|---|
| FR-DC-001/002 | unit/test_api_client.py; unit/test_main_window.py; background probes and stale-profile regression in unit/test_desktop_qualification.py | Reference deployment connection/profile switching with real credentials, administrator |
| FR-DC-003 | unit/test_config.py and API token/HTTPS tests; session-only token factory remains in __main__.py | Administrator's real profile/credential setup; no secret file read for this candidate |
| FR-DC-010/011 | unit/test_search_debounce.py; integration/test_full_flow.py actual-widget search and entity navigation | Reference keyboard/display usability, Ubuntu operator |
| FR-DC-020/021/022 | unit/test_entity_view.py; main-window wiring; actual-widget graph/API assertion provenance and incremental expansion | Interactive visual/provenance usability on reference display |
| FR-DC-023/044 | unit/test_news_view.py, test_developments_view.py; BE-43/DC-15 and BE-44/DC-16 graph scenarios retained | Production source completeness/model quality stays unmeasured under D-84 |
| FR-DC-030/031/032/033/034 | unit/test_query_views.py, test_query_builder_view.py, test_coverage_panel.py; actual-widget integration drives NLQ/editable rerun, builder, console, save/delete and empty diagnosis | Reference human review of generated-query/editing workflow; no paid call used |
| FR-DC-040/041/042/043 | unit/test_desktop_qualification.py real web rendering/clicks/Qt slots/network rejection; interval/belief redraw regression; existing viz tests | Reference interactive geometry/zoom/selection and bitemporal interpretation |
| FR-DC-050/051/052 | unit/test_ops_views.py; visible shared health banner and repeated connection recovery | Real operational histories remain administrator evidence |
| FR-DC-060/061/062/063 | unit/test_backup_runner.py: no submission before visible consequence confirmation, single UUID submission, async status, retained job ID/dump, health result, unavailable/consumer capability handling | End-to-end administrator deployment backup and desktop confirmation of recovered health; disposable physical recovery remains BE-45 evidence |
| NFR-DC-070 | unit/test_app.py real local socket; isolated native WebEngine lifecycle subprocess | **External blocker REF-DC-1:** no Ubuntu 24.04+ X11/Wayland reference session/hardware is attached; current host is Debian 13/offscreen |
| NFR-DC-071 | Cold subprocess imports, shows actual shell, types into search and records elapsed seconds; asserts WebEngine core/widgets remain unloaded; slow-probe responsiveness regression | **REF-DC-1:** ≤3s target on the reference machine remains unmeasured; local offscreen observation is not substituted |
| NFR-DC-072 | Enforced local resource policy and real forbidden-resource regression; no map provider; bounded same-origin HTTP client redirects | No external tile policy decision outstanding; API-only requirement preserved |
| NFR-DC-073/074 | Existing offline suites, model parity/ontology guards, disposable integration and new real-widget scenario | Conformance to arbitrary third-party API implementations cannot be inferred beyond the checked contract |
| AC-DC-1 | Actual widgets → authenticated API → disposable graph complete flow, plus independently rendered JS/Qt pages | **External blocker DEP-DC-1:** current administrator production Compose endpoint/revision not supplied; no live deployed manual flow claimed |
| AC-DC-2 | Provenance displays distinct validity/belief labels; real timeline has both named traces; UTC interval/belief filtering regression | **REF-DC-1:** human cross-view interpretation on reference display |
| AC-DC-3/4 | Coverage/diagnosis tests and real-widget empty query; ontology-free contract guard retained | None for the bounded implementation contract |
| AC-DC-5 | Actual dialog confirmation/status unit scenario, plus BE-45 physical dump/content restoration test | **DEP-DC-1:** current administrator deployment + desktop observation of the real backup; not claimed from mocks |
| AC-DC-6 | Shared always-visible banner, async repeated outage/recovery and old-profile rejection; individual query/ops error tests; search failure clears hits | **REF-DC-1/DEP-DC-1:** manual multi-view outage/recovery on actual deployment |
| AC-DC-7 | contract/test_model_parity.py includes jobs, enrichment, news, developments and top-level query/neighbors; full source guards preserved | No semantic universality claim from field parity alone |
| AC-DC-8/9 | Existing BE-43/DC-15 and BE-44/DC-16 graph/API/desktop scenarios remain in full candidate suites | Production/source/model evidence remains separate, as recorded in those deliveries |

**External blocker HIST-DC-1 (OI-05):** the original ignored
`.superpowers/sdd/2026-09-09-desktop-client/progress.md` is absent. This current
inventory cannot authenticate/reconstruct its unknown 18 findings. No waiver or
historical closure is inferred. The original must be recovered from its owner if
historical review closure is required.

## Reference operator follow-through

On the exact qualified source, record OS/Qt/session/hardware and actual displayed
workflow evidence on both Ubuntu X11 and Wayland. Measure cold process start to
interactive search against the ≤3s target. Exercise selection and time filters in
all three visualizations, both temporal axes with a known historical assertion,
invalid/missing geometry, a multi-hop direction change, API loss/recovery and profile
switch. Confirm graph downtime/180-second stop grace before one deliberate backup,
retain its job ID/dump and verify API health after it. Record the production revision
and deployment observation separately from disposable fixtures. These actions need
the named reference host and administrator deployment; they are not silently waived
or executed against unspecified production data.
