# DECISIONS — LIMES decision ledger

Append-only ledger per the global AGENTS.md §5. Entries are tagged by
reversibility: **R1** reversible in under an hour, **R2** bounded recoverable
cost, **R3** one-way door. Written when each decision is made, latest first.
Nothing here is a status report; unlogged decisions are unmade decisions.

## 2026-08-03 — Approval — phase-11-v1.0.0 (WP-40)

The human approved phase-11-v1.0.0 (100% line coverage suite) on
2026-08-03 and instructed merge, commit, and push. Delivered as branch
`wp-40-line-coverage`, merged to `main` and pushed; the topic branch is
pushed as well. This approval names the presented version and cannot be
reused for any other version of the phase.

## 2026-08-03 — D-63 (R2) — Operator-instructed 100% line coverage (WP-40)

The operator instructed "add tests until we have 100% test coverage".
Doc 2 §12.4 declares line coverage not a target ("the required condition
is that every error path in §11 and every rejection code in §8.10 is
triggered by at least one test"), but a later explicit operator
instruction overrides an earlier document sentence. Logged as the
delegation's basis so a future reader does not treat 100% as the spec's
own requirement. Measurement: statement coverage of `src/limes` over all
three suites combined (`unit` + `integration` + `acceptance`; separate
runs appended via `coverage run --append` because the acceptance
conftest's `pytest_plugins` is rejected by pytest 9.1.1 in whole-tree
collection — pre-existing quirk, not touched here). Subprocess-based
tests are invisible to the coverage tracer, which is why the CLI command
bodies that the integration suite runs as subprocesses needed in-process
unit tests.

## 2026-08-03 — D-62b (R2) — Dead builder-hold callback repaired in `ui/callbacks/query.py`

Found by the WP-40 coverage exercise: `builder_hop_change` decoded the
hop index with `triggered_index("builder")`, but every hop control's
pattern id is `{"type": "builder-rel"|"builder-dir"|…, "index": n}` — the
exact-type match can never succeed, so every hop-control interaction
raised `PreventUpdate` and the entire callback (lines 231–311) was dead
in production. The fix decodes the index from the same decoded control
type (`triggered_index(control)`), restoring the documented behavior
("applies whichever hop control changed"). Rejected alternative: testing
around the defect by driving the branches with a hand-built context — the
branches were unreachable through the callback's own contract, and
covering dead code would enshrine it. R2: bounded, restores the WP-36
design intent; the UI suite (`test_ui_callbacks.py`) now exercises every
branch.

## 2026-08-03 — D-64 (R1) — Test isolation from the repository `.env` (WP-40)

The pre-existing WP-02 failure documented in the phase-10 changelog
(`test_config.py::test_load_settings_missing_required_key_names_it` fails
when the repo's own `.env` exists at the CWD) was fixed in the test:
an autouse fixture forces `Settings(_env_file=None)` so the unit suite
asserts on the environment alone. R1 — test-only, no production change;
the phase-10 changelog's "not fixed here" note is now resolved.

## 2026-08-03 — D-65 (R2, user-approved) — `coverage` added to the dev dependency group

The task requires measuring coverage; the project venv had no coverage
tool (the system site-packages copy is ABI-compatible but outside the
project contract). The operator approved adding `coverage>=7.15` to
`[dependency-groups].dev` in pyproject.toml; installed into `./venv/`.
Host tooling lives in the venv per the global contract §3.

## 2026-08-03 — Approval — phase-10-v1.0.0 (WP-39)

The human approved phase-10-v1.0.0 (acceptance test suite) on 2026-08-03
and instructed merge, commit, and push. Delivered as branch
`wp-39-acceptance-tests`, merged to `main` and pushed; the topic branch is
pushed as well. This approval names the presented version and cannot be
reused for any other version of the phase.
---

## 2026-08-03 — Phase 10 invariants (WP-39), derived at phase start

Derived from the roadmap's WP-39 entry and Doc 2 §12.4/§14, per the global
contract §6. Guarded (automatically tested) and triggered (review-trigger)
invariants, logged when derived:

- **G1 (guarded)** — Every AC-01…AC-44 has a mechanical test in
  `tests/acceptance/` and the suite passes → asserted by the meta-test
  `test_ac00_meta_coverage.py` (scans for `test_acNN_*` functions and
  fails on any gap) plus the suite itself.
- **G2 (guarded)** — No acceptance test touches a live external service;
  the paid boundary is respx-mocked or fixture-stubbed → enforced by the
  suite's construction: every test that crosses the paid boundary uses
  `respx.mock` or an injected fake; a test that performs live network
  access fails loudly (respx with no routes).
- **G3 (guarded)** — Cross-process acceptance tests cross a real process
  boundary via `subprocess` (AC-39's lookup read, AC-01's startup check,
  AC-44's check_docs run) per Doc 2 §12.2 rule 2.
- **G4 (guarded)** — No acceptance test hand-builds the graph state the
  production path produces: all graph state is established through
  `execute_run`, `load`, or the API (Doc 2 §12.2 rule 1) → enforced by
  the suite's construction and reviewable per test.
- **T1 (triggered)** — The `populated_graph` fixture's stub seam (class
  method replacements on the adapters and `composition.spacy.load`): any
  change to what is stubbed or how requires re-review that the production
  path still runs for real underneath.
- **T2 (triggered)** — AC-32's testable proxy: the test asserts the
  §13.4 declared caps sum below 11 GB, not a measured backfill resident
  set. A change to the caps or the ceiling requires re-review of the
  proxy's adequacy.

## 2026-08-03 — D-62 (R2) — Plan-gate row estimates repaired in `graph/driver.py`

Found by the AC-21 acceptance test: `_parse_plan` read the EXPLAIN row
estimate from a top-level `estimatedRows` key that the Neo4j 2026.06
server never emits — the estimate is nested under `args.EstimatedRows`.
Measured against a live container: every plan reported max=0/total=0, so
the §8.10 rejections `OPERATOR_ROWS_EXCEEDED` and `TOTAL_ROWS_EXCEEDED`
silently never fired; two of the five plan-gate rejections were dead code.
The fix reads `args.EstimatedRows` with the legacy top-level key as
fallback (one function, no signature change). Rejected alternative:
leaving the dead parsing and writing the AC-21 test against mocked plan
dicts — that would enshrine the defect and fail the criterion's letter
(a crafted query must produce the rejection against the real database).
The fix is R2 (bounded, spec-mandated — §8.10 requires the rejections);
the pre-existing `test_nlq_plan` unit suite never exercised the estimate
fields, which is why the defect shipped. The affected integration suites
(test_graph_driver, test_loader, test_resolution, test_ui,
test_api_query_*, test_pipeline_run_*) re-ran green after the fix.

## 2026-08-03 — Approval — phase-9-v1.0.0 (WP-37, WP-38)

The human approved phase-9-v1.0.0 (Docker images and Compose topology;
Makefile and bootstrap procedure) on 2026-08-03 and instructed merge,
commit, and push. Delivered as branch `wp-37-38-infrastructure`, merged to
`main` and pushed; the topic branch is pushed as well. This approval names
the presented version and cannot be reused for any other version of the
phase.

## 2026-08-03 — Phase 9 invariants (WP-37, WP-38), derived at phase start

Derived from the roadmap's WP-37/WP-38 entries, Doc 1 §8.1–§8.4/§6.6, and
Doc 2 §13.1–§13.4/§8.14, per the global contract §6. Guarded (automatically
tested) and triggered (review-trigger) invariants, logged when derived:

- **G1 (guarded)** — AC-34: the base Compose file publishes no ports, and
  the Neo4j port appears in neither file except as the `LIMES_NEO4J_URI`
  value → asserted by `tools/smoke_test.py` (compose config + source
  scan) before any stack action.
- **G2 (guarded)** — The `ui` service holds no credentials: no `env_file`
  and no Neo4j/OpenRouter key in its environment; its only variable is
  `LIMES_API_BASE_URL` (D-09) → asserted by `tools/smoke_test.py` against
  the rendered compose config.
- **G3 (guarded)** — Only the worker image installs the spaCy models: the
  api and ui Dockerfiles prune `de-core-news-md` and `en-core-web-md` from
  the lockfile export → asserted by `tools/smoke_test.py` (static scan of
  the three Dockerfiles plus a `python -c "import de_core_news_md"` check
  against the built images).
- **G4 (guarded)** — Every `make` target from Doc 2 §8.14 exists, and
  `backfill`/`reextract` refuse to run without `BUDGET` → asserted by
  `tools/smoke_test.py` (`make help` lists all eleven targets; a missing
  `BUDGET` invocation exits non-zero).
- **T1 (triggered)** — The neo4j boot wrapper's user-creation step: any
  change to the wrapper, to `LIMES_NEO4J_USER`/`LIMES_NEO4J_PASSWORD`
  handling, or to the neo4j image tag requires re-review of the auth flow
  (the wrapper is the only path that creates the production user).
- **T2 (triggered)** — The worker's docker-socket mount is host-level
  privilege: any topology change touching the socket mount, the worker's
  docker CLI, or the compose files mounted into the worker requires
  review of what a compromised worker could reach.

## 2026-08-03 — [CONFLICT] resolved by the human — the production `limes` Neo4j user is created by a boot wrapper (R2)

The documentation set defines no mechanism that creates the production
`limes` Neo4j user. Verified in the `neo4j:2026.06-community` image itself:
the entrypoint's only user mechanism is `NEO4J_AUTH`, which provisions the
first-boot `neo4j` admin only. `bootstrap-db` is a no-op, `up` is bare
`docker compose up -d`, and the topology is exactly four services — yet
`.env.example`, the API, the worker, and the WP-38 verification's own
`cypher-shell -u limes` all require `limes` to exist. Recorded as
`[CONFLICT]` per roadmap §1.3 and presented to the human with four
branches (entrypoint wrapper; `make up` gains a user-creation step; manual
operator step; connect as `neo4j`). The human chose the **entrypoint
wrapper**: the base compose overrides the neo4j service's entrypoint with a
bash wrapper that starts the stock `/startup/docker-entrypoint.sh neo4j` in
the background, polls `cypher-shell -u neo4j` until the database accepts
connections, runs `CREATE USER ${LIMES_NEO4J_USER:-limes} IF NOT EXISTS SET
PASSWORD '<escaped>' CHANGE NOT REQUIRED`, then `wait`s on the server. Any
other invocation is `exec "$@"`, so the WP-28 backup path
(`docker compose run --rm --no-deps neo4j neo4j-admin …`) bypasses the boot
logic. Idempotent per volume, consistent with "provisioning happens on
every context build". Rejected alternatives and their consequences were
presented; the operator's choice is recorded here and cannot be reused for
another phase.

## 2026-08-03 — D-59 (R2) — Dependency layer via `uv export` + `uv pip install --system`, not `uv sync`

`uv sync` unconditionally creates a virtual environment — verified locally
that `UV_PROJECT_ENVIRONMENT` merely redirects where the venv is created —
and Doc 2 §13.1 forbids a virtual environment inside an image. The shared
dependency layer therefore runs `uv export --frozen --no-dev
--no-emit-project` and `uv pip install --system -r` (system-prefix install,
no venv), then `uv pip install --system --no-deps .` for the project. The
api and ui exports additionally `--prune de-core-news-md --prune
en-core-web-md`; the worker's export keeps them, which is how "only the
worker installs spaCy models" is satisfied — from the locked 3.8.0 wheels
in the committed lockfile, not `python -m spacy download`. Same frozen
resolution either way.

## 2026-08-03 — D-58 (R2) — api image CMD uses the factory form

`src/limes/api/main.py` exposes `create_app` and no module-level `app`
(phase-8 observation, 2026-08-02); the roadmap's literal
`uvicorn limes.api.main:app` would fail at boot. The api.Dockerfile CMD is
`uvicorn limes.api.main:create_app --factory --host 0.0.0.0 --port 8000`.

## 2026-08-03 — D-57 (R2) — Worker carries the docker CLI and the compose context; project named `limes`; `.env` delivered by mount, never `env_file`

The WP-28 `backup` command orchestrates `docker compose stop/run/start`
from its process working directory, and `select_models` writes pins into
`Path(".env")` in its CWD — both execute inside the worker container via
the Makefile. The worker image therefore carries `docker.io` and
`docker-compose-v2`, and the base compose mounts into the worker: the
docker socket, `docker-compose.yml` and `docker-compose.override.yml`
(read-only, so compose resolves the project from `/app`), and `./.env`
(read-write, so the pins persist to the host). `name: limes` makes the
worker's compose invocations resolve the same project as the host's
regardless of directory.

Configuration is delivered to `api` and `worker` by the `./.env` mount and
the app's own dotenv read (`config.py`'s `env_file=".env"`) — **not** by
compose `env_file`. Verified empirically with the pinned pydantic-settings:
an environment variable set to the empty string shadows a dotenv value
(present-but-empty env wins over the file). Compose `env_file` passes the
empty pin keys from `.env.example`, so the container environment would
permanently dead-letter the pins `select_models` writes — the bootstrap's
step-3-to-step-7 sequence (pin, then backfill) would fail with "no
extraction model pinned" even though `.env` holds the pin. The mount keeps
every exec'd process reading the current `.env` from its working directory
(`/app`), pins included, without any restart. The api mount is read-only;
the worker's is read-write (it writes pins). These are host paths in the
base file; Doc 1 §8.4's "no host paths" governs storage, and these carry
the configuration and compose context the delivered CLI requires. Rejected:
`env_file` (proven to dead-letter the pins), baking the compose files into
the image (drift), or running backup from the host (the roadmap fixes the
target to `docker compose exec worker limes backup`).

## 2026-08-03 — D-56 (R2) — `stamp-embeddings` Makefile target

The WP-25a contract names WP-38 as the wiring point for
`stamp_missing_embeddings`, which no CLI command exposes, and Doc 1 §6.6's
target list names no such target. The Makefile gains `stamp-embeddings`,
which runs a `python -c` invocation inside the worker with the inference
context (`build_run_context(needs_inference=True)`); the bootstrap
documents it between steps 6 and 7 per §13.3. Rejected: extending the CLI
(outside WP-38's file scope) and folding the stamp into an existing target
(wrong semantics; the stamp is a one-shot, not an ingestion).

## 2026-08-03 — D-55 (R1) — `migrate` target variable, `.dockerignore`, neo4j healthcheck

Three small calls: (1) the roadmap's `migrate` usage line says
`ONTOLOGY_VERSION=<v>` while its recipe line says `$(VERSION)`; the target
uses `$(ONTOLOGY_VERSION)` so the documented invocation works. (2) A
`.dockerignore` exists (build-context hygiene; without it the repo, the
host venv, and `.git` are copied into every build context — Doc 2 §2 does
not list it, it sits beside `.gitignore`). (3) The neo4j service declares a
cypher-shell healthcheck (as the `limes` user) and api/worker use
`depends_on: condition: service_healthy`, so `make up` returns with the
stack actually ready instead of merely started.

## 2026-08-03 — D-60 (R1) — `select-models` arguments pass through `ARGS=`, not `make --`

GNU make treats everything after `--` as goals: `make select-models --
--provisional` (the form written in §13.3's bootstrap and the delivered
README) fails with "No rule to make target '--provisional'" — verified
locally. The Makefile's `select-models $(ARGS)` mechanism per the WP-38
task list therefore requires `make select-models ARGS="--provisional"`;
the bootstrap documentation written by this phase uses that form. The
spec's literal invocation is a defect in the operator syntax, not in the
target; nothing in the Makefile changed to work around it.

## 2026-08-03 — D-61 (R1) — Compose wiring facts discovered during live verification

Three verified behaviors shaped the delivered files; recorded so the next
topology change does not rediscover them:

1. **Compose drops the image CMD when `entrypoint` is overridden as a
   list** (reproduced minimally: `Cmd=null` in the created container). The
   neo4j service therefore restates `command: ["neo4j"]`, and the boot
   wrapper dispatches on `$0` — `bash -c script neo4j` puts the CMD in
   `$0`, not `$1` — re-executing arbitrary commands as `"$0" "$@"` so the
   WP-28 backup's `docker compose run --no-deps neo4j sh -c …` works.
2. **Debian trixie has no compose v2 plugin package** (`docker-compose-v2`
   does not exist there; only `docker-cli` and the python `docker-compose`
   v1). The worker image installs `docker-cli` and the pinned upstream
   compose v2.40.3 plugin binary, SHA-256-verified against the release
   checksums at build time.
3. **`docker stop`'s default 10 s grace kills Neo4j uncleanly**: the first
   backup attempt failed with "Active logical log detected" and the dump
   refused. The neo4j service sets `stop_grace_period: 180s`; a verified
   clean stop of a small graph took ~120 s (Doc 1 §8.3 budgets 5-20 GB).
   Also: `docker compose ps --format json` emits JSONL, one object per
   line — `tools/smoke_test.py` parses it line by line.

## 2026-08-02 — Approval — phase-8-v1.0.0 (WP-36)

The human approved phase-8-v1.0.0 (Dash UI: three synchronized panes, the
schema-generated builder, NL input and editable Cypher console, coverage
and provenance panels, saved queries, budget indicator) on 2026-08-02 and
instructed merge, commit, and push. Delivered as branch `wp-36-dash-ui`
(commits `48556d3`, `fb7cab1`), merged to `main` and pushed; the topic
branch is pushed as well. This approval names the presented version and
cannot be reused for any other version of the phase.

## 2026-08-02 — D-14 (R1) — Selection sync semantics for the three panes

AC-29's "all three panes react to a selection change" is implemented
symmetrically: a node selection highlights the node in the network, its
marker on the map, and the rows of its incident edges in the timeline; an
edge selection highlights the edge in the network, its row in the timeline,
and the markers of both endpoints on the map. The map can only highlight
coordinate-bearing nodes (the only points it renders), and the timeline can
only highlight edges present in the result — a pane reacts exactly as far
as the data it renders admits.

## 2026-08-02 — D-13 (R1) — Builder bounds: one property filter per hop, one instant picker

The generated builder offers one (property, value) filter per hop and a
date picker for `as_of`/`as_believed` instants, and caps no hop count.
Richer filters and instant precision are the console's job; the builder
guarantees admissibility, not completeness. The instant is date-only: the
API's parameter passing cannot string-match datetime properties anyway
(`coerce_filter_value` documents this), so a date picker cannot promise a
match the API cannot deliver.

## 2026-08-02 — Observations for later phases (triggered paths)

- `src/limes/api/main.py` exposes `create_app` but no module-level `app`.
  WP-37's api.Dockerfile CMD `uvicorn limes.api.main:app` will therefore
  fail; it needs `uvicorn limes.api.main:create_app --factory`. Flagged
  here because it is outside WP-36's scope (the UI test uses the factory
  form). The ui.Dockerfile CMD `python -m limes.ui.app` works as specified.
- `src/limes/graph/lookups.py` fails `ruff format --check` on `main`
  (pre-existing WP-08 formatting deviation, unrelated to this phase);
  left untouched as out of scope.

## 2026-08-02 — D-12 (R1) — Panes re-render from the full query response envelope

The `current-result` store holds the whole `QueryResponse` (results,
coverage, diagnosis, notes), not just the graph: the coverage panel and the
console need the API's annotations, and AC-27's merge operates on the
`results` slice only. `merge_neighborhood` always returns the envelope form,
so the store has one shape regardless of whether the view started from a
query, a search jump, or an expansion.

## 2026-08-02 — Phase 8 invariants (WP-36), derived at phase start

Derived from the roadmap's WP-36 entry, Doc 1 §6.5/§4.13, and Doc 2 §8.13,
per the global contract §6. Guarded (automatically tested) and triggered
(review-trigger) invariants, logged when derived:

- **G1 (guarded)** — The UI holds no credentials and performs no database
  access: no `neo4j`, `GraphDriver`, or `bolt://` reference anywhere in
  `src/limes/ui/` → `test_ui.py::test_ui_holds_no_credentials_and_no_database_access`
  (source scan).
- **G2 (guarded)** — No UI module contains a hardcoded ontology type name
  or relation name as a literal; the builder is generated from
  `/builder/schema` → `test_ui.py::test_ui_source_contains_no_ontology_literals`
  (AST literal scan against the loaded ontology).
- **G3 (guarded)** — Node click expands one hop through
  `/entity/{id}/neighbors` and merges into the current view without
  re-running the original query (AC-27) →
  `test_ui.py::test_ac27_node_click_expands_one_hop_without_rerunning_the_query`
  (recording fake api_client asserts no query-path call).
- **G4 (guarded)** — Edge selection displays full provenance including the
  originating sentence when the evidence document is available through the
  API (AC-28) → `test_ui.py::test_ac28_edge_selection_shows_provenance_and_sentence`.
- **G5 (guarded)** — All three panes react to a selection change and to a
  timeline brush within one interaction cycle; the brush triggers a re-query,
  never client-side filtering (AC-29, Doc 2 §8.13) →
  `test_ui.py::test_ac29_panes_react_to_selection_and_brush_in_one_cycle`.
- **T1 (triggered)** — The builder's per-hop options stay admissible as the
  ontology evolves: any change to `ontology/ontology.yaml` that adds or
  renames a type or relation requires re-review of the builder rendering and
  of the map's coordinate-type derivation (the schema-derived lookups in
  `ui/components/builder.py` and `ui/components/map.py` are the affected
  paths).

## 2026-08-02 — D-11 (R2) — Timeline brush re-queries with `as_of` = brush right edge

The brush stores `{as_of, range}` in `temporal-filter` and re-runs the
query that produced the current view through the same API path: the builder
path re-runs `POST /query/builder` with `as_of` qualifiers on temporal hops
(the schema's `temporal` flag decides, never a UI list), and the NL and raw
Cypher paths re-run their stored payload (`POST /query/nl` with the same
question, `POST /query/cypher` with the same cypher). The API surface (Doc
2 §6) has no temporal parameter for arbitrary Cypher, so those two paths
cannot carry the instant without the UI authoring Cypher fragments (which
§8.13 forbids); their re-run keeps the panes reproducible by the graph.
`as_of` = brush right edge means the panes show the state at the end of the
brushed period — the only single-instant semantics expressible through
`BuilderHop.temporal_qualifier` and the neighbors endpoint's `as_of`.
Rejected alternative: client-side interval filtering (explicitly forbidden
by §8.13); appending `WHERE` clauses in the UI (a Cypher fragment, also
forbidden).

## 2026-08-02 — D-10 (R2) — Originating sentence availability is bounded by the API

AC-28 requires the provenance panel to show the originating sentence for
news-extracted assertions. The API (Doc 2 §6) exposes no document-text
endpoint, and — as WP-32's search test documents — no production path
stamps `title`/`body` on `:Document` nodes today, so `get_entity()` returns
404 for an evidence document. The panel therefore displays the full `EdgeRef`
provenance plus the evidence coordinates and fetches the sentence via
`get_entity(evidence_document_id)` when the document node exists (the
sanctioned read path, and the mechanism that works unchanged once the
pipeline materializes document entities). When the document is absent the
panel states so explicitly — nothing is fabricated. This bounds AC-28's
mechanical testability for WP-39 to the API's current surface; recorded as a
seam gap rather than resolved by an out-of-scope API change.

## 2026-08-02 — D-09 (R1) — UI reads `LIMES_API_BASE_URL` from the environment, never `.env`

The UI is the one process that must hold no credentials (Doc 1 §7.4); it
never loads `Settings` and never parses `.env` (which carries the OpenRouter
key and the Neo4j password). It reads the single `LIMES_API_BASE_URL`
variable directly, defaulting to `http://127.0.0.1:8000` for a bare local
run; the compose `ui` service receives the value from the environment
(WP-37).

## 2026-08-02 — D-08 (R1) — UI callbacks are plain functions with a thin registration layer

Each `callbacks/*.py` module defines its logic as pure functions (inputs in,
outputs out) and a small `register(app)` that wires them into Dash. This
makes AC-27/28/29 mechanically testable without a browser (the functions
are called directly with recorded-fake API clients), keeps the Dash layer
to a thin shell, and keeps `api_client.py` the only module performing HTTP.

## 2026-08-02 — Approval — phase-7-v1.0.0 (WP-32…WP-35)

The human approved phase-7-v1.0.0 (query API foundation, NL-to-Cypher
service, coverage report and empty-result diagnosis, query routers with
the enumerated write surface) on 2026-08-02 and instructed merge, commit,
and push. Delivered as branch `wp-32-35-query-api` (commits `ef749e4`
… `a115610`), merged to `main` and pushed; the topic branch is pushed as
well. This approval names the presented version and cannot be reused for
any other version of the phase.

## 2026-08-02 — Phase 7 invariants (WP-32…WP-35), derived at phase start

Derived from the roadmap's WP-32…WP-35 entries and Doc 2 §6–§8.12, per the
global contract §6. Guarded (automatically tested) and triggered
(review-trigger) invariants, logged when derived:

- **G1 (guarded)** — The API's write surface is exactly the three
  enumerated writes of §7.3 and nothing else in `src/limes/api/` →
  `test_api_write_surface.py::test_ac18_grep_finds_only_the_sanctioned_writes`
  and `test_ac18_write_attempt_corpus_is_rejected` (obfuscation corpus).
- **G2 (guarded)** — Every §8.10 validation code is produced by a crafted
  query and blocks execution →
  `test_nlq_validate.py::test_ac20_every_validation_code_is_produced_and_blocks`.
- **G3 (guarded)** — Every plan-gate rejection is produced by a crafted
  query and blocks execution →
  `test_nlq_plan.py::test_ac21_*`.
- **G4 (guarded)** — An empty result produces a diagnosis naming the
  correct failing clause → `test_diagnosis.py::test_ac22_*`.
- **G5 (guarded)** — Every executed result carries a coverage report with
  correct graph-wide counts and refresh stamps →
  `test_coverage.py::test_ac23_coverage_counts_match_the_graph`.
- **G6 (guarded)** — The builder cannot construct a query violating domain
  or range; rejections are precise → `test_api_builder.py::test_ac24_*`
  and `test_api_query_builder.py::test_ac24_invalid_spec_rejected_precisely`.
- **G7 (guarded)** — Generated Cypher is returned and editable in every NL
  outcome, including failures, with exactly one regeneration →
  `test_nlq_service.py::test_answer_*`, `test_nlq_generate.py`.
- **G8 (guarded)** — Every executed query is persisted as `:SavedQuery`
  with question, Cypher, ontology version, and result count (AC-30) →
  `test_api_query_nl.py::test_query_nl_runs_trace_3_end_to_end`.
- **G9 (guarded)** — Every API response carries `X-LIMES-Ontology-Version`
  and errors use the §6 envelope with the §11 HTTP mapping →
  `test_api_health.py`, `test_api_query_cypher.py::test_query_cypher_write_attempt_is_rejected_400`.
- **T1 (triggered)** — No example questions in `nl2cypher_v1.0.0.md`
  (NG-08): review-trigger on the prompt file;
  `test_nlq_generate.py::test_ng08_prompt_contains_no_example_questions`
  guards the property mechanically.
- **T2 (triggered)** — Validator stays parse-level (no substring search):
  review-trigger on `nlq/validate.py`;
  `test_nlq_validate.py::test_write_clause_hidden_in_string_or_comment_cannot_pass`
  guards the mechanism.

## 2026-08-02 — D-54 (R1) — The three enumerated writes, verified by grep

The AC-18 grep over `src/limes/api/` finds write tokens in exactly one
module — `routers/saved_queries.py` (the `:SavedQuery` create and delete
statements plus their call sites). The third enumerated write
(`:CostLedgerEntry` on the NL path) physically lives in `cost/ledger.py`
via the OpenRouter client, outside `src/limes/api/` by the §5.2/§7.3
ownership table — the grep's contract is the shape of the code in the API
package, and that shape holds. The dedicated guard test
`test_api_write_surface.py` freezes this property, including the
obfuscation corpus (case variants, comments, `CALL {}` subqueries,
`apoc.*` procedures, comment-embedded write text that must *pass*
validation because it is data, not syntax).

## 2026-08-02 — D-53 (R1) — API test isolation via sanctioned module wipes

The integration suite shares one session container; the API tests that run
a real gisco ingest (sources, ingest status, coverage) leave a `:Country`
with `iso2 = 'DE'` behind, which breaks
`test_loader.py::test_load_materializes_standalone_entities`'s
fresh-graph premise, and the absolute-count assertions of the query tests
assumed no prior SUBSIDIARY_OF edges. Fix: `wipe_graph` in
`tests/fixtures/graph_data.py` (the `DETACH DELETE` fixture-teardown
exception the CLI tests already use), wired as a module-scoped autouse
fixture — reset at module start for the query/saved-query/write-surface
modules, reset at module end for the gisco-ingesting modules. The suite is
order-independent again (149 integration tests, any subset order).

## 2026-08-02 — D-52 (R1) — `BuilderHop` gains `temporal_instant`

Doc 2 §6's hop shape `{relation, direction, target_type, filters,
temporal_qualifier}` cannot express the instant an `as_of`/`as_believed`
qualifier needs. `BuilderHop` carries a companion `temporal_instant:
datetime | None`; a qualifier without an instant is rejected precisely
("temporal_qualifier 'as_of' needs temporal_instant"), so the invalid
combination stays unrepresentable (AC-24).

## 2026-08-02 — D-51 (R1) — Saved-query delete: existence read, then `write_batch`

A `DELETE` cannot run in `GraphDriver.read`'s read-access-mode session,
and `WriteResult` carries no deletion counter. `DELETE /saved-queries/{id}`
therefore checks existence via a read (404 on absence) and deletes through
`write_batch` — two round trips, no count recovery needed. The same split
applies to the duplicate check before the `:SavedQuery` create.

## 2026-08-02 — D-50 (R1) — Plan gate reads variable-length bounds from the query text

An EXPLAIN plan cannot express a variable-length expansion's hop bound —
the operator name carries no depth — so `UNBOUNDED_EXPANSION` and
`EXPANSION_TOO_DEEP` are decided by the `nlq/validate.py` tokenizer over
the query text (`[*]`, `[*N..]`, `[*N]`, `[*1..M]` forms), while
`CARTESIAN_PRODUCT`, `OPERATOR_ROWS_EXCEEDED`, and `TOTAL_ROWS_EXCEEDED`
come from the plan. `QueryPlanRejected` carries `code` and `plan_summary`
as documented attributes on the §11 class rather than new subclasses — the
specified error hierarchy stays untouched (two `type: ignore[attr-defined]`
mark the attachment site).

## 2026-08-02 — D-49 (R1) — The Cypher tokenizer lives in `nlq/validate.py`

Doc 2 §2's module list is authoritative and has no `tokens.py`; parse-level
inspection is §7.2's validator concern, so the tokenizer lives there and is
consumed by the plan gate (`nlq/plan.py`), the diagnosis service
(`coverage/diagnose.py`), and the coverage router's relation extraction —
one parser, one set of clause boundaries, no second tokenizer drifting.

## 2026-08-02 — D-48 (R1) — `/builder/schema` delivered whole in the phase

The roadmap splits the endpoint across WPs (route registered in WP-32,
projection logic in WP-35), but a registered route needs its projection to
serve. Delivered as one piece: the route in `routers/ontology.py` and
`project_for_builder` in `src/limes/api/builder.py` (the roadmap's
sanctioned location for the projection). The spec-route (WP-32) is
satisfied in the phase's final state.

## 2026-08-02 — D-47 (R2) — AC-40 guard test: the API startup handler's driver exemption

Doc 2 §8.15 exempts "the API startup handler" from the construction ban,
§15.2's FastAPI row names `api/main.py` as the driver's constructor
("constructs settings, ontology, driver"), and the roadmap's WP-32 task 1
instructs the startup handler to construct the GraphDriver. The existing
AC-40 grep test predates the API and would flag that construction. The
guard test now carries the exemption for exactly the driver pattern in
exactly `api/main.py`, with the §15.2 citation in the test — a repair to
match the spec's own seam register, not a weakening: every other
constructor in `src/limes/api/` still fails the test. Rejected
alternative: hiding the construction behind an indirection to keep the
old grep green — evasion, and it would obscure the sanctioned seam.

---

## 2026-08-02 — Approval — phase-6-v1.0.0 (WP-28…WP-31 + the WP-28 conflict repair)

The human approved phase-6-v1.0.0 (CLI core with the advisory lock —
`ingest`, `ingest-all`, `backfill`, `reextract`, `backup`; model selection
provisional and measured stages; the evaluation harness with gold set,
calibration set, and reference questions; the ontology migration CLI; and
the loader lookup-row batching repair D-46 that un-halted the phase,
verified live against the production §13.4 configuration) on 2026-08-02 and
instructed merge, commit, and push. Delivered as branch
`wp-28-31-cli-and-evaluation`, merged to `main` as `753c955` and pushed;
the topic branch is pushed as well. This approval names the presented
version and cannot be reused for any other version of the phase.

---

## 2026-08-02 — Phase 6 resumes: loader lookup-row batching repair (human decision, branch a)

The human chose branch (a) of the halted-phase decision, in the human's own
words: **"(a) repair the loader's lookup-row batching. Proceed."** The phase
resumes as a repair unit; the phase-6 invariants (G1–G11, T1–T4, logged
above) are unaffected by the repair and hold as derived.

**D-46 (R2)** — Lookup rows are chunked at `BATCH_SIZE` like assertions.
`load` partitions `lookup_rows` into chunks of 500; chunk *i* rides with
assertion batch *i*, and overflow chunks each run in their own transaction.
Every transaction therefore carries at most 500 assertions and at most 500
lookup rows: §8.3's "at most 500 assertions per transaction" keeps its
literal shape, the WP-07 "ride with the first batch" decision holds for
payloads that fit, and the live GISCO payload (~300k rows) spans ~600
bounded transactions instead of one 120s-timeout transaction. Rejected
alternatives: (a) a single `UNWIND`-based statement per chunk in
`queries.py` — a real round-trip win (~300k `tx.run` calls become ~600) but
a rewrite of the WP-07 query shape and failure granularity, not required
for correctness, and beyond the chosen repair branch; (b) dedicated
lookup-only transactions for every chunk — a larger departure from the
first-batch-riding shape with no additional guarantee. Known characteristic,
accepted: per-statement `tx.run` remains the established pattern, so the
full 300k-row load is a multi-minute, bounded operation — fine for a
one-shot reference bootstrap.

**New phase-6 invariant (guarded):** **G12** — lookup rows are batched: a
load of more than `BATCH_SIZE` lookup rows spans multiple transactions, none
carrying more than `BATCH_SIZE` postal statements, and every row is
materialized → guard
`test_loader.py::test_lookup_rows_are_batched_across_transactions`
(instrumentation through the documented `GraphDriver._driver` seam counts
postal statements per committed transaction).

Baseline deviation, not introduced by the repair (D-27 precedent — flagged,
not fixed): `tests/integration/test_loader.py` fails `ruff format --check`
and carries 14 pre-existing E501 lines on pristine main.

The three entries below were decided and implemented before the halt but
never logged — they exist only as code references (D-43 in `cli/ingest.py`
and `cli/main.py`, D-44 in `cli/backfill.py`, D-45 in `cli/reextract.py`).
Logging them here at resume closes the gap; an unlogged decision is an
unmade decision, and these were made.

## 2026-08-02 — D-43 (R1) — `build_default_registry` is the CLI's only sanctioned registry inspection

A command must know a source's `kind` (structured vs unstructured) before
it can choose `needs_inference`, and `enrichment-only` before `ingest-all`
can skip it — but AC-40 binds the registry's constructor to the composition
root, and `build_run_context` is not asked the kind question. The CLI
therefore inspects through `build_default_registry()`, the one sanctioned
population function, purely for inspection: the registry used for a run is
always the context's own (D-36). `ingest-all` skips `wikidata`, the
enrichment-only source named by the roadmap, whose `fetch` would otherwise
surface as a `NotImplementedError` traceback rather than a `LimesError`; the
skip list in `cli/ingest.py` is the named refresh point.

## 2026-08-02 — D-44 (R1) — `backfill --days` becomes an explicit `since = now − days`

The run spec carries an explicit window: `--days` is resolved once in the
CLI to `since = now − days`, because the §8.6.2 explicit-since rule makes
the window deterministic — a non-incremental source asked for a window gets
exactly that window, and nothing re-derives the window from the clock at
resolution time.

## 2026-08-02 — D-45 (R1) — `reextract` defaults to every unstructured source

Without `--source`, re-extraction runs every unstructured source in
sequence: document-producing sources are the only ones with anything to
re-extract (structured loads are re-run by `ingest` itself), and a
structured source would silently re-load rather than re-extract — a
non-operation presented as a success.

---

## 2026-08-02 — Phase 6 [CONFLICT] — live `limes ingest --source gisco_nuts` fails; phase halted per human decision

The roadmap's WP-28 verification command `limes ingest --source gisco_nuts`
(roadmap §WP-28 Verification) was run against a live Neo4j container with
the production §13.4 memory configuration (heap 2G, page cache 2G,
transaction cap 512m, transaction timeout 120s). It failed: the delivered
WP-07 loader materializes every lookup row of a record in the *first*
batch's single transaction — `loader.py:112-118` passes the whole
`lookup` list to `_load_batch` for `index == 0`, and `loader.py:312-324`
issues one `POSTAL_CODE_MERGE` statement per row in that one transaction.
The live GISCO postcode correspondence payload (12 MB gzip, ~300k rows,
archived during the run) then times out the single transaction
(`TransactionTimedOutClientConfiguration` after 120s; with the 512m heap
test container it failed earlier as `MemoryPoolOutOfMemoryError` at the
358 MiB default cap). The fixture-based suites (436 tests, including the
fixture-fetched CLI Trace 1) are green because the fixture postcode file
carries 3 rows. This is not a Docs 1–2 gap: §5.6's batching rule covers
assertions and the loader complies; the lookup-row batching was a WP-07
implementation decision ("ride with the first batch", loader.py:84-85)
that does not scale to the live file. The WP-28 acceptance criterion
"Trace 1 runs via `limes ingest --source gisco_nuts`" cannot pass as
delivered.

Human decision, 2026-08-02, in the human's own words: **"Record
[CONFLICT], halt phase."** The phase is therefore halted, not delivered:
no phase version is presented and no approval is requested. The phase-6
work products (CLI core, advisory lock, model selection, evaluation
harness, gold-set and calibration artifacts, reference questions,
migration CLI, and their tests) remain on branch
`wp-28-31-cli-and-evaluation`, unmerged; their invariants were derived and
logged above but are not asserted as a delivery. The phase resumes only on
a human decision about the loader repair (the halted work is unaffected by
any of the three presented branches: repair the loader's lookup-row
batching, narrow the criterion to fixture-level Trace 1, or re-scope).

---

## 2026-08-02 — Phase 6 invariants (WP-28…WP-31), derived and tagged

Guarded (automated check, named guard installed and green):
- **G1** — Trace 1 runs through the CLI: `ingest --source gisco_nuts`
  (CliRunner, adapter fetch stubbed with the recorded fixtures — the same
  seam Trace 1's own test uses) builds the context, acquires and releases
  the advisory lock, loads the run, and closes the `:IngestionRun` with
  honest counts → guard `test_cli_ingest.py::test_cli_ingest_gisco_nuts_end_to_end`.
- **G2** — `backfill` and `reextract` refuse without `--budget` (usage
  error, non-zero exit, no context built) → guards
  `test_cli_backfill.py::test_backfill_refuses_without_budget`,
  `test_cli_reextract.py::test_reextract_refuses_without_budget`
  (subprocess — the refusal must hold across a real process boundary).
- **G3** — Advisory lock: a second acquire on the same source fails while
  held; a stale lock is reclaimed with a warning; release clears; the
  refusal is honored across a real process boundary (subprocess) →
  guards `test_cli_lock.py` (four tests).
- **G4** — `limes backup` stops the database, dumps offline to the archive
  with a timestamped filename, restarts, and verifies reachability — a
  real `docker compose` lifecycle against a disposable container →
  guard `test_cli_backup.py::test_backup_stops_dumps_and_restarts`.
- **G5** — AC-36: `select-models --provisional` writes a complete pin set
  (four roles + `LIMES_MODEL_PIN_STAGE` + date) into `.env` after operator
  confirmation, without reading the gold set → guard
  `test_select_models.py::test_ac36_provisional_writes_pin_set_without_gold_set`.
- **G6** — AC-37: `select-models --measured` refuses without a gold set at
  version ≥ 1.0.0; on re-pinning it reports affected source/document
  counts and a cost estimate and performs no re-extraction → guards
  `test_select_models.py::test_ac37_measured_refuses_without_gold_set`,
  `test_ac37_repin_reports_counts_without_reextracting`.
- **G7** — AC-31: `evaluate` computes per-relation precision/recall/F1,
  writes `baseline.json` (the sole regression-gate source of truth),
  appends to `gold_set/CHANGELOG.md`, writes `:GoldSetItem` nodes, and
  exits non-zero when a per-relation F1 regresses beyond 0.05 absolute →
  guards `test_evaluate.py::test_ac31_metrics_and_regression_gate`,
  `test_gold_set_items_written_to_graph`.
- **G8** — AC-25: five reference questions load with hand-written Cypher;
  each passes the structural reference check (declared labels/relations
  exist in the ontology, no write clauses, limit present or injectable) →
  guard `test_evaluate.py::test_ac25_reference_questions_validate`.
- **G9** — Gold-set artifacts: `gold_set.jsonl` validates against its
  schema with items labeled from passage text; the calibration set counts
  exactly 40 true / 40 hard-negative / 20 cross-language and 50 de / 50 en
  → guard `test_evaluate.py::test_gold_set_schema_and_calibration_counts`.
- **G10** — WP-31: `migrate --ontology-version 1.0.0` is a no-op on a
  fresh database and reports nothing to migrate; the migration pattern
  (`TO_VERSION` + `upgrade(driver) -> None`) is importable and runnable →
  guards `test_migrate.py` (integration).
- **G11** — `ingest-all` skips enrichment-only sources (wikidata) without
  ever invoking their `fetch` → guard
  `test_cli_ingest.py::test_ingest_all_skips_enrichment_only_sources`.

Triggered (review-flag paths, no automated guard):
- **T1** — `cli/main.py` is the sole writer of `:AdvisoryLock` (§5.8,
  §15.2): any diff adding another writer of the node type, or a graph
  write in the CLI beyond the lock, is flagged for review before commit.
- **T2** — `cli/evaluate.py` is the sole writer of `:GoldSetItem` (§5.8):
  any diff adding another writer, or any graph write in `src/limes/api/`
  beyond §7.3's three enumerated writes, is flagged.
- **T3** — `reference_questions/questions.yaml` is an expressibility
  fixture, not a template library (NG-08): any diff that surfaces the
  questions in the UI, the NLQ prompt, or any suggestion list is flagged.
- **T4** — `select-models` writes pins only into the local `.env` file:
  any diff that commits pins, writes another config file, or performs
  re-extraction or an index rebuild automatically is flagged.

---

## 2026-08-01 — Approval — phase-5-v1.0.0 (WP-26, WP-27)

The human approved phase-5-v1.0.0 (composition root: `build_run_context`/
`build_nlq_context`/`embedder_for` with `needs_inference` gating; pipeline
run orchestration: `RunSpec`/`execute_run`, window resolution,
`:Source`/`:IngestionRun` lifecycle, registry-stamped provenance, clean
budget termination) on 2026-08-01 and instructed merge, commit, and push.
Delivered as branch `wp-26-27-composition-and-pipeline`, merged to `main`
as `b927986` and pushed; the topic branch is pushed as well. This approval
names the presented version and cannot be reused for any other version of
the phase.

---

## 2026-08-01 — D-42 (R2) — First-run deterministic links to backbone-absent entities no-op by design

The trace test's original expectation (SAME_AS on the first ingest of an
unknown LEI) failed against spec-consistent behavior: `link.link` MATCHes
the `:Entity` node, which does not exist until the loader runs — and the
loader runs after resolution per §15.3's trace order. The resolver cannot
create the node (AC-17) or the relationship that would create it (the
mint-band rationale, §8.8.5, applies to every band whose entity is
absent). Every stated requirement is satisfied literally: a `:Mention`
exists for every endpoint; `link` creates SAME_AS when the entity exists;
minted mentions never link. Not a [CONFLICT] — the corner is production-
marginal because the structured backbone (GLEIF golden copy) pre-loads the
LEI space before any extraction, and a version-change reextract re-runs
resolution against the now-materialized nodes, creating the links. The
phase's tests assert this: first ingest → zero SAME_AS (documented), and
the reextract test proves the links materialize on the second pass.

## 2026-08-01 — D-41 (R1) — Extractor seam cast in `composition.py`; the §8.7.1 protocol keeps its literal shape

WP-22's `OpenRouterExtractor.model_id` is a read-only property (the pinned
model is immutable by design), but the §8.7.1 protocol block declares
`model_id: str`, which mypy treats as settable — the first real consumer
(the composition root) hit the mismatch. Resolution: `cast(Extractor, ...)`
at the seam site with a why-comment, matching the repo's existing pattern
(`# type: ignore[arg-type]` in `resolve.py`). Rejected alternatives:
changing the protocol to a `@property` member (deviates from the spec's
literal §8.7.1 block and would break attribute-style implementers);
changing the extractor to a settable attribute (removes WP-22's deliberate
immutability and touches a WP-22 file).

## 2026-08-01 — D-40 (R1) — `resolve_window` gains `settings` and `now` beyond the §8.6.2 signature

The §8.6.2 signature `resolve_window(spec, adapter, source_node)` cannot
compute `now − LIMES_BACKFILL_DAYS_UNSTRUCTURED`: the days value lives in
Settings, which the signature does not carry (same class of gap as D-32).
`settings` is added as a keyword parameter, and `now` as an injectable
clock for deterministic tests; the first two parameters and the return
shape are unchanged, and `execute_run` is the only caller.

## 2026-08-01 — Phase 5 invariants (WP-26, WP-27), derived and tagged

Guarded (automated check, named guard installed and green):
- **G1** — AC-40: `composition.py` is the only constructor of driver,
  registry, archive, governor, client, extractor, gate → guard
  `test_composition_root.py::test_ac40_composition_is_the_only_constructor`
  (grep over `src/limes/` for the constructor calls, tests excluded) plus
  the roadmap's verification greps run at phase end.
- **G2** — AC-41: `build_run_context(needs_inference=False)` constructs no
  extractor, loads no spaCy model, and leaves the inference slots None;
  `needs_inference=True` fills them all → guard
  `test_build_run_context_inference_gating`.
- **G3** — `provision()` runs on every `build_run_context` invocation (and
  with it the ontology downgrade guard) → guard
  `test_provision_called_on_every_build`.
- **G4** — `RunContext`/`GateContext`/`NlqContext` are frozen dataclasses;
  mutation after construction raises → guard `test_contexts_are_frozen`.
- **G5** — AC-42: an explicit `since` always wins; an incremental source
  anchors at `Source.last_success_at`; a never-run incremental source starts
  at `now − LIMES_BACKFILL_DAYS_UNSTRUCTURED`; a non-incremental source is a
  full load `(None, None)` → guard `tests/unit/test_pipeline_window.py`
  (four routing tests, clock injected).
- **G6** — AC-05: re-running an identical ingest writes zero new nodes and
  zero new relationships and reports the skip count → guard
  `test_pipeline_run_structured.py::test_ac05_reingest_writes_nothing_new`.
- **G7** — Trace 1 end-to-end: a structured run (GISCO adapter, stubbed
  fetch, fixture payload) archives, normalizes, stamps provenance from the
  registry, validates, loads, and closes the run record with honest counts
  → guard `test_trace1_structured_run_end_to_end`.
- **G8** — Trace 2 end-to-end: a document run (feeds adapter, stubbed
  fetch, fake gate models, respx-mocked transport, deterministic-key
  mentions) passes the gate, extracts, caches, resolves, stamps
  pipeline-known provenance (never the resolver's intermediates), loads
  with the wired embedder, and reports per-band counts → guard
  `test_trace2_document_run_end_to_end` and
  `test_assertion_provenance_stamped_by_pipeline`.
- **G9** — Gated-out documents are counted (`documents_gated_out`) with
  their reason; nothing is dropped silently → guard
  `test_documents_gated_out_are_counted`.
- **G10** — `BudgetExhausted` closes the run record with `finished_at` set,
  does not update `:Source.last_success_at`, and re-raises; the remaining
  documents are logged as queued → guard
  `test_budget_exhausted_closes_run_cleanly`.

Triggered (review-flag paths, no automated guard):
- **T1** — `pipeline/run.py` is the sole writer of `:Source` and
  `:IngestionRun` (§15.2): any diff touching `run.py` that writes another
  node type, or any new write to `:Source`/`:IngestionRun` outside it, is
  flagged for review before commit.
- **T2** — The run's cost figure is a governor `remaining()` delta (D-38),
  not a new ledger query: any diff that adds a spend read or a second
  budget-check path to the pipeline is flagged (the governor is the only
  refusal point, §10).

## 2026-08-01 — D-39 (R2) — Reextract retracts only superseded assertions, after the new load's id set is known

`retract()` needs explicit `assertion_id`s, and the loader skips any
existing `assertion_id` (AC-05) — so retract-then-load would kill an
unchanged fact (same digest, now retracted, skipped forever). Reextract
therefore: extract + resolve the document first, then read the source's
non-retracted assertions for that document
(`evidence_document_id = content_hash, source_id = run's source`), retract
exactly those whose `assertion_id` is not in the new set, then load. A
failed extraction never retracts anything — the prior record survives as
the only record. The cache triple (prompt/schema/model) is in the key, so
reextract with an unchanged version hits the gate's cache check and is a
no-op — deliberate re-extraction always carries a version. Rejected
alternative: retract-all-before-load (destroys unchanged facts).

## 2026-08-01 — D-38 (R2) — Run cost is a governor `remaining()` delta; `cache.put` after load

The `:IngestionRun` record's `cost_eur` is the delta of
`governor.remaining()` across the run, floored at zero: exact for the
envelope scope (in-process running total), and the ledger-anchored period
delta for the monthly scope. Rejected alternatives: extending
`cost/ledger.py` with a per-run read (outside WP-27's file scope, §15.2
binds ledger writes but the module is WP-06's), or stamping `run_id` in
the client (WP-22 change). Also: `cache.put` runs **after** the document's
load succeeds, not before resolution — the roadmap's literal order lets a
mid-document resolve/load failure leave a cache entry that gates the
document out on retry, losing its assertions permanently; re-paying
extraction is the safe failure direction.

## 2026-08-01 — D-37 (R1) — Loader embedder wiring lives in `composition.py` as `embedder_for`

D-26 named the wiring point as WP-26 and `RunContext` has no embedder slot
(§8.15 shape, AC-44). `composition.embedder_for(settings, client)` returns
the callable `load(..., embedder=)` receives: `client.embed(labels,
settings.embedding_model)`, dimension-checked and L2-normalized through
`normalize_embedding` (the declared-dimension check the loader cannot
perform). `execute_run` passes `embedder_for(...)` on every load when the
client exists; structured-only runs pass None and write null embeddings,
which the §13.3 backfill fills. This is a wiring function, not a fourth
infrastructure constructor — AC-40's greps are unaffected.

## 2026-08-01 — D-36 (R1) — `NlqContext` defined in `composition.py`; the two build functions there are the construction surface

Following D-22/D-28, `RunContext` lives in `resolution/resolve.py` and
`GateContext` in `pipeline/gate.py`; `NlqContext` (no consumer module
exists yet — WP-32 creates `api/deps.py`) is defined in `composition.py`
next to `build_nlq_context`, the §8.15 home. `build_run_context` stamps
`source_id`/`source_trust` from the registry — the binding §15.2 authority,
idempotent over the adapters' own stamps — and the document path re-stamps
the D-29 intermediates and recomputes `assertion_id` with the real
`source_id` before load.

---

## 2026-08-01 — WP-25 [CONFLICT] resolved (human decision) — the `label_embedding` merge stamp

The halt on WP-25 was correct: the §5.3 vector index over `:Entity.label_embedding`
had no writer in §15.2 or in any WP task list (rg over docs and code finds only
the index definition), so `candidates()` would query an always-empty index and
every key-less mention would mint a fresh entity against the backbone. The
resolution is the human's, in the human's own words, 2026-08-01: this is not a
WP-25 code fix but a missing stamp in the §5.6 merge contract, resolved
upstream at one choke point. The merge stamp includes
`label_embedding = embed(label)` on ON CREATE, and re-stamps on ON MATCH only
when `label` changed (the stored label is immutable on merge, AC-09, so the
embedding is immutable in practice). §15.2 attributes the property to the
merge choke point through which every entity creation — structured loads and
resolver-approved mints alike — passes, not to a new eighth writer. The
resolver remains strictly read-only against the index; AC-17, §8.8.3, and
Doc 1 §4.6 stay intact. A one-shot backfill walks `(:Entity) WHERE
label_embedding IS NULL`, computes, stamps — a migration, not part of WP-25.
Embeddings must be exactly `LIMES_EMBEDDING_DIMENSIONS` long and L2-normalized
for the §5.3 cosine metric, or `queryNodes` similarity is invalid and
candidates() silently under-recalls. Implemented as Technical Specification
v2.1.0 (§5.2, §5.3, §5.6, §8.3, §13.3, §15.2) and Implementation Roadmap
v2.1.0 (new upstream WP-25a). Resume gate: WP-25 resumes with the stamp
registered and the backfill path in place; integration tests populate the
index through the production `load` path with an injected embedder.

## 2026-08-01 — D-26 (R1) — Loader embedder seam is a plain callable; the loader normalizes defensively

`load(..., embedder: Callable[[list[str]], list[list[float]]] | None = None)`
returns one vector per label, in order, each exactly
`LIMES_EMBEDDING_DIMENSIONS` long; the dimension check lives at the wiring
point (WP-26), because the loader never sees Settings. The loader re-normalizes
(L2) whatever it stamps — `normalize_embedding` in the new `graph/embeddings.py`
— because the merge choke point must not stamp an unnormalized vector into a
cosine index. `embedder=None` writes null embeddings with a logged line; the
backfill `stamp_missing_embeddings` is the only path that fills a null.
Rejected alternatives: a named `Embedder` type (AC-44 pins every §8 signature
type to §5.5/§8.15); a client inside the loader (the loader stays
inference-free); re-embedding existing endpoints (paid, and the embedding is
immutable on re-merge anyway — one read per batch establishes which endpoints
have no node yet).

## 2026-08-01 — D-27 (R1) — Spec amendment mechanics: v2.1.0 renames both amended documents

Technical Specification and Implementation Roadmap move to v2.1.0 with their
filenames (the repo convention embeds the version in the name); references in
README, AGENTS.md, and the Design Document companion line are updated. The
Design Document stays v2.0.0 (its companion line and revision history record
the reference update; no substantive change). `tools/check_docs.py` gains
`Callable` in its external-type set, required by the amended §8.3 signature.
Pre-existing baseline deviation discovered during verification: `ruff format
--check` fails on `src/limes/graph/lookups.py:28` on the pristine main —
untouched here (out of scope), flagged for the human.

---

## 2026-08-01 — Approval — phase-4-v1.0.0 (WP-25a, WP-25)

The human approved phase-4-v1.0.0 (entity resolution: the `label_embedding`
merge stamp and backfill, and the resolution pipeline — keys, blocking,
adjudication, linking, minting) on 2026-08-01 and instructed merge, commit,
and push. Delivered as branches `wp-25a-embedding-merge-stamp` and
`wp-25-entity-resolution`, merged to `main` as `6c3962a` and `d1fc305` and
pushed; the topic branches are pushed as well. This approval names the
presented version and cannot be reused for any other version of the phase.
The phase's seam conflict was resolved before delivery per the human's
decision recorded above (the §5.6 merge stamp); no conflict markers remain.

---

## 2026-08-01 — Phase 4 invariants (WP-25a, WP-25), derived and tagged

Guarded (automated check, named guard installed and green):
- **G1** — Every entity node created by `load` with an embedder carries a
  normalized `label_embedding`; a re-merge never changes it (the §5.6 stamp,
  AC-09 semantics) → `test_embedding_stamp.py::test_load_stamps_label_embedding_on_create`,
  `test_remerge_never_overwrites_embedding`.
- **G2** — `stamp_missing_embeddings` fills exactly the nulls and is
  idempotent; `embedder=None` writes nulls with a logged line →
  `test_backfill_stamps_exactly_the_nulls`, `test_load_without_embedder_writes_null`.
- **G3** — Deterministic keys short-circuit with no embedding, no vector
  query, and no paid call (AC-16) →
  `test_resolution.py::test_ac16_deterministic_keys_short_circuit`.
- **G4** — The four §8.8.3 bands route correctly, including the
  `≥ 0.93`-with-margin-`< 0.05` trigger; the mint branch writes no entity
  node (AC-17) → `test_ac17_routes_across_all_four_bands`,
  `test_ac17_margin_below_threshold_adjudicates`.
- **G5** — `unlink` retracts `SAME_AS` without deleting any node; prior
  assertions remain attributed (AC-19) →
  `test_ac19_unlink_retracts_without_deleting`.
- **G6** — `resolve_assertions` converts `ExtractedAssertion` to
  `Assertion`, creates one `:Mention` per endpoint, and returns stats
  matching the four bands (AC-43) →
  `test_ac43_conversion_mentions_and_stats`.
- **G7** — Candidate scores are cosines: the engine's `(1 + cosine) / 2`
  is converted in `candidates()` (D-34) →
  `test_resolution_blocking.py::test_candidates_parses_rows_and_filters_type`
  and the band tests' score assertions.

Triggered (review-flag paths, no automated guard):
- **T1** — The resolver never writes an entity node and `resolution/` writes
  nothing but `:Mention`/`SAME_AS`: any diff touching
  `resolution/link.py` or `resolution/resolve.py` that introduces a graph
  write outside that surface is flagged for review before commit.
- **T2** — The deterministic-key table (`resolution/keys.py`) and the
  extraction/adjudication prompts are versioned artifacts: any diff touching
  them that changes a pattern or prompt without the documented refresh
  discipline is flagged.

---

## 2026-08-01 — D-28 (R2) — `RunContext` defined in `resolution/resolve.py`

`resolve_assertions` consumes `RunContext` (the §8.15 shape), which is
WP-26's to construct; following the D-22 precedent for `GateContext`, the
frozen dataclass lives in the module that consumes it, and the composition
root imports it from there. Rejected: defining it in `composition.py` now
(that file is WP-26's scope).

## 2026-08-01 — D-29 (R2) — Provenance completion is `execute_run`'s contract, not the resolver's

Five provenance fields — `source_id`, `source_trust`, `extractor_model`,
`prompt_version`, `schema_version` — are only known to the pipeline, and
§15.2 binds their stamping to `execute_run`; the §8.8.4 signature gives the
resolver no way to receive them. The resolver stamps what its context
determines (ontology_version, confidence = the extraction confidence carried
through — the resolution confidence lives on the SAME_AS link per §8.8.3 —
evidence fields) and fills the five pipeline-known fields with
type-satisfying intermediates (empty string, 0.0, None). `execute_run`
re-stamps them before load — the intermediates never reach the graph — and
recomputes `assertion_id` with the real `source_id` (the D-10 digest needs
the source, and a source-less digest would collide across sources).
Rejected alternatives: extending `RunContext` with source fields (§8.15
deviation); empty-assertion refusal (the resolver is not the stamp point).

## 2026-08-01 — D-30 (R1) — The deterministic-key table is exact-value, not pattern-only

A pattern whose match does not equal the structured adapter's emitted key
value would resolve to a different `entity_id` and duplicate the backbone
node instead of hitting it. The table therefore matches only canonical
surface forms and rebuilds values from capture groups where the surface
differs (the BGBl citation's periodikum dot). Excluded despite plausible
patterns: `german_register_number` (court suffixes like "HRB 12345 B"),
`bundestag_id`/`osm_id`/`geonames_id` (bare digits match anything), `iso2`
(two letters appear everywhere), `nuts_code`, `source_event_id` — a missed
key costs one embed and possibly one mint; a wrong key costs a wrong
identity, the failure that matters.

## 2026-08-01 — D-31 (R2) — Wikidata enrichment sits between keys and embedding

The roadmap's contracts list `WikidataAdapter.enrich()` as consumed by
WP-25 but its routing omits the step; an unambiguous QID is a deterministic
identity, so enrichment runs after `keys.deterministic_key` and before any
embedding, gated on the type declaring `wikidata_qid` (a QID the loader
cannot stamp would mint a second node). Results are cached per (type,
surface) for the process — a backfill re-encounters the same surfaces, and
each hit saved is a network round trip not made; misses are cached too.
Network failure is a counted miss (`SourceFetchError` caught), never a
guess. Rejected: dropping enrichment from the path (WP-18's contract names
WP-25 as its consumer).

## 2026-08-01 — D-32 (R1) — Adjudication is pairwise against the top candidate

The v1.0.0 adjudication prompt is pairwise (Mention A vs Mention B), and
the WP-30 calibration set is pairwise-shaped (parent-vs-subsidiary pairs);
§8.8.3 budgets one adjudication call. `adjudicate` therefore presents the
mention against its top candidate, with the remaining candidates riding in
the prompt's context slot as evidence. The `model_id` parameter is passed
explicitly because the adjudication model lives in Settings, which the
roadmap's four-parameter signature cannot reach. Rejected: a list-form
prompt rewrite plus version bump (the prompt and the calibration set are
pairwise by design).

## 2026-08-01 — D-33 (R1) — Deterministic `mention_id`; minted mentions never link

`mention_id` is a digest over (document, type, normalized surface, offsets),
so re-extracting a document merges into the same `:Mention` node instead of
accumulating duplicates. The mint branch writes no `SAME_AS` at all: the
minted entity node does not exist until the loader materializes it, and
creating the relationship would create the node — the one write the
resolver is forbidden. Traceability of a minted mention is via the
assertion's `entity_id` and evidence span, never via a link.

## 2026-08-01 — D-34 (R1) — Candidate scores are converted from the engine's `(1 + cosine) / 2`

Measured against the Neo4j 2026.x cosine vector index: the returned score
is `(1 + cosine) / 2`, not the cosine (its cosine distance is the half-angle
form). `candidates()` converts back to cosine space — the §8.8.3 thresholds
are cosines, and an unconverted score would auto-link at a true cosine of
only 0.86 (observed: a 0.88-cosine mention scored 0.94 and auto-linked).
The conversion is linear, so ordering is unchanged. This finding belongs to
the merge-stamp amendment's correctness constraint (a wrong similarity
silently under- or over-recalls) and was caught by the AC-17 integration
test, not by reading docs.

## 2026-08-01 — D-35 (R1) — Stats count endpoint occurrences; margin zeroes a missing second

`ResolutionStats` counts endpoint occurrences — each extracted endpoint
resolves in exactly one band, matching the mention policy (one `:Mention`
per endpoint) — so a mention appearing in two assertions counts twice even
though its resolution is computed once. The §8.8.3 margin is top minus
second score, with second zeroed when only one candidate exists — a single
candidate at 0.95 auto-links (margin 0.95), which is the intended reading
of the table. Unstated `valid_from` on an extracted assertion defaults to
the resolution instant.

---

## 2026-08-01 — Approval — phase-3-v1.0.0 (WP-21…WP-24)

The human approved phase-3-v1.0.0 (unstructured pipeline: GDELT/feeds
adapters, extractor, cache, gate) on 2026-08-01 and instructed merge, commit,
and push. Delivered as branch `wp-21-24-unstructured-pipeline`, merged to
`main` as `36fb8a7` and pushed; the topic branch is pushed as well. This
approval names the presented version and cannot be reused for any other
version of the phase.

---

## 2026-08-01 — Phase 3 invariants (WP-21…WP-24), derived and tagged

Guarded (automated check, named guard installed and green):
- **G1** — A cache hit on the current version triple issues no paid call
  (AC-12) → `test_extraction_cache.py::test_full_rebuild_with_unchanged_triple_hits_every_document`,
  `test_extraction_evidence_span.py::test_cache_hit_short_circuits_before_any_paid_call`.
- **G2** — An assertion whose mapped evidence span contains neither surface
  is rejected as `EVIDENCE_SPAN_MISMATCH` and counted (AC-13) →
  `test_extraction_evidence_span.py`, `test_extractor.py::test_evidence_span_not_containing_surfaces_is_rejected`.
- **G3** — Documents below the mention threshold are rejected with the reason
  recorded, never silently dropped (AC-11) →
  `test_gate.py::test_below_mention_threshold_rejects_with_reason`.
- **G4** — §11 retry policy: 429/5xx/connect/timeout retried (max 4, backoff),
  other 4xx never → `test_openrouter_client.py::test_retry_on_429_then_success`,
  `test_no_retry_on_other_4xx`, `test_exhausted_retries_raise_extraction_error`.
- **G5** — `governor.check` before and `governor.commit` after every paid
  request; ledger entries only for attempts that returned token usage →
  `test_openrouter_client.py::test_complete_checks_before_and_commits_after`,
  `test_no_ledger_entry_when_usage_missing`.
- **G6** — The API key never reaches a log line →
  `test_openrouter_client.py::test_api_key_never_reaches_a_log_line`.
- **G7** — GDELT events carry `ACTOR_IN`/`TARGET_OF` with correct directional
  asymmetry and ontology-bounded actor typing →
  `test_gdelt_adapter.py::test_normalize_emits_event_with_actor_target_and_location_edges`.
- **G8** — `cache_key` deterministic across processes and sensitive to any
  triple component (AC-33 partial) →
  `test_extraction_cache.py::test_cache_key_is_deterministic_across_processes`.
- **G9** — Every passage satisfies `text[doc_start:doc_end] == passage.text`
  (the invariant the extractor's offset mapping anchors to) →
  `test_gate.py::test_passage_offsets_are_correct_relative_to_document`,
  `test_extractor.py::test_extract_batches_and_parses_assertions`.

Triggered (review-flag paths, no automated guard):
- **T1** — Untrusted document text stays inside the explicit `<PASSAGES>`
  delimiters, never in the instruction portion (§7.5): any diff touching
  `extraction/prompts/*.md` or `extraction/base.py::build_extraction_messages`
  is flagged for review before commit.
- **T2** — Adapters write nothing to the graph and the loader stays the sole
  writer of ontology-typed nodes (DD-19): any diff touching the new
  `sources/gdelt.py`/`sources/feeds.py` that introduces a graph write or a
  `MERGE` outside `graph/loader.py` is flagged.

---

## 2026-08-01 — D-25 (R1) — Feed language and GDELT vintage semantics

The feeds adapter uses the feed's declared language (`feeds.yaml`) when
present and the dependency-free detector only as the fallback — the curator
knows the feed. GDELT documents carry `published_at` = the file's latest
SQLDATE (the events' vintage), never the fetch instant; feeds fall back to
the fetch instant for undated entries with a counted log line.

## 2026-08-01 — D-24 (R1) — One cache entry per document, merged across calls

The cache key (§8.7.5) has no batch index, so per-call cache entries would
collide for a multi-call document. `extract()` merges every batch's
assertions and token counts into one `ExtractionResult`; WP-27 caches one
entry per document. Rejected alternative: extending the key with a batch
index (deviates from the fixed §8.7.5 key).

## 2026-08-01 — D-23 (R2) — Model pricing from the OpenRouter catalogue with a conservative fallback

`OpenRouterClient` prices calls from `GET /models` (lazy, cached per model);
catalogue prices are per-token USD. A model absent from the catalogue falls
back to 0.50 USD/M in and out — deliberately conservative, because the
governor's safe failure direction is refusal, and a wrong *cheap* price
silently breaches the budget. The fallback is always logged. Rejected
alternatives: fixed pricing (wrong for nearly every model); refusing calls
without catalogue pricing (over-strict — the catalogue is not load-bearing).

## 2026-08-01 — D-22 (R1) — `GateContext` defined in `pipeline/gate.py`

The roadmap says WP-24 may define a local type; the §8.15 shape (settings,
driver, nlp_de, nlp_en) is a frozen dataclass in `pipeline/gate.py`, the
module that consumes it. WP-26 imports and constructs it. Rejected:
defining it in `composition.py` now (that file is WP-26's scope).

## 2026-08-01 — D-21 (R2) — Evidence-span check is the AC-13 literal reading

An assertion is rejected as `EVIDENCE_SPAN_MISMATCH` when its mapped span
contains *neither* the subject nor the object surface (case-insensitive);
containing either passes. The extraction prompt states the same rule.
Rejected alternative: requiring both surfaces — stricter than the AC, and
the AC is the binding form.

## 2026-08-01 — D-20 (R2) — Per-feed trust override is a produced seam for WP-27

`NormalizedRecord` and `DocumentPayload` carry no trust field and §15.2 has
`execute_run` stamp `source_trust` from the registry, so a per-feed
`trust_rank` in `feeds.yaml` cannot flow through the record types. The
adapter exposes `FeedsAdapter.trust_rank_for(url)` as the seam WP-27 uses to
stamp per-document trust; the class-level 0.60 remains the registry value.
Rejected alternative: leaving the config override as dead weight.

## 2026-08-01 — D-19 (R2) — Feed entry payloads are deterministic JSON envelopes, not feed XML

The archive stores one record per feed *entry*; the payload is a
deterministic JSON envelope of the feedparser-extracted fields. If the
payload were the whole feed XML, every entry of a feed would share one
content hash and collapse into a single document. The XML is a transport
format, re-fetchable; the envelope is the system of record for re-derivation.

## 2026-08-01 — D-18 (R2) — GDELT actor typing bounded by the ontology; state actors counted, not typed

`ACTOR_IN`/`TARGET_OF` take an `Agent` domain and `Country` is a `Place`,
so the ontology has no Agent type for a sovereign state: bare-country GDELT
actor codes (USA, RUS, …) cannot be represented and their edges are skipped
— counted, never silent. GDELT's own actor type codes drive the typing:
GOV/MIL/COP/JUD → `PublicBody`, BUS → `Corporation` (the table is the
refresh point). Event identity follows D-10 (stampable
`source_event_id` key, full identity in the hash). Rejected alternative:
inventing an Agent type for states (ontology change = R3, migration).

---

## 2026-08-01 — D-17 (R2) — Source URLs are module constants; unverified endpoints are declared

The source layer's URLs were verified live where reachable (GISCO hierarchy
and postcode files, EUR-Lex Cellar SPARQL, gii-toc.xml and the per-law
`xml.zip` pattern, Overpass, wikidata.org API, data.europa.eu, DIP 401
without key). GLEIF golden copy, FSD consolidated list (token), TED search,
and the OffeneRegister data files could not be fully verified from this host;
their documented canonical URLs are module constants with docstrings naming
them as the single refresh point. A live fetch failure surfaces as
`SourceFetchError` (403/404 are not retried), never as silent misbehavior.

## 2026-08-01 — D-16 (R2) — Wikidata enrichment uses wbsearchentities, not SPARQL

The source table (§8.5.2) names SPARQL for Wikidata enrichment; the SPARQL
endpoint is unreachable in practice while the search/entities API answers.
`WikidataAdapter.enrich` uses `action=wbsearchentities` + `wbsgetentities`
(P31 class filter), both read-only. Rejected alternative: inventing a SPARQL
URL that does not answer.

## 2026-08-01 — D-15 (R1) — Structured assertions carry confidence 1.0

Structured adapters are deterministic data, not model output, so every
structured assertion's `Provenance.confidence` is 1.0; trust differentiation
happens through `source_trust` (Doc 1 §5.8), and the effective trust of
extracted assertions is the document-trust × extraction-confidence product —
there is no product for structured data.

## 2026-08-01 — D-14 (R1) — Roadmap key name overridden by the ontology: `bgb_citation`

WP-17's roadmap names the deterministic key
`("bundesgesetzblatt_citation", ...)`; the ontology artifact declares
`bgb_citation` in LegalAct's `identifying_keys`. Precedence (Roadmap →
Specification) makes the artifact authoritative: the adapter emits
`("bgb_citation", citation)` or the loader would refuse to stamp it.

## 2026-08-01 — D-13 (R1) — Location identity is an address hash; NUTS rides `LOCATED_IN`

Locations without a GeoNames ID get `coordinate_hash` identity over the
normalized address (GLEIF/TED) or rounded coordinates (OSM) — the hash is
identity, never location. Region membership is expressed as
`Location/Asset → LOCATED_IN → AdministrativeRegion` (the only Place→Region
edge the ontology has), resolved by postal lookup only: never geometry
(C-06, NG-06), misses counted.

## 2026-08-01 — D-12 (R2) — Postal lookup injected into `normalize`, not held by the adapter

GLEIF/TED/OSM accept `normalize(record, *, postal_lookup=None)`; the caller
(WP-27 `execute_run`, which holds the driver) passes the bound
`postal_code_to_nuts`. A None lookup or a miss leaves the region unassigned
and counted — the adapter never guesses and never holds a driver (AC-40:
composition root owns construction). The production wiring point is WP-27.

## 2026-08-01 — D-11 (R2) — Adapters stamp `ontology_version` from one constant

`Provenance.ontology_version` is required, and no seam stamps it after
normalize (§15.2 lists only `source_id`/`source_trust`/`content_hash`).
Every adapter therefore reads `ONTOLOGY_VERSION` from `sources/base.py` —
one bump point for the WP-31 migration instead of eleven.

## 2026-08-01 — D-10 (R2) — Shared deterministic `entity_id` and `assertion_id` schemes

Cross-source node identity works because the loader merges on `entity_id`:
endpoints with a deterministic key use `"<keyname>:<value>"` (`key_entity_id`),
endpoints without one use a typed SHA-256 namespace (`hash_entity_id`).
`assertion_id` is a digest over (source, relation, subject, object,
valid_from, valid_to), so re-runs over an identical window produce zero new
edges (AC-05) and changed facts produce new assertions alongside old ones.
Multi-key types (Topic, Sanction, Office, Event) stamp the single declared
key the loader can stamp and encode the full identity in `entity_id`.



The `CHANGELOG.md` diverged across the WP-04…WP-08 branches because each
branch was cut from `wp-04-graph-driver` and recorded only its own entries.
Merging all five branches into `main` produces conflicts on that file only;
resolution keeps a single canonical changelog with every WP entry, latest
first. Rejected alternative: re-recording entries per branch (rewrites
committed history). The WP-02/WP-03 entries had been missing entirely and
were added when the WP-04 changelog was first written.

## 2026-08-01 — D-08 (R2) — LookupRow source attribution resolved in the loader

`LookupRow` (§5.5) carries no source field, while the `:PostalCode` schema
(§5.8) requires `source_id`. The loader maps `kind → producing source`
(`postal_code → gisco_nuts`), fixed by the source table (§8.5.2: only the
GISCO adapter emits the correspondence). Rejected alternative: extending
`LookupRow` with a source field (touches a §5.5 core type, and the mapping
is already determined by §8.5.2).

## 2026-08-01 — D-07 (R2) — Loader batch transactions use the driver's raw session

`load` runs each ≤500-assertion batch through the driver's underlying
session (same seam as schema.py's downgrade guard) because honest
per-statement outcomes — `written`/`skipped` per assertion and `closed`
counts — are required for `LoadResult`, and `GraphDriver.write_batch`
returns only aggregated counters. Rejected alternatives: (a) deriving
`skipped`/`closed_intervals` from aggregates (dishonest counts violate the
"nothing silently dropped" rule); (b) splitting closure into a second
transaction (violates §5.6 "per batch, in one transaction").

## 2026-08-01 — D-06 (R2) — `recorded_at` stamped from the assertion, never the clock

The loader stamps `recorded_at` from `Validity.recorded_at` rather than the
wall clock, because §5.6's "recorded_at now" is the default case and
OffeneRegister publishes its own vintage (Doc 1 §5.8); stamping ingestion
time would make multi-year-stale directorships look current.

## 2026-08-01 — D-05 (R1) — Deterministic key property names bounded by the ontology

Cypher cannot parameterize property names; the loader interpolates the
deterministic key property only when the key name is declared in the
endpoint type's `identifying_keys` (ontology-bounded, never source data),
and logs a warning otherwise. Rejected alternative: interpolating the key
name from the endpoint (source data reaches the query text, §5.6).

## 2026-08-01 — D-04 (R2) — `provision()` issues one DDL statement per transaction

Neo4j 2026.x fails a single transaction issuing many schema changes with
"Could not compile query due to insanely frequent schema changes" — the
failure is order-dependent (passes in isolation, fails under load). Each
§5.3 statement now runs in its own transaction; all are `IF NOT EXISTS`, so
partial provisioning is never an error on the next run. Rejected
alternative: keeping one batched `write_batch` (brittle).

## 2026-08-01 — D-03 (R2) — Test container boots with `neo4j` admin, then creates `limes`

Neo4j 2026.x rejects any first-boot admin username other than `neo4j`
("Invalid admin username, it must be neo4j."), so the integration conftest
starts the container with `neo4j` credentials and then `CREATE USER limes`.
Rejected alternative: connecting tests as `neo4j` throughout (works, but
further from the production `LIMES_NEO4J_USER=limes` configuration; C-01
makes the users privilege-identical anyway).

## 2026-08-01 — D-02 (R1) — Integration test data isolated per test

Ledger and loader integration tests share one session-scoped container;
totals are asserted only over per-test period strings or relative
expectations (`remaining()`), so no test depends on the order the suite
runs in.

## 2026-08-01 — D-01 (R1) — Ledger entries MERGE on `ledger_id`

`write_entry` uses `MERGE` on the unique `ledger_id` so a driver-level
retry of the transaction is idempotent instead of failing on the
constraint. Rejected alternative: `CREATE` (fails on retry after a
successful commit that reported transient failure).
