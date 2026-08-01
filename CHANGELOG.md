# CHANGELOG — LIMES

All notable changes to this project are recorded here as work happens. Format:
one entry per work package, latest first. Independent version lines (ontology,
gold set, prompts) are recorded in their own changelogs.

---

## 2026-08-01 — WP-08 (Graph lookups)

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

## 2026-08-01 — WP-02 (Configuration, types, errors, logging)

- `config.py` with one typed field per §4.2 key and `load_settings()` failing
  startup with a named key (AC-01); full `.env.example`.
- `types.py` with every §5.5 core type; `errors.py` with the full §11
  hierarchy; `logging_setup.py` with secret redaction.
- 30 unit tests across `test_config`, `test_types`, `test_errors`,
  `test_logging`.

## 2026-08-01 — WP-03 (Ontology artifact, schema, registry, validator)

- `ontology/ontology.yaml` with 17 entity types and 30 relations (verified
  17/30), validated against `ontology.schema.json` and self-validated per §5.1.
- `model.py` (`Ontology`, `labels_for`, `permits`, `serialize_for_prompt`),
  `registry.py` (`load_ontology`), `validator.py` (`validate_assertions`).
- 46 unit tests in `test_ontology.py`.

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
