# AGENTS.md — LIMES

Ontology-driven knowledge graph over Neo4j 2026.x Community, Docker Compose,
four services (`neo4j` / `api` / `worker` / `ui`). Python ≥3.12, uv-managed
venv at `./venv`. Authoritative artifacts: `docs/LIMES_Design_Document_v2.0.0.md`
and `docs/LIMES_Technical_Specification_v2.1.0.md` (§15 is the seam register).
On re-entry, resume from the last five entries of `DECISIONS.md`.

## Verification loop

```bash
./venv/bin/ruff check src tests                    # NOT `ruff check .`
./venv/bin/mypy                                    # strict, scoped to src/limes
./venv/bin/python -m pytest tests/unit -q          # no Docker needed
# Integration and acceptance are separate invocations: whole-tree collection
# trips over the acceptance conftest's pytest_plugins under pytest 9.x (D-63).
# Both need the Docker daemon and share one session-scoped container.
./venv/bin/python -m pytest tests/integration -q
./venv/bin/python -m pytest tests/acceptance -q
```

- Plain `ruff check .` fails on the standalone scripts in `tools/`; they are
  not part of the lint gate.
- E501 is waived only for `src/limes/graph/schema.py` (single-string Cypher
  DDL); everywhere else the limit is 100.
- Integration and acceptance share one session-scoped disposable Neo4j
  container booted via the docker CLI (first boot can take ~4 min). Reuse a
  running instance with `LIMES_TEST_NEO4J_URI`; override image with
  `LIMES_TEST_NEO4J_IMAGE`.
- Tests never make real paid calls: OpenRouter endpoints are respx-mocked and
  spaCy models are faked. Keep it that way when adding tests.
- After editing `docs/`: `python3 tools/check_docs.py docs/` (type closure, AC
  numbering, seam coverage; C7 rejects TBD/FIXME/"final").
- `python3 tools/smoke_test.py` = clean-host bootstrap smoke test.

## Runtime vs host

Operational commands run inside the worker container: every `make` target wraps
`docker compose exec worker limes …`. Never run ingestion on the host.
Config flows from `./.env`, mounted into containers and read by the app's own
dotenv loader — do not add compose `env_file:` or set empty-string env vars:
an empty string shadows the dotenv value and dead-letters model pins (D-57).

- The base compose file publishes **no ports** (AC-34); the override publishes
  only the UI on `127.0.0.1:8050`. Server promotion = removing the override.
- The worker mounts the docker socket and compose files because `limes backup`
  orchestrates the host daemon from inside the container.

## Money

Every OpenRouter call goes through the hard budget governor. `make backfill`
and `make reextract` refuse without an explicit `BUDGET=` envelope. Never start
ingestion, backfill, or re-extraction without operator instruction. Bootstrap
order is load-bearing (README §Bootstrap): structured sources (`gisco_nuts`,
`gleif`, `ingest-all`) before any unstructured backfill, with `make
stamp-embeddings` exactly between them. Reordering pays for extraction twice.

## Architecture rules (guarded by tests)

- One composition root: `src/limes/composition.py` constructs every component;
  nothing below CLI/API startup instantiates infrastructure.
- `ontology/ontology.yaml` is the single source of truth for entity and
  relation types, consumed by loader, Cypher validator, query builder, and API.
  Never hardcode type/relation names elsewhere. The UI holds no ontology
  literals and no DB access — AST/source scans enforce this in
  `tests/integration/test_ui.py`.
- Query path is read-only by construction: write clauses rejected at parse
  level; the API has exactly three enumerated writes (cost entry, saved query,
  saved-query delete), pinned by acceptance tests. Do not add write surfaces.
- Assertions are bitemporal: validity time ≠ belief time. Contradictions are
  retained under different source ids, never overwritten. `recorded_at` comes
  from the assertion, never the wall clock (D-06).
- Empty query results carry a coverage report naming which hop emptied the set;
  never return a bare empty result.

## Neo4j quirks (details in DECISIONS.md)

- First-boot admin must be named `neo4j`; the app user `limes` is created by
  the compose boot wrapper on every fresh volume.
- `provision()` issues one DDL statement per transaction (many-DDL transactions
  fail with "insanely frequent schema changes") and serializes concurrent
  provisioners through an `:AdvisoryLock` mutex (D-67b).
- Schema provisioning runs on every context build — `make bootstrap-db` is a
  deliberate no-op.
- Clean shutdown takes up to ~120 s (`stop_grace_period: 180s`); after an
  abrupt kill, `neo4j-admin database dump` refuses to run.

## Conventions

- File headers carry a version comment: `# path | vX.Y.Z | why`. Nothing is
  ever labeled "final".
- Each versioned artifact has its own changelog: root `CHANGELOG.md` (one entry
  per work package), `ontology/CHANGELOG.md`, `gold_set/CHANGELOG.md`. A model,
  prompt, or schema change is a versioned event recorded there.
- Guarded invariants get named guard tests referenced from their DECISIONS.md
  entry (e.g. D-67 → `test_concurrent_provision_is_serialized`); never weaken,
  skip, or delete one without an R3 decision.
- Branches follow `wp-NN-slug` or short topic names; merging to `main` happens
  only on explicit operator instruction.
