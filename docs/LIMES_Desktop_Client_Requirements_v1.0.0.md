<!-- LIMES — Desktop Client Requirements | v1.1.0 | 2026-09-08 | Status: Maintained -->

# LIMES — Desktop Client Requirements

| Field | Value |
|---|---|
| Document | LIMES — Desktop Client Requirements (Document 3 of 3) |
| Version | 1.1.0 |
| Date | 2026-09-08; reconciled 2026-10-27, 2026-11-09 (DC-17 web-client/launcher swap, D-99) |
| Status | Maintained requirements; per-package evidence in DESKTOP_ROADMAP.md |
| Depends on | LIMES — Design Document v2.0.0 (§4, §6); LIMES — Technical Specification v2.1.0 (§6 API, §13.2 topology) |
| Supersedes | the v1.0.0 content of this same filename (stable link identity preserved) |

This document defines the requirements for the LIMES desktop client: a browser
SPA served by a local Python launcher that fully replaces the Dash UI and adds
read-only operational monitoring plus backup orchestration. It is a pure API
consumer for all data paths — it holds no database access, no ontology
literals, and no extraction logic.

## 1. Purpose and scope

The client gives the operator the complete LIMES workflow in one browser
window served by the local launcher: find entities, interrogate the graph
through three query surfaces (natural language, query builder, Cypher
console), inspect results as network, map, and timeline with full provenance
and coverage reporting, and monitor and operate the running stack (ingest
status, cost ledger, backups).

In scope: query/entity/network/map/timeline investigation, qualified
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
| Toolkit | React 19 SPA (Vite 8, TypeScript, Tailwind v4) on the ReUI/shadcn registry, served by a Python FastAPI launcher | The required ReUI visual system needs a web component runtime; Qt cannot host it (D-99). The SPA replaces QWebEngine hosting entirely |
| Graph/map/timeline rendering | Cytoscape.js, Leaflet (coordinate-only), Plotly bundled inside the SPA | Exact visual parity carries over from the Dash components; D-86's no-tile policy and bundled-resource principle are preserved in the browser |
| Application structure | `desktop/web/` (SPA) plus `desktop/src/limes_desktop/` (launcher: static serve, `/api` bearer proxy, XDG profile store, loopback bind, flock single-instance guard) | The browser never holds credentials — the proxy injects the session token; profiles stay name+URL only |
| API contract | TypeScript types generated from the API's OpenAPI schema (`desktop/web/src/api/openapi.json`, `schema.ts`); pytest contract tests recompute the schema and pin the client's endpoint surface | Contract data comes from the live application, so drift fails CI without needing node |
| Distribution | uv-managed workspace; source checkout plus `pnpm build`; `.deb`/packaged bundle deferred | Lowest-friction path first |

Rejected alternatives (D-99): hosting ReUI inside PySide6/QWebEngine (no
component-level compatibility); all-native Qt rendering of network/map/timeline
(rebuilds three nontrivial viz surfaces, drifts from Dash parity); Electron or
Tauri shells (a second language stack the repo does not carry; the Python
launcher already owns loopback serving, the proxy and the profile store).

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
  an XDG-conformant config location (`~/.config/limes-desktop/`). Credentials stay in session memory and are sent as bearer tokens. All surfaces require authentication; only operator credentials can submit/read operational jobs. Profiles never store tokens. The profile record is name + base URL only (the legacy compose_root field is retired with DC-17).

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

- FR-DC-040: Network view (Cytoscape.js in the SPA): nodes/edges from
  any query or entity-neighborhood result, incremental expansion from a
  selected node, layout controls, and selection sync with the entity view.
- FR-DC-041: Map view (Leaflet in the SPA, coordinate-only): entities with point geometry plotted; a
  selected entity's geographic relations drawn as lines; temporal filtering
  applies.
- FR-DC-042: Timeline view (Plotly in the SPA): assertions and relations over validity
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

- NFR-DC-070: The launcher binds loopback-only and enforces single-instance
  behavior as a process-level rule (advisory flock under `$XDG_RUNTIME_DIR`); any
  conforming desktop browser hosts the served SPA.
- NFR-DC-071: From the launcher's first serve of the built bundle to
  interactive search in ≤ 3 s on the reference machine; heavy visualization
  libraries load lazily on first visualization use.
- NFR-DC-072: No telemetry; no network calls beyond the launcher origin, the
  configured API and the operator job API — local-first defaults. The SPA ships
  its own fonts and visualization libraries; no tile/basemap provider is
  registered (D-86 preserves the conforming coordinate-only map policy).
- NFR-DC-073: Offline test suites for all client logic — vitest for the SPA's
  pure modules, pytest for the launcher and contract surfaces; API interactions
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
- AC-DC-4: Source scans of `desktop/src/limes_desktop/` and `desktop/web/src/`
  find no ontology type or relation literals (guard tests; the same standard
  `test_ui.py` set for the Dash UI).
- AC-DC-5: Triggering backup from the client produces a timestamped
  `limes-<timestamp>-<suffix>.dump` in the archive volume and a successful post-backup
  `/health` check, with the confirmation dialog shown before execution
  (FR-DC-061).
- AC-DC-6: With the API stopped, every view shows the unreachable state
  within its refresh interval and no unhandled exception escapes to the user.
- AC-DC-7: Contract tests recompute the API's OpenAPI schema and require it to
  match the committed generated files (`desktop/web/src/api/openapi.json`,
  `schema.ts`), and pin the TS client's endpoint surface to the API surface
  (required surfaces must exist; new API surfaces without a client mirror or
  an allowed-residual reason fail CI).

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

DESKTOP_ROADMAP and DESKTOP_QUALIFICATION retain a disposition for every AC/NFR
and grouped functional requirements. DC-14 repairs OI-10 builder semantics and
OI-11/18 map networking/guard without weakening API-only operation; DC-17 (D-99)
retires the Qt/QWebEngine shell for the browser SPA plus launcher while
preserving every semantic requirement of this document. DESKTOP_QUALIFICATION's
evidence binds the retired Qt stack; carry-over obligations (building-browser
and served-SPA qualification, covered empty/diagnosis display, backup
consequence UX) are named with the DC-17 roadmap row. Original-review,
reference-browser/launcher-platform and manual deployment evidence remain named
external obligations.
Authentication and API backup are implemented current requirements, not deferred.
Distribution packaging and ledger write UI have no implementation commitment.
