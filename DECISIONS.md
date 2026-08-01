# DECISIONS — LIMES decision ledger

Append-only ledger per the global AGENTS.md §5. Entries are tagged by
reversibility: **R1** reversible in under an hour, **R2** bounded recoverable
cost, **R3** one-way door. Written when each decision is made, latest first.
Nothing here is a status report; unlogged decisions are unmade decisions.

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
