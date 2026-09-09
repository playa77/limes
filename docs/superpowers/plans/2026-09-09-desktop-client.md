# LIMES Desktop Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the LIMES desktop client — a PySide6 application in a new `desktop/` uv workspace member that fully replaces the Dash UI, adds read-only ops monitoring, and triggers backups by shelling out to `limes backup` inside the worker container.

**Architecture:** Strict API consumer: a typed `ApiClient` (httpx, one method per Technical Specification §9 endpoint) feeds a `SessionState` Qt-signals hub; views never fetch and never mutate each other. The three viz views (network/map/timeline) are QWebEngineView pages hosting the existing Cytoscape/Leaflet/Plotly stack, bridged by one QWebChannel adapter. The client runtime never imports `limes` — only the contract tests do.

**Tech Stack:** Python 3.12, PySide6 (Qt 6), httpx, PySide6-WebEngine (QWebEngineView), pytest + pytest-qt + respx, uv workspace, ruff, mypy strict.

**Spec:** `docs/LIMES_Desktop_Client_Requirements_v1.0.0.md` (FRs/ACs) and `docs/LIMES_Desktop_Client_Architecture_v1.0.0.md` (layers, layout, testing strategy). This plan argues from both; executors read all three.

## Global Constraints

- Python `>=3.12,<3.14` (root `pyproject.toml`).
- Ruff line-length 100, select `E,F,W,I,UP,B`; mypy strict `files = ["src/limes"]` must be extended to include `desktop/src/limes_desktop` — never weakened for existing code.
- No ontology entity/relation type literals anywhere in `desktop/src/limes_desktop/` (AC-DC-4 guard test; pattern mirrors `tests/integration/test_ui.py:280-305`, which AST-scans string constants against type names and Cypher keywords).
- The client runtime never imports `limes` (only `desktop/tests/contract/` may). The client is installable standalone against a remote API.
- No new API write surfaces: the client calls only `POST /saved-queries`, `DELETE /saved-queries/{id}`, `POST /coverage`, and reads. `POST /cost/ledger` write does NOT exist in the API — the ledger view is read-only in v1 (FR-DC-051).
- No test makes real OpenRouter calls; API interactions mocked with respx (repo invariant, NFR-DC-073).
- Offline test suites: `desktop/tests/unit` and `desktop/tests/contract` must run without Docker. Integration/acceptance suites follow the repo's separate-invocation rule (AGENTS.md D-63: whole-tree collection trips the acceptance conftest under pytest 9.x).
- File headers: `# path | vX.Y.Z | why`. Nothing labeled "final". Changelog entries per work package in root `CHANGELOG.md`.
- Branches `wp-NN-slug`; merge to main only on explicit operator instruction.
- Ubuntu 24.04+ target; QWebEngineView lazy-loaded on first viz use (NFR-DC-071).

## File Structure (map)

```
desktop/
  pyproject.toml
  src/limes_desktop/
    __init__.py  __main__.py  app.py  config.py  state.py  backup_runner.py
    api/{__init__.py, client.py, models.py, errors.py}
    views/{__init__.py, main_window.py, search.py, entity.py, query_nl.py,
           query_builder.py, query_cypher.py, coverage_panel.py, backup.py,
           viz/{__init__.py, network.py, map.py, timeline.py, bridge.py},
           ops/{__init__.py, ingest.py, ledger.py, references.py}}
    resources/web/{network.html, map.html, timeline.html}
  tests/
    unit/ contract/ integration/
Makefile  (modify: desktop-test, desktop-lint, desktop-run targets)
pyproject.toml  (modify: mypy files += desktop/src/limes_desktop)
CHANGELOG.md    (modify: one entry per work package)
```

Dependency direction: `views/* → state.py → api/client.py → api/models.py`; `backup_runner.py` standalone; `contract/` tests import both packages.

---

### Task 1: Workspace scaffolding + config/profile store (FR-DC-001, FR-DC-003)

**Files:**
- Create: `desktop/pyproject.toml`
- Create: `desktop/src/limes_desktop/__init__.py`, `desktop/src/limes_desktop/config.py`, `desktop/src/limes_desktop/api/__init__.py`, `desktop/src/limes_desktop/api/errors.py`
- Modify: root `pyproject.toml` (mypy `files`), `Makefile` (desktop-lint/desktop-test targets)
- Test: `desktop/tests/unit/test_config.py`

**Interfaces:**
- Produces:
  - `class ConnectionProfile(BaseModel)`: fields `name: str`, `base_url: str` (default `"http://127.0.0.1:8000"`), `compose_root: str | None` (None = backup disabled, FR-DC-063).
  - `class ProfileStore`: `__init__(config_dir: Path | None = None)` (default `~/.config/limes-desktop/`); methods `profiles() -> list[ConnectionProfile]`, `save(profile: ConnectionProfile) -> None`, `delete(name: str) -> None`, `active() -> ConnectionProfile | None`, `set_active(name: str) -> None`. Persists as `profiles.json` + `active` file in the config dir.
  - `class ApiUnreachable(Exception)`, `class ApiError(Exception)` with attributes `status: int`, `detail: str` (verbatim body, FR-DC-062/§4).

- [ ] **Step 1: Write `desktop/pyproject.toml`** — hatchling backend (same rationale as root: future packaged resources), `name = "limes-desktop"`, `dependencies = ["pyside6>=6.7", "pyside6-webengine>=6.7", "httpx>=0.27", "pydantic>=2.8"]`, dev group `["pytest>=8.3", "pytest-qt>=4.4", "respx>=0.21", "ruff>=0.6", "mypy>=1.11"]`, `[project.scripts] limes-desktop = "limes_desktop.__main__:main"`, `[tool.hatch.build.targets.wheel] packages = ["src/limes_desktop"]`, pytest `testpaths = ["tests"]`, `pythonpath = ["src", "../src"]`.

- [ ] **Step 2: Register the workspace.** Root `pyproject.toml` gains `[tool.uv.workspace] members = ["desktop"]` and `[tool.uv.sources] limes-desktop = { workspace = true }`. Extend mypy: `files = ["src/limes", "desktop/src/limes_desktop"]`. Ruff already runs per-invocation; Makefile targets:
  ```make
  desktop-lint:
  	./venv/bin/ruff check desktop/src desktop/tests
  desktop-test:
  	./venv/bin/python -m pytest desktop/tests/unit desktop/tests/contract -q
  ```
  Run `uv sync` so `limes-desktop` and PySide6 install into `./venv`.

- [ ] **Step 3: Write the failing test** `desktop/tests/unit/test_config.py`:
  ```python
  import json
  from pathlib import Path
  from limes_desktop.config import ConnectionProfile, ProfileStore


  def test_store_roundtrip(tmp_path: Path) -> None:
      store = ProfileStore(config_dir=tmp_path)
      p = ConnectionProfile(name="local", base_url="http://127.0.0.1:8000",
                            compose_root="/home/daniel/projects/limes")
      store.save(p)
      assert store.profiles() == [p]


  def test_active_profile_roundtrip(tmp_path: Path) -> None:
      store = ProfileStore(config_dir=tmp_path)
      store.save(ConnectionProfile(name="local"))
      store.set_active("local")
      assert store.active() is not None and store.active().name == "local"


  def test_defaults_match_fr_dc_001(tmp_path: Path) -> None:
      p = ConnectionProfile(name="x")
      assert p.base_url == "http://127.0.0.1:8000"
      assert p.compose_root is None


  def test_corrupt_file_yields_empty(tmp_path: Path) -> None:
      (tmp_path / "profiles.json").write_text("{not json")
      assert ProfileStore(config_dir=tmp_path).profiles() == []
  ```

- [ ] **Step 4: Run test to verify it fails** — `./venv/bin/python -m pytest desktop/tests/unit/test_config.py -q` → FAIL, `ModuleNotFoundError: limes_desktop`.

- [ ] **Step 5: Implement** `config.py` (stdlib json + pydantic; atomic write via temp file + `os.replace`; `delete` removes profile and clears `active` if it pointed at it; `active()` returns None when unset/stale). `api/errors.py` gets the two exception classes. All files carry `# path | v0.1.0 | why` headers.

- [ ] **Step 6: Run tests to verify pass** — `./venv/bin/python -m pytest desktop/tests/unit -q` → PASS; `make desktop-lint` and `./venv/bin/mypy` clean.

- [ ] **Step 7: Commit** — `git add -A && git commit -m "wp-01: desktop workspace scaffolding + connection profile store"`

### Task 2: ApiClient + mirrored models (FR-DC-002, §9 surface; AC-DC-7 groundwork)

**Files:**
- Create: `desktop/src/limes_desktop/api/models.py`, `desktop/src/limes_desktop/api/client.py`
- Test: `desktop/tests/unit/test_api_client.py`, `desktop/tests/contract/test_model_parity.py`

**Interfaces:**
- Consumes: `ApiUnreachable`, `ApiError` from Task 1.
- Produces: `ApiClient(base_url: str, timeout_s: float = 30.0)` with one method per endpoint, return types are the mirrored models: `health() -> HealthInfo`, `ontology() -> OntologyInfo`, `ontology_versions() -> list[str]`, `builder_schema() -> dict[str, Any]`, `query_cypher(cypher, params=None) -> QueryOutcome`, `query_nl(question) -> QueryOutcome`, `query_builder(spec) -> QueryOutcome`, `entity(entity_id) -> EntityDetail`, `entity_neighbors(entity_id, filters=None) -> GraphResult`, `search(query, kind=None, limit=50) -> list[SearchHit]`, `coverage(request) -> CoverageReport`, `saved_queries() -> list[SavedQuery]`, `save_query(name, surface, payload) -> SavedQuery`, `delete_saved_query(id) -> None`, `sources() -> list[SourceInfo]`, `cost_ledger(period=None) -> CostLedger`, `ingest_status() -> list[IngestRun]`. Mirrored dataclasses in `api/models.py`: `EntityRef`, `EdgeRef`, `GraphResult`, `CoverageReport`, `Diagnosis`, `NlqOutcome`, `BuilderSpec`, `HealthInfo`, `SearchHit`, `EntityDetail`, `SavedQuery`, `SourceInfo`, `CostLedger`, `CostEntry`, `IngestRun` — each with `from_api(d: dict) -> Self`.

- [ ] **Step 1: Read the live models.** Read `src/limes/api/models.py` and every router in `src/limes/api/routers/` and record each endpoint's real response shape (`EntityRef`, `EdgeRef`, `GraphResult`, `CoverageReport`, `Diagnosis`, `NlqOutcome`, plus the dict shapes returned by health/search/saved-queries/sources/cost/ingest_status routers). The mirrors must match these exactly — copy field names, optionality, and nesting.

- [ ] **Step 2: Write the failing contract test** `desktop/tests/contract/test_model_parity.py`. The parity mechanism (this is AC-DC-7's core, so it is exact):
  ```python
  """Contract: client model mirrors of src/limes/api/models.py. AC-DC-7."""
  import dataclasses
  import inspect

  import limes.api.models as api_models
  import limes_desktop.api.models as dc_models

  MIRRORED = [
      ("EntityRef", "EntityRef"),
      ("EdgeRef", "EdgeRef"),
      ("GraphResult", "GraphResult"),
      ("CoverageReport", "CoverageReport"),
      ("Diagnosis", "Diagnosis"),
      ("NlqOutcome", "NlqOutcome"),
  ]


  def _api_fields(cls: type) -> set[str]:
      return {f for f in cls.model_fields}  # pydantic v2


  def _client_fields(cls: type) -> set[str]:
      return {f.name for f in dataclasses.fields(cls)}


  def test_field_parity() -> None:
      for api_name, dc_name in MIRRORED:
          api_cls = getattr(api_models, api_name)
          dc_cls = getattr(dc_models, dc_name)
          assert _client_fields(dc_cls) == _api_fields(api_cls), (
              f"{api_name}: client mirror out of sync with limes.api.models — "
              f"update desktop/src/limes_desktop/api/models.py"
          )
  ```
  If a mirrored model turns out to need nested mirrors (e.g. `GraphResult` containing `EntityRef`s), extend `MIRRORED` and the mirror dataclasses accordingly — every nested model the client actually consumes gets a parity entry.

- [ ] **Step 3: Run to verify fail** — `./venv/bin/python -m pytest desktop/tests/contract -q` → FAIL (models module empty / missing names). Note: contract tests import `limes`, so they need the root package importable — the workspace `pythonpath` in `desktop/pyproject.toml` (Step 1) plus repo `src/` layout via `uv sync` handles this; verify `./venv/bin/python -c "import limes, limes_desktop"` works before proceeding.

- [ ] **Step 4: Implement the model mirrors** as `@dataclass(frozen=True, slots=True)` classes with `from_api` classmethods that tolerate the API's actual JSON (e.g. datetime strings kept as str, nested entity refs built recursively).

- [ ] **Step 5: Write the failing client test** `desktop/tests/unit/test_api_client.py` with respx (pattern follows `tests/unit/test_api_handlers.py`'s fixtures, but standalone):
  ```python
  import httpx
  import respx
  from limes_desktop.api.client import ApiClient
  from limes_desktop.api.errors import ApiError, ApiUnreachable


  @respx.mock
  def test_search_parses_hits() -> None:
      respx.get("http://x.test/search").mock(
          return_value=httpx.Response(200, json=[{"entity_id": "e1", "name": "ACME",
                                                 "entity_type": "Organization",
                                                 "score": 0.9}])
      )
      hits = ApiClient("http://x.test").search("acme")
      assert hits[0].entity_id == "e1"


  @respx.mock
  def test_unreachable_raises_api_unreachable() -> None:
      respx.get("http://x.test/health").mock(side_effect=httpx.ConnectError("refused"))
      try:
          ApiClient("http://x.test").health()
      except ApiUnreachable:
          pass
      else:
          raise AssertionError("expected ApiUnreachable")


  @respx.mock
  def test_error_body_preserved_verbatim() -> None:
      respx.post("http://x.test/query/cypher").mock(
          return_value=httpx.Response(400, json={"detail": "write clause refused"})
      )
      try:
          ApiClient("http://x.test").query_cypher("MERGE (n)")
      except ApiError as exc:
          assert exc.status == 400 and "write clause refused" in exc.detail
      else:
          raise AssertionError("expected ApiError")
  ```
  (Adjust the JSON fixtures in Step 6 to the real router response shapes found in Step 1 — the mirror's `from_api` must consume what the routers actually emit.)

- [ ] **Step 6: Run to verify fail, then implement** `api/client.py`: single `httpx.Client` per instance, `_request()` wrapper mapping `httpx.ConnectError`/`TimeoutException` → `ApiUnreachable`, non-2xx → `ApiError(status, detail=json body or raw text)`, 2xx → parsed JSON. No view ever imports httpx directly (architecture §2.2).

- [ ] **Step 7: Run both suites** — `desktop/tests/unit desktop/tests/contract -q` PASS; ruff + mypy clean (strict on both files).

- [ ] **Step 8: Commit** — `git commit -m "wp-02: typed ApiClient with mirrored response models + AC-DC-7 contract tests"`

### Task 3: Ontology-literal guard test (AC-DC-4)

**Files:**
- Create: `desktop/tests/contract/test_no_ontology_literals.py`

**Interfaces:**
- Consumes: `limes.ontology` loader (the same artifact the UI guard uses).
- Produces: the guard itself — running it on an empty client now, failing later if any literal creeps in.

- [ ] **Step 1: Write the failing-capable guard** mirroring `tests/integration/test_ui.py:280-305` but over `desktop/src/limes_desktop/`:
  ```python
  """AC-DC-4: no ontology type/relation literals in the desktop client."""
  import ast
  from pathlib import Path

  from limes.ontology import load_ontology_artifact

  CLIENT_ROOT = Path(__file__).parents[2] / "src" / "limes_desktop"

  CYIPHER_KEYWORDS = (
      "MATCH", "RETURN", "MERGE", "CREATE", "WHERE", "LIMIT", "UNWIND",
      "WITH", "DETACH", "SET", "REMOVE", "LOAD",
  )


  def test_no_ontology_literals() -> None:
      ontology = load_ontology_artifact()
      names = set(ontology.entity_type_names()) | set(ontology.relation_type_names())
      for py_file in CLIENT_ROOT.rglob("*.py"):
          tree = ast.parse(py_file.read_text())
          for node in ast.walk(tree):
              if isinstance(node, ast.Constant) and isinstance(node.value, str):
                  assert node.value not in names, f"{py_file.name}: literal {node.value!r}"
                  assert not any(k in node.value for k in CYIPHER_KEYWORDS), (
                      f"{py_file.name}: literal {node.value!r} contains a Cypher keyword"
                  )
  ```
  Before writing it, read `tests/integration/test_ui.py` and reuse its exact ontology-name enumeration (the real loader's API — do not guess `entity_type_names()`; match whatever `test_ui.py` calls).

- [ ] **Step 2: Run** — `./venv/bin/python -m pytest desktop/tests/contract/test_no_ontology_literals.py -q` → PASS on the (nearly empty) client.

- [ ] **Step 3: Commit** — `git commit -m "wp-03: AC-DC-4 ontology-literal guard for desktop client"`

### Task 4: SessionState hub (FR-DC-043, FR-DC-042 groundwork)

**Files:**
- Create: `desktop/src/limes_desktop/state.py`
- Test: `desktop/tests/unit/test_state.py`

**Interfaces:**
- Consumes: mirrored models from Task 2.
- Produces: `class SessionState(QObject)` with:
  - Signals: `selection_changed(str | None)` (entity id), `result_arrived(object)` (a `QueryOutcomeBundle`), `connection_changed(ConnectionProfile | None)`, `temporal_filter_changed(object)` (a `TemporalFilter` dataclass: `validity_from/validity_to/belief_as_of: str | None`).
  - `class QueryOutcomeBundle`: `result: GraphResult | EntityDetail | list[SearchHit]`, `coverage: CoverageReport | None`, `source: str` (view name), `cypher: str | None` (for NLQ/builder display), `nlq: NlqOutcome | None`.
  - Methods: `set_selection(entity_id: str | None)`, `publish(bundle: QueryOutcomeBundle)`, `set_temporal_filter(f: TemporalFilter)`, `history() -> list[QueryOutcomeBundle]` (capped deque, max 100, for the Cypher-history FR-DC-032 and back-navigation).

- [ ] **Step 1: Write the failing test** `desktop/tests/unit/test_state.py` using `pytest-qt`'s `qtbot`:
  ```python
  from limes_desktop.state import QueryOutcomeBundle, SessionState, TemporalFilter


  def test_selection_signal(qtbot) -> None:
      state = SessionState()
      with qtbot.waitSignal(state.selection_changed) as blocker:
          state.set_selection("e-42")
      assert blocker.args == ["e-42"]


  def test_publish_stores_history_and_emits(qtbot) -> None:
      state = SessionState()
      bundle = QueryOutcomeBundle(result=[], coverage=None, source="search",
                                  cypher=None, nlq=None)
      with qtbot.waitSignal(state.result_arrived):
          state.publish(bundle)
      assert state.history()[-1] is bundle


  def test_temporal_filter_propagates(qtbot) -> None:
      state = SessionState()
      f = TemporalFilter(validity_from=None, validity_to=None, belief_as_of="2025-03-01")
      with qtbot.waitSignal(state.temporal_filter_changed) as blocker:
          state.set_temporal_filter(f)
      assert blocker.args[0].belief_as_of == "2025-03-01"


  def test_history_capped(qtbot) -> None:
      state = SessionState()
      for i in range(150):
          state.publish(QueryOutcomeBundle(result=i, coverage=None, source="t",
                                           cypher=None, nlq=None))
      assert len(state.history()) == 100
  ```

- [ ] **Step 2: Run to verify fail** — `ModuleNotFoundError` / import error on `limes_desktop.state`.

- [ ] **Step 3: Implement** `state.py` exactly per the interface above. Signals carry immutable payloads (frozen dataclasses) so views can't cross-mutate.

- [ ] **Step 4: Run pass + lint/mypy clean, commit** — `git commit -m "wp-04: SessionState signal hub"`

### Task 5: Application shell — MainWindow, search bar, connection banner (FR-DC-001/002/010/011, NFR-DC-070/071)

**Files:**
- Create: `desktop/src/limes_desktop/__main__.py`, `app.py`, `views/__init__.py`, `views/main_window.py`, `views/search.py`
- Test: `desktop/tests/unit/test_main_window.py`, `desktop/tests/unit/test_search_debounce.py`

**Interfaces:**
- Consumes: `ProfileStore`, `ApiClient`, `SessionState` (Tasks 1/2/4).
- Produces:
  - `main()` in `__main__.py`: creates `QApplication`, single-instance guard via `QRemoteObjectNode`-free approach — a `QLocalServer` named `"limes-desktop"`; if bind fails, show the existing instance and exit 0 (NFR-DC-070).
  - `MainWindow(SessionState, ProfileStore, ApiClient factory)`: left dock = search results; central = QStackedWidget of views (placeholder `QWidget`s for now, filled by Tasks 7–11); top = connection banner (`_ConnectionBanner`: green/amber/red pill + API version + graph summary from `/health`, refreshed every 10 s by a QTimer, pausable when unreachable per §4).
  - `SearchBar(QWidget)`: `QLineEdit` + `QListView` results. Debounce: `QTimer.setSingleShot(True)`, `setInterval(300)` restarted on `textEdited` (FR-DC-011 ≥300 ms). Emits `search_submitted(str)`; receives hits via `SessionState.result_arrived` with `source == "search"`. Arrow keys move the list selection, Enter triggers `SessionState.set_selection(hit.entity_id)` (FR-DC-010).

- [ ] **Step 1: Write failing tests.** Debounce test uses `qtbot.waitUntil` with a mocked ApiClient (respx at the ApiClient boundary is already covered; here the client is a stub class injected into MainWindow — define `FakeClient` in the test with canned `search()`/`health()` returns). Assert: typing "acme" fires exactly one `search_submitted` after ≥300 ms of quiet; Enter on a highlighted hit calls `state.set_selection`. Unreachable test: `FakeClient.health()` raises `ApiUnreachable` → banner shows the unreachable state and no exception escapes (AC-DC-6 groundwork).
- [ ] **Step 2: Run to verify fail**, implement `app.py`/`main_window.py`/`search.py`/`__main__.py`, run to pass.
- [ ] **Step 3: Lint/mypy clean; manual smoke**: `uv run limes-desktop` opens the window (screenshot or `--version` flag for CI-less sanity); commit — `git commit -m "wp-05: app shell, connection banner, debounced search"`

### Task 6: Shared coverage panel + entity view (FR-DC-020/021/022, FR-DC-034, AC-DC-2)

**Files:**
- Create: `desktop/src/limes_desktop/views/coverage_panel.py`, `desktop/src/limes_desktop/views/entity.py`
- Test: `desktop/tests/unit/test_coverage_panel.py`, `desktop/tests/unit/test_entity_view.py`

**Interfaces:**
- Consumes: `SessionState`, `EntityDetail`, `CoverageReport`, `Diagnosis` mirrors.
- Produces:
  - `CoveragePanel(QWidget)`: `render(coverage: CoverageReport | None)` — when a result is empty, the panel IS the empty state: hop-level `Diagnosis` rows (which hop emptied the set + graph-wide counts), never a bare "no results" (FR-DC-034, AC-DC-3). Non-empty results show the collapsible coverage summary.
  - `EntityView(QWidget)`: property table (type-appropriate rendering: timestamps rendered as labeled VALIDITY / BELIEF rows — distinct labels is the AC-DC-2 requirement), `QListView` of assertions each with confidence badge and one-click provenance expander showing source + source sentence (FR-DC-021), neighbors table from `entity_neighbors` with relation-type filter combo populated from the cached ontology response (no literals), neighbor click → `state.set_selection(neighbor_id)` (incremental re-centering, FR-DC-022).

- [ ] **Step 1: Write failing tests with stubbed SessionState/frozen mirror instances** (construct mirrors from dicts via `from_api`). Key assertions: an empty `GraphResult` bundle renders one row per diagnosis hop with its graph-wide count; an `EntityDetail` whose properties include `valid_from`/`recorded_at` renders both under distinct labels; clicking an assertion row reveals the source-sentence text.
- [ ] **Step 2: Verify fail → implement → pass;** wire `EntityView` into `MainWindow`'s stack (replacing the placeholder), commit — `git commit -m "wp-06: coverage panel + entity view with provenance"`

### Task 7: Query surfaces — NLQ, Cypher console, saved queries (FR-DC-030/032/033/034)

**Files:**
- Create: `desktop/src/limes_desktop/views/query_nl.py`, `views/query_cypher.py`, `views/query_history.py`
- Test: `desktop/tests/unit/test_query_views.py`

**Interfaces:**
- Consumes: `ApiClient.query_nl/query_cypher/saved_queries/save_query/delete_saved_query`, `SessionState.publish`, `CoveragePanel`.
- Produces:
  - `NlqView(QWidget)`: question input (DE/EN), on submit calls `query_nl`; result pane shows generated Cypher in an editable `QPlainTextEdit` with a "Run" button that re-executes it via `query_cypher` (FR-DC-030's always-editable rule), `NlqOutcome` metadata (adjudication fields from the mirror) beside it, results + `CoveragePanel`.
  - `CypherConsole(QWidget)`: `QPlainTextEdit` input, run via `query_cypher`; history `QComboBox` populated from `SessionState.history()` entries with `source in {"cypher", "nlq-run"}`, persisted per-session (FR-DC-032; cross-session persistence is optional per spec — implement via `ProfileStore`-adjacent JSON file `history.json` in the config dir, off by default, checkbox in the console toolbar). Write-clause rejections surface `ApiError.detail` verbatim in an error pane (§4).

- [ ] **Step 1: Failing tests with FakeClient**: NLQ submit → editable pane contains the returned Cypher; editing it and pressing Run issues a `query_cypher` call with the edited text; a 400 with `{"detail": "write clause refused"}` renders that string verbatim; saved-query save captures surface+text+name and the delete button calls `delete_saved_query`.
- [ ] **Step 2: fail → implement → pass → lint/mypy → commit** — `git commit -m "wp-07: NLQ + Cypher console + saved queries"`

### Task 8: Query builder (FR-DC-031)

**Files:**
- Create: `desktop/src/limes_desktop/views/query_builder.py`
- Test: `desktop/tests/unit/test_query_builder_view.py`

**Interfaces:**
- Consumes: `ApiClient.builder_schema()` response (`GET /builder/schema` — the same schema the Dash UI's `ui/components/builder.py` consumes; read that file first and mirror its hop-construction logic in client terms), `CoveragePanel`.
- Produces: `BuilderView(QWidget)`: start-type combo ← schema `entity_types`; per-hop relation + direction + target combos ← the schema's domain/range data (exactly `relations_for`/`targets_for` semantics as in `tests/integration/test_ui.py`'s admissibility test); "Add hop" / "Remove hop"; submit calls `query_builder(spec)` and publishes the bundle. Zero ontology literals — all options are schema data (guard test from Task 3 enforces).

- [ ] **Step 1: Failing test**: given a canned builder-schema dict (two entity types, one relation with both directions), selecting start type "A" populates exactly the schema-admissible (relation, direction, target) triples; submit builds the expected spec dict and calls `query_builder`. Construct the canned schema from the shape `src/limes/api/routers/ontology.py` actually returns.
- [ ] **Step 2: fail → implement → pass → commit** — `git commit -m "wp-08: ontology-driven query builder view"`

### Task 9: Viz views — QWebEngineView + bridge + network/map/timeline (FR-DC-040..043, NFR-DC-071)

**Files:**
- Create: `desktop/src/limes_desktop/views/viz/__init__.py`, `bridge.py`, `network.py`, `map.py`, `timeline.py`, `resources/web/network.html`, `map.html`, `timeline.html`
- Test: `desktop/tests/unit/test_viz_bridge.py` (bridge logic without a real WebEngine), `desktop/tests/unit/test_viz_payload.py`

**Interfaces:**
- Consumes: `SessionState.result_arrived` bundles (`GraphResult` nodes/edges with x/y geometry for map, validity/belief times for timeline).
- Produces:
  - `bridge.py`: `VizBridge(QObject)` with slots `push_result(json_str: str)` and signal `selection_changed(str)`. `VizPage(QWebEngineView)` subclass: lazy `QWebEnginePage` creation (first `show()` — NFR-DC-071), loads `qrc`-style local HTML from `resources/web/` via `setHtml(..., baseUrl=QUrl("file:///..."))` with the bundled libraries copied from the Dash stack's CDN versions pinned into `resources/web/vendor/` (cytoscape.min.js, leaflet.js+css, plotly.min.js — downloaded once at build time and committed; no CDN fetch at runtime, NFR-DC-072), registers `QWebChannel` with the bridge as `"bridge"`.
  - `network.py`: `NetworkView(VizPage)` over `network.html` — Cytoscape graph from `GraphResult` (nodes styled by entity type from the ontology response held in state, not literals), click → `selection_changed` → `state.set_selection`; "expand" button re-calls `entity_neighbors` on the selected node and pushes a delta (incremental expansion, FR-DC-040).
  - `map.py`: Leaflet markers for entities carrying point geometry, polylines for the selected entity's geographic relations, honoring `SessionState.temporal_filter_changed` (FR-DC-041).
  - `timeline.py`: Plotly scatter/step traces of assertions over validity time, belief-time discriminator input publishes `state.set_temporal_filter` (FR-DC-042); all three views honor the filter (FR-DC-043).

- [ ] **Step 1: Write the bridge test** without WebEngine (CI-safe): `VizBridge.push_result` serializes a `GraphResult` bundle to the exact JSON the HTML pages' JS expects (assert keys: `nodes`, `edges`, `coverage`); `selection_changed` fires when the slot `on_node_clicked('e-1')` is invoked directly. The HTML/JS itself is validated in Task 12's integration step, not here.
- [ ] **Step 2: fail → implement bridge + pages.** The three HTML files share one pattern: load vendor libs, open a QWebChannel to `bridge`, define `window.pushResult(payload)` renderers. Keep each page <150 lines.
- [ ] **Step 3: Payload tests**: map payload only includes entities with non-null geometry; timeline payload splits validity vs belief series.
- [ ] **Step 4: pass + lint/mypy + commit** — `git commit -m "wp-09: viz views over QWebEngineView with Qt↔JS bridge"`

### Task 10: Ops views — ingest status, cost ledger, references (FR-DC-050/051/052)

**Files:**
- Create: `desktop/src/limes_desktop/views/ops/__init__.py`, `ingest.py`, `ledger.py`, `references.py`
- Test: `desktop/tests/unit/test_ops_views.py`

**Interfaces:**
- Consumes: `ApiClient.ingest_status/cost_ledger/sources/ontology/ontology_versions`.
- Produces: `IngestView` (table of runs, auto-refresh QTimer 10 s that runs only while the tab is visible — `showEvent`/`hideEvent` start/stop it, FR-DC-050), `LedgerView` (entries table + per-model and per-run spend groupings computed client-side from entries, running total vs the budget shown in `/health` graph summary when available; strictly read-only, FR-DC-051), `ReferencesView` (source registry table + ontology type catalog with domain/range columns + version list, FR-DC-052).

- [ ] **Step 1: Failing tests with FakeClient**: ingest rows render from canned `IngestRun` list; the refresh timer does not fire while hidden (use `qtbot.waitUntil` with a counter and assert no increment after hiding); ledger groups by model correctly; references view renders the canned ontology response without any literal in the view module (Task 3 guard re-verifies).
- [ ] **Step 2: fail → implement → pass → commit** — `git commit -m "wp-10: read-only ops views"`

### Task 11: BackupRunner + BackupDialog (FR-DC-060..063, AC-DC-5)

**Files:**
- Create: `desktop/src/limes_desktop/backup_runner.py`, `desktop/src/limes_desktop/views/backup.py`
- Test: `desktop/tests/unit/test_backup_runner.py`

**Interfaces:**
- Consumes: `ConnectionProfile.compose_root`, `ApiClient.health()` (post-verification).
- Produces:
  - `class BackupRunner(QObject)`: `run(profile: ConnectionProfile)` — builds `["docker", "compose", "exec", "worker", "limes", "backup"]` with `cwd=profile.compose_root`; prerequisites checked first via `shutil.which("docker")` and `Path(compose_root).is_dir()`, exposed as `prerequisites(profile) -> list[str]` returning human-readable reasons (empty = OK, FR-DC-063). Signals: `output_line(str)`, `finished(exit_code: int, health_ok: bool | None)`. Streams stdout+stderr line-wise from `QProcess` (merge channels). After exit 0, calls `ApiClient.health()`; `health_ok=None` means never checked (non-zero exit, no retry — §4). Parses the dump filename `limes-<ts>.dump` from output lines when present and exposes it on `finished` via a `dump_path: str | None` attribute. No backup logic duplicated from `src/limes/cli/backup.py` (architecture §2.2).
  - `BackupDialog(QDialog)`: consequence confirmation naming "Neo4j unavailable for the duration; graceful stop up to ~120 s" verbatim before enabling Run (FR-DC-061); Run disabled with inline reason when `prerequisites()` is non-empty.

- [ ] **Step 1: Failing tests** — `QProcess` is mocked by subclassing BackupRunner to accept a fake process emitter; assert: command list exactly `["docker", "compose", "exec", "worker", "limes", "backup"]` with cwd set; missing docker in PATH → prerequisite reason; output lines flow to `output_line`; `limes-20260909T120000.dump` parsed from a canned line; exit 1 → `health_ok is None` and no health call made.
- [ ] **Step 2: fail → implement → pass → commit** — `git commit -m "wp-11: backup runner + confirmation dialog"`

### Task 12: Wire-up, integration suite, docs, changelog (AC-DC-1/3/6/7 verification)

**Files:**
- Create: `desktop/tests/integration/test_full_flow.py` (opt-in, needs the API app; mirrors `tests/integration/` pattern — in-process FastAPI via `httpx.ASGITransport` mounted in the ApiClient's transport so no Docker is needed for the API side; the graph data comes from the session-scoped test container like existing integration tests)
- Modify: `CHANGELOG.md`, `README.md` (one desktop-client paragraph + `make desktop-run`), `Makefile` (`desktop-run` target: `uv run --project desktop limes-desktop`)

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Write the integration flow test** (AC-DC-1's automatable core): seed the test container's graph (reuse existing integration fixtures), then: `search` → pick hit → `entity` → `entity_neighbors` → `query_nl` with a stubbed OpenRouter (respx-mocked, repo invariant) → `query_builder` → `query_cypher` → `save_query`/`delete_saved_query`; assert every outcome's coverage/report presence (AC-DC-3: empty-result case included with a query that matches nothing) and that `NlqOutcome` carries the editable Cypher (AC-DC-2 covered at the unit level in Task 6).
- [ ] **Step 2: Run the repo gates in full**:
  ```bash
  ./venv/bin/ruff check src tests desktop/src desktop/tests
  ./venv/bin/mypy
  ./venv/bin/python -m pytest tests/unit -q
  ./venv/bin/python -m pytest desktop/tests/unit desktop/tests/contract -q
  ./venv/bin/python -m pytest tests/integration desktop/tests/integration -q   # Docker; separate invocation
  ```
  Existing suites must be untouched-green (no regression from the mypy `files` addition).
- [ ] **Step 3: `python3 tools/check_docs.py docs/`** — the desktop docs already pass; re-run after any doc touch.
- [ ] **Step 4: Update `CHANGELOG.md`** with one entry covering the desktop-client work package, referencing the two design docs. Commit — `git commit -m "wp-12: integration flow test + docs/changelog + Makefile targets"`

---

## Acceptance coverage map

| AC | Verified by |
|---|---|
| AC-DC-1 | Task 12 integration flow (API-level full path); manual Compose walk-through at hand-off |
| AC-DC-2 | Task 6 unit test (distinct VALIDITY/BELIEF labels) |
| AC-DC-3 | Task 6 (coverage panel IS the empty state) + Task 12 empty-result case |
| AC-DC-4 | Task 3 guard test, runs in every CI invocation |
| AC-DC-5 | Task 11 unit tests for command/confirmation logic; the dump-file + `/health` verification needs the live stack — manual acceptance step at hand-off with a disposable volume (architecture §5) |
| AC-DC-6 | Task 5 unreachable-banner unit test + per-view degraded states in Tasks 8–10 |
| AC-DC-7 | Task 2 contract test, runs in every CI invocation |

## Self-review notes

- Spec coverage: FR-DC-001..003 (T1, T5), 010/011 (T5), 020..022 (T6), 030..034 (T6/T7/T8), 040..043 (T9), 050..052 (T10), 060..063 (T11), NFR-070..074 (T1/T5/T9/T12) — all mapped; AC map above.
- Type consistency: `QueryOutcomeBundle`/`TemporalFilter` defined in Task 4 and consumed in Tasks 5–10 with the same field names; `ApiClient` method names fixed in Task 2 and used verbatim later.
- Known risks flagged for executors: (a) the mirrored-model list in Task 2 must be extended to every nested model the client actually renders — run the contract test as the source of truth; (b) `VizBridge` unit tests deliberately avoid instantiating `QWebEngineView` (import it only inside `VizPage`, never at module import of `bridge.py`) so the unit suite stays headless-CI-safe; (c) pytest-qt needs a Qt platform — if the CI host is headless, set `QT_QPA_PLATFORM=offscreen` in `desktop/tests/conftest.py`.
