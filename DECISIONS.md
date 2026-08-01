# DECISIONS — LIMES decision ledger

Append-only ledger per the global AGENTS.md §5. Entries are tagged by
reversibility: **R1** reversible in under an hour, **R2** bounded recoverable
cost, **R3** one-way door. Written when each decision is made, latest first.
Nothing here is a status report; unlogged decisions are unmade decisions.

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
