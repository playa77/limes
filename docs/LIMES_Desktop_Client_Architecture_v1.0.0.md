<!-- LIMES — Desktop Client Architecture | v1.0.0 | 2026-09-08 | Status: Draft -->

# LIMES — Desktop Client Architecture

| Field | Value |
|---|---|
| Document | LIMES — Desktop Client Architecture |
| Version | 1.0.0 |
| Date | 2026-09-08 |
| Status | Draft |
| Depends on | LIMES — Desktop Client Requirements v1.0.0 (all); LIMES — Technical Specification v2.1.0 (§9, §13.2, §15) |
| Supersedes | none (initial) |

## 1. Overview

The desktop client is a PySide6 application in a new `desktop/` workspace
member. It is a strict API consumer: every graph fact it displays comes from
the FastAPI service over HTTP; the single exception is backup orchestration,
which shells out to `limes backup` inside the worker container (FR-DC-060).
The client holds no Neo4j driver, no ontology file, and no extraction code.

```
┌────────────────────────── limes_desktop (Qt) ──────────────────────────┐
│  MainWindow                                                            │
│   ├── SearchBar ─────────────┐                                         │
│   ├── EntityView             │                                         │
│   ├── QueryViews             ├── SessionState ◄── ApiClient (typed,   │
│   │    NLQ / Builder / Cypher│      (selection,          httpx)       │
│   ├── VizViews               │       history,     ► ApiModels (mirror   │
│   │    Network/Map/Timeline   │       connection)     of api/models.py)  │
│   ├── OpsViews               │                                         │
│   │    Ingest / Ledger / Refs│                                         │
│   └── BackupDialog ──────────┴── BackupRunner (subprocess)             │
│        (each VizView wraps a QWebEngineView page)                      │
└────────────────────────────────────────────────────────────────────────┘
            │ HTTP (read endpoints + 3 saved-query/cost writes)      │ subprocess
            ▼                                                        ▼
     FastAPI (§9)                                    docker compose exec worker
     Neo4j stack                                     limes backup
```

## 2. Layout and components

### 2.1 Repository layout

```
desktop/
  pyproject.toml            # limes-desktop distribution; depends on httpx, PySide6
  src/limes_desktop/
    __init__.py
    __main__.py             # entry point: --version, single-instance guard, MainWindow
    app.py                  # single-instance guard (QLocalServer, NFR-DC-070)
    config.py               # connection profiles in ~/.config/limes-desktop/
    state.py                # SessionState: Qt signals for selection/history
    backup_runner.py        # subprocess orchestration (FR-DC-060..063)
    api/
      client.py             # ApiClient: httpx-based, one method per endpoint
      models.py             # mirrors src/limes/api/models.py (AC-DC-7)
      errors.py             # ApiUnreachable, ApiError with verbatim detail
    views/
      main_window.py        # shell: connection banner, docks, stacked views
      search.py             # SearchBar + results
      entity.py             # entity detail + provenance panel
      query_nl.py           # NLQ surface, editable Cypher pane
      query_builder.py      # builder from /builder/schema
      query_cypher.py       # console with history
      query_history.py      # saved-query panel (FR-DC-033)
      coverage_panel.py     # shared coverage/diagnosis panel (FR-DC-034)
      backup.py             # BackupDialog
      viz/                  # QWebEngineView wrappers
        page.py             # base page: lazy QWebEnginePage + QWebChannel (NFR-DC-071)
        network.py  map.py  timeline.py
        bridge.py           # Qt↔JS bridge
      ops/
        ingest.py  ledger.py  references.py
    resources/
      web/                  # bundled Cytoscape/Leaflet/Plotly pages (offline assets)
  tests/
    unit/                   # offline; ApiClient via respx; logic under pytest-qt
    contract/               # AC-DC-7 model parity + AC-DC-4 ontology-literal guard
    integration/            # against the API app mounted in-process (opt-in)
```

`desktop/` is added as a uv workspace member; the root `Makefile` gains
`desktop-install`, `desktop-run`, `desktop-lint` and `desktop-test` targets:
`uv sync --project desktop`; a `--version` sanity launch (or `MODE=ui` for the
real GUI); offline `ruff check desktop/src desktop/tests`; and
`pytest desktop/tests/unit desktop/tests/contract`. `mypy` is scoped to both
packages (`pyproject.toml`: `files = ["src/limes", "desktop/src/limes_desktop"]`).

### 2.2 Client layers and rules

- **ApiClient layer** (`api/client.py`): one synchronous method per endpoint of
  the API surface, on a single `httpx.Client` per connection profile. All HTTP
  goes through it — no view constructs a request. Errors are typed:
  `ApiUnreachable` for connection-level failures and `ApiError(status, detail)`
  for non-2xx responses (with the API's error body preserved verbatim), both in
  `api/errors.py`.
- **Model layer** (`api/models.py`): dataclasses mirroring the API response
  models — `EntityRef`, `EdgeRef`, `GraphResult`, `CoverageReport`,
  `Diagnosis`, `NlqOutcome`, `BuilderHop`, `BuilderSpec`, `HealthInfo`,
  `SearchHit`, `EntityDetail`, `NeighborRow`, `GraphNeighbors`, `SavedQuery`,
  `SourceInfo`, `CostEntry`, `CostLedger`, `IngestRun` — plus the composite
  `QueryOutcome` that fuses results with their coverage/diagnosis. Timestamps
  stay the strings the JSON carries, so the client needs no Pydantic.
  `contract/` tests import the live `limes.api.models` and the router view
  models and assert field parity, so an API model change without a client
  update fails CI (AC-DC-7). Import direction: contract tests may import
  `limes`; the client runtime must not (it can be installed against a remote
  API without the server package).
- **SessionState**: a plain Qt object carrying current selection (entity id),
  navigation history, temporal filters (validity vs belief time), and the
  active connection profile. Views never mutate each other directly —
  everything flows through signals on SessionState (this is the desktop
  analogue of the Dash UI's callback graph).
- **Views**: Qt widgets for chrome (lists, forms, tables, provenance panel).
  The three viz views each embed a QWebEngineView loading a bundled offline
  page from `resources/web/`; a `bridge.py` QWebChannel adapter is the only
  Qt↔JS seam (push results in, selection changes out). No view fetches data.
- **BackupRunner**: not an API consumer. Runs
  `docker compose exec worker limes backup` with `cwd=<compose root from the
  profile>`, streams stdout/stderr into the dialog, and verifies recovery with
  `GET /health` afterward (FR-DC-062). It deliberately duplicates nothing from
  `src/limes/cli/backup.py` — the worker-side command remains the single
  implementation of the backup procedure.

### 2.3 Ontology handling

The client fetches `GET /ontology` and `GET /builder/schema` at connect time
and caches per profile. Entity and relation type names appear only as data
from these responses; no literals are hardcoded (AC-DC-4, guard test scans
`desktop/src/limes_desktop/` the way `tests/integration/test_ui.py` scans the
Dash UI). The query builder's structure — hops, domain/range constraint — is
driven entirely by the builder schema response.

## 3. Data flow

Query (any surface): user input → view → ApiClient method → response model →
SessionState publishes result + coverage report → active viz views and the
entity panel update → selection changes flow back through SessionState.

Every response's `CoverageReport` is stored on the result object and rendered
by a shared coverage widget (FR-DC-034); the hop-level diagnosis is the empty
state.

Bitemporal display: results carry both validity and belief timestamps; the
timeline view's belief-time discriminator sets a SessionState filter that all
views honor (FR-DC-043, FR-DC-042).

Backup: dialog (consequence confirmation) → BackupRunner subprocess → output
stream → `/health` verification → result banner with dump filename parsed from
command output when present.

## 4. Error handling

| Condition | Behavior |
|---|---|
| API unreachable (any view) | Banner + per-view degraded state within one refresh cycle; no traceback dialog (AC-DC-6). Auto-refreshing views pause. |
| API 4xx/5xx | API error body shown verbatim (esp. Cypher write-clause rejection and validation errors — the wording is diagnostic signal). |
| Schema mismatch | Typed as a client bug; dialog offers "copy details" and points at the contract test. |
| Backup prerequisites missing (no compose root / no docker CLI) | Backup action disabled with the reason inline (FR-DC-063). |
| Backup command failure | Output verbatim, exit code shown; client makes no retry — the underlying command owns the procedure. |
| Subprocess/QWebEngine crash | View resets to a recoverable state; session state preserved. |

## 5. Testing strategy

- Unit (offline, `pytest-qt`, `desktop/tests/unit/`): SessionState signal flow,
  config/profile handling, search debounce, coverage panel, entity/query/ops
  views, viz payload shaping and Qt↔JS bridge, BackupRunner argument
  construction and output parsing (subprocess mocked, health stubbed).
- Contract (`desktop/tests/contract/`): `test_model_parity.py` imports the live
  `limes.api.models` and the router view models and asserts field-level parity
  with `limes_desktop.api.models` (AC-DC-7); `test_no_ontology_literals.py` is
  the ontology-literal guard over `desktop/src/limes_desktop/` (AC-DC-4).
- Integration (needs the shared test Neo4j container, like the existing
  suites; `desktop/tests/integration/`): ApiClient against the real API app
  mounted in-process (`httpx.ASGITransport`); the full search → entity →
  neighbors → NLQ → builder → Cypher → save/delete flow, plus the empty-result
  diagnosis case.
- AC-DC-1's live Compose walk-through and AC-DC-5's dump/`/health` acceptance
  are manual hand-off steps recorded in the implementation plan; there is no
  automated acceptance suite under `desktop/tests/`.
- No test makes real OpenRouter calls (repo invariant).

## 6. Security and privacy

No authentication in v1 — the API is unauthenticated by design for a
single-operator loopback deployment (Requirements §1). The client therefore
adds no credential storage; connection profiles contain only names and URLs.
Remote-connection use is over the operator's own tunnel; the client performs
no TLS handling beyond what httpx defaults provide. No telemetry; the only
network traffic is the configured API (NFR-DC-072).

## 7. Non-goals and deferred decisions

- No ingest/backfill orchestration UI: budget-governed paid operations stay
  CLI-only with explicit `BUDGET=` envelopes (AGENTS.md money rules).
- No cost-ledger writes from the client in v1 (FR-DC-051).
- No API changes required by this architecture: §9's existing surface plus the
  three enumerated writes are sufficient. Any future API addition is a
  Technical Specification amendment with its own seam-register entry (§15),
  not a client-side workaround.
- Deferred: `.deb` packaging, Wayland-specific polish beyond baseline,
  credentials/auth when the API gains them.

## 8. Changelog

### v1.0.0 — 2026-09-08
- Initial architecture: PySide6 client in `desktop/` workspace member; strict
  API-consumer rule with a Qt↔JS bridge confined to the three viz views;
  backup via subprocess to `limes backup` (no duplicated backup logic);
  ontology-literal-free invariant enforced by guard test; contract tests
  pinning client models to `src/limes/api/models.py`.
