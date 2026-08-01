# CHANGELOG — LIMES

All notable changes to this project are recorded here as work happens. Format:
one entry per work package, latest first. Independent version lines (ontology,
gold set, prompts) are recorded in their own changelogs.

---

## 2026-08-01 — WP-25a (Embedding merge stamp and backfill)

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
