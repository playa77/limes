# CHANGELOG — LIMES

All notable changes to this project are recorded here as work happens. Format:
one entry per work package, latest first. Independent version lines (ontology,
gold set, prompts) are recorded in their own changelogs.

---

## 2026-08-23 — Refactor — architecture consolidation (operator-instructed)

- **S5 — Model-output parsing and prompt resolution stated once.**
  `strip_model_fence()` and `prompt_path()` added to
  `extraction/base.py`. The byte-identical JSON-fence pair
  (`extraction/schema`, `resolution/adjudicate`) and the Cypher variant in
  `cli/evaluate` (tag parameter) now share the strict whole-text policy;
  `nlq/generate`'s lenient line-based stripper is deliberately different and
  stays local, documented as such. Three `PROMPTS_DIR` definitions collapse
  into one resolver; missing-prompt error messages unchanged (paths are
  identical values, pinned by tests). One test re-pointed to the shared
  helper with identical assertions. Verified: unit 696 + integration 163 vs
  live Neo4j; ruff/mypy clean.
- **S4 — The §11 retry policy stated once (metric M2c).**
  `request_with_retry()` in `sources/base.py` is the single transport
  (tenacity: 2 s exponential, factor 2, jitter, 4 attempts, on connection
  errors/timeouts/429/5xx); `sources/base._fetch`,
  `openrouter_client.post_json_with_retry`, the catalogue GET, and the
  Ollama chat call now delegate. Observable behavior preserved exactly:
  per-layer error types and message prefixes (pinned by tests), per-module
  backoff-log attribution, the source layer's UA header, and Ollama's
  headerless non-following requests (`follow_redirects=False` passed
  explicitly). `graph/driver.py` keeps its deliberately distinct
  Neo4j-transient policy. Two tests re-pointed at the shared constants/
  predicate with identical assertions (test_ollama's `_is_retryable`
  import, HTTP_MAX_ATTEMPTS reference). Verified: unit 696 + integration
  163 vs live Neo4j; ruff/mypy clean.
- **S3 — Shared identity constructors for the source layer
  (metric M2b).** `topic_endpoint()`, `address_location()`,
  `coordinate_location()` added to `sources/base.py`; the byte-identical
  address-hash pair (GLEIF/TED), coordinate-digest pair (GDELT/OSM), and
  five topic-endpoint builders (TED/EUR-Lex/Gesetze/OSM/
  transparency-register) now call them. Digest inputs unchanged to the
  byte, so entity_ids — and therefore loader merges — are unchanged;
  the adapter suites pin exact ids and act as the guard. The TED buyer
  digest stays local deliberately: a single-site convention, not a shared
  family. Verified: unit 696 + integration 163 vs live Neo4j,
  ruff/mypy clean.
- **S2 — One canonical assertion constructor for the source layer
  (metric M2a).** `make_assertion()` added to `sources/base.py`; all 11
  source adapters migrated; the 12 local `_assertion`/`_actor_assertion`/
  `_provenance` copies deleted (~205 lines net). Parameter order drift
  between the old copies is why the shared signature is keyword-only for
  `valid_from`/`valid_to`/`recorded_at`. Semantic identity preserved:
  same digest inputs, same `recorded_at` defaults, offeneregister's
  dataset-publication vintage passed explicitly. A positional slip in the
  gdelt migration was caught by its adapter tests before commit.
  Verified: unit 696 passed, integration 163 passed against live Neo4j,
  ruff/mypy clean.


- **S1 — Lint/format debt zeroed (metric M1).** `ruff check` 16→0 errors,
  `ruff format --check` 6 deviating files→0, on `refactor-consolidation`.
  Formatting-only diff plus four long Cypher literals re-wrapped as adjacent
  string literals (semantically identical). Includes the lockfile refresh the
  D-65 `coverage` addition should have carried (`uv.lock` last committed at
  WP-01; pyproject's dev group and the lock disagreed until now). Stop
  condition, scope decision D-66, and task invariants logged in DECISIONS.md.

---

## 2026-08-03 — Phase 11 — WP-40 100% line coverage (operator-instructed)

- **WP-40 — Full line coverage of `src/limes` (6882/6882 statements,
  100%), driven by 321 new/extended unit tests plus integration
  additions.** Operator instruction ("add tests until we have 100% test
  coverage") overrides Doc 2 §12.4's line-coverage non-target; the
  override is logged as D-63. Measurement combines all three suites
  (unit + integration + acceptance, `coverage run --append`), statement
  coverage, `coverage>=7.15` added to the dev group (D-65, approved).
  Coverage by area: all 13 sources adapters and `sources/base.py` (new
  `test_sources_base.py`, extended adapter tests — error branches,
  retry/skip paths, csv field-size failures); `nlq/*`, `resolution/*`,
  `pipeline/*`, `extraction/*`, `graph/*`, `coverage/diagnose`,
  `composition`, `ontology/*`, `api/builder`, `api/models` (extended/new
  unit tests, including loader error paths via the driver raw-session
  seam); CLI command bodies that the subprocess integration tests cannot
  measure (`test_cli_commands.py`: `backup` lifecycle with the compose
  seam stubbed, `reextract`, `ingest-all`, `main()` entry point via
  runpy, `parse_iso_datetime` error branches; extended `test_migrate.py`
  migration-discovery error paths, `test_select_models.py` stage wiring
  and selector routing, `test_evaluate.py` artifact-loader error paths,
  NL-to-Cypher measurement, and the `--resolution`/`--nl2cypher` command
  flags); API exception handlers against the real registered handlers
  (`test_api_handlers.py`: §11 mapping incl. the catch-all and the
  ServerErrorMiddleware re-raise behavior, the startup-fatal
  provisioning path, the builder-translation validation failure; the
  `believed` neighbors path in `test_api_entity.py`); the Dash layer
  (`test_ui_callbacks.py`, `test_ui_components.py`: every pure callback
  branch via the `dash._callback_context.context_value` seam, the
  `register()` wiring and wrapper bodies through a recording fake app,
  all component render branches, `create_app()`, and the UI's remaining
  `api_client` endpoints respx-mocked).
- **Repair in `src/limes/ui/callbacks/query.py` (WP-36 defect found by
  the coverage exercise).** `builder_hop_change` decoded the hop index
  with `triggered_index("builder")`, but every hop control's pattern id
  is `{"type": "builder-rel"|"builder-dir"|…, "index": n}` — the
  exact-type match never succeeds, so every hop-control interaction
  raised `PreventUpdate` and the whole callback was dead in production.
  The index now decodes from the same decoded control type (D-62b).
- **Fix of the phase-10 documented pre-existing failure.** The WP-02
  `test_config.py` missing-key test now forces `Settings(_env_file=None)`
  via an autouse fixture, so the suite passes regardless of a `.env` at
  the CWD (D-64) — resolving the phase-10 changelog's "not fixed here"
  note.
- **Pre-existing, not touched here:** 16 E501 line-length violations in
  `test_loader.py`, `test_lookups_cross_process.py`, `test_archive.py`
  and 10 unformatted files (incl. `src/limes/graph/lookups.py`) predate
  WP-40 (38 E501s and 10 unformatted at HEAD); only files touched by this
  package were formatted, ruff-checked, and mypy-clean.

## 2026-08-03 — Phase 10 — WP-39 acceptance test suite (phase-10-v1.0.0, in work)

- **WP-39 — Acceptance test suite.** `tests/acceptance/` — 86 tests across
  27 files, one mechanical test per acceptance criterion AC-01…AC-44, plus
  the meta-test `test_ac00_meta_coverage.py` that fails when any criterion
  loses its test. `conftest.py` inherits the disposable Neo4j container
  from the integration suite (`pytest_plugins`) and provides the
  module-scoped `populated_graph` fixture, which builds graph state
  through the production ingestion path — `execute_run` over the recorded
  GISCO, GLEIF, and feed fixtures with only the network boundary stubbed
  (fixture fetches, respx-mocked paid endpoints, injected fake spaCy
  models; Doc 2 §12.2 rule 1). Coverage by area: config/ontology/schema
  (AC-01…AC-03), all 13 adapters from recorded fixtures with attribution
  (AC-04), loader bitemporal semantics (AC-05…AC-10), gate and ingest
  status (AC-11), extraction cache and evidence spans (AC-12, AC-13),
  governor ceiling and envelope metering (AC-14, AC-15), resolution bands
  and unlink (AC-16, AC-17, AC-19), the API write surface with an
  obfuscated-write corpus (AC-18), every validation code and plan-gate
  rejection produced by crafted queries against the real EXPLAIN plan
  (AC-20, AC-21), diagnosis and coverage (AC-22, AC-23), builder
  rejections (AC-24), reference questions against an empty graph (AC-25),
  NL/Cypher persistence and the UI interaction contract (AC-26…AC-30),
  evaluate's regression gate (AC-31), the §13.4 memory caps (AC-32, the
  testable proxy for the backfill memory ceiling), zero-paid-call rebuild
  (AC-33), compose port topology (AC-34), the personal-artifact disclaimer
  (AC-35), select-models stages (AC-36, AC-37), registry and composition
  root greps (AC-38, AC-40, AC-41), cross-process lookups via subprocess
  (AC-39), window resolution (AC-42), the four-band resolver conversion
  (AC-43), and `tools/check_docs.py` (AC-44).
- **Repair in `src/limes/graph/driver.py` (WP-33 defect found by AC-21).**
  `_parse_plan` read the row estimate from a top-level `estimatedRows`
  key that the 2026.x server never emits (the estimate is nested under
  `args.EstimatedRows`), so `OPERATOR_ROWS_EXCEEDED` and
  `TOTAL_ROWS_EXCEEDED` silently never fired — two of §8.10's five
  rejections were dead code. Verified against a live 2026.06 container
  (max=0/total=0 for every plan); the parser now reads `args.EstimatedRows`
  with the legacy key as fallback. The AC-21 crafted queries (eight chained
  UNWINDS for the operator ceiling; a sixteen-branch capped UNION for the
  total ceiling) now produce both rejections. Decision D-62 in
  DECISIONS.md.
- Pre-existing finding, not fixed here (outside WP-39 scope): the WP-02
  unit test `test_config.py::test_load_settings_missing_required_key_names_it`
  fails when the repository's own `.env` exists — the dotenv fills the
  key the test removes. The AC-01 acceptance test is robust to this by
  running in a subprocess with a clean working directory.

## 2026-08-03 — Phase 9 delivered — phase-9-v1.0.0 (WP-37, WP-38)

- **WP-37 — Docker images and Compose topology.** `docker/api.Dockerfile`,
  `docker/ui.Dockerfile`, `docker/worker.Dockerfile` over a shared
  dependency layer (Python 3.12 slim, `uv export --frozen` + `uv pip
  install --system` — no virtual environment inside an image, D-59; the
  api and ui exports prune the two spaCy model wheels, only the worker
  installs them, G3). `docker-compose.yml` (base: four services, one
  network, named volumes `neo4j_data`/`neo4j_logs`/`archive`, no published
  ports — AC-34; Neo4j runtime per §13.4; the `limes` user created by a
  boot wrapper over the stock entrypoint, the [CONFLICT] resolution; the
  worker mounts gold_set rw, the archive, the docker socket and the
  compose files for `limes backup`, and `.env` rw for the model pins,
  D-57; configuration delivered by the `.env` mount and the app's dotenv
  read — compose `env_file` provably dead-letters the pins) and
  `docker-compose.override.yml` (loopback `127.0.0.1:8050` for the UI only,
  source mounts, api reload, debug logging). `.dockerignore` added.
- **WP-38 — Makefile and bootstrap.** Full target set replacing the WP-01
  stub: `up`, `down`, `bootstrap-db` (no-op per C-01), `ingest`,
  `ingest-all`, `backfill`/`reextract` (BUDGET-guarded), `select-models
  ARGS=…` (the `make --` form is broken GNU make syntax, D-60),
  `evaluate`, `migrate`, `backup`, plus `stamp-embeddings` (the §13.3
  one-shot embedding backfill wired by this WP per the WP-25a contract,
  D-56). The `limes` console script registered in `pyproject.toml` per the
  assignment in `cli/main.py`. README bootstrap rewritten to the full
  §13.3 sequence with the ordering constraints. `tools/smoke_test.py` runs
  the paid-free bootstrap core on a clean host and asserts the phase's
  guarded invariants G1–G4.
- Decision ledger: the `[CONFLICT]` (no documented production mechanism
  creates the `limes` Neo4j user) resolved by the operator in favor of the
  entrypoint wrapper; D-55…D-61 recorded (healthcheck, `.dockerignore`,
  `migrate` variable, `stamp-embeddings`, worker docker CLI/socket and the
  `.env`-by-mount config delivery with the pydantic shadowing evidence,
  factory-form api CMD, `uv export` dependency layer, and the three
  compose wiring facts found in live verification: CMD dropped on
  entrypoint override, trixie's missing compose plugin, and the
  `stop_grace_period` requirement).

## 2026-08-02 — Phase 8 delivered — phase-8-v1.0.0 (WP-36 Dash UI)

- **WP-36 — Dash UI.** `ui/api_client.py` (one function per §6 endpoint,
  `LIMES_API_BASE_URL` from the environment only — never `Settings`, never
  `.env`, so the UI holds no credentials, D-09; `ApiError` with the §6
  envelope on non-2xx), `ui/layout.py` (one exploration screen with the
  three synchronized panes, the console, the generated builder container,
  search, saved-query list, budget indicator and system-status panel; all
  state in `dcc.Store`s per §8.13), `ui/components/*.py` (network via
  dash-cytoscape with the AC-27 neighborhood merge; map via dash-leaflet
  with markers for schema-derived coordinate-bearing nodes; timeline via
  plotly with a rangeslider brush; console; schema-generated builder with
  domain/range-admissible options; coverage panel; provenance panel with
  the originating sentence), `ui/callbacks/*.py` (selection sync and the
  one-cycle three-pane render; the three run paths plus boot/search/saved-
  query actions; the brush → temporal-filter → re-query chain), and
  `ui/app.py` (Dash application, `python -m limes.ui.app` entry point).
  AC-27 (node click expands one hop through `/entity/{id}/neighbors`
  without re-running the original query), AC-28 (edge selection shows full
  §5.6 provenance plus the originating sentence when the evidence document
  exists — bounded by the API surface, D-10), AC-29 (all three panes react
  to a selection change and to the timeline brush within one interaction
  cycle; the brush re-queries with `as_of` = the brush's right edge, D-11).
  The UI holds no credentials and performs no database access (grep guard),
  contains no type name, relation name, or Cypher fragment literal (AST
  guard against the loaded ontology), and its builder is generated from
  `/builder/schema` at runtime.
- 13 integration tests in `tests/integration/test_ui.py`: the AC-27/28/29
  interactions as direct callback invocations with recorded API fakes,
  schema-admissibility of every builder option against `Ontology.permits`,
  the two source guards, the run paths and boot load, and the `api_client`
  seam against a real uvicorn process (subprocess) serving the real
  application against the disposable container.

## 2026-08-02 — Phase 7 delivered — phase-7-v1.0.0 (WP-32…WP-35)

Approved by the human (DECISIONS.md, 2026-08-02) and merged to `main`,
pushed. Delivered on branch `wp-32-35-query-api`.

- **WP-32 — Query API foundation.** `api/main.py` (FastAPI app, startup
  handler, `X-LIMES-Ontology-Version` middleware, §6 error envelope, §11
  HTTP mapping), `api/deps.py` (dependency injection; `NlqContext` built
  lazily), `api/models.py` (`GraphResult`, `CoverageReport`, `Diagnosis`,
  `EntityRef`, `EdgeRef`, `NlqOutcome`, `BuilderSpec`, plus the row→result
  conversion), `api/builder.py` (`project_for_builder`), and the seven
  non-query routers: health, ontology (+versions), entity (+neighbors with
  relation and `as_of`/`believed` temporal filters via the §5.7
  fragments), search (fulltext over `entity_names`), sources, cost/ledger,
  ingest/status. Startup provisions (downgrade guard, AC-01) and verifies
  Neo4j reachability; unreachable does not abort startup — `/health`
  reports 503.
- **WP-33 — NL-to-Cypher service.** `nlq/generate.py` (prompt load by
  version, delimited question, feedback verbatim, code-fence strip),
  `nlq/validate.py` (a real Cypher tokenizer — comments, strings, and
  backticked identifiers are single tokens, so a write hidden in one is
  data, not syntax — plus clause walker, pattern walker with direction
  awareness, all seven §8.10 validation codes, LIMIT injection,
  partial-verification notes), `nlq/plan.py` (plan gate: cartesian/rows
  from EXPLAIN, variable-length bounds from the query text), `nlq/service.py`
  (`answer()` with exactly one regeneration), and the prompt
  `nl2cypher_v1.0.0.md` (no example questions, NG-08).
- **WP-34 — Coverage and diagnosis.** `coverage/report.py`
  (`report_for_relations`: graph-wide counts, contributing sources, refresh
  stamps) and `coverage/diagnose.py` (`diagnose`: clause decomposition via
  the shared tokenizer, first-empty-clause naming, plain-language note).
- **WP-35 — Query routers.** `routers/query.py` (`POST /query/cypher`,
  `/query/nl` with `:SavedQuery` persistence per FR-14, `/query/builder`
  with precise AC-24 rejections), `routers/coverage.py`, and
  `routers/saved_queries.py` — the sole writer of `:SavedQuery` and the
  only module in `src/limes/api/` with write tokens (AC-18 grep verified).
  The builder translation parameterizes every filter value and temporal
  instant and composes the §5.7 temporal fragments.
- **AC-18 enforcement.** Grep verification finds write tokens only in
  `saved_queries.py`; a write-attempt corpus (including obfuscated forms
  and comment-embedded write text that must pass) runs against the live
  API. AC-20, AC-21, AC-22, AC-23, AC-24, AC-26, AC-28 (partial), AC-30
  guarded by tests; Trace 3 (`POST /query/nl`) runs end-to-end against the
  test container with the paid-inference client stubbed at the
  composition-root seam — no live call, no ledger write (the same
  no-live-network rule as every other test).
- **Guard-test repair (D-47):** the AC-40 grep carries the §15.2/§8.15
  exemption for `api/main.py`'s driver construction.
- Verification: `ruff check src/limes/`, `mypy src/limes/`, and
  `python tools/check_docs.py` clean; full suite **525 passed** (437
  baseline + 88 new: 33 unit, 55 integration) against a disposable Neo4j
  container.

---

## 2026-08-02 — Phase 6 delivered — phase-6-v1.0.0 (WP-28…WP-31)

Approved by the human (DECISIONS.md, 2026-08-02) and merged to `main` as
`753c955`, pushed. The halted phase resumed with the loader lookup-row
batching repair (above): the live Trace 1 verification now passes, all 12
guarded invariants (G1–G12) are green, and the four triggered paths (T1–T4)
hold against the phase's diff. One roadmap verification remains
operator-gated: the live `backfill --source feeds` run needs the operator's
OpenRouter key and spends budget; its fixture-based end-to-end test is
green. Pre-existing `tests/` ruff baseline deviations remain flagged, not
fixed (D-27 precedent).

---

## 2026-08-02 — Phase 6 [CONFLICT] repair: loader lookup-row batching

The halted phase resumes per the human's decision (DECISIONS.md, 2026-08-02,
branch a): the WP-07 loader no longer writes a record's whole lookup list in
one transaction. `graph/loader.py::load` (v1.2.0) chunks `lookup_rows` at
`BATCH_SIZE`; chunk *i* rides with assertion batch *i* and overflow chunks
each run in their own transaction, so every transaction carries at most 500
assertions and at most 500 lookup rows (D-46).

- New guard `tests/integration/test_loader.py::test_lookup_rows_are_batched_across_transactions`
  — spies per-transaction postal statements through the documented
  `GraphDriver._driver` seam: > `BATCH_SIZE` rows ⇒ multiple transactions,
  none exceeding `BATCH_SIZE`, all rows materialized.
- Full suite re-run: **437 passed** (436 + the new guard), `ruff`/`mypy`
  clean on the touched modules.
- **Live verification (the failed roadmap criterion, re-run):**
  `limes ingest --source gisco_nuts` against a disposable Neo4j container
  with the production §13.4 memory configuration (heap 2G, page cache 2G,
  transaction cap 512m, timeout 120s) fetched the live GISCO files
  (NUTS hierarchy + the 127 MB postcode correspondence), normalized
  802,841 lookup rows, and loaded them in bounded transactions —
  `:PostalCode` nodes exactly 802,841, `nodes_created=804812`,
  `assertions_written=1932`, `errors=0`, `:IngestionRun` closed, advisory
  lock acquired and released. The prior failure mode (one 300k-row
  transaction timing out at 120s) did not recur; the ~6.5-minute load time
  is the accepted bounded-transaction cost (D-46).
- Ledger integrity: D-43, D-44, D-45 (decided before the halt, referenced
  by the CLI code) were logged at resume; the repair's decision is D-46.
- Baseline deviation, not introduced here (D-27 precedent, flagged not
  fixed): `tests/integration/test_loader.py` fails `ruff format --check`
  and carries 14 pre-existing E501 lines on pristine main.

---

## 2026-08-02 — Phase 6 (WP-28…WP-31) — halted at [CONFLICT], not delivered

The phase's work products exist on branch `wp-28-31-cli-and-evaluation`
(unmerged) and their suites are green, but the phase is **halted** per the
human's decision (DECISIONS.md, 2026-08-02): the roadmap's live
verification `limes ingest --source gisco_nuts` fails against the live
GISCO postcode file because the delivered WP-07 loader writes all ~300k
lookup rows in one transaction (`graph/loader.py:112-118`, `:312-324`).
No phase version was presented and no approval was requested.

What exists on the branch (all 436 tests green, `ruff`/`mypy`/`check_docs`
clean):

- WP-28 — CLI core: `cli/main.py` (Typer app, `:AdvisoryLock` lifecycle —
  acquire/release/reclaim, cross-process refusal proven), `cli/ingest.py`
  (ingest, ingest-all with enrichment-only skip), `cli/backfill.py`
  (`--days` → explicit window, mandatory `--budget`), `cli/reextract.py`
  (`--prompt-version` flows into Settings; defaults to unstructured
  sources), `cli/backup.py` (compose stop → `neo4j-admin database dump` →
  start → reachability, timestamped archive dump; real-lifecycle test).
- WP-29 — `cli/select_models.py`: provisional stage (catalogue filtering
  by §8.7.2 criteria, ranking, operator confirmation, `.env` pins, no gold
  set read — AC-36) and measured stage (gold-set ≥ 1.0.0 refusal, per-role
  harness scores, impact report without re-extraction or index rebuild —
  AC-37). `composition.extractor_for` added as the per-candidate extractor
  construction point.
- WP-30 — `cli/evaluate.py` (extraction P/R/F1 per relation with §12.5
  multiset semantics, baseline gate at 0.05 — AC-31, `:GoldSetItem`
  writes, `--resolution` recall@10/accuracy, `--nl2cypher` provisional
  validation-pass rate, AC-25 reference-question check); `gold_set/`
  (schema, 2 placeholder items, 100-pair calibration set with exact
  40/40/20 and 50/50 counts, empty baseline, changelog);
  `reference_questions/questions.yaml` (5 questions with ontology-valid
  reference Cypher).
- WP-31 — `cli/migrate.py` (stamped-version routing: fresh/already-at/
  downgrade/additive/breaking; numbered migrations with `TO_VERSION` +
  `upgrade(driver)`), `ontology/migrations/0001_initial.py`.

---

## 2026-08-01 — WP-26 (Composition root)

- `composition.py`: the single module that constructs every component in
  dependency order, once per process (AC-40 — repo-wide grep proves no
  other module constructs a driver, registry, archive, governor, client,
  extractor, or gate). `build_run_context(settings, *, needs_inference,
  budget_eur=None)`: ontology, driver, idempotent `provision()` with the
  downgrade guard, default registry, archive, governor (monthly, or an
  envelope when `budget_eur` is given); `needs_inference` gates spaCy model
  loading and extractor construction (AC-41 — a structured-only build loads
  no model and leaves the inference slots None). `build_nlq_context` for
  the API path. Context types follow the D-22/D-28 precedent: `RunContext`
  stays in `resolution/resolve.py`, `GateContext` in `pipeline/gate.py`;
  `NlqContext` is defined here (§8.15 home). `embedder_for(settings,
  client)` is the loader-embedder wiring point D-26 named: dimension-
  checked, L2-normalized, None when no client exists.
- The §8.7.1 protocol declares a settable `model_id`, WP-22's extractor a
  read-only property — the seam site narrows with a `cast` and a why-
  comment (D-41); the spec block keeps its literal shape.
- 9 integration tests: AC-40 grep guard, AC-41 inference gating (with
  `spacy.load` made to explode on a structured build), provision-on-every-
  build, frozen contexts, envelope governor, `embedder_for` wiring, and
  clean import circularity.

## 2026-08-01 — WP-27 (Pipeline run orchestration + window resolution)

- `pipeline/window.py`: `resolve_window(spec, adapter, source_node,
  settings, now=None)` — explicit `since` wins; an incremental source
  anchors at `Source.last_success_at`, a never-run one at
  `now − LIMES_BACKFILL_DAYS_UNSTRUCTURED`; a non-incremental source is a
  full load `(None, None)` (AC-42). `settings`/`now` are the D-40 additions
  the §8.6.2 signature cannot reach.
- `pipeline/run.py`: `RunSpec` and `execute_run(spec, ctx)` — the §15.3
  traces 1 and 2: `:Source` MERGE and `:IngestionRun` lifecycle (the two
  node types run.py owns), registry-based window, fetch → archive
  (content-addressed, `content_hash` re-stamped from `ArchiveStore.put`) →
  normalize → structured records validate and load; document records gate
  (cache-hit/gate-out counted with reason), extract, cache, resolve, load
  with the wired embedder. §15.2 provenance: `source_id`/`source_trust`
  stamped from the registry on every assertion; the resolver's five
  pipeline-known intermediates re-stamped before load and `assertion_id`
  recomputed with the real `source_id` (D-29) — the intermediates never
  reach the graph. The D-20 per-feed trust seam is keyed on
  `RawRecord.source_url` (the feed's URL — `doc.url` is the entry link and
  would never match).
- Failure semantics (§8.6.1): record-level parse errors counted in
  `errors` and skipped; fetch/config failures abort with the record closed;
  `BudgetExhausted` closes the run cleanly — `finished_at` set,
  `last_success_at` untouched — logs the queued remainder, and re-raises
  (AC-14). `cost_eur` is the governor `remaining()` delta (D-38). Reextract
  (D-39) retracts only the source's prior assertions for the document that
  the new extraction did not reproduce — after extraction and resolution
  succeed, so a failed re-extraction never destroys the prior record.
  `cache.put` runs only after the document's load succeeded (D-38).
- SAME_AS semantics documented (D-42): first-run deterministic mentions of
  backbone-absent entities carry no link — the loader materializes after
  resolution by the trace order, and the resolver may not create entity
  nodes (AC-17); the structured backbone pre-loads the LEI space and a
  version-change reextract creates the links on the second pass.
- 7 window unit tests and 9 pipeline integration tests: Trace 1 end-to-end
  with the GISCO adapter, AC-05 re-ingest (zero new nodes, skip count
  reported), record-level error counting, fetch-abort with the record
  closed and `last_success_at` untouched, `:Source`/`:IngestionRun`
  durability; Trace 2 end-to-end with the feeds adapter, per-feed trust
  override, provenance never carrying the resolver's intermediates, gate-
  out counting, budget exhaustion closing the run, cache-hit re-ingest,
  and reextract relinking plus superseded retraction.

---

## 2026-08-01 — WP-25 (Entity resolution)

- `resolution/keys.py`: `deterministic_key` — the mention-carried key honored
  only when declared for the type, plus a conservative surface-pattern table
  whose produced values exactly equal the structured adapters' emitted key
  values (LEI, QID, CELEX, BGBl citation with periodikum-dot normalization,
  TED notice, transparency-register id, content hash). Formats without a
  canonical surface form (register numbers with court suffixes, bare-digit
  ids) are excluded: a wrong key costs a wrong identity.
- `resolution/blocking.py`: `embed` (per-process cache keyed by text and
  model, L2-normalized with the dimension contract) and `candidates`
  (read-only vector-index query, type-filtered, k = limit×5 pre-filter).
  **Finding:** the engine's cosine index reports `(1 + cosine) / 2`, not the
  cosine — `candidates` converts back to cosine space, or the §8.8.3
  thresholds would auto-link at a true cosine of only 0.86.
- `resolution/adjudicate.py`: one pairwise call (v1.0.0 prompt) of the
  mention against its top candidate, the remaining candidates riding in the
  context slot; schema-validated response, confidence capped at 0.90; a
  false verdict, malformed response, or schema violation is `(None, 0.0)`
  and the caller mints, each logged.
- `resolution/link.py`: deterministic `mention_id` (MERGE-idempotent across
  re-extraction), `:Mention` per endpoint with §5.8 offsets, scored
  `SAME_AS` with `method`/`score`/`decision_at`/`retracted_at`; `unlink`
  retracts through a write session (the statement writes while returning a
  count — `GraphDriver.read` would refuse it); re-linking re-activates.
- `resolution/resolve.py`: `RunContext` (§8.15 shape, defined here per the
  D-22 precedent, consumed by WP-26), `ResolutionStats`, and
  `resolve_assertions` — per unique (type, surface): deterministic key →
  Wikidata enrichment (only types declaring `wikidata_qid`, cached, network
  failure = counted miss) → embed + candidates → §8.8.3 thresholds (margin
  is top minus second, second zeroed when a single candidate) → deterministic
  mint id. The resolver never writes an entity node; minted mentions get no
  `SAME_AS` (the node does not exist until the loader runs). Provenance
  contract: the resolver stamps what its context determines; `source_id`,
  `source_trust`, model/prompt/schema versions are type-satisfying
  intermediates that `execute_run` re-stamps before load per §15.2, which
  also recomputes `assertion_id`.
- 30 unit tests (keys, blocking, adjudicate) and 5 integration tests
  (AC-16 short-circuit with zero reads and zero paid calls; AC-17 four-band
  routing incl. the `≥ 0.93`-with-margin-`< 0.05` trigger and the mint
  branch writing no entity node; AC-19 unlink retraction with assertion
  attribution intact; AC-43 conversion, mention policy, and stats) — the
  index populated through the production `load` path with an injected
  embedder (WP-25a resume gate).

---

Closes the seam conflict found while starting WP-25: the §5.3 vector index
over `:Entity.label_embedding` had no registered writer (§15.2, verified by
repo-wide search). Human decision (DECISIONS.md 2026-08-01): the fix is a
missing stamp in the §5.6 merge contract, upstream at one choke point.

- `graph/embeddings.py`: `normalize_embedding` — unit L2 norm with optional
  dimension check, the single write-side enforcement of the §5.3 cosine
  contract; zero vectors fail loudly.
- `graph/queries.py`: `merge_entity` stamps `label_embedding = $label_embedding`
  on `ON CREATE` only — `ON MATCH` never touches it, mirroring the stored
  label's immutability (AC-09) — plus the read/stamp statements for the
  backfill.
- `graph/loader.py`: `load(..., embedder=None)` — one read per batch
  establishes which endpoints have no node yet; only those labels are
  embedded (never re-embedding existing nodes); the loader normalizes
  defensively; `embedder=None` writes nulls with a logged line.
  `stamp_missing_embeddings(driver, embedder, batch_size=500)` — the one-shot
  backfill over `label_embedding IS NULL`, idempotent, the only path that
  fills a null.
- Documentation set: Technical Specification v2.1.0 (§5.2, §5.3, §5.6, §8.3,
  §13.3, §15.2, revision history), Implementation Roadmap v2.1.0 (WP-25a
  entry; phase 4, dependencies, critical path, file ownership updated),
  Design Document companion references, README and AGENTS.md filename
  references; `tools/check_docs.py` external-type set gains `Callable`.
- 6 unit tests (normalization contract) and 8 integration tests through the
  production `load` path (ON CREATE stamping, re-merge immutability, no
  re-embedding, nulls, backfill exactness and idempotency, embedder contract
  violations, defensive normalization).
- Baseline deviation discovered, left untouched (out of scope): `ruff format
  --check` fails on `src/limes/graph/lookups.py:28` on the pristine main.

---

## 2026-08-01 — WP-24 (Gate: spaCy NER, passage selection, idempotency)

- `pipeline/gate.py`: `GateContext` (settings, driver, nlp_de, nlp_en — the
  §8.15 shape, defined here for WP-26 to construct), `gate_document` (cache
  short-circuit first, then spaCy NER with date/number labels filtered, then
  passage selection; `cache_hit` / `unsupported_language` /
  `below_mention_threshold` reasons, every rejection logged — AC-11), and
  `select_passages` (the pure mention-threshold half). The label filter set
  is a named refresh-point constant.
- `pipeline/passages.py`: dependency-free `split_sentences` and
  `window_passages` (merged overlapping windows with exact document offsets —
  `text[doc_start:doc_end] == text`, the invariant the extractor's
  evidence-span mapping anchors to).
- `pipeline/idempotency.py`: `is_already_extracted` — the zero-cost
  short-circuit over `cache.exists` (AC-12 partial).
- 9 unit tests with the real installed de/en spaCy models; cache-hit and
  zero-passage paths exercised with driver stubs.

## 2026-08-01 — WP-23 (Extraction cache)

- `extraction/cache.py`: `:ExtractionCacheEntry` write/read/exists keyed by
  `SHA-256(content_hash | prompt_version | schema_version | model_id)` —
  deterministic across processes (proven by a subprocess test), version
  triple in the key (DD-08: a prompt/schema/model change is a miss, AC-12).
  The cache is the sole writer of the node type (§15.2). Full-rebuild test
  shows every document short-circuits with zero paid calls (AC-33 partial).
- 8 integration tests against the disposable Neo4j container.

## 2026-08-01 — WP-22 (Extractor: protocol, OpenRouter client, schema, prompts)

- `extraction/base.py`: `Extractor` protocol, `ExtractionResult`, shared
  batching (`batch_passages` — count and token bounds, oversized passage
  stays its own batch, never dropped) and `build_extraction_messages`
  (passages inside explicit `<PASSAGES>` delimiters, §7.5).
- `extraction/openrouter_client.py`: the single `OpenRouterClient` for
  chat/embeddings/catalogue; `governor.check` before and `commit` after every
  request (the only module writing `:CostLedgerEntry`, §15.2); ledger entries
  only for attempts that returned token usage; §11 retry policy (2s
  exponential jitter, max 4, on connect/timeout/429/5xx — never other 4xx);
  API key only ever in the Authorization header, never a log line; pricing
  from the model catalogue with a conservative, always-logged fallback
  (D-23).
- `extraction/schema.py`: versioned `EXTRACTION_SCHEMA` (additionalProperties
  false throughout) and `parse_extraction_response` — schema, ontology
  relation/type validation, passage-local → document offset mapping, and the
  AC-13 evidence-span check (rejected when the mapped span contains neither
  surface, D-21). Stable rejection reason prefixes for counting.
- `extraction/openrouter.py`: `OpenRouterExtractor` — per-version prompt
  loading (a missing prompt file fails loudly), schema-version validation,
  per-batch calls merged into one per-document `ExtractionResult` (D-24).
- `extraction/ollama.py`: `OllamaExtractor` — laptop-only local path (C-05),
  same protocol and parsing, no governor/ledger, §11 retries.
- `extraction/prompts/extraction_v1.0.0.md` and
  `extraction/prompts/adjudication_v1.0.0.md` (the latter consumed by WP-25).
- 34 unit tests (retry policy, redaction, governor ordering, budget refusal
  without a request, batching, every rejection reason) and 4 integration
  tests (AC-13 across the full extractor, AC-12 partial via a pre-populated
  cache).

## 2026-08-01 — WP-21 (Unstructured adapters: GDELT + feeds)

- `ontology/feeds.yaml`: the curated feed set — Commission RAPID,
  Bundesregierung press releases (0.70), tagesschau, EUobserver (0.60);
  URLs are the named refresh point.
- `sources/gdelt.py`: `GdeltAdapter` (trust 0.50) — one 15-minute event file
  per window slot, sequential; `Event` nodes (D-10 multi-key identity,
  stampable `source_event_id`), directional `ACTOR_IN`/`TARGET_OF` (Doc 1
  §5.4) typed by GDELT's own actor type codes (GOV/MIL/COP/JUD →
  PublicBody, BUS → Corporation; state actors are counted skips — D-18),
  `OCCURRED_IN` to `Country` (ISO2) or coordinate-hash `Location` (D-13
  rounding); one per-file `DocumentPayload` with the event-vintage
  `published_at`.
- `sources/feeds.py`: `FeedsAdapter` (trust 0.60) — per-entry deterministic
  JSON envelopes from `feedparser` (D-19: entry-unique content hashes),
  HTML body extraction, declared-language-wins detection (D-25), undated
  entries fall back to the fetch instant with a count, per-feed trust
  override exposed as `trust_rank_for` for WP-27 (D-20); config defects are
  `ConfigurationError` at construction.
- Two registry lines; 21 unit tests, respx-mocked, no live network.

---

## 2026-08-01 — WP-20 (OffeneRegister adapter)

- `sources/offeneregister.py`: `OffeneRegisterAdapter` (trust 0.30, lowest
  deliberately). The vintage rule: `recorded_at` on every assertion is the
  dataset's publication date from the metadata record, never the ingestion
  timestamp — and a data record normalized without a prior metadata record is
  refused with `SourceParseError` rather than wall-clock-stamped (DD-15).
  Metadata date is in-process instance state within one run (C-07 concerns
  cross-process state); `DIRECTOR_OF` from officer records with start/end
  intervals; register-number Corporation keys; German officer names verbatim.
- 10 unit tests including the refusal path and `recorded_at != fetched_at`.

## 2026-08-01 — WP-19 (OSM adapter)

- `sources/osm.py`: `OsmAdapter` (trust 0.75) — Overpass query over the
  German bounding box for KRITIS-tagged elements; `Asset` (OSM ID keys),
  `OPERATES` (operator), `LOCATED_IN` via the postal-code lookup only (region
  assignment is a lookup, never geometry), standalone KRITIS `Topic` and
  coordinate-hash `Location` entities. Ontology-gap reading documented: no
  Asset→Topic and no Asset→Location edge exists, so sectors and points are
  represented as standalone nodes with the raw payload in the archive.
- 8 unit tests, respx-mocked.

## 2026-08-01 — WP-18 (Wikidata adapter, enrichment only)

- `sources/wikidata.py`: `WikidataAdapter` with `enrich(entity_type, label)
  -> WikidataMatch | None` — wbsearchentities + wbsgetentities (P31 class
  filter per a closed type→class map), exact-label match only, `None` on any
  ambiguity (never guessing). `fetch`/`normalize` raise `NotImplementedError`;
  registered in `build_default_registry` as enrichment-only.
- 11 unit tests, respx-mocked.

## 2026-08-01 — WP-17 (Gesetze im Internet adapter)

- `sources/gesetze_im_internet.py`: `GesetzeImInternetAdapter` — TOC
  (`gii-toc.xml`, verified live) then per-law `xml.zip` (BJNR member);
  `LegalAct` keyed by the Bundesgesetzblatt citation from the XML's
  `fundstelle` (`BGBl I 2000, 2045`), `ABOUT_TOPIC`/`APPLIES_TO` to
  source-namespaced `topic:Sachgebiet:*` topics where the XML declares them.
- 10 unit tests, respx-mocked.

## 2026-08-01 — WP-16 (Bundestag DIP adapter)

- `sources/bundestag_dip.py`: `BundestagDipAdapter` — DIP API (operator API
  key accepted via constructor, no config key added; 401 surfaces honestly as
  `SourceFetchError`); `Person` (Bundestag ID keys), reified `Office` nodes
  (body+title+interval identity, DD-13), temporal `HOLDS_OFFICE`/`OFFICE_AT`
  and `MEMBER_OF`; Wahlperiode start dates from a documented refresh-point
  constant.
- 10 unit tests, respx-mocked.

## 2026-08-01 — WP-15 (Transparency Register adapter)

- `sources/transparency_register.py`: `TransparencyRegisterAdapter` — export
  XML; `InterestGroup` (TR IDs), `MEMBER_OF` (head persons), `LOBBIES_FOR`
  to source-namespaced `topic:EU_TR:*` interests, `MET_WITH` for declared
  meetings.
- 7 unit tests, respx-mocked.

## 2026-08-01 — WP-14 (TED adapter)

- `sources/ted.py`: `TedAdapter` — notice search API (POST, shared retry
  policy) then per-notice XML; `Contract` (TED notice IDs), `PublicBody`
  buyers (stable `ted_buyer_id` surrogate digest), `AWARDED_TO`/`BUYER_OF`/
  `ABOUT_TOPIC` (CPV), `HEADQUARTERED_IN`+`LOCATED_IN` region assignment via
  the postal lookup (BUYER_NUTS preferred when present).
- 10 unit tests, respx-mocked.

## 2026-08-01 — WP-13 (FSD adapter)

- `sources/fsd.py`: `FsdAdapter` — consolidated XML; the three-way sanction
  decomposition (TARGETS, IMPOSED_BY, ESTABLISHED_BY as separate assertions,
  Doc 1 §5.4); Sanction key `("fsd_id", "<id>:<regime>")`; regime→IGO
  mapping (EU→Q458, UN→Q1065); rotating public token isolated in the
  `FSD_URL` constant.
- 15 unit tests, respx-mocked.

## 2026-08-01 — WP-12 (EUR-Lex adapter)

- `sources/eurlex.py`: `EurlexAdapter` — Cellar SPARQL (verified live),
  window compiled into the query; `LegalAct` (CELEX keys), `ADOPTED`
  (closed author→QID map), `AMENDS`/`REPEALS`/`CITES` (non-temporal),
  `ABOUT_TOPIC`/`APPLIES_TO` to `topic:EuroVoc:*`.
- 8 unit tests, respx-mocked.

## 2026-08-01 — WP-11 (GLEIF adapter)

- `sources/gleif.py`: `GleifAdapter` — golden-copy zips (entity +
  relationships CSV); `Corporation` (LEI keys), `HEADQUARTERED_IN` to
  address-hash `Location` nodes, `SUBSIDIARY_OF`, `OWNS_STAKE_IN` gated on a
  positive direct percentage, `LOCATED_IN` via `postal_lookup` (misses
  counted, never guessed).
- 10 unit tests, respx-mocked.

## 2026-08-01 — WP-10 (GISCO/NUTS adapter)

- `sources/gisco_nuts.py`: `GiscoNutsAdapter` — verified live files: the
  2024 NUTS hierarchy CSV (level from `NUTS_ID` length, parent by prefix,
  country row from the 2-char id) and the postcode correspondence at
  `/v2/pcode/csv/` (mixed single/double quoting handled by quote
  normalization); `AdministrativeRegion`/`Country`/`PART_OF_REGION` plus
  `LookupRow(kind="postal_code")` — the first cross-process reference data
  (C-07).
- 8 unit tests, respx-mocked, fixtures from real file rows.

## 2026-08-01 — WP-09 (Source adapter protocol, registry, normalizer)

- `sources/base.py`: `SourceAdapter` protocol (§8.5.1, runtime-checkable),
  shared fetch helpers with the §11 retry policy (GET + POST, 2s→factor
  2→jitter, 4 attempts, 429/5xx/connect/timeout only), `ONTOLOGY_VERSION`
  constant (single bump point for WP-31), deterministic `entity_id` and
  `assertion_id` schemes (cross-run idempotency, AC-05).
- `sources/registry.py`: `SourceRegistry` (`get` names unknown + registered
  sources, AC-38) and `build_default_registry` — the authoritative source
  set; no import-time self-registration.
- `pipeline/normalize.py`: `detect_language` (stopword heuristic, no new
  dependency), `normalize_timestamp` (day-first European default, naive→UTC),
  `extract_text_from_html`, `extract_text_from_xml`.
- 17 unit tests.



- `graph/lookups.py`: `postal_code_to_nuts` per §8.16 — graph query plus
  in-process LRU cache; misses return `None` and are cached; the
  correspondence itself lives in `:PostalCode` nodes, never module state
  (C-07, DD-20, AC-39).
- 5 integration tests: hit, miss-without-raise, cache hits proven by read
  counts, LRU eviction, and a real subprocess crossing the process boundary
  (Doc 2 §12.2 rule 2).

## 2026-08-01 — WP-07 (Graph loader)

- `graph/loader.py`: `load` (batches ≤500 assertions, §5.6 semantics: node
  materialization by `Ontology.labels_for` label sets, idempotent
  `assertion_id`-keyed relationship merge, same-source interval closure,
  non-destructive re-merge, `ENDPOINT_UNIDENTIFIED` rejection AC-10) and
  `retract`. Sole writer of ontology-typed nodes, relationships, and lookup
  rows (§15.2, DD-19). Batch transactions run through the driver's raw
  session to collect per-statement outcomes (write_batch aggregates only).
- `graph/queries.py`: parameterized Cypher templates; label and relation-type
  segments built only from ontology data, never source data (§5.6).
- 8 unit tests (partitioning, key guard, metadata map) plus 11 integration
  tests (AC-05, AC-06, AC-07 partial, AC-08, AC-09, AC-10) green.

## 2026-08-01 — WP-06 (Cost ledger and budget governor)

- `cost/ledger.py`: `write_entry` (`:CostLedgerEntry` per §5.8, MERGE on the
  unique ledger_id) and `read_period_spend` (period sum read from the graph,
  never process memory — C-07).
- `cost/governor.py`: `Governor` per §8.9 — `check`/`commit`/`remaining`;
  monthly metering reads the graph every call (cross-process spend visible),
  envelope metering is in-process and never draws on the monthly ceiling
  (AC-15); refusal at the soft-stop fraction of the ceiling (AC-14).
- 10 unit tests plus 6 integration tests green.

## 2026-08-01 — WP-05 (Archive store)

- `archive/store.py`: `ArchiveStore` per §8.4 — SHA-256 content addressing,
  gzip compression, two-level hex prefix directories, atomic write by
  temporary name and rename; `put` idempotent.
- 9 unit tests including cross-process hash stability (Doc 2 §12.1).

## 2026-08-01 — WP-04 (Graph driver, schema provisioning, temporal fragments)

- `graph/driver.py`: `GraphDriver` with read-access-mode sessions (§7.2),
  single-transaction `write_batch` with `GraphWriteError` wrapping (§11),
  `EXPLAIN` plan parsing into `PlanSummary`.
- `graph/schema.py`: idempotent `provision()` of all §5.3 constraints and
  indexes (AC-03) plus the ontology downgrade guard (AC-01). One DDL
  statement per transaction: Neo4j fails a transaction issuing many schema
  changes with "insanely frequent schema changes".
- `graph/temporal.py`: `as_of`, `as_believed`, `currently` composable
  fragments with matching parameter helpers (§5.7).
- Integration conftest starts a disposable `neo4j:2026.06-community`
  container; 2026.x requires the first-boot admin user to be `neo4j`, so the
  conftest creates the `limes` test user via `CREATE USER`.
- 4 unit tests plus 9 integration tests green.

## 2026-08-01 — WP-03 (Ontology artifact, schema, registry, validator)

- `ontology/ontology.yaml` with 17 entity types and 30 relations (verified
  17/30), validated against `ontology.schema.json` and self-validated per §5.1.
- `model.py` (`Ontology`, `labels_for`, `permits`, `serialize_for_prompt`),
  `registry.py` (`load_ontology`), `validator.py` (`validate_assertions`).
- 46 unit tests in `test_ontology.py`.

## 2026-08-01 — WP-02 (Configuration, types, errors, logging)

- `config.py` with one typed field per §4.2 key and `load_settings()` failing
  startup with a named key (AC-01); full `.env.example`.
- `types.py` with every §5.5 core type; `errors.py` with the full §11
  hierarchy; `logging_setup.py` with secret redaction.
- 30 unit tests across `test_config`, `test_types`, `test_errors`,
  `test_logging`.

## 2026-08-01 — WP-01 (Repository skeleton, tooling, check_docs.py)

- Established the directory tree from Technical Specification §2 with empty
  packages for every `src/limes/*` module and `tests/`.
- `pyproject.toml` with all dependencies from Technical Specification §3,
  ruff (line length 100) and mypy (strict) configuration.
- `uv.lock` generated and `uv sync` verified against `./venv/`.
- `tools/check_docs.py` specification consistency validator (C1–C7) passes
  against the v2.0.0 document set.
- `README.md` (includes the personal-artifact disclaimer, AC-35) and
  `AGENTS.md` confirmed present.
- `.gitignore` (existing) covers Python, Docker, Neo4j data, and `.env`.
