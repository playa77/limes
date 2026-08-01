# CHANGELOG — LIMES

All notable changes to this project are recorded here as work happens. Format:
one entry per work package, latest first. Independent version lines (ontology,
gold set, prompts) are recorded in their own changelogs.

---

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
