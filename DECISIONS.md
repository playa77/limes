# DECISIONS — LIMES decision ledger

Append-only ledger per the global AGENTS.md §5. Entries are tagged by
reversibility: **R1** reversible in under an hour, **R2** bounded recoverable
cost, **R3** one-way door. Written when each decision is made, latest first.
Nothing here is a status report; unlogged decisions are unmade decisions.

---

## 2026-08-01 — D-09 (R1) — Changelog divergence reconciled at merge

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
