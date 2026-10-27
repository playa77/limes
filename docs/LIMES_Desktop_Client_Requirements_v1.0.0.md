<!-- LIMES — Desktop Client Requirements | v1.0.0 | 2026-09-08 | Status: Maintained -->

# LIMES — Desktop Client Requirements

| Field | Value |
|---|---|
| Document | LIMES — Desktop Client Requirements (Document 3 of 3) |
| Version | 1.0.0 |
| Date | 2026-09-08; reconciled 2026-10-27 |
| Status | Maintained requirements; per-package evidence in DESKTOP_ROADMAP.md |
| Depends on | LIMES — Design Document v2.0.0 (§4, §6); LIMES — Technical Specification v2.1.0 (§6 API, §13.2 topology) |
| Supersedes | none (initial) |

This document defines the requirements for the LIMES desktop client: a native
Ubuntu application that fully replaces the Dash UI and adds read-only
operational monitoring plus backup orchestration. It is a pure API consumer for
all data paths — it holds no database access, no ontology literals, and no
extraction logic.

## 1. Purpose and scope

The client gives the operator the complete LIMES workflow in one native
window: find entities, interrogate the graph through three query surfaces
(natural language, query builder, Cypher console), inspect results as network,
map, and timeline with full provenance and coverage reporting, and monitor and
operate the running stack (ingest status, cost ledger, backups).

In scope: native query/entity/network/map/timeline investigation, qualified
news/event evidence within the same graph as registries, source coverage, passive
usage monitoring, authenticated API connection management and operator backup
jobs. [DESKTOP_ROADMAP](DESKTOP_ROADMAP.md) records actual implementation and
acceptance gaps separately from these complete-product requirements.

The client is an API consumer. It contains no extractor, ontology literals,
Neo4j driver, Docker invocation or host backup command. Ingestion remains a
bounded operator HTTP/CLI job; no separate news ledger application is delivered.
Multi-user accounts, automatic retention and distribution packaging remain
outside current scope. Shared backend requirements are in the core design and
technical specification; runtime settings are in OPERATIONS.

## 2. Technology decisions

| Decision | Choice | Rationale |
|---|---|---|
| Toolkit | Python 3.12 + PySide6 (Qt 6) | Same language and venv as the repo; native desktop chrome |
| Graph/map/timeline rendering | QWebEngineView hosting Cytoscape.js, Leaflet, Plotly | Exact visual parity with the Dash UI; the web components are proven |
| Application structure | `desktop/` workspace member (`desktop/src/limes_desktop/`) | Isolated from `src/limes`; shares types, not infrastructure |
| API contract | Typed client mirroring `src/limes/api/models.py` Pydantic models | Contract tests pin client models to API models; drift fails CI |
| Distribution | uv-managed; installable via `pipx`/`uv tool install` in v1; `.deb` later | Lowest-friction path first |

Rejected alternatives: all-native Qt rendering of network/map/timeline
(rebuilds three nontrivial viz surfaces, drifts from Dash parity); Electron or
Tauri shells (introduce a second language stack the repo does not carry).

## 3. Functional requirements

Requirements are numbered FR-DC-nnn. "API" means the FastAPI service
(Technical Specification §6). Every data-driven view degrades gracefully when
the API is unreachable: connection state is visible at all times (FR-DC-002).

### 3.1 Connection management

- FR-DC-001: The client connects to the API over HTTP at a user-configurable
  base URL. Default: `http://127.0.0.1:8000`, published by base Compose. Remote access uses HTTPS or loopback SSH forwarding.
- FR-DC-002: On startup and on connection-profile change, the client calls
  `GET /health` and displays reachability, API version, and graph summary.
- FR-DC-003: The client stores named connection profiles (name, base URL) in
  an XDG-conformant config location (`~/.config/limes-desktop/`). Credentials stay in session memory and are sent as bearer tokens. All surfaces require authentication; only operator credentials can submit/read operational jobs. Profiles never store tokens. The legacy compose_root field is ignored.

### 3.2 Search

- FR-DC-010: Free-text search over entity names and aliases via `GET /search`,
  with result type badges (entity type from the ontology) and immediate
  navigation to the entity view.
- FR-DC-011: Search-as-you-type with debounce (≥ 300 ms) and keyboard
  navigation (arrow keys, Enter) — the search box is the primary navigation
  instrument, mirroring the Dash UI's global search.

### 3.3 Entity view

- FR-DC-020: Entity detail via `GET /entity/{entity_id}`: all properties with
  type-appropriate rendering, bitemporal validity and belief timestamps
  displayed distinctly.
- FR-DC-021: Provenance panel: for every assertion, its source, confidence,
  and (where applicable) the source sentence that produced it. Provenance is
  one click from any displayed assertion, never a separate hunt.
- FR-DC-022: Neighborhood browsing via `GET /entity/{entity_id}/neighbors`
  with relation-type filtering (ontology-driven) and incremental expansion —
  clicking a neighbor re-centers the view without losing history.

### 3.4 Query surfaces

- FR-DC-030: Natural-language query via `POST /query/nl`: question in German
  or English, generated Cypher always displayed alongside results and always
  editable before execution, NLQ outcome (including adjudication metadata)
  shown per Technical Specification §6.
- FR-DC-031: Query builder: constructed at runtime from
  `GET /builder/schema`; the client contains no ontology literals (same
  invariant enforced on the Dash UI by `tests/integration/test_ui.py` — the
  desktop client is held to the identical standard by its own guard test).
- FR-DC-032: Cypher console: direct read-only queries via `POST /query/cypher`;
  write-clause rejection surfaces the API's parse-level error verbatim. Multi-
  statement history, persisted locally for the session and optionally across
  sessions.
- FR-DC-033: Saved queries: list, create, and delete via the three saved-query
  endpoints. Save actions capture the query text, surface, and a name.
- FR-DC-034: Every result — on every surface — carries the API's coverage
  report; empty results show which hop emptied the set and the graph-wide
  counts, never a bare empty list.

### 3.5 Visualization

- FR-DC-040: Network view (Cytoscape.js in QWebEngineView): nodes/edges from
  any query or entity-neighborhood result, incremental expansion from a
  selected node, layout controls, and selection sync with the entity view.
- FR-DC-041: Map view (Leaflet): entities with point geometry plotted; a
  selected entity's geographic relations drawn as lines; temporal filtering
  applies.
- FR-DC-042: Timeline view (Plotly): assertions and relations over validity
  time, with a belief-time discriminator so "what did the graph believe at T"
  is separately viewable — bitemporality is a first-class UI concern, not a
  footnote.
- FR-DC-043: All three views share one selection state: selecting a node in
  any view updates the entity panel and highlights across views, matching the
  Dash UI's `selection`/`temporal` callback behavior.

### 3.6 Operations monitoring (read-only)

- FR-DC-050: Ingest status via `GET /ingest/status`: run history, current
  stage, per-source state; auto-refresh configurable (default: 10 s while the
  panel is visible, disabled otherwise).
- FR-DC-051: Cost ledger via `GET /cost/ledger`: entries with spend by model,
  by run, and passive totals without a budget ceiling. The ledger view is
  read-only in the client in v1 — cost entries are written by the pipeline.
- FR-DC-052: Sources and ontology metadata via `GET /sources`,
  `GET /ontology`, and `GET /ontology/versions`, presented as reference
  panels (source registry, entity/relation type catalog with domain/range).

### 3.7 Backup orchestration

- FR-DC-060: Submit backup via the API's operator-only `/operations/jobs` using
  an idempotent request UUID. No local Docker, shell or compose-root access.
- FR-DC-061: Confirm the consequence before submission: graph unavailable during
  clean stop/dump/recovery; supervisor stop grace is 180 seconds. Never retry a
  failed paid/operational job automatically.
- FR-DC-062: Poll job status asynchronously, surface bounded output/dump name and
  success/failure, then verify API health. Disconnecting does not cancel the server
  job; retain its identifier for observation. Protect credentials in errors/logs.
- FR-DC-063: Disable backup with a precise explanation when the API is unreachable
  or an operator credential/capability is absent. A consumer token cannot submit it.

### 3.8 Non-functional requirements

- NFR-DC-070: Ubuntu 24.04+ on X11 and Wayland; single-instance behavior.
- NFR-DC-071: Startup to interactive search in ≤ 3 s on the reference machine;
  the QWebEngineView runtime is lazy-loaded on first visualization use.
- NFR-DC-072: No telemetry, no network calls beyond the configured API and
  operator job API — local-first defaults. Current external OSM tiles violate this requirement; OI-11/DC-14 requires an explicit policy or conforming map repair, not a silent exception.
- NFR-DC-073: Offline unit test suites for all client logic; API interactions
  mocked; no test makes real inference calls (repo invariant).
- NFR-DC-074: The client is replaceable against the API contract: it must work
  unmodified against any conformant implementation of Technical
  Specification §6.

## 4. Acceptance criteria

- AC-DC-1: With the Compose stack up, the client performs end-to-end: search →
  entity view with provenance → incremental network expansion → NLQ with
  editable Cypher → builder query → Cypher console → save/delete a saved
  query, each result carrying its coverage report.
- AC-DC-2: Bitemporal display: a single entity view shows at least one
  assertion's validity time and belief time as distinct, labeled values.
- AC-DC-3: An empty result on any surface renders the hop-level diagnosis,
  never a bare empty state.
- AC-DC-4: Source scan of `desktop/src/limes_desktop/` finds no ontology type
  or relation literals (guard test, mirroring `test_ui.py` for the Dash UI).
- AC-DC-5: Triggering backup from the client produces a timestamped
  `limes-<timestamp>-<suffix>.dump` in the archive volume and a successful post-backup
  `/health` check, with the confirmation dialog shown before execution
  (FR-DC-061).
- AC-DC-6: With the API stopped, every view shows the unreachable state
  within its refresh interval and no unhandled exception escapes to the user.
- AC-DC-7: Client contract tests validate every API response model used by
  the client against the live Pydantic models in `src/limes/api/models.py`;
  a model change without a client update fails CI.

## 5. Qualified news and event requirements

- FR-DC-023: Show dispatch/provider/version, text span or coded row/report locator,
  correction and syndication lineage, source trust, extraction confidence and
  evidence assessment as separate facts. Missing text or attribution stays visible.
- FR-DC-044: Render statement kind, modality, attributed speaker/proposition,
  event lifecycle and temporal precision in query/entity/network/timeline views.
  Support validity-time and recorded-time exploration; a denial/proposal never
  renders as an unqualified completed fact.
- AC-DC-8: In the BE-43/DC-15 end-to-end scenario, navigate from a qualified claim
  to its immutable evidence and correction. Preserve unknowns and dependent reports,
  update parity/ontology guards, and show API failure without losing the session.
- AC-DC-9: In BE-44/DC-16, compare proposal, denial, agreement and official registry
  confirmation across sources and both time axes without implying causality.

## 6. Open acceptance and deferred scope

DESKTOP_ROADMAP has a disposition for every AC and NFR, current defects and next
packages. OI-10 builder semantics, OI-11/18 map network policy/guard, missing original
review evidence and reference-platform/performance/manual qualification remain open.
Authentication and API backup are implemented current requirements, not deferred.
Distribution packaging and ledger write UI have no implementation commitment.
