<!-- LIMES — Implementation Roadmap | v2.0.0 | 2026-07-28 | Status: Draft -->

# LIMES — Implementation Roadmap

| Field | Value |
|---|---|
| Document | LIMES — Implementation Roadmap (Document 3 of 3) |
| Version | 2.0.0 |
| Date | 2026-07-28 |
| Status | Draft |
| Depends on | LIMES — Design Document v2.0.0 (all sections); LIMES — Technical Specification v2.0.0 (all sections) |
| Supersedes | v1.x roadmap, withdrawn with the v1.x document set |

## Revision History

| Version | Date | Changes |
|---|---|---|
| 2.0.0 | 2026-07-28 | Clean re-issue for the v2.0.0 document set. Decomposes Technical Specification v2.0.0 §1 scope items S-01…S-28 into 39 work packages across 11 phases. Every WP references exact Doc 1 / Doc 2 sections that fully define it; no WP invents specification beyond Docs 1–2. Dependency graph is acyclic and verified. Coverage matrix accounts for all 28 scope items and every module in Doc 2 §2. |

---

## 1. Roadmap Overview

### 1.1 Implementation Strategy

The project is decomposed into **39 work packages (WPs)** across **11 phases**. Each WP is scoped to be completable in a single coding-agent session: one cohesive concern, a bounded file set, objective acceptance criteria, and a verification procedure that produces a pass/fail signal.

The fundamental ordering principle mirrors the system's own architecture (Doc 1 §3.1): **strict downward dependency**. Foundation layers (configuration, ontology, graph driver) are built before storage layers, storage before sources, sources before pipeline, pipeline before CLI, CLI before API, API before UI. The composition root (Doc 2 §8.15) is the keystone: it is built only after every component it constructs exists, and nothing downstream of it can be built until it is in place.

### 1.2 Phase Sequence

| Phase | WPs | Theme | Exit criterion |
|---|---|---|---|
| 0 | WP-01 – WP-04 | Foundation: skeleton, config, ontology, graph driver | Ontology loads and self-validates; Neo4j schema provisions idempotently |
| 1 | WP-05 – WP-08 | Storage and cost: archive, ledger/governor, loader, lookups | Graph loader writes bitemporal assertions; lookups cross process boundaries |
| 2 | WP-09 – WP-20 | Source layer: protocol, registry, 11 structured adapters + normalizer | All structured adapters produce correct records from fixtures |
| 3 | WP-21 – WP-24 | Unstructured pipeline: feeds/GDELT, extractor, cache, gate | Gate filters documents; extractor returns pre-resolution assertions |
| 4 | WP-25 | Entity resolution | Mentions resolve to identified endpoints through all four bands |
| 5 | WP-26 – WP-27 | Composition root and pipeline orchestration | `execute_run` traces 1 and 2 run end-to-end against a Neo4j container |
| 6 | WP-28 – WP-31 | CLI: ingest/backfill/reextract/backup, model selection, evaluation, migration | All `make` targets from Doc 2 §8.14 available and functional |
| 7 | WP-32 – WP-35 | Query API: foundation, NL-to-Cypher, coverage, query routers | Trace 3 (`POST /query/nl`) runs end-to-end |
| 8 | WP-36 | Dash UI | Three synchronized panes render query results |
| 9 | WP-37 – WP-38 | Infrastructure: Docker images, Compose, Makefile, bootstrap | `make up` + `make ingest SOURCE=gisco_nuts` succeeds on a clean host |
| 10 | WP-39 | Acceptance test suite | Every AC-01…AC-44 has a mechanical test |

### 1.3 Consumption Model

A coding agent executes one work package per session, strictly in dependency order. The agent receives: this document, Doc 1, Doc 2, and the WP's entry. No other context is required. Each WP entry names exactly which Doc 1 / Doc 2 sections define the behavior, which files to create, what contracts prior WPs provide, and what commands to run for verification.

**An agent must not deviate from the WP scope.** If a gap in Docs 1–2 is discovered during execution, the agent records it as `[CONFLICT]` and halts the WP rather than inventing a local resolution. This is the same rule that governs Doc 2 §15.

---

## 2. Global Conventions

### 2.1 Repository Bootstrap

All WPs assume WP-01 has been completed. WP-01 establishes the directory structure from Doc 2 §2, the dependency manifest, linting/type-checking configuration, and the `tools/check_docs.py` consistency validator. Every subsequent WP creates files only at paths defined in Doc 2 §2.

### 2.2 Branch and Commit Conventions

- One branch per WP, named `wp-NN-slug` (e.g., `wp-03-ontology-registry`).
- One commit per task within the WP, or one squash commit if the WP is small. Commit messages reference the WP ID.
- The `main` branch is advanced only after the WP's verification commands pass.

### 2.3 Artifact Versioning

Per NFR-08, three independent semantic version lines:

| Artifact | Current version | Bumped by |
|---|---|---|
| Deliverable documents (Docs 1–3) | 2.0.0 | This re-issue |
| Ontology (`ontology/ontology.yaml`) | 1.0.0 | WP-03 (initial); WP-31 (migration) |
| Gold set (`gold_set/gold_set.jsonl`) | 1.0.0 | WP-30 (initial creation) |

Each artifact has its own `CHANGELOG.md` in its directory.

### 2.4 Definition of Done (All WPs)

A WP is done when all of the following hold:

1. Every file listed in the WP's Scope section exists at the path specified in Doc 2 §2.
2. Every item in the WP's Task list is completed.
3. Every criterion in the WP's Acceptance Criteria section is met.
4. Every command in the WP's Verification section passes.
5. `ruff check src/limes/` and `mypy src/limes/` pass with no new errors.
6. `python tools/check_docs.py` passes (no cross-document contradictions introduced).
7. No `[CONFLICT]` markers remain in any file created by the WP.
8. No production implementation code has been written beyond what Doc 2 §8 specifies — interface signatures, types, and pseudocode are the ceiling; the agent writes real Python only where Doc 2 §8 gives a concrete function or class signature.

**Test-construction rule (Doc 2 §12.2):** No test may hand-build the state the code under test is supposed to produce. Pre-existing state is established by calling the production path, never by direct fixture writes. A cross-process test must cross a real process boundary (`subprocess`, not a fresh object in the same interpreter).

### 2.5 Check Tool

`tools/check_docs.py` (created in WP-01) verifies:
- Every type named in a Doc 2 §8 signature is defined in Doc 2 §5.5 or §8.15 (AC-44).
- Every module in Doc 2 §2 has at least one caller in Doc 2 §15.2.
- No section references a constraint capability excluded by Doc 1 §2.3.

The agent runs this tool after every WP. A failure is a `[CONFLICT]` and halts the WP.

---

## 3. Dependency Graph

### 3.1 Full WP Index

| WP | Title | Phase | Depends on | Parallelizable with |
|---|---|---|---|---|
| WP-01 | Repository skeleton, tooling, check_docs.py | 0 | — | — |
| WP-02 | Configuration, types, errors, logging | 0 | WP-01 | — |
| WP-03 | Ontology artifact, schema, registry, validator | 0 | WP-02 | WP-05, WP-37 |
| WP-04 | Graph driver, schema provisioning, temporal fragments | 0 | WP-02, WP-03 | WP-09 |
| WP-05 | Archive store | 1 | WP-02 | WP-03, WP-37 |
| WP-06 | Cost ledger and budget governor | 1 | WP-02, WP-04 | WP-07, WP-08, WP-10…WP-21 |
| WP-07 | Graph loader | 1 | WP-03, WP-04 | WP-06, WP-08, WP-10…WP-21 |
| WP-08 | Graph lookups (cross-process reference data) | 1 | WP-04 | WP-06, WP-07, WP-10…WP-21 |
| WP-09 | Source adapter protocol, registry, normalizer | 2 | WP-02, WP-03 | WP-04 |
| WP-10 | GISCO/NUTS adapter | 2 | WP-09 | WP-11…WP-21, WP-06…WP-08 |
| WP-11 | GLEIF adapter | 2 | WP-09 | WP-10, WP-12…WP-21, WP-06…WP-08 |
| WP-12 | EUR-Lex adapter | 2 | WP-09 | WP-10…WP-11, WP-13…WP-21, WP-06…WP-08 |
| WP-13 | FSD adapter | 2 | WP-09 | WP-10…WP-12, WP-14…WP-21, WP-06…WP-08 |
| WP-14 | TED adapter | 2 | WP-09 | WP-10…WP-13, WP-15…WP-21, WP-06…WP-08 |
| WP-15 | Transparency Register adapter | 2 | WP-09 | WP-10…WP-14, WP-16…WP-21, WP-06…WP-08 |
| WP-16 | Bundestag DIP adapter | 2 | WP-09 | WP-10…WP-15, WP-17…WP-21, WP-06…WP-08 |
| WP-17 | Gesetze im Internet adapter | 2 | WP-09 | WP-10…WP-16, WP-18…WP-21, WP-06…WP-08 |
| WP-18 | Wikidata adapter (enrichment) | 2 | WP-09 | WP-10…WP-17, WP-19…WP-21, WP-06…WP-08 |
| WP-19 | OSM adapter | 2 | WP-09 | WP-10…WP-18, WP-20…WP-21, WP-06…WP-08 |
| WP-20 | OffeneRegister adapter | 2 | WP-09 | WP-10…WP-19, WP-21, WP-06…WP-08 |
| WP-21 | Unstructured adapters: GDELT + feeds | 3 | WP-09 | WP-22, WP-23 |
| WP-22 | Extractor: protocol, OpenRouter client, schema, prompts | 3 | WP-02, WP-03, WP-06 | WP-21, WP-23 |
| WP-23 | Extraction cache | 3 | WP-02, WP-04 | WP-21, WP-22 |
| WP-24 | Gate: spaCy NER, passage selection, idempotency | 3 | WP-02, WP-23 | WP-25 |
| WP-25 | Entity resolution | 4 | WP-03, WP-04, WP-22 | WP-24 |
| WP-26 | Composition root | 5 | WP-02, WP-03, WP-04, WP-05, WP-06, WP-09, WP-22, WP-24, WP-25 | — |
| WP-27 | Pipeline run orchestration + window resolution | 5 | WP-07, WP-09, WP-22, WP-24, WP-25, WP-26 | — |
| WP-28 | CLI core: ingest, backfill, reextract, backup | 6 | WP-26, WP-27 | WP-29, WP-30, WP-31 |
| WP-29 | Model selection CLI | 6 | WP-22, WP-26 | WP-28, WP-30, WP-31 |
| WP-30 | Evaluation harness, gold set, reference questions | 6 | WP-22, WP-26 | WP-28, WP-29, WP-31 |
| WP-31 | Ontology migration CLI | 6 | WP-03, WP-04, WP-26 | WP-28, WP-29, WP-30 |
| WP-32 | Query API foundation | 7 | WP-03, WP-04, WP-06, WP-26, WP-27 | WP-33, WP-34 |
| WP-33 | NL-to-Cypher service | 7 | WP-03, WP-04, WP-06, WP-22 | WP-32, WP-34 |
| WP-34 | Coverage report and empty-result diagnosis | 7 | WP-03, WP-04 | WP-32, WP-33 |
| WP-35 | Query routers, builder projection, saved queries | 7 | WP-32, WP-33, WP-34 | — |
| WP-36 | Dash UI | 8 | WP-35 | — |
| WP-37 | Docker images and Compose topology | 9 | WP-01 | (parallel from Phase 0) |
| WP-38 | Makefile and bootstrap procedure | 9 | WP-28, WP-29, WP-37 | — |
| WP-39 | Acceptance test suite | 10 | WP-38 | — |

### 3.2 Acyclicity Verification

Topological levels (each level's WPs depend only on WPs in earlier levels):

| Level | WPs |
|---|---|
| 0 | WP-01 |
| 1 | WP-02 |
| 2 | WP-03, WP-05, WP-37 |
| 3 | WP-04, WP-09 |
| 4 | WP-06, WP-07, WP-08, WP-10…WP-21 |
| 5 | WP-22, WP-23 |
| 6 | WP-24, WP-25, WP-33 |
| 7 | WP-26 |
| 8 | WP-27, WP-29, WP-30, WP-31, WP-34 |
| 9 | WP-28, WP-32 |
| 10 | WP-35 |
| 11 | WP-36, WP-38 |
| 12 | WP-39 |

No WP at level *n* depends on a WP at level ≥ *n*. **The graph is acyclic.**

### 3.3 Critical Path

The longest dependency chain determines the minimum sequential execution:

```
WP-01 → WP-02 → WP-03 → WP-04 → WP-06 → WP-22 → WP-25 → WP-26 → WP-27 → WP-28 → WP-38 → WP-39
```

12 WPs on the critical path. The remaining 27 WPs can be parallelized across multiple agents where the dependency graph permits.

---

## 4. Work Packages

---

### WP-01 — Repository Skeleton, Tooling, check_docs.py

| Field | Value |
|---|---|
| Phase | 0 |
| Depends on | — |
| Sizing | Single session |

**Objective:** Establish the directory structure from Doc 2 §2, the dependency manifest, linting and type-checking configuration, and the specification consistency validator.

**Spec references:** Doc 2 §2 (Project Structure), §3 (Dependencies), §12.7 (Coverage Target).

**Scope — files created:**
- `pyproject.toml` — project metadata, all dependencies from Doc 2 §3 with stated constraints, `ruff` and `mypy` configuration
- `uv.lock` — lock file
- `README.md` — includes the personal-artifact disclaimer required by Doc 1 §7.5 (AC-35)
- `CHANGELOG.md` — project changelog
- `AGENTS.md` — coding-agent instructions
- `.env.example` — stub; full content comes in WP-02
- `Makefile` — stub with `help` target only; full content in WP-38
- `tools/check_docs.py` — specification consistency validator per §2.5 of this document
- `src/limes/__init__.py`, `tests/__init__.py`, `tests/conftest.py`
- `ruff.toml` or `[tool.ruff]` in `pyproject.toml`; `mypy.ini` or `[tool.mypy]` in `pyproject.toml`
- `.gitignore`

**Out of scope:** Any source module content beyond `__init__.py` files. Any Docker file. Any ontology artifact content.

**Task list:**
1. Create the full directory tree from Doc 2 §2, including empty `__init__.py` files for every Python package.
2. Write `pyproject.toml` with all dependencies from Doc 2 §3, pinned to the stated minimum constraints. Configure `ruff` with line length 100, `mypy` with `strict = true` for `src/limes/`.
3. Write `README.md` including: project name, one-paragraph description from Doc 1 §1.1, and the personal-artifact disclaimer from Doc 1 §7.5 verbatim.
4. Write `AGENTS.md` with: instruction to read Docs 1–3 before any work, the Definition of Done from §2.4 of this document, the test-construction rule from Doc 2 §12.2, and the `[CONFLICT]` reporting protocol.
5. Write `tools/check_docs.py` implementing the three checks from §2.5 of this document. The tool reads `docs/LIMES_Design_Document_v2.0.0.md` and `docs/LIMES_Technical_Specification_v2.0.0.md` and validates: (a) every type name in a `§8` signature has a definition in `§5.5` or `§8.15`; (b) every module listed in `§2` has at least one entry in `§15.2`; (c) the tool exits non-zero with a precise message on failure.
6. Write `.gitignore` for Python, Docker, Neo4j data, and `.env`.
7. Run `uv lock` to generate `uv.lock`.

**Contracts consumed:** None (first WP).

**Contracts produced:**
- Directory structure per Doc 2 §2
- `pyproject.toml` with all dependencies declared
- `tools/check_docs.py` executable
- `README.md` with personal-artifact disclaimer

**Acceptance criteria:**
- AC-35 (partial): Repository contains the personal-artifact disclaimer.
- `python tools/check_docs.py` runs without error against the (not-yet-present) Docs 1–2 markdown files — the tool handles missing files gracefully with a clear message.
- `uv sync` succeeds.
- `ruff check src/limes/` passes (on empty packages).
- `mypy src/limes/` passes (on empty packages).

**Verification:**
```bash
uv sync
ruff check src/limes/
mypy src/limes/
python tools/check_docs.py  # may report missing docs; must not crash
test -f README.md && grep -q "personal research artifact" README.md
```

---

### WP-02 — Configuration, Types, Errors, Logging

| Field | Value |
|---|---|
| Phase | 0 |
| Depends on | WP-01 |
| Sizing | Single session |

**Objective:** Implement the configuration loader, core type definitions, error hierarchy, and structured logging setup that every subsequent module depends on.

**Spec references:** Doc 2 §4 (Configuration), §5.5 (Core Types), §8.1 (config.py), §11 (Error Handling), §10 (Observability).

**Scope — files created:**
- `src/limes/config.py` — `Settings` class and `load_settings()` per Doc 2 §8.1
- `src/limes/types.py` — all types from Doc 2 §5.5
- `src/limes/errors.py` — error hierarchy from Doc 2 §11
- `src/limes/logging_setup.py` — structlog configuration per Doc 2 §10
- `.env.example` — full content from Doc 2 §4.2

**Out of scope:** Any module that consumes these types (all subsequent WPs).

**Task list:**
1. Write `.env.example` with every key from Doc 2 §4.2, including the comments about C-01 and the OpenRouter key being held by both `api` and `worker`.
2. Implement `config.py`: `Settings` as a Pydantic BaseSettings class with one typed field per §4.2 key. Implement `load_settings() -> Settings` that reads from environment variables. No module-level singleton.
3. Implement `types.py` with every type defined in Doc 2 §5.5: `Mention`, `EntityEndpoint`, `Provenance`, `Validity`, `ExtractedAssertion`, `Assertion`, `LookupRow`, `DocumentPayload`, `Passage`, `RawRecord`, `NormalizedRecord`, `NerSpan`, `GateDecision`, `ValidationError`, `WriteResult`, `PlanSummary`, `CostLedgerEntry`, `SourceRecord`, `IngestionRunRecord`. Use `pydantic.BaseModel` for all. Ensure `NormalizedRecord` has `assertions`, `entities`, `lookup_rows` defaulting to empty lists and `document` defaulting to `None`.
4. Implement `errors.py` with the full hierarchy from Doc 2 §11: `LimesError` base, then `ConfigurationError`, `OntologyError`, `SourceFetchError`, `SourceParseError`, `ExtractionError`, `ExtractionSchemaError`, `BudgetExhausted`, `ValidationRejected`, `EndpointUnidentified`, `GraphWriteError`, `CypherValidationFailed`, `QueryPlanRejected`. Each is a subclass of `LimesError`.
5. Implement `logging_setup.py`: structlog configuration with JSON output, `run_id`/`source_id`/`module`/`event` on every line, and a redaction processor that masks values of keys whose names match a configured secret-key list (including `LIMES_OPENROUTER_API_KEY`, `LIMES_NEO4J_PASSWORD`). Provide a `configure_logging(settings: Settings) -> None` function.
6. Write unit tests for: configuration loading with all keys present; configuration loading with a missing required key (must raise `ConfigurationError` naming the key); type serialization round-trips; error hierarchy `issubclass` relationships; redaction processor masks secret values.

**Contracts consumed:**
- Directory structure (WP-01)
- `pyproject.toml` dependencies (WP-01)

**Contracts produced:**
- `Settings` class and `load_settings()` — consumed by every WP that reads configuration
- All §5.5 types — consumed by every WP that handles assertions, records, or pipeline data
- Error hierarchy — consumed by every WP that raises or catches exceptions
- `configure_logging()` — consumed by the composition root (WP-26) and API startup (WP-32)

**Acceptance criteria:**
- AC-01 (partial): Startup fails with a named key when any required configuration is absent.
- All §5.5 types are importable and instantiate correctly with valid data.
- `load_settings()` raises `ConfigurationError` with the missing key's name when a required key is absent.
- The redaction processor replaces secret values with `***REDACTED***` in log output.

**Verification:**
```bash
ruff check src/limes/config.py src/limes/types.py src/limes/errors.py src/limes/logging_setup.py
mypy src/limes/config.py src/limes/types.py src/limes/errors.py src/limes/logging_setup.py
pytest tests/unit/test_config.py tests/unit/test_types.py tests/unit/test_errors.py tests/unit/test_logging.py -v
python tools/check_docs.py
```

---

### WP-03 — Ontology Artifact, Schema, Registry, Validator

| Field | Value |
|---|---|
| Phase | 0 |
| Depends on | WP-02 |
| Sizing | Single session |

**Objective:** Create the declarative ontology artifact with all 17 entity types and 30 relations, its JSON Schema, the loader, self-validation, and the registry that exposes types and constraints to four consumers (loader, Cypher validator, builder projection, API).

**Spec references:** Doc 1 §5.1–5.4 (Ontology Principles, Entity Types, Relation Types); Doc 2 §5.1 (Ontology Artifact), §5.4 (Relation Domains and Ranges), §8.2 (Ontology module).

**Scope — files created:**
- `ontology/ontology.yaml` — the full ontology artifact
- `ontology/ontology.schema.json` — JSON Schema for the ontology artifact
- `ontology/CHANGELOG.md` — initial entry for v1.0.0
- `src/limes/ontology/model.py` — `Ontology`, `EntityTypeSpec`, `RelationTypeSpec` classes with `labels_for()`, `permits()`, `serialize_for_prompt()`
- `src/limes/ontology/registry.py` — `load_ontology(path: Path) -> Ontology`
- `src/limes/ontology/validator.py` — `validate_assertions(assertions, ontology) -> tuple[list[Assertion], list[ValidationError]]`

**Out of scope:** Migration execution (WP-31). Builder projection logic (WP-35). The `feeds.yaml` file (WP-21).

**Task list:**
1. Write `ontology/ontology.schema.json` validating the structure shown in Doc 2 §5.1: `version`, `supertypes`, `entity_types` (each with `name`, `supertype`, `identifying_keys`, `properties`), `relation_types` (each with `name`, `domain`, `range`, `temporal`), `vocabularies`. Enforce `additionalProperties: false`.
2. Write `ontology/ontology.yaml` with all 17 entity types from Doc 1 §5.2, all 30 relations from Doc 1 §5.4 with domains and ranges from Doc 2 §5.4, and the three vocabularies (EuroVoc, CPV, KRITIS). Set `version: "1.0.0"`. Include `temporal: false` for the nine non-temporal relations listed in Doc 2 §5.1.
3. Implement `model.py`:
   - `EntityTypeSpec` and `RelationTypeSpec` as Pydantic models matching the YAML structure.
   - `Ontology` class with `version`, `supertypes`, `entity_types: dict[str, EntityTypeSpec]`, `relation_types: dict[str, RelationTypeSpec]`.
   - `labels_for(type_name) -> list[str]`: returns `[type_name, supertype, "Entity"]` for concrete types; resolves supertypes transitively.
   - `permits(relation, subject_type, object_type) -> bool`: resolves supertypes for both subject and object, then checks domain/range.
   - `serialize_for_prompt() -> str`: serializes types and relations into a compact text representation; logs token estimate at startup and warns above 3000 (A-04).
4. Implement `registry.py`: `load_ontology(path) -> Ontology` — reads YAML, validates against `ontology.schema.json`, runs self-validation. Self-validation rejects per Doc 2 §5.1: undeclared type in domain/range, undeclared supertype, duplicate names, identifying key absent from property list, unique property that is not an identifying key.
5. Implement `validator.py`: `validate_assertions(assertions, ontology) -> tuple[list[Assertion], list[ValidationError]]`. Partitions rather than raising. For each assertion: checks relation exists, checks `permits()` for subject/relation/object type, checks temporal relations have validity information. Returns accepted assertions and rejected ones with reasons.
6. Write unit tests for: every self-validation rejection case from Doc 2 §5.1; `labels_for` for concrete types and supertypes; `permits` for valid and invalid domain/range combinations including supertype resolution; `serialize_for_prompt` output; `validate_assertions` partitioning with at least one accepted and one rejected assertion.

**Contracts consumed:**
- `types.py` types: `Assertion`, `ValidationError` (WP-02)
- `errors.py`: `OntologyError` (WP-02)

**Contracts produced:**
- `Ontology` class with `labels_for()`, `permits()`, `serialize_for_prompt()` — consumed by WP-04, WP-07, WP-09, WP-22, WP-25, WP-26, WP-32, WP-33, WP-34, WP-35
- `load_ontology()` — consumed by WP-26 (composition root), WP-32 (API startup)
- `validate_assertions()` — consumed by WP-07 (graph loader), WP-27 (pipeline run)
- `ontology/ontology.yaml` artifact — the authoritative ontology definition

**Acceptance criteria:**
- AC-02: The ontology loads, self-validates, and rejects each malformed case in §5.1.
- All 17 entity types and 30 relations are present in the loaded `Ontology`.
- `permits()` correctly resolves supertypes (e.g., `SUBSIDIARY_OF` permitted for a `Corporation` subject, rejected for a `Person` subject).
- `validate_assertions` returns a non-empty accepted list for valid assertions and a non-empty rejection list for invalid ones.

**Verification:**
```bash
ruff check src/limes/ontology/
mypy src/limes/ontology/
pytest tests/unit/test_ontology.py -v
python -c "from limes.ontology.registry import load_ontology; o = load_ontology(__import__('pathlib').Path('ontology/ontology.yaml')); print(len(o.entity_types), len(o.relation_types))"
# Expected: 17 30
python tools/check_docs.py
```

---

### WP-04 — Graph Driver, Schema Provisioning, Temporal Fragments

| Field | Value |
|---|---|
| Phase | 0 |
| Depends on | WP-02, WP-03 |
| Sizing | Single session |

**Objective:** Implement the Neo4j driver wrapper with read/write session separation, idempotent schema and index provisioning from the ontology, and composable temporal query fragment builders.

**Spec references:** Doc 1 §7.2 (Read-Only Enforcement), §8.5 (Backup); Doc 2 §5.3 (Constraints and Indexes), §7.1–7.2 (C-01 and enforcement), §8.3 (Graph module).

**Scope — files created:**
- `src/limes/graph/driver.py` — `GraphDriver` class with `read()`, `write_batch()`, `explain()`
- `src/limes/graph/schema.py` — `provision()` function
- `src/limes/graph/temporal.py` — `as_of()`, `as_believed()`, `currently()` builders

**Out of scope:** The graph loader (WP-07). Graph lookups (WP-08). Graph queries module (WP-07).

**Task list:**
1. Implement `driver.py`:
   - `GraphDriver` class initialized with URI, user, password, database name.
   - `read(cypher, params, timeout_s) -> list[dict]`: opens sessions in **read access mode** (Doc 2 §7.2, point 2). Returns list of dicts.
   - `write_batch(statements: list[tuple[str, dict]]) -> WriteResult`: opens a write session, executes all statements in one transaction, returns `WriteResult`.
   - `explain(cypher, params) -> PlanSummary`: runs `EXPLAIN` or `PROFILE`, parses the plan into `PlanSummary` with `operators`, `max_estimated_rows`, `total_estimated_rows`, `has_cartesian_product`, `max_varlength_hops`.
2. Implement `schema.py`:
   - `provision(driver, ontology, embedding_dimensions) -> None`: executes all DDL from Doc 2 §5.3 idempotently (all `IF NOT EXISTS`). Includes constraints, indexes, fulltext indexes, and the vector index with the configured dimensions.
   - Ontology downgrade guard: queries the maximum `ontology_version` stamped on any `:Entity` node and raises `OntologyError` if the artifact version is older (Doc 2 §4.3). On a fresh database, the guard passes.
3. Implement `temporal.py`:
   - `as_of(alias, instant) -> str`: returns a Cypher fragment filtering `valid_from <= instant AND (valid_to IS NULL OR valid_to > instant)`.
   - `as_believed(alias, instant) -> str`: returns a Cypher fragment filtering `recorded_at <= instant AND (retracted_at IS NULL OR retracted_at > instant)`.
   - `currently(alias) -> str`: returns a Cypher fragment filtering `valid_to IS NULL`.
   - These are composable string builders, never string concatenation at call sites (Doc 2 §5.7).
4. Write integration tests against a disposable Neo4j container:
   - Schema provisioning is idempotent (AC-03): running twice produces no error and no duplicate index.
   - `read()` opens in read access mode and refuses a write statement.
   - `write_batch()` executes multiple statements in one transaction.
   - `explain()` returns a `PlanSummary` with correct fields.
   - Ontology downgrade guard rejects an older ontology version after a newer one is stamped.

**Contracts consumed:**
- `Settings` (WP-02) — for Neo4j connection parameters
- `Ontology` (WP-03) — for relation types to generate relationship property indexes
- `WriteResult`, `PlanSummary` types (WP-02)

**Contracts produced:**
- `GraphDriver` class — consumed by WP-06, WP-07, WP-08, WP-22, WP-23, WP-25, WP-26, WP-27, WP-32, WP-33, WP-34, WP-35
- `provision()` — consumed by WP-26 (composition root, called on every context build)
- `as_of()`, `as_believed()`, `currently()` — consumed by WP-33 (NL-to-Cypher), WP-34 (coverage)

**Acceptance criteria:**
- AC-03: Schema provisioning is idempotent; running it twice produces no error and no duplicate index.
- AC-01 (partial): Ontology downgrade guard rejects an older artifact.
- `read()` sessions are opened in read access mode (verifiable by attempting a write and observing refusal).

**Verification:**
```bash
ruff check src/limes/graph/driver.py src/limes/graph/schema.py src/limes/graph/temporal.py
mypy src/limes/graph/driver.py src/limes/graph/schema.py src/limes/graph/temporal.py
pytest tests/integration/test_graph_driver.py tests/integration/test_schema_provision.py -v
# Requires a running Neo4j container; conftest.py starts one via docker
python tools/check_docs.py
```

---

### WP-05 — Archive Store

| Field | Value |
|---|---|
| Phase | 1 |
| Depends on | WP-02 |
| Sizing | Single session |

**Objective:** Implement the content-addressed, compressed, durable raw payload archive that is the system of record from which the entire graph is re-derivable.

**Spec references:** Doc 1 §4.2 (Raw Archive), §8.3 (Storage); Doc 2 §8.4 (Archive).

**Scope — files created:**
- `src/limes/archive/store.py` — `ArchiveStore` class

**Out of scope:** Any consumer of the archive (WP-27 pipeline run).

**Task list:**
1. Implement `ArchiveStore` per Doc 2 §8.4:
   - `__init__(self, root: Path)`: stores root directory.
   - `put(source_id, payload, content_type) -> str`: computes SHA-256 of payload, gzip-compresses, writes to two-level hex prefix directory (`ab/cd/abcdef...`), atomic write by temporary name and rename. Returns content hash. Idempotent: existing hash is a no-op returning the same value.
   - `get(content_hash) -> bytes`: reads and gunzips. Raises `FileNotFoundError` if absent.
   - `exists(content_hash) -> bool`: checks file existence.
   - `path_for(content_hash) -> Path`: returns the full path for a hash.
2. Write unit tests for: `put` returns correct SHA-256; `put` is idempotent (same payload returns same hash, no duplicate write); `get` returns original bytes after `put`; `exists` returns True after `put`, False before; two-level directory structure is correct; gzip compression is applied.

**Contracts consumed:**
- `Settings` (WP-02) — for `LIMES_ARCHIVE_PATH`

**Contracts produced:**
- `ArchiveStore` class — consumed by WP-26 (composition root), WP-27 (pipeline run)

**Acceptance criteria:**
- `put` is idempotent: calling with the same payload twice returns the same hash and writes the file only once.
- `get` recovers the exact original bytes.
- Hash stability across processes (Doc 2 §12.1): the same payload produces the same hash in different Python invocations.

**Verification:**
```bash
ruff check src/limes/archive/store.py
mypy src/limes/archive/store.py
pytest tests/unit/test_archive.py -v
python -c "import hashlib, gzip; from limes.archive.store import ArchiveStore; from pathlib import Path; import tempfile, os; d = tempfile.mkdtemp(); s = ArchiveStore(Path(d)); h = s.put('test', b'hello', 'text/plain'); assert s.get(h) == b'hello'; assert s.put('test', b'hello', 'text/plain') == h; print('OK')"
python tools/check_docs.py
```

---

### WP-06 — Cost Ledger and Budget Governor

| Field | Value |
|---|---|
| Phase | 1 |
| Depends on | WP-02, WP-04 |
| Sizing | Single session |

**Objective:** Implement the cost ledger that records every paid API call as a graph node and the budget governor that enforces the monthly ceiling and per-run envelopes.

**Spec references:** Doc 1 §4.9 (Cost Ledger and Budget Governor), §9.3 (Cost Control); Doc 2 §8.9 (Cost), §5.8 (`:CostLedgerEntry` schema).

**Scope — files created:**
- `src/limes/cost/governor.py` — `Governor` class
- `src/limes/cost/ledger.py` — ledger writing function

**Out of scope:** The OpenRouter client that calls the governor (WP-22).

**Task list:**
1. Implement `governor.py` — `Governor` class per Doc 2 §8.9:
   - `__init__(self, driver: GraphDriver, monthly_ceiling_eur: Decimal, soft_stop_fraction: float, usd_eur_rate: float, envelope_eur: Decimal | None = None)`: stores configuration. When `envelope_eur` is set, the governor meters against it and does not draw on the monthly ceiling.
   - `check(estimated_cost_eur: Decimal) -> None`: queries the ledger for the current month's total spend (or envelope spend), adds the estimate, and raises `BudgetExhausted` if the result exceeds the ceiling (or envelope). Does not write.
   - `commit(actual: CostLedgerEntry) -> None`: writes the `:CostLedgerEntry` node to the graph via the driver and updates the in-memory running total.
   - `remaining() -> Decimal`: returns remaining budget for the current metering scope (monthly or envelope).
2. Implement `ledger.py`:
   - `write_entry(driver: GraphDriver, entry: CostLedgerEntry) -> None`: writes a `:CostLedgerEntry` node with all properties from Doc 2 §5.8. Parameterized Cypher, no operator input.
   - `read_period_spend(driver: GraphDriver, period: str) -> Decimal`: sums `cost_eur` for entries matching the given `period` (YYYY-MM).
3. Write unit and integration tests:
   - Governor arithmetic: `check` passes when projected spend is below ceiling; raises `BudgetExhausted` when above.
   - Envelope mode: `check` meters against the envelope, not the monthly ceiling.
   - `commit` writes a `:CostLedgerEntry` node; `read_period_spend` returns the correct total.
   - Soft-stop fraction: `check` raises at `ceiling * soft_stop_fraction`, not at `ceiling`.

**Contracts consumed:**
- `GraphDriver` (WP-04)
- `CostLedgerEntry` type (WP-02)
- `BudgetExhausted` error (WP-02)
- `Settings` (WP-02) — for ceiling, soft-stop, USD/EUR rate

**Contracts produced:**
- `Governor` class — consumed by WP-22 (OpenRouter client), WP-26 (composition root)
- `write_entry()`, `read_period_spend()` — consumed by `Governor.commit()`

**Acceptance criteria:**
- AC-14 (partial): The governor refuses a call that would breach the ceiling.
- AC-15 (partial): Envelope mode meters against the envelope, not the monthly ceiling.
- `commit` writes a node with all properties from Doc 2 §5.8.

**Verification:**
```bash
ruff check src/limes/cost/
mypy src/limes/cost/
pytest tests/unit/test_governor.py tests/integration/test_cost_ledger.py -v
python tools/check_docs.py
```

---

### WP-07 — Graph Loader

| Field | Value |
|---|---|
| Phase | 1 |
| Depends on | WP-03, WP-04 |
| Sizing | Single session |

**Objective:** Implement the sole writer of ontology-typed nodes and relationships, including node materialization, bitemporal merge, lookup-row materialization, and retraction.

**Spec references:** Doc 1 §4.7 (Graph Loader), §5.6 (Assertion Metadata), §5.7 (Bitemporal and Node Semantics); Doc 2 §5.6 (Merge Semantics), §8.3 (Graph — `load`, `retract`).

**Scope — files created:**
- `src/limes/graph/loader.py` — `load()` and `retract()` functions, `LoadResult` type
- `src/limes/graph/queries.py` — Cypher query templates used by the loader

**Out of scope:** The pipeline that calls the loader (WP-27). Schema provisioning (WP-04).

**Task list:**
1. Implement `LoadResult` per Doc 2 §8.3: `nodes_created`, `nodes_matched`, `lookup_rows_written`, `written`, `skipped`, `closed_intervals`, `rejected`.
2. Implement `load()` per Doc 2 §8.3 and §5.6:
   - Signature: `load(driver, assertions, ontology, standalone_entities=None, lookup_rows=None) -> LoadResult`.
   - Process in batches of at most 500 assertions per transaction.
   - Step 1 — Materialize endpoint nodes: for each `EntityEndpoint`, group by label set from `ontology.labels_for(type)`. Issue one `MERGE` per label group. `ON CREATE` stamps `label`, deterministic key property, `ontology_version`, `created_at`. `ON MATCH` adds unseen aliases only — never overwrites label, key, or original ontology version.
   - Step 2 — Materialize lookup rows as system nodes per `LookupRow.kind`.
   - Step 3 — Idempotency: if a relationship with the same `assertion_id` exists, skip.
   - Step 4 — Create relationship with `recorded_at` now and `valid_from` from source.
   - Step 5 — Close superseded interval only from the same `source_id`: existing relationship of same type between same endpoints with null `valid_to` and earlier `valid_from` gets `valid_to` set.
   - Step 6 — Never modify relationships from a different `source_id`.
   - Reject assertions whose endpoints lack `entity_id` as `ENDPOINT_UNIDENTIFIED` (AC-10).
   - Also materialize `standalone_entities` (entities in no relationship) identically to assertion endpoints.
3. Implement `retract(driver, assertion_ids, at) -> int`: sets `retracted_at` on matching relationships. Returns count retracted.
4. Implement `queries.py`: Cypher templates for node merge (parameterized except labels), relationship merge, interval closure, lookup-row merge, retraction. Label segments built from `ontology.labels_for()`, never from source data.
5. Write integration tests against a disposable Neo4j container:
   - AC-08: Loading into an empty graph materializes endpoint nodes with labels, deterministic keys, and ontology version; standalone entities materialized identically. **No test pre-creates endpoint nodes by direct Cypher.**
   - AC-09: Re-merging from a lower-trust source does not overwrite label, key, or original ontology version.
   - AC-05: Re-running an identical load writes zero new relationships and zero new nodes.
   - AC-06: Interval closure occurs within a source and does not occur across sources.
   - AC-10: An assertion whose endpoint lacks `entity_id` is rejected as `ENDPOINT_UNIDENTIFIED`, counted, never written.
   - AC-07 (partial): Every relationship carries complete non-null assertion metadata.

**Contracts consumed:**
- `GraphDriver` (WP-04)
- `Ontology` with `labels_for()` (WP-03)
- `Assertion`, `EntityEndpoint`, `LookupRow`, `WriteResult` types (WP-02)

**Contracts produced:**
- `load()` function — consumed by WP-27 (pipeline run)
- `retract()` function — consumed by WP-27 (re-extraction)
- `LoadResult` type — consumed by WP-27

**Acceptance criteria:**
- AC-05, AC-06, AC-07 (partial), AC-08, AC-09, AC-10.
- Cypher label segments are built from `Ontology.labels_for`, never from source data.
- Batch size does not exceed 500 assertions per transaction.

**Verification:**
```bash
ruff check src/limes/graph/loader.py src/limes/graph/queries.py
mypy src/limes/graph/loader.py src/limes/graph/queries.py
pytest tests/integration/test_loader.py -v
python tools/check_docs.py
```

---

### WP-08 — Graph Lookups (Cross-Process Reference Data)

| Field | Value |
|---|---|
| Phase | 1 |
| Depends on | WP-04 |
| Sizing | Single session |

**Objective:** Implement the cross-process reference-data reader that resolves postal-code-to-NUTS correspondences from the graph, satisfying C-07's requirement that cross-process state lives in the graph, not in module globals or derived files.

**Spec references:** Doc 1 §5.9 (Cross-Process State), DD-20; Doc 2 §5.9 (Cross-Process State), §8.16 (Lookups).

**Scope — files created:**
- `src/limes/graph/lookups.py` — `postal_code_to_nuts()` function

**Out of scope:** The GISCO adapter that writes `:PostalCode` nodes (WP-10). The composition root (WP-26).

**Task list:**
1. Implement `postal_code_to_nuts(driver, country_code, postal_code) -> str | None` per Doc 2 §8.16:
   - Graph query: `MATCH (p:PostalCode {country_code: $cc, postal_code: $pc}) RETURN p.nuts_code`.
   - In-process LRU cache (e.g., `functools.lru_cache` or a small dict with max size).
   - A miss returns `None`; the caller leaves the field unassigned and counts it. Never raises on a miss.
2. Write integration tests:
   - AC-39 (partial): A value written as a `LookupRow` by one CLI invocation is readable by `postal_code_to_nuts` in a **separate operating-system process**. Use `subprocess` to cross the process boundary. Write the `:PostalCode` node via the loader (production path), then read it from a fresh process.
   - A miss returns `None` without raising.
   - LRU cache returns the same result for repeated queries without hitting the database.

**Contracts consumed:**
- `GraphDriver` (WP-04)

**Contracts produced:**
- `postal_code_to_nuts()` — consumed by WP-11 (GLEIF adapter), WP-14 (TED adapter), WP-19 (OSM adapter)

**Acceptance criteria:**
- AC-39: Cross-process lookup works; a miss returns `None` without raising.
- The test crosses a real process boundary via `subprocess`.

**Verification:**
```bash
ruff check src/limes/graph/lookups.py
mypy src/limes/graph/lookups.py
pytest tests/integration/test_lookups_cross_process.py -v
python tools/check_docs.py
```

---

### WP-09 — Source Adapter Protocol, Registry, Normalizer

| Field | Value |
|---|---|
| Phase | 2 |
| Depends on | WP-02, WP-03 |
| Sizing | Single session |

**Objective:** Define the `SourceAdapter` protocol, the `SourceRegistry` with its authoritative population function, and the shared normalizer utilities (language detection, timestamp normalization, text extraction) that all adapters call.

**Spec references:** Doc 1 §4.1 (Source Adapter), §4.3 (Normalizer); Doc 2 §8.5.1 (Protocol and Registry), §8.6 (Pipeline — normalizer role).

**Scope — files created:**
- `src/limes/sources/base.py` — `SourceAdapter` protocol, `SourceFetchError`
- `src/limes/sources/registry.py` — `SourceRegistry` class, `build_default_registry()` function
- `src/limes/pipeline/normalize.py` — shared normalization utilities

**Out of scope:** Individual adapter implementations (WP-10 through WP-21). Pipeline run orchestration (WP-27).

**Task list:**
1. Implement `base.py`:
   - `SourceAdapter` protocol per Doc 2 §8.5.1 with attributes: `source_id`, `name`, `kind` (Literal["structured", "unstructured"]), `trust_rank`, `supports_backfill`, `supports_incremental`; methods: `fetch(since, until) -> Iterator[RawRecord]`, `normalize(record: RawRecord) -> NormalizedRecord`.
   - `SourceFetchError(LimesError)` — raised by `SourceRegistry.get` on unknown source (AC-38).
2. Implement `registry.py`:
   - `SourceRegistry` class with `register(adapter)`, `get(source_id) -> SourceAdapter` (raises `SourceFetchError` naming both the unknown source and the registered ones), `source_ids() -> list[str]`, `trust_rank(source_id) -> float`.
   - `build_default_registry() -> SourceRegistry`: the authoritative list of live sources. Initially empty — each adapter WP adds exactly one import and one `register()` call. **Import-time self-registration is rejected.** This is the only place the ingestable source set is defined.
   - At this stage, `build_default_registry()` returns an empty registry. Each subsequent adapter WP (WP-10…WP-21) adds one line.
3. Implement `normalize.py`:
   - `detect_language(text: str) -> str`: returns "de" or "en" using a simple heuristic or `langdetect`.
   - `normalize_timestamp(raw: str | datetime, source_format: str | None = None) -> datetime`: normalizes various timestamp formats to `datetime` using `python-dateutil`.
   - `extract_text_from_html(html: str) -> str`: extracts visible text from HTML using `lxml`.
   - `extract_text_from_xml(xml: str, xpath: str) -> str`: extracts text from XML at a given XPath.
4. Write unit tests for: `SourceRegistry.get` raises `SourceFetchError` naming both the unknown and registered sources (AC-38); `build_default_registry()` returns a registry with zero sources at this stage; normalization utilities produce correct outputs for known inputs.

**Contracts consumed:**
- `RawRecord`, `NormalizedRecord` types (WP-02)
- `SourceFetchError` (WP-02)
- `Ontology` (WP-03) — not directly, but adapters will use it via `NormalizedRecord`

**Contracts produced:**
- `SourceAdapter` protocol — consumed by WP-10…WP-21 (all adapters implement it)
- `SourceRegistry` and `build_default_registry()` — consumed by WP-26 (composition root)
- Normalization utilities — consumed by WP-10…WP-21 (all adapters call from their `normalize` methods)

**Acceptance criteria:**
- AC-38 (partial): `build_default_registry()` returns a registry (empty at this stage); an unknown source fails naming both the unknown and the registered ones.
- No production module constructs an empty `SourceRegistry` except `build_default_registry()`.
- Import-time self-registration is not used.

**Verification:**
```bash
ruff check src/limes/sources/base.py src/limes/sources/registry.py src/limes/pipeline/normalize.py
mypy src/limes/sources/base.py src/limes/sources/registry.py src/limes/pipeline/normalize.py
pytest tests/unit/test_source_registry.py tests/unit/test_normalize.py -v
python tools/check_docs.py
```

---

### WP-10 — GISCO/NUTS Adapter

| Field | Value |
|---|---|
| Phase | 2 |
| Depends on | WP-09 |
| Sizing | Single session |

**Objective:** Implement the GISCO/NUTS adapter that loads administrative regions, the NUTS hierarchy, and the postal-code-to-NUTS correspondence — the first cross-process reference data in the system.

**Spec references:** Doc 1 §5.2 (AdministrativeRegion, Location), §5.9 (Cross-Process State); Doc 2 §8.5.2 (source table: `gisco_nuts`), §5.3 (`:PostalCode` constraint).

**Scope — files created:**
- `src/limes/sources/gisco_nuts.py`
- One line added to `src/limes/sources/registry.py` (`build_default_registry`)

**Out of scope:** The lookup reader (WP-08, already built). Other adapters.

**Task list:**
1. Implement `GiscoNutsAdapter` implementing `SourceAdapter`:
   - `source_id = "gisco_nuts"`, `name = "GISCO/NUTS"`, `kind = "structured"`, `trust_rank = 1.00`, `supports_backfill = False`, `supports_incremental = False`.
   - `fetch(since, until)`: fetches the NUTS hierarchy CSV and the postcode correspondence CSV from the verified URLs in Doc 2 §8.5.2 (`/v2/pcode/csv/` for postcodes; NUTS_ID length determines level; parent by prefix). Yields `RawRecord` per file.
   - `normalize(record)`: parses CSV. Emits `AdministrativeRegion` entities, `PART_OF_REGION` relationships, and `LookupRow(kind="postal_code")` records. Level derives from `NUTS_ID` length. Parent derives from prefix. Handle mixed single/double quoting in the postcode file (Doc 2 §8.5.2).
2. Add to `build_default_registry()`: `from limes.sources.gisco_nuts import GiscoNutsAdapter` and `registry.register(GiscoNutsAdapter())`.
3. Write adapter tests using `respx` with recorded fixtures:
   - AC-04 (partial): Known input produces the exact expected record set including deterministic keys (`nuts_code` for regions, `(country_code, postal_code)` for lookup rows) and source attribution (`source_id = "gisco_nuts"`, `source_trust = 1.00`).
   - NUTS level is correctly derived from `NUTS_ID` length.
   - Postal-code lookup rows are emitted as `LookupRow(kind="postal_code")`.
   - No live network access in tests.

**Contracts consumed:**
- `SourceAdapter` protocol, `SourceRegistry` (WP-09)
- Normalization utilities (WP-09)
- `RawRecord`, `NormalizedRecord`, `EntityEndpoint`, `Assertion`, `LookupRow` types (WP-02)
- `Ontology` (WP-03) — via `NormalizedRecord`

**Contracts produced:**
- `GiscoNutsAdapter` class — registered in `build_default_registry()`, consumed by WP-27 (pipeline run)
- `:PostalCode` nodes (written by the loader from `LookupRow` records) — consumed by WP-08 (lookups), which is consumed by WP-11, WP-14, WP-19

**Acceptance criteria:**
- AC-04 (partial): Adapter produces correct records from recorded fixtures.
- Postal-code lookup rows are emitted as `LookupRow` objects, not as entity properties.
- `source_id` and `source_trust` are stamped on every assertion and entity.

**Verification:**
```bash
ruff check src/limes/sources/gisco_nuts.py
mypy src/limes/sources/gisco_nuts.py
pytest tests/unit/test_gisco_nuts_adapter.py -v
python -c "from limes.sources.registry import build_default_registry; r = build_default_registry(); assert 'gisco_nuts' in r.source_ids(); print('OK')"
python tools/check_docs.py
```

---

### WP-11 — GLEIF Adapter

| Field | Value |
|---|---|
| Phase | 2 |
| Depends on | WP-09 |
| Sizing | Single session |

**Objective:** Implement the GLEIF adapter that loads the legal-entity identifier backbone — corporations, headquarters, subsidiaries, and ownership stakes — using deterministic LEI keys.

**Spec references:** Doc 1 §5.2 (Corporation), §5.8 (Trust Rank 1.00); Doc 2 §8.5.2 (source table: `gleif`).

**Scope — files created:**
- `src/limes/sources/gleif.py`
- One line added to `build_default_registry()`

**Out of scope:** Entity resolution (GLEIF uses deterministic keys, no resolution needed).

**Task list:**
1. Implement `GleifAdapter` implementing `SourceAdapter`:
   - `source_id = "gleif"`, `name = "GLEIF"`, `kind = "structured"`, `trust_rank = 1.00`, `supports_backfill = True`, `supports_incremental = True`.
   - `fetch(since, until)`: fetches the GLEIF golden copy CSV. Yields `RawRecord`.
   - `normalize(record)`: parses CSV. Emits `Corporation` entities (deterministic key: `("lei", lei_value)`), `HEADQUARTERED_IN` relationships (to `Location` entities with coordinate hashes), `SUBSIDIARY_OF` relationships (Corporation → Corporation), `OWNS_STAKE_IN` relationships with percentage where available.
   - Uses `postal_code_to_nuts` from WP-08 to assign `LOCATED_IN` for headquarters addresses. A miss leaves the field unassigned and is counted, never guessed (Doc 2 §8.16).
2. Add to `build_default_registry()`.
3. Write adapter tests with `respx` fixtures: deterministic keys use LEI; source attribution correct; `supports_incremental = True`.

**Contracts consumed:**
- `SourceAdapter` protocol (WP-09)
- `postal_code_to_nuts()` (WP-08) — for region assignment
- Normalization utilities (WP-09)

**Contracts produced:**
- `GleifAdapter` — registered, consumed by WP-27

**Acceptance criteria:**
- AC-04 (partial): Correct records from fixtures with LEI deterministic keys.
- AC-16 (partial): Deterministic keys are present on all assertions (LEI), meaning resolution will short-circuit with no embedding.

**Verification:**
```bash
ruff check src/limes/sources/gleif.py
mypy src/limes/sources/gleif.py
pytest tests/unit/test_gleif_adapter.py -v
python tools/check_docs.py
```

---

### WP-12 — EUR-Lex Adapter

| Field | Value |
|---|---|
| Phase | 2 |
| Depends on | WP-09 |
| Sizing | Single session |

**Objective:** Implement the EUR-Lex adapter that loads EU legal acts, topics, and their citation relationships via the Cellar SPARQL endpoint.

**Spec references:** Doc 2 §8.5.2 (source table: `eurlex`); Doc 1 §5.2 (LegalAct, Topic), §5.4 (ADOPTED, AMENDS, REPEALS, CITES, ABOUT_TOPIC, APPLIES_TO).

**Scope — files created:**
- `src/limes/sources/eurlex.py`
- One line added to `build_default_registry()`

**Task list:**
1. Implement `EurlexAdapter`:
   - `source_id = "eurlex"`, `name = "EUR-Lex"`, `kind = "structured"`, `trust_rank = 1.00`, `supports_backfill = True`, `supports_incremental = True`.
   - `fetch(since, until)`: queries Cellar SPARQL for legal acts adopted in the window. Yields `RawRecord` (XML/JSON).
   - `normalize(record)`: emits `LegalAct` entities (deterministic key: `("celex", celex_number)`), `Topic` entities (EuroVoc, CPV), `ADOPTED`, `AMENDS`, `REPEALS`, `CITES`, `ABOUT_TOPIC`, `APPLIES_TO` relationships. Non-temporal relations (`AMENDS`, `REPEALS`, `CITES`) have `temporal: false` per the ontology.
2. Add to `build_default_registry()`.
3. Write adapter tests with `respx` fixtures.

**Contracts consumed:** `SourceAdapter` protocol, normalization utilities (WP-09).

**Contracts produced:** `EurlexAdapter` — registered, consumed by WP-27.

**Acceptance criteria:** AC-04 (partial): correct records from fixtures with CELEX deterministic keys.

**Verification:**
```bash
ruff check src/limes/sources/eurlex.py
mypy src/limes/sources/eurlex.py
pytest tests/unit/test_eurlex_adapter.py -v
python tools/check_docs.py
```

---

### WP-13 — FSD Adapter

| Field | Value |
|---|---|
| Phase | 2 |
| Depends on | WP-09 |
| Sizing | Single session |

**Objective:** Implement the EU Financial Sanctions Database adapter that loads sanctions with their targets, imposing authorities, and establishing legal acts.

**Spec references:** Doc 1 §5.4 (TARGETS, IMPOSED_BY, ESTABLISHED_BY — decomposed for three sources/intervals); Doc 2 §8.5.2 (source table: `fsd`).

**Scope — files created:**
- `src/limes/sources/fsd.py`
- One line added to `build_default_registry()`

**Task list:**
1. Implement `FsdAdapter`:
   - `source_id = "fsd"`, `name = "EU FSD"`, `kind = "structured"`, `trust_rank = 1.00`, `supports_backfill = True`, `supports_incremental = True`.
   - `fetch`: fetches consolidated XML from the FSD.
   - `normalize`: emits `Sanction` entities (deterministic key: `("fsd_id", id_plus_regime)`), `TARGETS` (Sanction → Person/Corporation/Country/Topic), `IMPOSED_BY` (Sanction → Country/IGO), `ESTABLISHED_BY` (Sanction → LegalAct). The three-way decomposition per Doc 1 §5.4 is critical: each relation has its own source and validity interval. `ESTABLISHED_BY` is non-temporal.
2. Add to `build_default_registry()`.
3. Write adapter tests with `respx` fixtures: verify the three-way sanction decomposition; deterministic key includes regime.

**Contracts consumed:** `SourceAdapter` protocol, normalization utilities (WP-09).

**Contracts produced:** `FsdAdapter` — registered, consumed by WP-27.

**Acceptance criteria:** AC-04 (partial): correct records with three-way sanction decomposition and FSD ID + regime deterministic keys.

**Verification:**
```bash
ruff check src/limes/sources/fsd.py
mypy src/limes/sources/fsd.py
pytest tests/unit/test_fsd_adapter.py -v
python tools/check_docs.py
```

---

### WP-14 — TED Adapter

| Field | Value |
|---|---|
| Phase | 2 |
| Depends on | WP-09 |
| Sizing | Single session |

**Objective:** Implement the TED (Tenders Electronic Daily) adapter that loads public procurement contracts, awards, and buyers.

**Spec references:** Doc 2 §8.5.2 (source table: `ted`); Doc 1 §5.4 (AWARDED_TO, BUYER_OF, ABOUT_TOPIC).

**Scope — files created:**
- `src/limes/sources/ted.py`
- One line added to `build_default_registry()`

**Task list:**
1. Implement `TedAdapter`:
   - `source_id = "ted"`, `name = "TED"`, `kind = "structured"`, `trust_rank = 1.00`, `supports_backfill = True`, `supports_incremental = True`.
   - `fetch`: fetches bulk XML from TED.
   - `normalize`: emits `Contract` entities (deterministic key: `("ted_notice_id", id)`), `Corporation` entities for awarded suppliers (LEI where available), `PublicBody` entities for buyers (TED buyer ID), `AWARDED_TO` (Contract → Corporation), `BUYER_OF` (PublicBody → Contract), `ABOUT_TOPIC` (Contract → Topic, CPV codes).
   - Uses `postal_code_to_nuts` (WP-08) for buyer region assignment.
2. Add to `build_default_registry()`.
3. Write adapter tests with `respx` fixtures.

**Contracts consumed:** `SourceAdapter` protocol (WP-09), `postal_code_to_nuts()` (WP-08).

**Contracts produced:** `TedAdapter` — registered, consumed by WP-27.

**Acceptance criteria:** AC-04 (partial): correct records with TED notice ID deterministic keys.

**Verification:**
```bash
ruff check src/limes/sources/ted.py
mypy src/limes/sources/ted.py
pytest tests/unit/test_ted_adapter.py -v
python tools/check_docs.py
```

---

### WP-15 — Transparency Register Adapter

| Field | Value |
|---|---|
| Phase | 2 |
| Depends on | WP-09 |
| Sizing | Single session |

**Objective:** Implement the EU Transparency Register adapter that loads interest groups, their lobbying targets, and meeting records.

**Spec references:** Doc 2 §8.5.2 (source table: `transparency_register`); Doc 1 §5.4 (LOBBIES_FOR, MET_WITH, MEMBER_OF).

**Scope — files created:**
- `src/limes/sources/transparency_register.py`
- One line added to `build_default_registry()`

**Task list:**
1. Implement `TransparencyRegisterAdapter`:
   - `source_id = "transparency_register"`, `name = "EU Transparency Register"`, `kind = "structured"`, `trust_rank = 1.00`, `supports_backfill = True`, `supports_incremental = True`.
   - `fetch`: fetches export XML.
   - `normalize`: emits `InterestGroup` entities (deterministic key: `("transparency_register_id", id)`), `LOBBIES_FOR` (InterestGroup → Corporation/PoliticalParty/Topic), `MET_WITH` (InterestGroup/Person → Person/PublicBody), `MEMBER_OF` (Person/Corporation → InterestGroup).
2. Add to `build_default_registry()`.
3. Write adapter tests with `respx` fixtures.

**Contracts consumed:** `SourceAdapter` protocol, normalization utilities (WP-09).

**Contracts produced:** `TransparencyRegisterAdapter` — registered, consumed by WP-27.

**Acceptance criteria:** AC-04 (partial): correct records with Transparency Register ID deterministic keys.

**Verification:**
```bash
ruff check src/limes/sources/transparency_register.py
mypy src/limes/sources/transparency_register.py
pytest tests/unit/test_transparency_register_adapter.py -v
python tools/check_docs.py
```

---

### WP-16 — Bundestag DIP Adapter

| Field | Value |
|---|---|
| Phase | 2 |
| Depends on | WP-09 |
| Sizing | Single session |

**Objective:** Implement the Bundestag DIP (Documentation and Information System for Parliamentary Material) adapter that loads persons, parties, offices, and parliamentary documents — the first adapter using the reified `Office` node.

**Spec references:** Doc 1 §5.2 (Person, PoliticalParty, Office — reified), DD-13; Doc 2 §8.5.2 (source table: `bundestag_dip`).

**Scope — files created:**
- `src/limes/sources/bundestag_dip.py`
- One line added to `build_default_registry()`

**Task list:**
1. Implement `BundestagDipAdapter`:
   - `source_id = "bundestag_dip"`, `name = "Bundestag DIP"`, `kind = "structured"`, `trust_rank = 1.00`, `supports_backfill = True`, `supports_incremental = True`.
   - `fetch`: queries the DIP API for persons, offices, and documents in the window.
   - `normalize`: emits `Person` entities (deterministic key: `("bundestag_id", id)`), `PoliticalParty` entities (Wikidata QID where known), `Office` entities (deterministic key: `("body_id_plus_title_plus_interval", ...)`), `HOLDS_OFFICE` (Person → Office, temporal), `OFFICE_AT` (Office → PublicBody/PoliticalParty, temporal), `Document` entities (content hash). `MEMBER_OF` (Person → PoliticalParty).
   - The `Office` entity is reified per DD-13: its identifying key is body ID + title + interval, making "who held this position when" a joinable question.
2. Add to `build_default_registry()`.
3. Write adapter tests with `respx` fixtures: verify `Office` reification with correct identifying key; `HOLDS_OFFICE` and `OFFICE_AT` carry temporal validity.

**Contracts consumed:** `SourceAdapter` protocol, normalization utilities (WP-09).

**Contracts produced:** `BundestagDipAdapter` — registered, consumed by WP-27.

**Acceptance criteria:** AC-04 (partial): correct records with Bundestag ID and Office reification.

**Verification:**
```bash
ruff check src/limes/sources/bundestag_dip.py
mypy src/limes/sources/bundestag_dip.py
pytest tests/unit/test_bundestag_dip_adapter.py -v
python tools/check_docs.py
```

---

### WP-17 — Gesetze im Internet Adapter

| Field | Value |
|---|---|
| Phase | 2 |
| Depends on | WP-09 |
| Sizing | Single session |

**Objective:** Implement the Gesetze im Internet adapter that loads German federal laws and their topic assignments.

**Spec references:** Doc 2 §8.5.2 (source table: `gesetze_im_internet`); Doc 1 §5.2 (LegalAct — Bundesgesetzblatt citation).

**Scope — files created:**
- `src/limes/sources/gesetze_im_internet.py`
- One line added to `build_default_registry()`

**Task list:**
1. Implement `GesetzeImInternetAdapter`:
   - `source_id = "gesetze_im_internet"`, `name = "Gesetze im Internet"`, `kind = "structured"`, `trust_rank = 1.00`, `supports_backfill = True`, `supports_incremental = True`.
   - `fetch`: fetches the index page, then individual law XML files.
   - `normalize`: emits `LegalAct` entities (deterministic key: `("bundesgesetzblatt_citation", citation)`), `Topic` entities, `APPLIES_TO` (LegalAct → Topic), `ABOUT_TOPIC` (LegalAct → Topic).
2. Add to `build_default_registry()`.
3. Write adapter tests with `respx` fixtures.

**Contracts consumed:** `SourceAdapter` protocol, normalization utilities (WP-09).

**Contracts produced:** `GesetzeImInternetAdapter` — registered, consumed by WP-27.

**Acceptance criteria:** AC-04 (partial): correct records with Bundesgesetzblatt citation deterministic keys.

**Verification:**
```bash
ruff check src/limes/sources/gesetze_im_internet.py
mypy src/limes/sources/gesetze_im_internet.py
pytest tests/unit/test_gesetze_im_internet_adapter.py -v
python tools/check_docs.py
```

---

### WP-18 — Wikidata Adapter (Enrichment Only)

| Field | Value |
|---|---|
| Phase | 2 |
| Depends on | WP-09 |
| Sizing | Single session |

**Objective:** Implement the Wikidata adapter as an enrichment service called by the resolver, not as a bulk-ingestion source. It provides QID-based identification and alias enrichment without loading entities into the graph.

**Spec references:** Doc 1 §5.8 (Trust Rank 0.90); Doc 2 §8.5.2 (source table: `wikidata` — "SPARQL, read-only enrichment; aliases and QIDs; never bulk-loaded; n/a").

**Scope — files created:**
- `src/limes/sources/wikidata.py`
- One line added to `build_default_registry()` — **but registered with a flag or method indicating it is enrichment-only, not ingestable** (per Doc 2 §8.5.2: "n/a" for incremental, does not ingest).

**Task list:**
1. Implement `WikidataAdapter`:
   - `source_id = "wikidata"`, `name = "Wikidata"`, `kind = "structured"`, `trust_rank = 0.90`, `supports_backfill = False`, `supports_incremental = False`.
   - Does not implement `fetch`/`normalize` in the standard way — instead exposes `enrich(entity_type: str, label: str) -> WikidataMatch | None` for the resolver (Doc 2 §8.5.2). Returns `None` on ambiguity rather than guessing.
   - `WikidataMatch` is a small type returned to the resolver: `qid: str`, `label: str`, `aliases: list[str]`.
   - `fetch` and `normalize` raise `NotImplementedError` — this adapter is never run through `execute_run`.
2. Add to `build_default_registry()` with a comment noting enrichment-only status.
3. Write adapter tests with `respx` fixtures: `enrich` returns a match for a known entity; returns `None` for an ambiguous query.

**Contracts consumed:** `SourceAdapter` protocol (WP-09) — partially; this adapter deviates from the standard protocol.

**Contracts produced:** `WikidataAdapter.enrich()` — consumed by WP-25 (entity resolution).

**Acceptance criteria:**
- `enrich` returns a `WikidataMatch` with QID for a known, unambiguous entity.
- `enrich` returns `None` for an ambiguous query.
- The adapter is not executable through `execute_run` (its `fetch` raises `NotImplementedError`).

**Verification:**
```bash
ruff check src/limes/sources/wikidata.py
mypy src/limes/sources/wikidata.py
pytest tests/unit/test_wikidata_adapter.py -v
python tools/check_docs.py
```

---

### WP-19 — OSM Adapter

| Field | Value |
|---|---|
| Phase | 2 |
| Depends on | WP-09 |
| Sizing | Single session |

**Objective:** Implement the OpenStreetMap adapter that loads critical infrastructure assets (KRITIS) within the German bounding box.

**Spec references:** Doc 1 §5.2 (Asset — OSM ID, KRITIS taxonomy), §5.8 (Trust Rank 0.75), §11.3.3 (OSM coverage limitations); Doc 2 §8.5.2 (source table: `osm`).

**Scope — files created:**
- `src/limes/sources/osm.py`
- One line added to `build_default_registry()`

**Task list:**
1. Implement `OsmAdapter`:
   - `source_id = "osm"`, `name = "OpenStreetMap"`, `kind = "structured"`, `trust_rank = 0.75`, `supports_backfill = False`, `supports_incremental = False`.
   - `fetch`: queries Overpass API for KRITIS-relevant tags within the German bounding box. Yields `RawRecord`.
   - `normalize`: emits `Asset` entities (deterministic key: `("osm_id", id)`), `Location` entities (coordinate hash), `LOCATED_IN` (Asset/Location → AdministrativeRegion via `postal_code_to_nuts` or coordinate-based region assignment), `OPERATES` (Corporation/PublicBody → Asset), `Topic` entities (KRITIS sector taxonomy).
   - Uses `postal_code_to_nuts` (WP-08) where postal codes are available; otherwise leaves region unassigned and counts it.
2. Add to `build_default_registry()`.
3. Write adapter tests with `respx` fixtures: OSM ID deterministic keys; KRITIS topic assignment.

**Contracts consumed:** `SourceAdapter` protocol (WP-09), `postal_code_to_nuts()` (WP-08).

**Contracts produced:** `OsmAdapter` — registered, consumed by WP-27.

**Acceptance criteria:** AC-04 (partial): correct records with OSM ID deterministic keys and KRITIS topic assignment.

**Verification:**
```bash
ruff check src/limes/sources/osm.py
mypy src/limes/sources/osm.py
pytest tests/unit/test_osm_adapter.py -v
python tools/check_docs.py
```

---

### WP-20 — OffeneRegister Adapter

| Field | Value |
|---|---|
| Phase | 2 |
| Depends on | WP-09 |
| Sizing | Single session |

**Objective:** Implement the OffeneRegister adapter that loads German company directorships with honest vintage — the dataset's publication date as `recorded_at`, not the ingestion timestamp.

**Spec references:** Doc 1 §5.8 (Trust Rank 0.30 — lowest, deliberately), DD-15; Doc 2 §8.5.2 (source table: `offeneregister` — "sets `recorded_at` to the dataset's publication date, never the ingestion timestamp").

**Scope — files created:**
- `src/limes/sources/offeneregister.py`
- One line added to `build_default_registry()`

**Task list:**
1. Implement `OffeneRegisterAdapter`:
   - `source_id = "offeneregister"`, `name = "OffeneRegister"`, `kind = "structured"`, `trust_rank = 0.30`, `supports_backfill = False`, `supports_incremental = False`.
   - `fetch`: fetches bulk JSON.
   - `normalize`: emits `Corporation` entities (deterministic key: `("german_register_number", reg_num)`), `Person` entities (resolved, no deterministic key), `DIRECTOR_OF` (Person → Corporation, temporal), `OWNS_STAKE_IN` where available.
   - **Critical:** Sets `recorded_at` on every assertion to the dataset's publication date from the OffeneRegister metadata, never to `datetime.now()`. This is what makes multi-year-stale directorships honestly representable and what makes the 0.30 trust rank safe (Doc 2 §8.5.2, DD-15).
2. Add to `build_default_registry()`.
3. Write adapter tests with `respx` fixtures: verify `recorded_at` is the dataset publication date, not ingestion time; verify `source_trust = 0.30`.

**Contracts consumed:** `SourceAdapter` protocol, normalization utilities (WP-09).

**Contracts produced:** `OffeneRegisterAdapter` — registered, consumed by WP-27.

**Acceptance criteria:**
- AC-04 (partial): correct records with German register number deterministic keys.
- `recorded_at` is the dataset publication date, not `datetime.now()`.

**Verification:**
```bash
ruff check src/limes/sources/offeneregister.py
mypy src/limes/sources/offeneregister.py
pytest tests/unit/test_offeneregister_adapter.py -v
python tools/check_docs.py
```

---

### WP-21 — Unstructured Adapters: GDELT + Feeds

| Field | Value |
|---|---|
| Phase | 3 |
| Depends on | WP-09 |
| Sizing | Single session |

**Objective:** Implement the two unstructured source adapters — GDELT (15-minute event CSV) and curated RSS/Atom feeds — that produce `DocumentPayload` records for the extraction pipeline.

**Spec references:** Doc 1 §3.2 (Two Asymmetric Ingestion Paths), §5.8 (GDELT 0.50, feeds 0.60–0.70); Doc 2 §8.5.2 (source tables: `gdelt`, `feeds`).

**Scope — files created:**
- `src/limes/sources/gdelt.py`
- `src/limes/sources/feeds.py`
- `ontology/feeds.yaml` — feed configuration (URLs, language, trust rank per feed)
- Two lines added to `build_default_registry()`

**Task list:**
1. Implement `GdeltAdapter`:
   - `source_id = "gdelt"`, `name = "GDELT"`, `kind = "unstructured"`, `trust_rank = 0.50`, `supports_backfill = True`, `supports_incremental = True`.
   - `fetch(since, until)`: fetches 15-minute CSV files for the window. Yields `RawRecord` per file.
   - `normalize(record)`: parses CSV. Emits `DocumentPayload` with `content_hash`, `title`, `body`, `language`, `published_at`, `url`. Also emits `Event` entities and `ACTOR_IN`/`TARGET_OF`/`OCCURRED_IN` relationships where GDELT provides actor and action codes — these are deterministic-keyed and need no extraction. The document text is emitted for passage extraction.
2. Implement `FeedsAdapter`:
   - `source_id = "feeds"`, `name = "Curated Feeds"`, `kind = "unstructured"`, `trust_rank = 0.60` (default; per-feed override in `feeds.yaml`), `supports_backfill = True`, `supports_incremental = True`.
   - `fetch(since, until)`: fetches RSS/Atom feeds listed in `feeds.yaml` using `feedparser`. Yields `RawRecord` per entry.
   - `normalize(record)`: emits `DocumentPayload` with title, body (extracted from HTML), language (detected), `published_at`, URL.
3. Write `feeds.yaml` with a small initial set of curated feeds (e.g., Commission RAPID, Bundesregierung press releases, and a curated German news outlet). Each entry: `url`, `name`, `language`, `trust_rank`.
4. Add both adapters to `build_default_registry()`.
5. Write adapter tests with `respx` fixtures: GDELT CSV parsing; feed XML parsing; `DocumentPayload` fields correct; `published_at` normalized.

**Contracts consumed:** `SourceAdapter` protocol, normalization utilities (WP-09), `DocumentPayload` type (WP-02).

**Contracts produced:** `GdeltAdapter`, `FeedsAdapter` — registered, consumed by WP-27 (pipeline run, unstructured path).

**Acceptance criteria:**
- AC-04 (partial): both adapters produce correct `DocumentPayload` records from fixtures.
- GDELT events carry `ACTOR_IN`, `TARGET_OF`, `OCCURRED_IN` with correct directional asymmetry (Doc 1 §5.4).
- Feed documents carry correct language detection.

**Verification:**
```bash
ruff check src/limes/sources/gdelt.py src/limes/sources/feeds.py
mypy src/limes/sources/gdelt.py src/limes/sources/feeds.py
pytest tests/unit/test_gdelt_adapter.py tests/unit/test_feeds_adapter.py -v
python tools/check_docs.py
```

---

### WP-22 — Extractor: Protocol, OpenRouter Client, Schema, Prompts

| Field | Value |
|---|---|
| Phase | 3 |
| Depends on | WP-02, WP-03, WP-06 |
| Sizing | Single session |

**Objective:** Implement the extraction protocol, the OpenRouter client (one client for chat, embeddings, and catalogue), the versioned JSON Schema for extraction output, and the prompt templates for extraction and adjudication.

**Spec references:** Doc 1 §4.5 (Extractor), §7.3 (Untrusted Ingested Content), §9.3 (Cost Control); Doc 2 §8.7 (Extraction), §8.7.6 (OpenRouter Client), §8.7.3 (Output Schema), §8.7.4 (Batching and Evidence Spans).

**Scope — files created:**
- `src/limes/extraction/base.py` — `Extractor` protocol, `ExtractionResult` type
- `src/limes/extraction/openrouter_client.py` — `OpenRouterClient` class
- `src/limes/extraction/openrouter.py` — `OpenRouterExtractor` implementing `Extractor`
- `src/limes/extraction/ollama.py` — `OllamaExtractor` (laptop-only, C-05)
- `src/limes/extraction/schema.py` — versioned JSON Schema for extraction output
- `src/limes/extraction/prompts/extraction_v1.0.0.md` — extraction prompt
- `src/limes/extraction/prompts/adjudication_v1.0.0.md` — adjudication prompt

**Out of scope:** Extraction cache (WP-23). The NL-to-Cypher prompt (WP-33).

**Task list:**
1. Implement `base.py`:
   - `Extractor` protocol per Doc 2 §8.7.1: `model_id` attribute, `extract(passages, ontology, prompt_version, schema_version) -> ExtractionResult`.
   - `ExtractionResult` per Doc 2 §8.7.1: `assertions: list[ExtractedAssertion]`, `input_tokens`, `output_tokens`, `raw_response`, `parse_errors`.
2. Implement `openrouter_client.py`:
   - `OpenRouterClient` per Doc 2 §8.7.6: `__init__(settings, governor)`, `complete(messages, model_id, purpose, json_schema) -> tuple[str, int, int]`, `embed(texts, model_id) -> list[list[float]]`, `catalogue() -> list[dict]`.
   - Calls `governor.check` before every request and `governor.commit` after, using reported token usage. This is the **only module that writes `:CostLedgerEntry`** (via the governor).
   - Retry policy per Doc 2 §11: exponential backoff from 2s, factor 2, jittered, max 4 attempts, on connection errors, timeouts, 429, 5xx. Never on other 4xx.
   - API key never reaches a log line (verified by the redaction processor).
   - Ledger entries written only for attempts that returned token usage.
3. Implement `schema.py`:
   - Versioned JSON Schema per Doc 2 §8.7.3: `additionalProperties: false` throughout. Requires `passage_index`, `subject`, `relation`, `object`, `confidence`, `evidence_start`, `evidence_end`. Mentions require `surface` and `type`. `relation` and mention `type` are validated against the ontology after parsing.
4. Implement `openrouter.py`:
   - `OpenRouterExtractor` implementing `Extractor`. Uses `OpenRouterClient.complete` with the extraction prompt and JSON schema. Parses the response into `ExtractionResult`.
   - Batching per Doc 2 §8.7.4: one call per document carrying up to `LIMES_EXTRACTION_MAX_PASSAGES_PER_CALL` passages, capped at `LIMES_EXTRACTION_MAX_INPUT_TOKENS`. Documents exceeding either bound split into multiple calls.
   - Maps passage-local offsets to document offsets using each passage's `doc_start`. Rejects assertions whose mapped span does not contain subject or object surface as `EVIDENCE_SPAN_MISMATCH` (AC-13).
5. Implement `ollama.py`:
   - `OllamaExtractor` for laptop-only use (C-05). Same protocol. Uses a local Ollama endpoint. Does not go through the governor or ledger (no paid calls). Marked as laptop-only in docstring and AGENTS.md.
6. Write prompt files:
   - `extraction_v1.0.0.md`: instructs the model to extract typed pre-resolution assertions from passages. Document text is supplied as explicitly delimited data, never concatenated into the instruction (Doc 1 §7.3). No tool definitions. Output must conform to the JSON schema.
   - `adjudication_v1.0.0.md`: instructs the model to adjudicate between two candidate entity mentions, returning a yes/no decision with confidence.
7. Write unit and integration tests:
   - AC-12 (partial): A cache hit (simulated by pre-populating) issues no paid call.
   - AC-13: Evidence span mismatch rejection.
   - Governor is called before and after every request.
   - Retry policy on 429/5xx; no retry on 4xx (except 429).
   - API key does not appear in any log line.

**Contracts consumed:**
- `Governor` (WP-06) — for budget enforcement
- `Ontology` (WP-03) — for relation/type validation
- `ExtractedAssertion`, `Passage`, `ExtractionResult` types (WP-02)
- `Settings` (WP-02) — for model IDs, API key, batching parameters

**Contracts produced:**
- `Extractor` protocol — consumed by WP-26 (composition root), WP-27 (pipeline run), WP-30 (evaluation)
- `OpenRouterClient` — consumed by WP-25 (resolution, for embeddings), WP-26 (composition root), WP-29 (model selection), WP-33 (NL-to-Cypher)
- `OpenRouterExtractor` — consumed by WP-26 (composition root)
- Extraction JSON Schema — consumed by `OpenRouterExtractor`
- Prompt files — consumed by `OpenRouterExtractor` and the adjudication module (WP-25)

**Acceptance criteria:**
- AC-13: An assertion whose evidence span does not contain its subject or object surface is rejected as `EVIDENCE_SPAN_MISMATCH`.
- The OpenRouter client calls `governor.check` before and `governor.commit` after every request.
- The API key does not appear in any log line.
- Retry policy matches Doc 2 §11.

**Verification:**
```bash
ruff check src/limes/extraction/base.py src/limes/extraction/openrouter_client.py src/limes/extraction/openrouter.py src/limes/extraction/ollama.py src/limes/extraction/schema.py
mypy src/limes/extraction/
pytest tests/unit/test_extractor.py tests/unit/test_openrouter_client.py tests/integration/test_extraction_evidence_span.py -v
python tools/check_docs.py
```

---

### WP-23 — Extraction Cache

| Field | Value |
|---|---|
| Phase | 3 |
| Depends on | WP-02, WP-04 |
| Sizing | Single session |

**Objective:** Implement the extraction cache that stores and retrieves extraction results keyed by content hash, prompt version, schema version, and model ID — making re-extraction explicit and a full rebuild free while the version triple is unchanged.

**Spec references:** Doc 1 §9.4 (Re-extraction), DD-08; Doc 2 §8.7.5 (Cache), §5.8 (`:ExtractionCacheEntry` schema).

**Scope — files created:**
- `src/limes/extraction/cache.py`

**Out of scope:** The gate that calls the cache (WP-24). The extractor (WP-22).

**Task list:**
1. Implement `extraction/cache.py`:
   - `cache_key(content_hash, prompt_version, schema_version, model_id) -> str`: returns `SHA-256(content_hash | prompt_version | schema_version | model_id)`.
   - `get(driver, content_hash, prompt_version, schema_version, model_id) -> ExtractionResult | None`: reads `:ExtractionCacheEntry` by `cache_key`. Returns `None` on miss.
   - `put(driver, content_hash, prompt_version, schema_version, model_id, result: ExtractionResult) -> None`: writes `:ExtractionCacheEntry` with `cache_key`, `content_hash`, `prompt_version`, `schema_version`, `model_id`, `result_json` (serialized `ExtractionResult`), `created_at`.
   - `exists(driver, content_hash, prompt_version, schema_version, model_id) -> bool`: checks existence without deserializing.
2. Write integration tests against a disposable Neo4j container:
   - AC-12: A cache hit on the current version triple issues no paid call and is recorded as cached.
   - AC-33 (partial): A full rebuild with unchanged version triple hits the cache for every document, issuing zero paid calls.
   - A version change (prompt, schema, or model) produces a cache miss.
   - `cache_key` is deterministic across processes.

**Contracts consumed:**
- `GraphDriver` (WP-04)
- `ExtractionResult` type (WP-02)

**Contracts produced:**
- `get()`, `put()`, `exists()`, `cache_key()` — consumed by WP-24 (gate, for cache-hit check), WP-27 (pipeline run)

**Acceptance criteria:**
- AC-12: Cache hit issues no paid call.
- AC-33 (partial): Full rebuild with unchanged triple hits cache.
- Cache key is deterministic and version-sensitive.

**Verification:**
```bash
ruff check src/limes/extraction/cache.py
mypy src/limes/extraction/cache.py
pytest tests/integration/test_extraction_cache.py -v
python tools/check_docs.py
```

---

### WP-24 — Gate: spaCy NER, Passage Selection, Idempotency

| Field | Value |
|---|---|
| Phase | 3 |
| Depends on | WP-02, WP-23 |
| Sizing | Single session |

**Objective:** Implement the deterministic gate that filters unstructured documents before any paid extraction call — content-hash deduplication, spaCy NER, and passage selection by mention density.

**Spec references:** Doc 1 §4.4 (Gate), DD-06; Doc 2 §8.6.3 (Gate), §8.6.3 (passage selection).

**Scope — files created:**
- `src/limes/pipeline/gate.py` — `gate_document()`, `select_passages()`
- `src/limes/pipeline/passages.py` — passage windowing utilities
- `src/limes/pipeline/idempotency.py` — content-hash deduplication check

**Out of scope:** The extractor (WP-22). The pipeline run that calls the gate (WP-27).

**Task list:**
1. Implement `idempotency.py`:
   - `is_already_extracted(driver, content_hash, prompt_version, schema_version, model_id) -> bool`: calls `cache.exists()` (WP-23). This is the zero-cost short-circuit.
2. Implement `passages.py`:
   - `window_passages(text: str, sentences: list, entity_positions: list[int], window_sentences: int) -> list[Passage]`: creates overlapping windows centered on sentences with at least `min_mentions` recognized entities. Each passage carries `index`, `text`, `doc_start`, `doc_end` (offsets in the source document).
3. Implement `gate.py`:
   - `gate_document(doc: DocumentPayload, ctx: GateContext) -> GateDecision` per Doc 2 §8.6.3:
     a. Cache-hit check via `idempotency.is_already_extracted`. If hit, return `GateDecision(passed=False, reason="cache_hit", passages=[])`.
     b. Load spaCy model matching detected language (`de_core_news_md` or `en_core_web_md`).
     c. Run NER. Collect `NerSpan` objects.
     d. Call `select_passages(text, language, entities, window_sentences, min_mentions)`.
     e. If zero passages, return `GateDecision(passed=False, reason="below_mention_threshold", passages=[])`.
     f. Otherwise return `GateDecision(passed=True, reason="passed", passages=[...])`.
   - `select_passages(text, language, entities, window_sentences, min_mentions) -> list[Passage]`: calls `passages.window_passages`. A document producing zero passages is recorded as gated-out with the reason — never silently dropped (Doc 2 §8.6.3, §11 governing principle).
4. Write unit tests:
   - AC-11: Gate rejects documents below the mention threshold and records the reason.
   - AC-12 (partial): Cache-hit short-circuits at zero cost.
   - Passage offsets are correct relative to the document.
   - German and English spaCy models are loaded correctly.
   - A document with zero passages produces `GateDecision(passed=False, reason="below_mention_threshold")`.

**Contracts consumed:**
- `GateContext` (will be defined in WP-26; for now, accept `settings`, `driver`, `nlp_de`, `nlp_en` directly or define a local type)
- `DocumentPayload`, `Passage`, `NerSpan`, `GateDecision` types (WP-02)
- `cache.exists()` (WP-23)
- `Settings` (WP-02) — for `LIMES_GATE_MIN_ENTITY_MENTIONS`, spaCy model names

**Contracts produced:**
- `gate_document()`, `select_passages()` — consumed by WP-27 (pipeline run)
- `GateContext` will be finalized in WP-26 — the composition root constructs it with spaCy models loaded

**Acceptance criteria:**
- AC-11: Documents below mention threshold are rejected with reason recorded.
- AC-12 (partial): Cache hit short-circuits at zero cost.
- No document is silently dropped.

**Verification:**
```bash
ruff check src/limes/pipeline/gate.py src/limes/pipeline/passages.py src/limes/pipeline/idempotency.py
mypy src/limes/pipeline/gate.py src/limes/pipeline/passages.py src/limes/pipeline/idempotency.py
pytest tests/unit/test_gate.py -v
python tools/check_docs.py
```

---

### WP-25 — Entity Resolution

| Field | Value |
|---|---|
| Phase | 4 |
| Depends on | WP-03, WP-04, WP-22 |
| Sizing | Single session |

**Objective:** Implement the entity resolution pipeline that converts pre-resolution `ExtractedAssertion` objects into resolved `Assertion` objects — the named converter from mentions to identified endpoints, using deterministic keys, vector blocking, adjudication, and minting.

**Spec references:** Doc 1 §4.6 (Entity Resolver), §5.5 (Two Assertion Types), DD-04 (Non-destructive reversible merges); Doc 2 §8.8 (Resolution), §8.8.3 (Thresholds), §8.8.5 (Mention Policy).

**Scope — files created:**
- `src/limes/resolution/keys.py` — deterministic key extraction
- `src/limes/resolution/blocking.py` — embedding and candidate retrieval
- `src/limes/resolution/adjudicate.py` — adjudication call
- `src/limes/resolution/link.py` — `:Mention` and `SAME_AS` management
- `src/limes/resolution/resolve.py` — `resolve_assertions()` converter

**Out of scope:** The loader that materializes resolved entities (WP-07, already built). The Wikidata enrichment (WP-18, already built — `enrich()` is called from here).

**Task list:**
1. Implement `keys.py`:
   - `deterministic_key(mention: Mention, ontology: Ontology) -> tuple[str, str] | None`: extracts a deterministic key from the mention's surface text using patterns appropriate to the inferred type (e.g., LEI pattern for Corporation, QID for Person). Returns `None` when no key is found. When present, resolution terminates with confidence 1.0 (Doc 2 §8.8.1).
2. Implement `blocking.py`:
   - `embed(texts: list[str], client: OpenRouterClient, model_id: str) -> list[list[float]]`: embeds mention surface + type + contextual qualifier. Uses a permanent cache keyed by text and model.
   - `candidates(driver: GraphDriver, embedding: list[float], entity_type: str, limit: int) -> list[dict]`: queries the vector index for nearest entities of the given type. Returns candidates with cosine similarity scores.
3. Implement `adjudicate.py`:
   - `adjudicate(mention: Mention, candidates: list[dict], client: OpenRouterClient, prompt_version: str) -> tuple[str | None, float]`: calls the adjudication model with the mention and top candidates. Returns `(entity_id, confidence)` or `(None, 0.0)`. Confidence capped at 0.90 (Doc 2 §8.8.3).
4. Implement `link.py`:
   - `create_mention(driver: GraphDriver, mention: Mention, document_id: str) -> str`: creates a `:Mention` node, returns `mention_id`. **Every extracted endpoint gets a `:Mention` node** (Doc 2 §8.8.5), including deterministic-key hits.
   - `link(driver: GraphDriver, mention_id: str, entity_id: str, method: str, score: float, decision_at: datetime) -> None`: creates a scored `SAME_AS` relationship.
   - `unlink(driver: GraphDriver, mention_id: str, entity_id: str, at: datetime) -> None`: retracts `SAME_AS` by setting `retracted_at`. No node is ever deleted (AC-19).
5. Implement `resolve.py`:
   - `resolve_assertions(extracted: list[ExtractedAssertion], ctx: RunContext, doc: DocumentPayload) -> tuple[list[Assertion], ResolutionStats]` per Doc 2 §8.8.4.
   - For each `ExtractedAssertion`:
     a. Create `:Mention` for subject and object endpoints.
     b. Try `keys.deterministic_key` for each. If match, link with confidence 1.0.
     c. If no key, `blocking.embed` + `blocking.candidates`.
     d. Route by thresholds (Doc 2 §8.8.3):
        - `cosine ≥ 0.93` and margin ≥ 0.05 → auto-link.
        - `0.82 ≤ cosine < 0.93` or `≥ 0.93` with margin < 0.05 → adjudicate.
        - `cosine < 0.82` → mint new `entity_id`, return `EntityEndpoint`.
     e. Assemble `Assertion` with full provenance.
   - **The resolver never writes an entity node.** In the mint branch, it returns an `EntityEndpoint` with a new `entity_id`; the loader materializes it (Doc 2 §8.8.3).
   - `ResolutionStats`: `deterministic`, `auto_linked`, `adjudicated`, `minted`.
6. Write unit and integration tests:
   - AC-16: Deterministic keys short-circuit with no embedding and no vector query issued.
   - AC-17: Resolution routes correctly across all four bands.
   - AC-19: `unlink` retracts `SAME_AS` without deleting any node; prior assertions remain attributed.
   - AC-43: `resolve_assertions` converts `ExtractedAssertion` to `Assertion`, creates `:Mention` per endpoint, and returns stats matching the four bands.
   - The mint branch writes no entity node directly (verify by checking the graph after resolution but before loading).

**Contracts consumed:**
- `Ontology` (WP-03) — for type validation
- `GraphDriver` (WP-04) — for vector queries and `:Mention`/`SAME_AS` writes
- `OpenRouterClient` (WP-22) — for embeddings and adjudication
- `ExtractedAssertion`, `Assertion`, `Mention`, `EntityEndpoint`, `Provenance` types (WP-02)
- `WikidataAdapter.enrich()` (WP-18) — for QID enrichment where deterministic keys are absent
- `Governor` (via `OpenRouterClient`) — adjudication calls are paid

**Contracts produced:**
- `resolve_assertions()` — consumed by WP-27 (pipeline run, unstructured path)
- `ResolutionStats` type — consumed by WP-27
- `link()`, `unlink()` — consumed by WP-27 (for re-extraction unlinking)

**Acceptance criteria:**
- AC-16, AC-17, AC-19, AC-43.
- The resolver never writes an entity node in any branch.
- Every extracted endpoint gets a `:Mention` node, including deterministic-key hits.

**Verification:**
```bash
ruff check src/limes/resolution/
mypy src/limes/resolution/
pytest tests/unit/test_resolution_keys.py tests/integration/test_resolution.py -v
python tools/check_docs.py
```

---

### WP-26 — Composition Root

| Field | Value |
|---|---|
| Phase | 5 |
| Depends on | WP-02, WP-03, WP-04, WP-05, WP-06, WP-09, WP-22, WP-24, WP-25 |
| Sizing | Single session |

**Objective:** Implement the single module that constructs every component the system needs, in dependency order, once per process. This is the keystone that resolves the v1.x defect of modules specified without named constructors.

**Spec references:** Doc 1 §4.14 (Composition Root), DD-18, C-07; Doc 2 §8.15 (Composition Root), §15.1 (Context Types), §15.2 (Seam Register).

**Scope — files created:**
- `src/limes/composition.py`

**Out of scope:** Any business logic. The pipeline run (WP-27). The API startup handler (WP-32, which calls `build_nlq_context`).

**Task list:**
1. Define context types per Doc 2 §8.15:
   - `RunContext` (frozen dataclass): `settings`, `ontology`, `driver`, `registry`, `archive`, `governor` (optional), `client` (optional), `extractor` (optional), `gate` (optional `GateContext`).
   - `GateContext` (frozen dataclass): `settings`, `driver`, `nlp_de` (spaCy Language), `nlp_en` (spaCy Language).
   - `NlqContext` (frozen dataclass): `settings`, `ontology`, `driver`, `client`, `governor`.
2. Implement `build_run_context(settings: Settings, *, needs_inference: bool, budget_eur: Decimal | None = None) -> RunContext`:
   a. Call `load_ontology(settings.ontology_path)` → `Ontology`.
   b. Construct `GraphDriver` from settings.
   c. Call `provision(driver, ontology, settings.embedding_dimensions)` — idempotent, every construction.
   d. Call `build_default_registry()` → `SourceRegistry`.
   e. Construct `ArchiveStore(settings.archive_path)`.
   f. Construct `Governor` — monthly ceiling always; if `budget_eur` is provided, construct with envelope.
   g. If `needs_inference`:
      - Load spaCy models: `spacy.load(settings.gate_spacy_model_de)`, `spacy.load(settings.gate_spacy_model_en)`.
      - Construct `GateContext`.
      - Construct `OpenRouterClient(settings, governor)`.
      - Construct `OpenRouterExtractor(client, settings, ontology)`.
      - Set `governor`, `client`, `extractor`, `gate` on `RunContext`.
   h. If not `needs_inference`: `governor`, `client`, `extractor`, `gate` are `None`. No spaCy models loaded. No extractor constructed. This is what keeps structured-only runs inside the resource contract (AC-41).
3. Implement `build_nlq_context(settings: Settings, ontology: Ontology, driver: GraphDriver) -> NlqContext`:
   a. Construct `Governor` (monthly ceiling).
   b. Construct `OpenRouterClient(settings, governor)`.
   c. Return `NlqContext`.
4. Write integration tests:
   - AC-40: `composition.py` is the only constructor of driver, registry, archive, governor, client, extractor, and gate. Grep-verified: no other module in `src/limes/` instantiates these classes.
   - AC-41: A structured-only run (`needs_inference=False`) loads no spaCy model and constructs no extractor.
   - `provision()` is called on every `build_run_context` invocation.
   - The ontology downgrade guard runs during `provision()`.
   - `RunContext` is a frozen dataclass; fields are immutable after construction.

**Contracts consumed:**
- `Settings`, `load_settings()` (WP-02)
- `Ontology`, `load_ontology()` (WP-03)
- `GraphDriver`, `provision()` (WP-04)
- `ArchiveStore` (WP-05)
- `Governor` (WP-06)
- `SourceRegistry`, `build_default_registry()` (WP-09)
- `OpenRouterClient`, `OpenRouterExtractor` (WP-22)
- `GateContext` — defined here; spaCy models loaded here

**Contracts produced:**
- `RunContext`, `GateContext`, `NlqContext` — consumed by WP-27 (pipeline), WP-28 (CLI), WP-29 (model selection), WP-30 (evaluation), WP-31 (migration), WP-32 (API)
- `build_run_context()` — consumed by WP-28, WP-29, WP-30, WP-31
- `build_nlq_context()` — consumed by WP-32 (API startup)

**Acceptance criteria:**
- AC-40: `composition.py` is the only constructor of infrastructure. Grep-verified.
- AC-41: Structured-only run loads no spaCy model and constructs no extractor.
- AC-44 (partial): `RunContext`, `GateContext`, `NlqContext` are defined here and are the only context types used in §8 signatures.

**Verification:**
```bash
ruff check src/limes/composition.py
mypy src/limes/composition.py
pytest tests/integration/test_composition_root.py -v
# AC-40 grep verification:
! grep -rn "GraphDriver(" src/limes/ --include="*.py" | grep -v "composition.py" | grep -v "test"
! grep -rn "OpenRouterClient(" src/limes/ --include="*.py" | grep -v "composition.py" | grep -v "test"
! grep -rn "ArchiveStore(" src/limes/ --include="*.py" | grep -v "composition.py" | grep -v "test"
! grep -rn "Governor(" src/limes/ --include="*.py" | grep -v "composition.py" | grep -v "test"
python tools/check_docs.py
```

---

### WP-27 — Pipeline Run Orchestration + Window Resolution

| Field | Value |
|---|---|
| Phase | 5 |
| Depends on | WP-07, WP-09, WP-22, WP-24, WP-25, WP-26 |
| Sizing | Single session |

**Objective:** Implement the pipeline run orchestrator that executes a single ingestion run end-to-end — from adapter fetch through archive, normalize, gate, extract, resolve, and load — plus the window resolution that determines the ingestion time range.

**Spec references:** Doc 1 §3.4–3.5 (Data Flows), §9.1 (Ingestion), §9.2 (Backfill); Doc 2 §8.6.1 (Run Orchestration), §8.6.2 (Window Resolution), §15.3 (Call Traces 1 and 2).

**Scope — files created:**
- `src/limes/pipeline/run.py` — `RunSpec`, `execute_run()`
- `src/limes/pipeline/window.py` — `resolve_window()`

**Out of scope:** CLI commands that call `execute_run` (WP-28). The composition root (WP-26, already built).

**Task list:**
1. Implement `window.py`:
   - `resolve_window(spec: RunSpec, adapter: SourceAdapter, source_node: SourceRecord | None) -> tuple[datetime | None, datetime | None]` per Doc 2 §8.6.2.
   - An explicit `since` in `RunSpec` always wins.
   - If `adapter.supports_incremental`: window starts at `Source.last_success_at`, or `now - LIMES_BACKFILL_DAYS_UNSTRUCTURED` if never run.
   - If not incremental: window is `(None, None)` meaning full load.
   - This is why `supports_incremental` exists on the protocol and why `Source.last_success_at` is read, not merely written.
2. Implement `run.py`:
   - `RunSpec` per Doc 2 §8.6.1: `source_id`, `mode`, `since`, `until`, `budget_eur` (required for backfill/reextract).
   - `execute_run(spec: RunSpec, ctx: RunContext) -> IngestionRunRecord` per Doc 2 §8.6.1 and §15.3 traces:
     a. Resolve adapter from `ctx.registry.get(spec.source_id)`.
     b. `MERGE` `:Source` node (id, name, kind, trust_rank). Read `Source.last_success_at` for window resolution.
     c. `resolve_window(spec, adapter, source_node)`.
     d. Open `:IngestionRun` node with `started_at`, `mode`, `window_from`, `window_to`.
     e. `adapter.fetch(since, until)` → for each `RawRecord`:
        - `ctx.archive.put(source_id, payload, content_type)` → `content_hash`.
        - `adapter.normalize(record)` → `NormalizedRecord`.
        - Stamp `source_id` and `source_trust` on every assertion and entity from the registry (Doc 2 §15.2: "Assertion.source_id | execute_run, from the registry").
        - Stamp `content_hash` from `ArchiveStore.put`.
        - If `NormalizedRecord.kind == "structured"`:
          - `ontology.validate_assertions(assertions, ontology)` → accepted, rejected.
          - `graph.loader.load(driver, accepted, ontology, standalone_entities, lookup_rows)`.
        - If `NormalizedRecord.kind == "document"`:
          - `pipeline.gate.gate_document(doc, ctx.gate)` → `GateDecision`.
          - If not passed: count as `documents_gated_out` with reason.
          - If passed:
            - `ctx.extractor.extract(passages, ontology, prompt_version, schema_version)` → `ExtractionResult`.
            - `OpenRouterClient`: governor.check → call → governor.commit.
            - Map passage offsets → document offsets; reject `EVIDENCE_SPAN_MISMATCH`.
            - `extraction.cache.put(driver, ...)`.
            - `resolution.resolve.resolve_assertions(extracted, ctx, doc)` → `(assertions, stats)`.
            - `ontology.validate_assertions` → accepted, rejected.
            - `graph.loader.load(driver, accepted, ontology)`.
     f. Close `:IngestionRun` with all counts: `records_fetched`, `nodes_created`, `nodes_matched`, `assertions_written`, `assertions_skipped`, `assertions_rejected`, `documents_gated_out`, `errors`, `cost_eur`, `finished_at`.
     g. Update `:Source.last_success_at` and `:Source.last_run_id`.
   - Record-level failures (`SourceParseError`, `ExtractionSchemaError`, `ValidationRejected`, `EndpointUnidentified`) are counted and skipped.
   - Fetch and configuration failures abort the run.
   - `BudgetExhausted` closes the run cleanly with remaining documents marked queued.
3. Write integration tests:
   - AC-05: Re-running an identical ingest writes zero new relationships and zero new nodes, and reports the skip count.
   - AC-42: Window resolution returns full load for non-incremental adapter; `last_success_at`-anchored window for incremental one that has run before.
   - Trace 1 (`make ingest SOURCE=gisco_nuts`) runs end-to-end against a Neo4j container with the GISCO adapter.
   - Trace 2 (`make backfill SOURCE=feeds DAYS=90 BUDGET=3.00`) runs end-to-end against a Neo4j container with the feeds adapter, extractor, and resolver.
   - `BudgetExhausted` closes the run cleanly.
   - No document is silently dropped.

**Contracts consumed:**
- `RunContext`, `GateContext` (WP-26)
- `SourceRegistry` (WP-09)
- `ArchiveStore` (WP-05)
- `GraphDriver` (WP-04)
- `load()`, `retract()` (WP-07)
- `gate_document()` (WP-24)
- `Extractor.extract()` (WP-22)
- `cache.put()` (WP-23)
- `resolve_assertions()` (WP-25)
- `validate_assertions()` (WP-03)
- `Ontology` (WP-03)
- `Governor` (WP-06, via `RunContext`)

**Contracts produced:**
- `execute_run()` — consumed by WP-28 (CLI: ingest, backfill, reextract)
- `RunSpec` — consumed by WP-28
- `IngestionRunRecord` — consumed by WP-32 (API: `/ingest/status`)
- `resolve_window()` — consumed internally by `execute_run`

**Acceptance criteria:**
- AC-05, AC-42.
- Trace 1 and Trace 2 from Doc 2 §15.3 run end-to-end.
- `BudgetExhausted` terminates cleanly with queued work recorded.
- Every skip is counted; every count is visible.

**Verification:**
```bash
ruff check src/limes/pipeline/run.py src/limes/pipeline/window.py
mypy src/limes/pipeline/run.py src/limes/pipeline/window.py
pytest tests/integration/test_pipeline_run_structured.py tests/integration/test_pipeline_run_unstructured.py -v
python tools/check_docs.py
```

---

### WP-28 — CLI Core: Ingest, Backfill, Reextract, Backup

| Field | Value |
|---|---|
| Phase | 6 |
| Depends on | WP-26, WP-27 |
| Sizing | Single session |

**Objective:** Implement the CLI commands for ingestion, backfill, re-extraction, and backup — including the advisory lock that prevents concurrent runs on the same source.

**Spec references:** Doc 1 §6.6 (Command Line), §8.5 (Backup), §9.1–9.2 (Ingestion, Backfill), §9.4 (Re-extraction); Doc 2 §8.14 (CLI), §5.8 (`:AdvisoryLock`).

**Scope — files created:**
- `src/limes/cli/main.py` — Typer app, advisory lock management
- `src/limes/cli/ingest.py` — `ingest` and `ingest-all` commands
- `src/limes/cli/backfill.py` — `backfill` command
- `src/limes/cli/reextract.py` — `reextract` command
- `src/limes/cli/backup.py` — `backup` command

**Out of scope:** `select-models` (WP-29), `evaluate` (WP-30), `migrate` (WP-31). The Makefile (WP-38).

**Task list:**
1. Implement `main.py`:
   - Typer application with subcommands: `ingest`, `ingest-all`, `backfill`, `reextract`, `backup` (plus stubs for `select-models`, `evaluate`, `migrate` to be filled by WP-29–31).
   - Advisory lock management: `acquire_lock(driver, source_id, run_id) -> None` creates an `:AdvisoryLock` node. `release_lock(driver, source_id) -> None` deletes it. `reclaim_stale_lock(driver, source_id, run_timeout) -> None` reclaims a lock older than the run timeout with a warning (Doc 2 §8.14).
   - Every command calls `build_run_context` from WP-26, then calls `execute_run` from WP-27.
2. Implement `ingest.py`:
   - `ingest --source <id> [--since <iso>] [--until <iso>]`: builds `RunSpec(mode="ingest")`, calls `execute_run`.
   - `ingest-all`: iterates all registered source IDs and calls `ingest` for each, skipping enrichment-only sources (Wikidata).
3. Implement `backfill.py`:
   - `backfill --source <id> --days <n> --budget <eur>`: requires `--budget` (Doc 2 §8.14). Builds `RunSpec(mode="backfill", budget_eur=<eur>)`, calls `execute_run`.
   - Refuses to run without `--budget`.
4. Implement `reextract.py`:
   - `reextract --prompt-version <v> [--source <id>] --budget <eur>`: requires `--budget`. Builds `RunSpec(mode="reextract", budget_eur=<eur>)`. Calls `execute_run` which re-extracts documents, retracts superseded assertions (never deletes), and writes new ones.
5. Implement `backup.py`:
   - `backup`: stops Neo4j, dumps offline to the archive volume with a timestamped filename, restarts (Doc 2 §13.6, Doc 1 §8.5). Uses `subprocess` to run `neo4j-admin dump`.
6. Write integration tests:
   - `ingest --source gisco_nuts` runs end-to-end against a Neo4j container (Trace 1).
   - `backfill --source feeds --days 90 --budget 3.00` runs end-to-end (Trace 2, simplified).
   - `backfill` without `--budget` exits with an error.
   - Advisory lock prevents concurrent runs on the same source.
   - Stale lock is reclaimed with a warning.

**Contracts consumed:**
- `build_run_context()` (WP-26)
- `execute_run()`, `RunSpec` (WP-27)
- `GraphDriver` (WP-04) — for advisory lock
- `Settings` (WP-02)

**Contracts produced:**
- `ingest`, `ingest-all`, `backfill`, `reextract`, `backup` commands — consumed by WP-38 (Makefile targets)

**Acceptance criteria:**
- Trace 1 runs via `limes ingest --source gisco_nuts`.
- `backfill` and `reextract` refuse without `--budget`.
- Advisory lock prevents concurrent runs on the same source.
- `backup` stops Neo4j, dumps, and restarts.

**Verification:**
```bash
ruff check src/limes/cli/
mypy src/limes/cli/
pytest tests/integration/test_cli_ingest.py tests/integration/test_cli_backfill.py -v
limes ingest --source gisco_nuts  # against a running Neo4j
limes backfill --source feeds --days 90 --budget 3.00  # against a running Neo4j
python tools/check_docs.py
```

---

### WP-29 — Model Selection CLI

| Field | Value |
|---|---|
| Phase | 6 |
| Depends on | WP-22, WP-26 |
| Sizing | Single session |

**Objective:** Implement the two-stage model selection CLI that filters, ranks, evaluates, and pins model identifiers for each role (extraction, adjudication, embedding, NL-to-Cypher).

**Spec references:** Doc 1 §11.2 OQ-01; Doc 2 §8.7.2 (Model Selection), §4.2 (model pin settings).

**Scope — files created:**
- `src/limes/cli/select_models.py`

**Task list:**
1. Implement `select_models.py`:
   - `select-models --provisional` (Stage 1):
     a. Calls `OpenRouterClient.catalogue()` to get the model list.
     b. Filters by role criteria from Doc 2 §8.7.2: extraction (JSON-schema-constrained, German+English, ≤ USD 0.50/M blended), adjudication (short-form reasoning, JSON, ≤ USD 0.30/M), embedding (multilingual, German-competent, ≤ 1536 dims, ≤ USD 0.20/M), NL-to-Cypher (strong instruction following, code output, ≤ USD 1.00/M blended).
     c. Ranks by published cost and declared structured-output support.
     d. Writes the top candidate per role with `LIMES_MODEL_PIN_STAGE=provisional` after operator confirmation (prints candidates, asks for confirmation).
     e. Does not read the gold set (AC-36).
   - `select-models --measured` (Stage 2):
     a. Requires a gold set at version 1.0.0 or higher. Refuses without it (AC-37).
     b. Evaluates the top three candidates per role using the evaluation harness (calls into WP-30's evaluation logic, or imports the extractor and runs extraction on the gold set).
     c. Writes the winner with `LIMES_MODEL_PIN_STAGE=measured`.
     d. On a change to the extraction or embedding model: reports affected source and document counts with a re-extraction cost estimate. Performs no re-extraction.
     e. An embedding change additionally requires a vector index rebuild (reported, not executed automatically).
2. Write unit tests:
   - AC-36: `--provisional` writes a complete pin set without reading the gold set, requiring operator confirmation.
   - AC-37: `--measured` refuses without a gold set; on re-pinning reports affected counts and cost without re-extracting.

**Contracts consumed:**
- `OpenRouterClient.catalogue()` (WP-22)
- `build_run_context()` (WP-26)
- Gold set (WP-30 — for `--measured` stage; but `--provisional` must not read it)

**Contracts produced:**
- `select-models` command — consumed by WP-38 (Makefile), WP-39 (acceptance tests for AC-36, AC-37)

**Acceptance criteria:**
- AC-36, AC-37.
- `--provisional` does not read the gold set.
- `--measured` refuses without a gold set.

**Verification:**
```bash
ruff check src/limes/cli/select_models.py
mypy src/limes/cli/select_models.py
pytest tests/unit/test_select_models.py -v
python tools/check_docs.py
```

---

### WP-30 — Evaluation Harness, Gold Set, Reference Questions

| Field | Value |
|---|---|
| Phase | 6 |
| Depends on | WP-22, WP-26 |
| Sizing | Single session |

**Objective:** Create the gold set (200 hand-labeled items), the calibration set (100 entity-resolution pairs), the reference questions (5 operator questions with hand-written Cypher), and the evaluation harness that measures extraction quality and gates version changes on non-regression.

**Spec references:** Doc 1 §9.5 (Quality Gate), §11.2 OQ-05; Doc 2 §12.5 (Gold Set), §12.6 (Reference Questions), §8.14 (`evaluate` CLI).

**Scope — files created:**
- `gold_set/gold_set.jsonl` — 200 items (initially empty or minimal; populated after backfill per Doc 2 §13.3 step 9)
- `gold_set/gold_set.schema.json` — JSON Schema for gold set items
- `gold_set/calibration_set.jsonl` — 100 entity-resolution pairs (50 DE, 50 EN; 40 true matches, 40 hard negatives, 20 cross-language)
- `gold_set/baseline.json` — machine-readable regression baseline (initially empty)
- `gold_set/CHANGELOG.md` — initial entry
- `reference_questions/questions.yaml` — 5 reference questions with hand-written Cypher
- `src/limes/cli/evaluate.py` — `evaluate` command

**Task list:**
1. Write `gold_set.schema.json`: each item has `item_id`, `language` ("de"/"en"), `passage` (text), `expected_json` (list of expected assertions with `subject.surface`, `relation`, `object.surface`), `gold_set_version`.
2. Write `gold_set/gold_set.jsonl` with a minimal placeholder (1–2 items) — the full 200 items are populated after the 90-day backfill per Doc 2 §13.3 step 9, using the provisional model pin. **Labeled from passage text, never from model output** (Doc 2 §12.5).
3. Write `gold_set/calibration_set.jsonl` with 100 entity-resolution pairs per Doc 2 §8.8.3: 50 German, 50 English; 40 true matches, 40 hard negatives (parent-vs-subsidiary name pairs), 20 cross-language.
4. Write `reference_questions/questions.yaml` with 5 operator questions. Each has:
   - `question` (natural language)
   - `reference_cypher` (hand-written Cypher that passes validation and planning against an empty graph — AC-25)
   - These are not templates (NG-08). Two roles: expressibility (data-independent) and generation quality (measured, not gated).
5. Implement `evaluate.py`:
   - `evaluate [--resolution] [--nl2cypher]`:
     a. `build_run_context(needs_inference=True, budget_eur=<envelope>)`.
     b. Load `gold_set.jsonl`, validate against `gold_set.schema.json`.
     c. For each item: call `extractor.extract` on the passage. Compare on `(subject.surface_normalized, relation, object.surface_normalized)` where normalization is casefold + whitespace collapse. Evidence span ignored for matching (Doc 2 §12.5).
     d. Compute precision, recall, F1 per relation type.
     e. Read `baseline.json`. Compare. Write `baseline.json` with new results.
     f. Append human-readable entry to `gold_set/CHANGELOG.md`.
     g. Exit non-zero if any per-relation F1 regressed by more than 0.05 absolute (AC-31).
   - `--resolution`: evaluates entity resolution against `calibration_set.jsonl` (recall@10, accuracy).
   - `--nl2cypher`: reports validation-pass rate and structural agreement with reference Cypher for the 5 reference questions.
6. Write tests:
   - AC-31: `evaluate` produces per-relation-type precision, recall, F1, writes `baseline.json`, and exits non-zero on regression > 0.05.
   - AC-25: All five reference questions have hand-written Cypher passing validation and planning against an empty graph.

**Contracts consumed:**
- `build_run_context()` (WP-26)
- `Extractor.extract()` (WP-22)
- `Ontology` (WP-03) — for relation types
- `Settings` (WP-02) — for gold set path, baseline path

**Contracts produced:**
- `evaluate` command — consumed by WP-38 (Makefile), WP-29 (model selection `--measured`)
- `gold_set/` artifacts — consumed by WP-29 (model selection `--measured`)
- `reference_questions/` artifacts — consumed by WP-33 (NL-to-Cypher evaluation), WP-39 (AC-25)

**Acceptance criteria:**
- AC-25, AC-31.
- Gold set items are labeled from passage text, not model output.
- Match semantics use surface normalization (casefold + whitespace collapse).
- `baseline.json` is the sole source of truth for the regression gate.

**Verification:**
```bash
ruff check src/limes/cli/evaluate.py
mypy src/limes/cli/evaluate.py
pytest tests/unit/test_evaluate.py -v
# AC-25: validate reference Cypher against empty graph
python -c "
import yaml
from limes.ontology.registry import load_ontology
from pathlib import Path
o = load_ontology(Path('ontology/ontology.yaml'))
qs = yaml.safe_load(open('reference_questions/questions.yaml'))
for q in qs:
    print(f'Question: {q[\"question\"]}')
    print(f'Cypher: {q[\"reference_cypher\"]}')
print(f'{len(qs)} reference questions loaded')
"
python tools/check_docs.py
```

---

### WP-31 — Ontology Migration CLI

| Field | Value |
|---|---|
| Phase | 6 |
| Depends on | WP-03, WP-04, WP-26 |
| Sizing | Single session |

**Objective:** Implement the ontology migration CLI that applies numbered migrations for breaking ontology changes, rewriting version stamps on affected nodes and edges.

**Spec references:** Doc 1 §9.6 (Ontology Change); Doc 2 §8.14 (`migrate` CLI), S-23.

**Scope — files created:**
- `src/limes/cli/migrate.py`
- `ontology/migrations/0001_initial.py` — initial migration (no-op for v1.0.0, establishes the pattern)

**Task list:**
1. Implement `migrate.py`:
   - `migrate --ontology-version <v>`: loads the specified ontology version, determines whether the change is additive (minor bump) or breaking (major bump).
   - Additive changes: no migration needed; existing data remains valid under its stamped version.
   - Breaking changes: find and run the numbered migration script for the target version. Migration scripts live in `ontology/migrations/` and follow a pattern: each has an `upgrade(driver: GraphDriver) -> None` function that rewrites version stamps on affected nodes and edges.
   - Reports counts of affected nodes and edges.
2. Write `ontology/migrations/0001_initial.py`:
   - `upgrade(driver: GraphDriver) -> None`: no-op for v1.0.0 (the initial version). Establishes the migration pattern for future versions.
   - Includes a docstring explaining: migrations are numbered, run in order, and each rewrites version stamps.
3. Write tests:
   - Migration pattern is established and runnable.
   - `migrate --ontology-version 1.0.0` is a no-op on a fresh database.
   - The downgrade guard (WP-04) prevents loading an ontology older than the graph's stamped version.

**Contracts consumed:**
- `Ontology` (WP-03)
- `GraphDriver` (WP-04)
- `build_run_context()` (WP-26)

**Contracts produced:**
- `migrate` command — consumed by WP-38 (Makefile)

**Acceptance criteria:**
- Migration pattern is established and runnable.
- `migrate --ontology-version 1.0.0` succeeds on a fresh database as a no-op.

**Verification:**
```bash
ruff check src/limes/cli/migrate.py ontology/migrations/0001_initial.py
mypy src/limes/cli/migrate.py
pytest tests/unit/test_migrate.py -v
python tools/check_docs.py
```

---

### WP-32 — Query API Foundation

| Field | Value |
|---|---|
| Phase | 7 |
| Depends on | WP-03, WP-04, WP-06, WP-26, WP-27 |
| Sizing | Single session |

**Objective:** Implement the FastAPI application, its dependency injection, response models, and all non-query routers (health, ontology, entity, search, sources, cost, ingest_status). This is the only path to the graph for user-facing components.

**Spec references:** Doc 1 §4.10 (Query API), §6.1 (API Surface); Doc 2 §6 (API Specification), §8.12 (API), §7.3 (Enumerated Write Surface).

**Scope — files created:**
- `src/limes/api/main.py` — FastAPI app, startup handler
- `src/limes/api/deps.py` — dependency injection
- `src/limes/api/models.py` — response models (`GraphResult`, `CoverageReport`, `Diagnosis`, `EntityRef`, `EdgeRef`, `NlqOutcome`, `BuilderSpec`)
- `src/limes/api/routers/health.py` — `GET /health`
- `src/limes/api/routers/ontology.py` — `GET /ontology`, `GET /ontology/versions`
- `src/limes/api/routers/entity.py` — `GET /entity/{id}`, `GET /entity/{id}/neighbors`
- `src/limes/api/routers/search.py` — `GET /search`
- `src/limes/api/routers/sources.py` — `GET /sources`
- `src/limes/api/routers/cost.py` — `GET /cost/ledger`
- `src/limes/api/routers/ingest_status.py` — `GET /ingest/status`

**Out of scope:** Query routers (`/query/cypher`, `/query/nl`, `/query/builder`) — WP-35. Coverage router — WP-34/WP-35. Saved-query router — WP-35. NL-to-Cypher service — WP-33.

**Task list:**
1. Implement `main.py`:
   - FastAPI application with startup handler that: calls `load_settings()`, `load_ontology()`, constructs `GraphDriver`, verifies Neo4j reachability, calls `build_nlq_context()` (for later use by query router). Registers all routers.
   - All responses carry `X-LIMES-Ontology-Version` header.
   - Error envelope per Doc 2 §6: `{"error": {"code": "...", "message": "...", "details": {}}}`.
2. Implement `deps.py`:
   - Provides `GraphDriver` (read access mode), `Ontology`, `Settings`, and `NlqContext` as FastAPI dependencies.
   - Routers contain no business logic; they call into service modules.
3. Implement `models.py`:
   - `GraphResult`: nodes, edges, counts.
   - `EntityRef`, `EdgeRef`: entity and edge representations with provenance.
   - `CoverageReport`, `Diagnosis`, `NlqOutcome`, `BuilderSpec` — defined here even though their routers come later; they compose §5.5 types.
4. Implement routers:
   - `health.py`: `GET /health` — liveness, Neo4j reachability, ontology version. Returns 503 if Neo4j unreachable.
   - `ontology.py`: `GET /ontology` — full serialized ontology. `GET /ontology/versions` — versions present in the graph with counts.
   - `entity.py`: `GET /entity/{id}` — entity with properties, provenance, edge summary. `GET /entity/{id}/neighbors` — one-hop expansion with relation and temporal filters. 404 if not found.
   - `search.py`: `GET /search` — full-text search over entity labels and document text using the `entity_names` and `document_text` fulltext indexes.
   - `sources.py`: `GET /sources` — registry with trust rank and last refresh timestamp.
   - `cost.py`: `GET /cost/ledger` — period spend, remaining budget, entries.
   - `ingest_status.py`: `GET /ingest/status` — last run per source, counts, errors. Reads `:IngestionRun` and `:Source` nodes.
5. Write integration tests:
   - `GET /health` returns 200 with ontology version when Neo4j is reachable.
   - `GET /ontology` returns the full serialized ontology.
   - `GET /entity/{id}` returns 404 for unknown ID.
   - `GET /search` returns matching entities.
   - `GET /sources` returns registered sources with trust ranks.
   - `GET /cost/ledger` returns period spend.
   - `GET /ingest/status` returns last run per source.
   - AC-18 (partial): `src/limes/api/` contains exactly the three writes enumerated in Doc 2 §7.3 and no other write path. At this stage, none of the three writes are implemented yet (they come in WP-35), so the grep test should find zero write paths.

**Contracts consumed:**
- `Settings`, `load_settings()` (WP-02)
- `Ontology`, `load_ontology()` (WP-03)
- `GraphDriver` (WP-04)
- `Governor` (WP-06) — via `build_nlq_context`
- `build_nlq_context()` (WP-26)
- `IngestionRunRecord`, `SourceRecord` types (WP-02) — for `/ingest/status`

**Contracts produced:**
- FastAPI application — consumed by WP-35 (query routers), WP-36 (UI calls API), WP-37 (Docker `api` service)
- Response models — consumed by WP-35, WP-36
- Dependency injection — consumed by WP-35

**Acceptance criteria:**
- `GET /health` returns 200 with ontology version.
- `GET /ontology` returns full ontology.
- `GET /entity/{id}` returns 404 for unknown ID.
- AC-18 (partial): No write paths in `src/limes/api/` at this stage.

**Verification:**
```bash
ruff check src/limes/api/
mypy src/limes/api/
pytest tests/integration/test_api_health.py tests/integration/test_api_ontology.py tests/integration/test_api_entity.py tests/integration/test_api_search.py tests/integration/test_api_sources.py tests/integration/test_api_cost.py tests/integration/test_api_ingest_status.py -v
# AC-18 grep: no write paths yet
! grep -rn "CREATE\|MERGE\|DELETE\|SET " src/limes/api/ --include="*.py" | grep -v "test" | grep -v "#"
python tools/check_docs.py
```

---

### WP-33 — NL-to-Cypher Service

| Field | Value |
|---|---|
| Phase | 7 |
| Depends on | WP-03, WP-04, WP-06, WP-22 |
| Sizing | Single session |

**Objective:** Implement the four-stage NL-to-Cypher pipeline: generate candidate Cypher from a question and the serialized ontology, validate it deterministically against the ontology, plan-gate it, and execute it read-only.

**Spec references:** Doc 1 §6.2 (Natural-Language Query Contract), DD-09, DD-10; Doc 2 §8.10 (NL-to-Cypher), §5.7 (Temporal Query Fragments).

**Scope — files created:**
- `src/limes/nlq/generate.py` — Cypher generation via OpenRouter
- `src/limes/nlq/validate.py` — deterministic Cypher validation
- `src/limes/nlq/plan.py` — plan-gate via `EXPLAIN`
- `src/limes/nlq/service.py` — `answer()` orchestrator
- `src/limes/extraction/prompts/nl2cypher_v1.0.0.md` — NL-to-Cypher prompt

**Out of scope:** The query router that calls `answer()` (WP-35). Coverage and diagnosis (WP-34).

**Task list:**
1. Write `nl2cypher_v1.0.0.md`: instructs the model to generate Cypher from a question and the serialized ontology. Includes the temporal helpers (`as_of`, `as_believed`, `currently`). **No example questions** (NG-08, Doc 2 §8.10).
2. Implement `generate.py`:
   - `generate(question: str, ontology: Ontology, client: OpenRouterClient, model_id: str, prompt_version: str) -> str`: serializes the ontology via `ontology.serialize_for_prompt()`, constructs the prompt, calls `client.complete`, returns the generated Cypher string.
3. Implement `validate.py`:
   - `validate(cypher: str, ontology: Ontology, settings: Settings) -> ValidationResult`: parse-level inspection (not substring search). Rejects per Doc 2 §8.10:
     - `CREATE`, `MERGE`, `DELETE`, `DETACH`, `SET`, `REMOVE`, `LOAD CSV`, writing `CALL {}` subquery, `apoc.` procedures outside an explicit read-only allowlist.
     - `UNKNOWN_LABEL`, `UNKNOWN_RELATION` — labels/relations not in the ontology.
     - `DOMAIN_VIOLATION`, `RANGE_VIOLATION` — relation used between types not in its domain/range.
     - `WRITE_CLAUSE` — any write clause.
     - `DISALLOWED_PROCEDURE` — procedure not on the allowlist.
     - `LIMIT_EXCEEDS_MAX` — limit above `LIMES_QUERY_MAX_LIMIT`.
   - Injects `LIMIT` if absent (default from `LIMES_QUERY_DEFAULT_LIMIT`).
   - Where a pattern position is untyped, domain/range check is skipped and a note is attached recording partial verification.
   - Returns `ValidationResult(valid: bool, errors: list[str], cypher: str, notes: list[str])`.
4. Implement `plan.py`:
   - `explain_gate(driver: GraphDriver, cypher: str, params: dict, settings: Settings) -> PlanSummary`: calls `driver.explain`, checks against plan-gate rules (Doc 2 §8.10):
     - `CARTESIAN_PRODUCT`: reject if `has_cartesian_product`.
     - `UNBOUNDED_EXPANSION`: reject if variable-length expansion without limit.
     - `EXPANSION_TOO_DEEP`: reject if `max_varlength_hops > LIMES_QUERY_MAX_VARLENGTH_HOPS`.
     - `OPERATOR_ROWS_EXCEEDED`: reject if any operator's estimated rows > `LIMES_QUERY_MAX_ESTIMATED_ROWS_OPERATOR`.
     - `TOTAL_ROWS_EXCEEDED`: reject if total estimated rows > `LIMES_QUERY_MAX_ESTIMATED_ROWS_TOTAL`.
   - Raises `QueryPlanRejected` with the plan summary on rejection.
5. Implement `service.py`:
   - `answer(question: str, ctx: NlqContext, execute: bool = True) -> NlqOutcome` per Doc 2 §8.10 and §15.3 Trace 3:
     a. `generate(question, ontology, client, model_id, prompt_version)` → Cypher.
     b. `validate(cypher, ontology, settings)`. On failure: exactly one regeneration with the failure reason supplied verbatim. Re-validate. If still invalid, return `NlqOutcome` with errors.
     c. If `execute`: `plan.explain_gate(driver, cypher)`. On rejection, return `NlqOutcome` with plan summary.
     d. `driver.read(cypher)` → results.
     e. Return `NlqOutcome` with Cypher (always returned, always editable — AC-26), results, validation notes.
   - `NlqOutcome`: `question`, `cypher`, `results` (optional), `validation_errors`, `plan_rejection` (optional), `notes`.
6. Write unit tests:
   - AC-20: Every validation code in §8.10 is produced by a crafted query and blocks execution.
   - AC-21: Every plan-gate rejection in §8.10 is produced by a crafted query and blocks execution.
   - AC-26 (partial): Generated Cypher is returned for every query, including failed ones.
   - Exactly one regeneration on validation failure.
   - No example questions in the prompt (NG-08).

**Contracts consumed:**
- `Ontology` with `serialize_for_prompt()`, `permits()` (WP-03)
- `GraphDriver` with `read()`, `explain()` (WP-04)
- `OpenRouterClient` (WP-22) — for generation (paid inference)
- `Governor` (WP-06) — via `NlqContext`
- `NlqContext` (WP-26)
- `as_of()`, `as_believed()`, `currently()` (WP-04) — referenced in the prompt
- `PlanSummary`, `CypherValidationFailed`, `QueryPlanRejected` (WP-02)

**Contracts produced:**
- `answer()` — consumed by WP-35 (query router for `POST /query/nl`)
- `NlqOutcome` — consumed by WP-35, WP-36 (UI)
- `validate()` — consumed by WP-35 (query router for `POST /query/cypher`)

**Acceptance criteria:**
- AC-20: Every validation code produced by a crafted query and blocks execution.
- AC-21: Every plan-gate rejection produced by a crafted query and blocks execution.
- AC-26 (partial): Cypher returned for every query including failed ones.
- Exactly one regeneration on validation failure.

**Verification:**
```bash
ruff check src/limes/nlq/
mypy src/limes/nlq/
pytest tests/unit/test_nlq_validate.py tests/unit/test_nlq_plan.py tests/integration/test_nlq_service.py -v
python tools/check_docs.py
```

---

### WP-34 — Coverage Report and Empty-Result Diagnosis

| Field | Value |
|---|---|
| Phase | 7 |
| Depends on | WP-03, WP-04 |
| Sizing | Single session |

**Objective:** Implement the coverage report that attaches to every query result (contributing sources, per-relation-type edge counts, per-source last-refresh timestamps) and the empty-result diagnosis that decomposes a query to identify the clause that emptied it.

**Spec references:** Doc 1 §4.12 (Coverage and Diagnosis), §6.3 (Empty-Result Diagnosis), DD-10, DD-11; Doc 2 §8.11 (Coverage).

**Scope — files created:**
- `src/limes/coverage/report.py` — `report_for_relations()`
- `src/limes/coverage/diagnose.py` — `diagnose()`

**Out of scope:** The API router that calls these functions (WP-35).

**Task list:**
1. Implement `report.py`:
   - `report_for_relations(driver: GraphDriver, relation_types: list[str]) -> CoverageReport` per Doc 2 §8.11:
     - Contributing sources: distinct `source_id` values on edges of the given relation types.
     - Per-relation-type edge counts: `MATCH ()-[r]->() WHERE type(r) IN $types RETURN type(r), count(*)`.
     - Per-source last-refresh timestamps: from `:Source.last_success_at`.
   - `CoverageReport`: `relation_counts: dict[str, int]`, `contributing_sources: list[str]`, `source_refresh: dict[str, datetime]`.
2. Implement `diagnose.py`:
   - `diagnose(driver: GraphDriver, cypher: str, params: dict) -> Diagnosis` per Doc 2 §8.11 and Doc 1 §6.3:
     - Decompose the query into individual `MATCH` clauses.
     - Execute each independently.
     - The first clause that returns nothing is reported as the failing clause.
     - Include graph-wide counts for the relation types involved in the failing clause.
     - Include a plain-language note explaining the failure (e.g., "No entities of type Corporation found matching the given filter").
   - `Diagnosis`: `failing_clause: str`, `clause_index: int`, `relation_counts: dict[str, int]`, `note: str`.
3. Write integration tests:
   - AC-22: A query returning zero rows automatically produces a diagnosis naming the correct failing clause.
   - AC-23: Every result carries a coverage report with correct graph-wide relation counts and source refresh timestamps.
   - Diagnosis identifies the first empty `MATCH` clause correctly.
   - Coverage report counts match the actual graph.

**Contracts consumed:**
- `GraphDriver` (WP-04)
- `Ontology` (WP-03) — for relation types
- `CoverageReport`, `Diagnosis` types (WP-02 or WP-32 `models.py`)

**Contracts produced:**
- `report_for_relations()` — consumed by WP-35 (query router, attaches to every result)
- `diagnose()` — consumed by WP-35 (query router, runs automatically on zero rows)

**Acceptance criteria:**
- AC-22: Empty result produces diagnosis naming the correct failing clause.
- AC-23: Every result carries a coverage report with correct counts and timestamps.

**Verification:**
```bash
ruff check src/limes/coverage/
mypy src/limes/coverage/
pytest tests/integration/test_coverage.py tests/integration/test_diagnosis.py -v
python tools/check_docs.py
```

---

### WP-35 — Query Routers, Builder Projection, Saved Queries

| Field | Value |
|---|---|
| Phase | 7 |
| Depends on | WP-32, WP-33, WP-34 |
| Sizing | Single session |

**Objective:** Implement the query routers (`/query/cypher`, `/query/nl`, `/query/builder`), the coverage router, the saved-query router, and the builder schema projection — completing the API's query path and its enumerated write surface.

**Spec references:** Doc 1 §6.4 (Generated Query Builder), §6.2 (NL Query Contract), FR-09, FR-13, FR-14; Doc 2 §6 (API Specification), §7.3 (Enumerated Write Surface), §8.12 (API).

**Scope — files created:**
- `src/limes/api/routers/query.py` — `POST /query/cypher`, `POST /query/nl`, `POST /query/builder`
- `src/limes/api/routers/coverage.py` — `POST /coverage`
- `src/limes/api/routers/saved_queries.py` — `GET/POST/DELETE /saved-queries`
- Builder schema projection logic (in `ontology/registry.py` or a new `src/limes/api/builder.py`)

**Out of scope:** The UI that calls these endpoints (WP-36).

**Task list:**
1. Implement builder schema projection:
   - `project_for_builder(ontology: Ontology) -> dict`: projects the ontology into a builder schema. For each entity type: its properties with types. For each relation: domain types, range types, temporal flag. This is what the UI uses to render the generated builder (Doc 1 §6.4, FR-09).
   - The projection is rendered from the ontology at runtime, not authored. No hand-authored templates (NG-08).
2. Implement `query.py`:
   - `POST /query/cypher`: accepts operator-supplied Cypher, calls `nlq.validate.validate()`, calls `nlq.plan.explain_gate()`, executes via `driver.read()`, attaches coverage report, runs diagnosis on empty results. Returns `GraphResult` with Cypher, results, coverage, diagnosis (if empty).
   - `POST /query/nl`: accepts a question, calls `nlq.service.answer()`, attaches coverage, runs diagnosis on empty results. Persists the query as a `:SavedQuery` (FR-14, AC-30). Returns `NlqOutcome` with results, coverage, diagnosis.
   - `POST /query/builder`: accepts a `BuilderSpec`, validates that every relation is permitted between adjacent types (rejecting invalid specs — AC-24), translates to Cypher, executes, attaches coverage. Returns `GraphResult`.
   - All three endpoints return editable Cypher (AC-26).
3. Implement `coverage.py`:
   - `POST /coverage`: accepts a relation set or a query, calls `coverage.report.report_for_relations()`. Returns `CoverageReport`.
4. Implement `saved_queries.py`:
   - `GET /saved-queries`: returns all saved queries.
   - `POST /saved-queries`: creates a `:SavedQuery` node. This is one of the three enumerated API writes (Doc 2 §7.3).
   - `DELETE /saved-queries/{id}`: deletes a `:SavedQuery` node. This is another of the three enumerated writes.
   - 409 on duplicate, 404 on not found.
5. **AC-18 enforcement:** After implementing all three writes (`:CostLedgerEntry` via the NL-to-Cypher path's OpenRouterClient call, `:SavedQuery` create per execution, `:SavedQuery` create/delete per POST/DELETE), verify that `src/limes/api/` contains exactly these three write paths and no others.
6. Write integration tests:
   - AC-18: `src/limes/api/` contains exactly the three writes enumerated in §7.3 and no other write path. Grep-based test plus a write-attempt corpus including obfuscated forms.
   - AC-24: The builder cannot construct a query violating domain or range; every rejection is precise.
   - AC-26: Generated Cypher is returned, displayed, and editable for every query, including failed ones.
   - AC-28 (partial): Edge selection would display provenance (tested at API level by checking provenance is in the response).
   - AC-30: Every executed query is persisted with question, Cypher, ontology version, result count.

**Contracts consumed:**
- API foundation: `main.py`, `deps.py`, `models.py` (WP-32)
- `answer()`, `validate()`, `explain_gate()` (WP-33)
- `report_for_relations()`, `diagnose()` (WP-34)
- `GraphDriver` (WP-04)
- `Ontology` (WP-03)

**Contracts produced:**
- `POST /query/cypher`, `POST /query/nl`, `POST /query/builder` — consumed by WP-36 (UI)
- `POST /coverage` — consumed by WP-36 (UI)
- `GET/POST/DELETE /saved-queries` — consumed by WP-36 (UI)
- `GET /builder/schema` (registered in WP-32 but projection logic added here) — consumed by WP-36 (UI builder generation)

**Acceptance criteria:**
- AC-18: Exactly three writes in `src/limes/api/`, no other write path.
- AC-24: Builder cannot construct an invalid query.
- AC-26: Cypher returned and editable for every query.
- AC-30: Every executed query persisted.
- Trace 3 (`POST /query/nl`) runs end-to-end per Doc 2 §15.3.

**Verification:**
```bash
ruff check src/limes/api/routers/query.py src/limes/api/routers/coverage.py src/limes/api/routers/saved_queries.py
mypy src/limes/api/routers/
pytest tests/integration/test_api_query_cypher.py tests/integration/test_api_query_nl.py tests/integration/test_api_query_builder.py tests/integration/test_api_saved_queries.py tests/integration/test_api_coverage.py -v
# AC-18 grep verification:
python -c "
import subprocess, re
result = subprocess.run(['grep', '-rn', '--include=*.py', '-E', '(CREATE|MERGE|DELETE|SET |REMOVE )', 'src/limes/api/'], capture_output=True, text=True)
lines = [l for l in result.stdout.strip().split('\n') if l and 'test' not in l and '#' not in l.split(':')[1][:1]]
# Should only contain the three enumerated writes
print(f'Write paths found: {len(lines)}')
for l in lines:
    print(l)
"
python tools/check_docs.py
```

---

### WP-36 — Dash UI

| Field | Value |
|---|---|
| Phase | 8 |
| Depends on | WP-35 |
| Sizing | Single session (large; may be split if needed) |

**Objective:** Implement the Dash user interface with three synchronized panes (network, map, timeline), the ontology-generated query builder, the natural-language input and editable Cypher console, and the coverage and provenance panels.

**Spec references:** Doc 1 §6.5 (UI Structure), §4.13 (Dash UI), DD-14; Doc 2 §8.13 (UI).

**Scope — files created:**
- `src/limes/ui/app.py` — Dash application
- `src/limes/ui/layout.py` — page layout
- `src/limes/ui/api_client.py` — HTTP client (only module performing HTTP)
- `src/limes/ui/components/__init__.py`
- `src/limes/ui/components/network.py` — network pane (dash-cytoscape)
- `src/limes/ui/components/map.py` — map pane (dash-leaflet)
- `src/limes/ui/components/timeline.py` — timeline pane (plotly)
- `src/limes/ui/components/console.py` — NL input + editable Cypher console
- `src/limes/ui/components/builder.py` — generated query builder
- `src/limes/ui/components/coverage.py` — coverage panel
- `src/limes/ui/components/provenance.py` — provenance panel
- `src/limes/ui/callbacks/__init__.py`
- `src/limes/ui/callbacks/selection.py` — shared selection state
- `src/limes/ui/callbacks/query.py` — query execution callbacks
- `src/limes/ui/callbacks/temporal.py` — timeline brush callback

**Out of scope:** Any database access from the UI. The UI calls the API exclusively and holds no credentials (Doc 1 §4.13).

**Task list:**
1. Implement `api_client.py`:
   - One function per API endpoint (Doc 2 §8.13). No UI module holds ontology knowledge, a type name, or a Cypher fragment.
   - Functions: `get_health()`, `get_ontology()`, `get_builder_schema()`, `post_query_cypher(cypher)`, `post_query_nl(question)`, `post_query_builder(spec)`, `get_entity(id)`, `get_entity_neighbors(id, filters)`, `search(query)`, `post_coverage(relations)`, `get_saved_queries()`, `post_saved_query(query)`, `delete_saved_query(id)`, `get_sources()`, `get_cost_ledger()`, `get_ingest_status()`.
2. Implement `layout.py`:
   - One exploration screen, three synchronized panes over a shared selection (Doc 1 §6.5).
   - Supporting elements: NL input, editable Cypher console, generated builder (rendered from `/builder/schema`), coverage panel, provenance panel, saved-query list, budget indicator.
   - State lives in `dcc.Store`: `current-result`, `selection`, `temporal-filter`, `builder-spec` (Doc 2 §8.13).
3. Implement components:
   - `network.py`: dash-cytoscape graph. Node-click expands one hop and merges into the current view without re-running the original query (AC-27).
   - `map.py`: dash-leaflet map. Points from `Location` entities.
   - `timeline.py`: plotly timeline with a brush. The brush triggers a re-query rather than client-side filtering (Doc 2 §8.13, Doc 1 §6.5). No pane shows a subset the graph cannot reproduce.
   - `console.py`: NL input field + editable Cypher textarea + run button. Generated Cypher is always displayed and editable (AC-26).
   - `builder.py`: rendered from `/builder/schema` at runtime. Selecting a type offers only relations its domain admits; selecting a relation offers only types its range admits; then property filters; then optionally another hop. Temporal qualifiers on every temporal relation. Cannot construct an invalid query (AC-24).
   - `coverage.py`: displays the coverage report attached to every result (AC-23).
   - `provenance.py`: displays full provenance for a selected edge, including the originating sentence for news-extracted assertions (AC-28).
4. Implement callbacks:
   - `selection.py`: shared selection state. All three panes react to a selection change within one interaction cycle (AC-29).
   - `query.py`: executes queries via `api_client`, stores results in `dcc.Store`.
   - `temporal.py`: timeline brush triggers re-query.
5. Write tests:
   - AC-27: Node click expands one hop and merges without re-running the original query.
   - AC-28: Edge selection displays full provenance including the originating sentence.
   - AC-29: All three panes react to a selection change and to a timeline brush within one interaction cycle.
   - The UI holds no credentials and performs no database access (verify no Neo4j driver imports in `src/limes/ui/`).

**Contracts consumed:**
- All API endpoints (WP-32, WP-35)
- `BuilderSpec` model (WP-32)
- Response models: `GraphResult`, `CoverageReport`, `Diagnosis`, `NlqOutcome` (WP-32)

**Contracts produced:**
- Dash application — consumed by WP-37 (Docker `ui` service)

**Acceptance criteria:**
- AC-27, AC-28, AC-29.
- The UI holds no credentials and performs no database access.
- The builder is generated from `/builder/schema`, not authored.
- The timeline brush triggers a re-query, not client-side filtering.

**Verification:**
```bash
ruff check src/limes/ui/
mypy src/limes/ui/
pytest tests/integration/test_ui.py -v
# Verify no database access from UI:
! grep -rn "neo4j\|GraphDriver\|bolt://" src/limes/ui/ --include="*.py"
python tools/check_docs.py
```

---

### WP-37 — Docker Images and Compose Topology

| Field | Value |
|---|---|
| Phase | 9 |
| Depends on | WP-01 |
| Sizing | Single session |

**Objective:** Create the three Dockerfiles over a shared dependency layer and the Compose topology (base + override) that defines four services, one internal network, named volumes, and no published ports in the base file.

**Spec references:** Doc 1 §8.1 (Compose Topology), §8.2 (Resource Contract), §8.4 (Configuration), C-03; Doc 2 §13.1 (Images), §13.2 (Compose), §13.4 (Neo4j Runtime).

**Scope — files created:**
- `docker/api.Dockerfile`
- `docker/ui.Dockerfile`
- `docker/worker.Dockerfile`
- `docker-compose.yml` — base file
- `docker-compose.override.yml` — local override

**Out of scope:** The Makefile (WP-38). Bootstrap procedure (WP-38).

**Task list:**
1. Write `api.Dockerfile`:
   - Shared dependency layer (Python 3.12, `uv sync`).
   - Installs `src/limes/` and all non-worker dependencies.
   - Does NOT install spaCy models.
   - CMD: `uvicorn limes.api.main:app --host 0.0.0.0 --port 8000`.
2. Write `worker.Dockerfile`:
   - Shared dependency layer.
   - Installs spaCy models: `python -m spacy download de_core_news_md en_core_web_md`.
   - No virtual environment inside the image (Doc 2 §13.1).
3. Write `ui.Dockerfile`:
   - Shared dependency layer.
   - Installs `src/limes/` with UI dependencies only.
   - CMD: `python -m limes.ui.app`.
4. Write `docker-compose.yml` (base):
   - Four services: `neo4j`, `api`, `ui`, `worker`.
   - One internal network.
   - Named volumes: `neo4j_data`, `neo4j_logs`, `archive`.
   - **No published ports** (AC-34).
   - `neo4j` environment: heap 2G, page cache 2G, transaction memory 512m, timeout 120s (Doc 2 §13.4, §4.2).
   - `api` and `worker` receive `LIMES_NEO4J_*` and `LIMES_OPENROUTER_API_KEY` (Doc 2 §7.4).
   - `ui` receives **no credentials** (Doc 2 §7.4, §13.2).
   - `worker` mounts `gold_set/` read-write (Doc 2 §12.5).
   - `neo4j` port never published in either file (AC-34).
5. Write `docker-compose.override.yml`:
   - Publishes `ui` on `127.0.0.1:8050` only.
   - Source mounts for development.
   - Debug logging.
6. Verify resource contract (Doc 1 §8.2): Neo4j ~4.5 GB, spaCy ~1.5 GB, workers ~2.0 GB, API+UI ~0.7 GB, OS+Docker ~1.5 GB = ~10.2 GB total.

**Contracts consumed:**
- Project structure, `pyproject.toml` (WP-01)
- All source modules (for the Dockerfiles to install)

**Contracts produced:**
- Docker images and Compose files — consumed by WP-38 (Makefile, bootstrap), WP-39 (acceptance tests)

**Acceptance criteria:**
- AC-32 (verifiable later): Total resident memory < 11 GB.
- AC-34: Base Compose file publishes no ports; database port unpublished in both files.
- `ui` service holds no credentials.
- `worker` installs spaCy models; `api` and `ui` do not.

**Verification:**
```bash
docker compose -f docker-compose.yml config  # validates base file
docker compose -f docker-compose.yml -f docker-compose.override.yml config  # validates override
# AC-34: no published ports in base
! docker compose -f docker-compose.yml config | grep -E "published|ports"
# Neo4j port not published in either file
! grep "7687" docker-compose.yml docker-compose.override.yml | grep -v "LIMES_NEO4J_URI"
python tools/check_docs.py
```

---

### WP-38 — Makefile and Bootstrap Procedure

| Field | Value |
|---|---|
| Phase | 9 |
| Depends on | WP-28, WP-29, WP-37 |
| Sizing | Single session |

**Objective:** Implement the Makefile with all targets from Doc 1 §6.6 and Doc 2 §8.14, and document the bootstrap procedure from Doc 2 §13.3.

**Spec references:** Doc 1 §6.6 (Command Line); Doc 2 §8.14 (CLI), §13.3 (Bootstrap).

**Scope — files created:**
- `Makefile` (replaces stub from WP-01)

**Task list:**
1. Implement Makefile targets:
   - `up`: `docker compose up -d`
   - `down`: `docker compose down`
   - `bootstrap-db`: no-op (C-01 offers no roles; provisioning happens on every context build). Target exists for operator familiarity but does nothing except echo a message.
   - `ingest SOURCE=<id>`: `docker compose exec worker limes ingest --source $(SOURCE)`
   - `ingest-all`: `docker compose exec worker limes ingest-all`
   - `backfill SOURCE=<id> DAYS=<n> BUDGET=<eur>`: `docker compose exec worker limes backfill --source $(SOURCE) --days $(DAYS) --budget $(BUDGET)`
   - `reextract PROMPT_VERSION=<v> BUDGET=<eur>`: `docker compose exec worker limes reextract --prompt-version $(PROMPT_VERSION) --budget $(BUDGET)`
   - `select-models`: `docker compose exec worker limes select-models $(ARGS)` — passes `--provisional` or `--measured`.
   - `evaluate`: `docker compose exec worker limes evaluate $(ARGS)`
   - `migrate ONTOLOGY_VERSION=<v>`: `docker compose exec worker limes migrate --ontology-version $(VERSION)`
   - `backup`: `docker compose exec worker limes backup`
2. Document the bootstrap procedure in `README.md` (or a `docs/BOOTSTRAP.md`):
   - Steps 1–11 from Doc 2 §13.3, with the ordering constraints noted: steps 4–6 must precede 7–8 (extraction against an empty backbone produces mentions with nothing to resolve against); step 9 precedes 10 precedes 11.
3. Write a smoke test script that runs the bootstrap procedure end-to-end against a clean Docker Compose environment.

**Contracts consumed:**
- All CLI commands (WP-28, WP-29, WP-30, WP-31)
- Docker Compose files (WP-37)

**Contracts produced:**
- `Makefile` — the operator's primary interface
- Bootstrap procedure documentation

**Acceptance criteria:**
- All `make` targets from Doc 2 §8.14 are available.
- `make up` starts all four services.
- `make ingest SOURCE=gisco_nuts` runs the GISCO ingestion end-to-end in the worker container.
- `backfill` and `reextract` targets require `BUDGET` argument.
- Bootstrap procedure steps are documented with ordering constraints.

**Verification:**
```bash
make help  # lists all targets
make up
sleep 10
make ingest SOURCE=gisco_nuts
docker compose exec neo4j cypher-shell -u limes -p change-me "MATCH (n:AdministrativeRegion) RETURN count(n);"  # should return > 0
make down
python tools/check_docs.py
```

---

### WP-39 — Acceptance Test Suite

| Field | Value |
|---|---|
| Phase | 10 |
| Depends on | WP-38 |
| Sizing | Single session |

**Objective:** Implement the acceptance test suite in `tests/acceptance/` that mechanically verifies every criterion AC-01…AC-44 from Doc 2 §14.

**Spec references:** Doc 2 §14 (Acceptance Criteria), §12.4 (Acceptance tests).

**Scope — files created:**
- `tests/acceptance/test_ac01_config.py` through `tests/acceptance/test_ac44_type_closure.py` — one test file per acceptance criterion (or grouped logically)
- `tests/acceptance/conftest.py` — shared fixtures for acceptance tests (disposable Neo4j container, populated graph)

**Out of scope:** Any new production code. This WP only tests existing code.

**Task list:**
1. Implement `conftest.py`:
   - Starts a disposable Neo4j container.
   - Provides a `populated_graph` fixture that runs the production ingestion path (GISCO + GLEIF + a small feed sample) to populate the graph. **Uses the production path, not direct fixture writes** (Doc 2 §12.2 rule 1).
2. Implement one test per acceptance criterion:
   - AC-01: Missing configuration key → startup failure naming the key; older ontology artifact → failure.
   - AC-02: Ontology loads, self-validates, rejects each malformed case.
   - AC-03: Schema provisioning idempotent.
   - AC-04: All thirteen adapters produce expected records from fixtures.
   - AC-05: Re-running identical ingest writes zero new relationships/nodes.
   - AC-06: Interval closure within source, not across sources.
   - AC-07: Every relationship carries complete assertion metadata; graph-wide audit returns zero rows.
   - AC-08: Loading materializes endpoint nodes; no test pre-creates them.
   - AC-09: Re-merge from lower-trust source doesn't overwrite.
   - AC-10: Endpoint without `entity_id` rejected as `ENDPOINT_UNIDENTIFIED`.
   - AC-11: Gate rejects below threshold, records reason.
   - AC-12: Cache hit issues no paid call.
   - AC-13: Evidence span mismatch rejected.
   - AC-14: Governor refuses call breaching ceiling.
   - AC-15: Backfill/reextract meter against envelope.
   - AC-16: Deterministic keys short-circuit resolution.
   - AC-17: Resolution routes across all four bands; mint branch writes no node.
   - AC-18: `src/limes/api/` contains exactly three writes; grep test + obfuscated write-attempt corpus.
   - AC-19: `unlink` retracts `SAME_AS` without deleting nodes.
   - AC-20: Every validation code produced by crafted query.
   - AC-21: Every plan-gate rejection produced by crafted query.
   - AC-22: Empty result produces diagnosis naming correct clause.
   - AC-23: Every result carries coverage report.
   - AC-24: Builder cannot construct invalid query.
   - AC-25: All five reference questions pass validation and planning against empty graph.
   - AC-26: Generated Cypher returned, displayed, editable.
   - AC-27: Node click expands one hop without re-running original query.
   - AC-28: Edge selection displays full provenance including originating sentence.
   - AC-29: All three panes react to selection and timeline brush.
   - AC-30: Every executed query persisted with question, Cypher, ontology version, result count.
   - AC-31: `make evaluate` produces F1, writes `baseline.json`, exits non-zero on regression > 0.05.
   - AC-32: Total resident memory < 11 GB under full backfill.
   - AC-33: Full rebuild from archive with unchanged version triple issues zero paid calls.
   - AC-34: Base Compose file publishes no ports; database port unpublished in both files.
   - AC-35: Repository contains personal-artifact disclaimer.
   - AC-36: `--provisional` writes pin set without reading gold set.
   - AC-37: `--measured` refuses without gold set; reports affected counts without re-extracting.
   - AC-38: `build_default_registry()` returns all adapters; unknown source fails naming both.
   - AC-39: Cross-process lookup via `subprocess`; miss returns `None`.
   - AC-40: `composition.py` is only constructor; grep-verified.
   - AC-41: Structured-only run loads no spaCy model.
   - AC-42: Window resolution for non-incremental and incremental adapters.
   - AC-43: `resolve_assertions` converts types, creates `:Mention`, returns stats.
   - AC-44: Every type in §8 signature defined in §5.5 or §8.15 (via `check_docs.py`).
3. Run the full suite and verify every test passes.

**Contracts consumed:**
- All production code (WP-01 through WP-38)
- `tools/check_docs.py` (WP-01)
- All test fixtures and recorded adapter fixtures (from adapter WPs)

**Contracts produced:**
- `tests/acceptance/` — the final verification artifact

**Acceptance criteria:**
- Every AC-01…AC-44 has a mechanical test.
- All tests pass.
- No test hand-builds state that the production path produces (Doc 2 §12.2 rule 1).
- Cross-process tests use `subprocess` (Doc 2 §12.2 rule 2).

**Verification:**
```bash
pytest tests/acceptance/ -v --tb=short
python tools/check_docs.py
# Final project-level check:
ruff check src/limes/
mypy src/limes/
```

---

## 5. Milestones and Integration Checkpoints

### 5.1 Milestone Definitions

| Milestone | After WP | System state | Smoke test |
|---|---|---|---|
| M1 — Storage Layer | WP-08 | Graph driver, loader, lookups, archive, cost ledger operational | `provision()` runs; `load()` writes bitemporal assertions; `postal_code_to_nuts()` crosses process boundary |
| M2 — Structured Ingestion | WP-20 | All 11 structured adapters produce correct records; source registry complete | `build_default_registry()` returns 13 sources (11 structured + 2 unstructured); each adapter passes fixture tests |
| M3 — Full Pipeline | WP-27 | Both ingestion paths (structured + unstructured) run end-to-end via `execute_run` | Trace 1 (`ingest SOURCE=gisco_nuts`) and Trace 2 (`backfill SOURCE=feeds`) run against a Neo4j container |
| M4 — CLI Complete | WP-31 | All CLI commands available; gold set and evaluation harness functional | `limes ingest`, `limes backfill`, `limes evaluate`, `limes select-models --provisional` all succeed |
| M5 — Query API | WP-35 | API serves all endpoints; Trace 3 runs end-to-end | `POST /query/nl` generates, validates, plans, executes; coverage and diagnosis attached |
| M6 — UI | WP-36 | Dash UI renders three synchronized panes | UI loads, displays query results in all three panes, selection syncs |
| M7 — Full System | WP-38 | Docker Compose system runs on a clean host | `make up` + bootstrap steps 1–8 succeed on a clean host |
| M8 — Acceptance | WP-39 | All acceptance criteria verified | `pytest tests/acceptance/` passes all AC-01…AC-44 |

### 5.2 Smoke-Test Procedures

**M1 smoke test:**
```bash
# Requires Neo4j container running
pytest tests/integration/test_graph_driver.py tests/integration/test_schema_provision.py tests/integration/test_loader.py tests/integration/test_lookups_cross_process.py -v
```

**M3 smoke test:**
```bash
# Requires Neo4j container + OpenRouter API key
pytest tests/integration/test_pipeline_run_structured.py tests/integration/test_pipeline_run_unstructured.py -v
# Verify Trace 1:
limes ingest --source gisco_nuts
# Verify graph has AdministrativeRegion nodes:
docker compose exec neo4j cypher-shell -u limes -p change-me "MATCH (n:AdministrativeRegion) RETURN count(n)"
```

**M5 smoke test:**
```bash
# Requires API running
curl -s http://localhost:8000/health | python -m json.tool
curl -s -X POST http://localhost:8000/query/nl -H "Content-Type: application/json" -d '{"question": "What corporations are subsidiaries of Siemens?"}' | python -m json.tool
# Verify Cypher is returned, coverage is attached, diagnosis runs on empty results
```

**M7 smoke test:**
```bash
cp .env.example .env  # populate secrets
make up
sleep 15
make select-models -- --provisional
make ingest SOURCE=gisco_nuts
make ingest SOURCE=gleif
make ingest-all
make backfill SOURCE=feeds DAYS=90 BUDGET=3.00
# Verify UI is accessible:
curl -s http://127.0.0.1:8050 | head -5
make down
```

**M8 smoke test:**
```bash
pytest tests/acceptance/ -v
python tools/check_docs.py
ruff check src/limes/
mypy src/limes/
```

---

## 6. Coverage and Traceability Matrix

### 6.1 Scope Item Coverage

Every scope item from Doc 2 §1 is mapped to one or more WPs.

| Scope item | Description | WP(s) |
|---|---|---|
| S-01 | Configuration loading, validation, startup failure semantics | WP-02 |
| S-02 | Ontology artifact, schema, registry, self-validation | WP-03 |
| S-03 | Neo4j driver, session modes, schema and index provisioning | WP-04 |
| S-04 | Raw archive store, content addressing, compression | WP-05 |
| S-05 | `SourceAdapter` protocol, source registry, registry population | WP-09 |
| S-06 | Structured adapters (11 sources) | WP-10…WP-20 |
| S-07 | Unstructured adapters (GDELT, feeds) | WP-21 |
| S-08 | Normalizer | WP-09 |
| S-09 | Gate: hash dedup, spaCy NER, passage selection | WP-24 |
| S-10 | Extractor protocol, OpenRouter/Ollama, output schema, prompts | WP-22 |
| S-11 | Extraction cache | WP-23 |
| S-12 | Cost ledger and budget governor | WP-06 |
| S-13 | Entity resolution | WP-25 |
| S-14 | Graph loader | WP-07 |
| S-15 | Query API | WP-32, WP-35 |
| S-16 | NL-to-Cypher | WP-33 |
| S-17 | Coverage report and empty-result diagnosis | WP-34 |
| S-18 | Builder schema projection | WP-35 |
| S-19 | Dash UI | WP-36 |
| S-20 | Saved-query persistence | WP-35 |
| S-21 | CLI and make targets | WP-28, WP-38 |
| S-22 | Gold set, calibration set, evaluation harness | WP-30 |
| S-23 | Ontology migration | WP-31 |
| S-24 | Images, Compose topology, bootstrap | WP-37, WP-38 |
| S-25 | Structured logging, run records, status endpoints | WP-02 (logging), WP-27 (run records), WP-32 (status endpoints) |
| S-26 | Two-stage model selection | WP-29 |
| S-27 | Composition root and run-context construction | WP-26 |
| S-28 | Cross-process reference data | WP-08 |

### 6.2 Module Coverage

Every module from Doc 2 §2 is mapped to the WP that creates it.

| Module path | Creating WP |
|---|---|
| `src/limes/config.py` | WP-02 |
| `src/limes/errors.py` | WP-02 |
| `src/limes/logging_setup.py` | WP-02 |
| `src/limes/types.py` | WP-02 |
| `src/limes/composition.py` | WP-26 |
| `src/limes/ontology/model.py` | WP-03 |
| `src/limes/ontology/registry.py` | WP-03 |
| `src/limes/ontology/validator.py` | WP-03 |
| `src/limes/graph/driver.py` | WP-04 |
| `src/limes/graph/schema.py` | WP-04 |
| `src/limes/graph/temporal.py` | WP-04 |
| `src/limes/graph/loader.py` | WP-07 |
| `src/limes/graph/queries.py` | WP-07 |
| `src/limes/graph/lookups.py` | WP-08 |
| `src/limes/archive/store.py` | WP-05 |
| `src/limes/sources/base.py` | WP-09 |
| `src/limes/sources/registry.py` | WP-09 (extended by WP-10…WP-21) |
| `src/limes/sources/gisco_nuts.py` | WP-10 |
| `src/limes/sources/gleif.py` | WP-11 |
| `src/limes/sources/eurlex.py` | WP-12 |
| `src/limes/sources/fsd.py` | WP-13 |
| `src/limes/sources/ted.py` | WP-14 |
| `src/limes/sources/transparency_register.py` | WP-15 |
| `src/limes/sources/bundestag_dip.py` | WP-16 |
| `src/limes/sources/gesetze_im_internet.py` | WP-17 |
| `src/limes/sources/wikidata.py` | WP-18 |
| `src/limes/sources/osm.py` | WP-19 |
| `src/limes/sources/offeneregister.py` | WP-20 |
| `src/limes/sources/gdelt.py` | WP-21 |
| `src/limes/sources/feeds.py` | WP-21 |
| `src/limes/pipeline/normalize.py` | WP-09 |
| `src/limes/pipeline/gate.py` | WP-24 |
| `src/limes/pipeline/passages.py` | WP-24 |
| `src/limes/pipeline/idempotency.py` | WP-24 |
| `src/limes/pipeline/run.py` | WP-27 |
| `src/limes/pipeline/window.py` | WP-27 |
| `src/limes/extraction/base.py` | WP-22 |
| `src/limes/extraction/openrouter_client.py` | WP-22 |
| `src/limes/extraction/openrouter.py` | WP-22 |
| `src/limes/extraction/ollama.py` | WP-22 |
| `src/limes/extraction/schema.py` | WP-22 |
| `src/limes/extraction/cache.py` | WP-23 |
| `src/limes/extraction/prompts/extraction_v1.0.0.md` | WP-22 |
| `src/limes/extraction/prompts/adjudication_v1.0.0.md` | WP-22 |
| `src/limes/extraction/prompts/nl2cypher_v1.0.0.md` | WP-33 |
| `src/limes/resolution/keys.py` | WP-25 |
| `src/limes/resolution/blocking.py` | WP-25 |
| `src/limes/resolution/adjudicate.py` | WP-25 |
| `src/limes/resolution/link.py` | WP-25 |
| `src/limes/resolution/resolve.py` | WP-25 |
| `src/limes/cost/ledger.py` | WP-06 |
| `src/limes/cost/governor.py` | WP-06 |
| `src/limes/nlq/generate.py` | WP-33 |
| `src/limes/nlq/validate.py` | WP-33 |
| `src/limes/nlq/plan.py` | WP-33 |
| `src/limes/nlq/service.py` | WP-33 |
| `src/limes/coverage/report.py` | WP-34 |
| `src/limes/coverage/diagnose.py` | WP-34 |
| `src/limes/api/main.py` | WP-32 |
| `src/limes/api/deps.py` | WP-32 |
| `src/limes/api/models.py` | WP-32 |
| `src/limes/api/routers/health.py` | WP-32 |
| `src/limes/api/routers/ontology.py` | WP-32 |
| `src/limes/api/routers/entity.py` | WP-32 |
| `src/limes/api/routers/search.py` | WP-32 |
| `src/limes/api/routers/sources.py` | WP-32 |
| `src/limes/api/routers/cost.py` | WP-32 |
| `src/limes/api/routers/ingest_status.py` | WP-32 |
| `src/limes/api/routers/query.py` | WP-35 |
| `src/limes/api/routers/coverage.py` | WP-35 |
| `src/limes/api/routers/saved_queries.py` | WP-35 |
| `src/limes/ui/app.py` | WP-36 |
| `src/limes/ui/layout.py` | WP-36 |
| `src/limes/ui/api_client.py` | WP-36 |
| `src/limes/ui/components/*.py` | WP-36 |
| `src/limes/ui/callbacks/*.py` | WP-36 |
| `src/limes/cli/main.py` | WP-28 |
| `src/limes/cli/ingest.py` | WP-28 |
| `src/limes/cli/backfill.py` | WP-28 |
| `src/limes/cli/reextract.py` | WP-28 |
| `src/limes/cli/backup.py` | WP-28 |
| `src/limes/cli/select_models.py` | WP-29 |
| `src/limes/cli/evaluate.py` | WP-30 |
| `src/limes/cli/migrate.py` | WP-31 |
| `ontology/ontology.yaml` | WP-03 |
| `ontology/ontology.schema.json` | WP-03 |
| `ontology/feeds.yaml` | WP-21 |
| `ontology/CHANGELOG.md` | WP-03 |
| `ontology/migrations/0001_initial.py` | WP-31 |
| `gold_set/gold_set.jsonl` | WP-30 |
| `gold_set/gold_set.schema.json` | WP-30 |
| `gold_set/calibration_set.jsonl` | WP-30 |
| `gold_set/baseline.json` | WP-30 |
| `gold_set/CHANGELOG.md` | WP-30 |
| `reference_questions/questions.yaml` | WP-30 |
| `tools/check_docs.py` | WP-01 |
| `tests/conftest.py` | WP-01 |
| `tests/acceptance/*` | WP-39 |
| `docker/{api,ui,worker}.Dockerfile` | WP-37 |
| `docker-compose.yml` | WP-37 |
| `docker-compose.override.yml` | WP-37 |
| `Makefile` | WP-01 (stub), WP-38 (full) |
| `.env.example` | WP-01 (stub), WP-02 (full) |
| `pyproject.toml` | WP-01 |
| `README.md` | WP-01 |
| `AGENTS.md` | WP-01 |
| `CHANGELOG.md` | WP-01 |

### 6.3 Acceptance Criterion Coverage

Every acceptance criterion from Doc 2 §14 is mapped to the WP(s) that implement and verify it.

| AC | WP(s) implementing | WP verifying |
|---|---|---|
| AC-01 | WP-02, WP-04 | WP-39 |
| AC-02 | WP-03 | WP-03, WP-39 |
| AC-03 | WP-04 | WP-04, WP-39 |
| AC-04 | WP-10…WP-21 | WP-10…WP-21, WP-39 |
| AC-05 | WP-07, WP-27 | WP-07, WP-27, WP-39 |
| AC-06 | WP-07 | WP-07, WP-39 |
| AC-07 | WP-07 | WP-07, WP-39 |
| AC-08 | WP-07 | WP-07, WP-39 |
| AC-09 | WP-07 | WP-07, WP-39 |
| AC-10 | WP-07 | WP-07, WP-39 |
| AC-11 | WP-24 | WP-24, WP-39 |
| AC-12 | WP-23, WP-24 | WP-23, WP-24, WP-39 |
| AC-13 | WP-22 | WP-22, WP-39 |
| AC-14 | WP-06 | WP-06, WP-39 |
| AC-15 | WP-06 | WP-06, WP-39 |
| AC-16 | WP-25 | WP-25, WP-39 |
| AC-17 | WP-25 | WP-25, WP-39 |
| AC-18 | WP-32, WP-35 | WP-35, WP-39 |
| AC-19 | WP-25 | WP-25, WP-39 |
| AC-20 | WP-33 | WP-33, WP-39 |
| AC-21 | WP-33 | WP-33, WP-39 |
| AC-22 | WP-34 | WP-34, WP-39 |
| AC-23 | WP-34 | WP-34, WP-39 |
| AC-24 | WP-35 | WP-35, WP-39 |
| AC-25 | WP-30 | WP-30, WP-39 |
| AC-26 | WP-33, WP-35 | WP-33, WP-35, WP-39 |
| AC-27 | WP-36 | WP-36, WP-39 |
| AC-28 | WP-36 | WP-36, WP-39 |
| AC-29 | WP-36 | WP-36, WP-39 |
| AC-30 | WP-35 | WP-35, WP-39 |
| AC-31 | WP-30 | WP-30, WP-39 |
| AC-32 | WP-37 | WP-39 |
| AC-33 | WP-23 | WP-23, WP-39 |
| AC-34 | WP-37 | WP-37, WP-39 |
| AC-35 | WP-01 | WP-01, WP-39 |
| AC-36 | WP-29 | WP-29, WP-39 |
| AC-37 | WP-29 | WP-29, WP-39 |
| AC-38 | WP-09 | WP-09, WP-39 |
| AC-39 | WP-08 | WP-08, WP-39 |
| AC-40 | WP-26 | WP-26, WP-39 |
| AC-41 | WP-26 | WP-26, WP-39 |
| AC-42 | WP-27 | WP-27, WP-39 |
| AC-43 | WP-25 | WP-25, WP-39 |
| AC-44 | WP-02, WP-26 | WP-01 (check_docs.py), WP-39 |

### 6.4 Contract Closure Verification

Every contract consumed by a WP is produced by an earlier WP or defined in Doc 2 §5.5 / §8.15. The following table verifies the critical contract dependencies:

| Consumer WP | Contract | Producer WP | Doc 2 definition |
|---|---|---|---|
| WP-26 (composition root) | `GraphDriver` | WP-04 | §8.3 |
| WP-26 | `ArchiveStore` | WP-05 | §8.4 |
| WP-26 | `Governor` | WP-06 | §8.9 |
| WP-26 | `SourceRegistry` | WP-09 | §8.5.1 |
| WP-26 | `OpenRouterClient` | WP-22 | §8.7.6 |
| WP-26 | `OpenRouterExtractor` | WP-22 | §8.7.1 |
| WP-26 | `GateContext` (spaCy) | WP-26 (self) | §8.15 |
| WP-27 (pipeline) | `load()` | WP-07 | §8.3 |
| WP-27 | `gate_document()` | WP-24 | §8.6.3 |
| WP-27 | `Extractor.extract()` | WP-22 | §8.7.1 |
| WP-27 | `resolve_assertions()` | WP-25 | §8.8.4 |
| WP-27 | `validate_assertions()` | WP-03 | §8.2 |
| WP-25 (resolution) | `OpenRouterClient.embed()` | WP-22 | §8.7.6 |
| WP-25 | `WikidataAdapter.enrich()` | WP-18 | §8.5.2 |
| WP-35 (query routers) | `answer()` | WP-33 | §8.10 |
| WP-35 | `report_for_relations()` | WP-34 | §8.11 |
| WP-35 | `diagnose()` | WP-34 | §8.11 |
| WP-36 (UI) | All API endpoints | WP-32, WP-35 | §6 |
| WP-11, WP-14, WP-19 (adapters) | `postal_code_to_nuts()` | WP-08 | §8.16 |
| WP-29 (model selection) | Gold set | WP-30 | §12.5 |

No WP consumes a contract not produced by an earlier WP or defined in Doc 2. **Contract closure verified.**

---

## 7. Completion Criteria

The project is complete when all of the following hold:

1. **All 39 work packages are done** per the Definition of Done (§2.4).
2. **All 44 acceptance criteria pass** — `pytest tests/acceptance/` exits zero (AC-01…AC-44).
3. **All three call traces from Doc 2 §15.3 run end-to-end:**
   - Trace 1: `make ingest SOURCE=gisco_nuts` — entry point to committed state.
   - Trace 2: `make backfill SOURCE=feeds DAYS=90 BUDGET=3.00` — full unstructured path.
   - Trace 3: `POST /query/nl` — generation, validation, planning, execution, coverage, persistence.
4. **`tools/check_docs.py` passes** — no cross-document contradictions, every type defined, every module has a caller (AC-44).
5. **`ruff check src/limes/` and `mypy src/limes/` pass** with no errors.
6. **The resource contract holds** — total resident memory of all services under 11 GB (AC-32, NFR-01).
7. **The budget contract holds** — steady-state paid inference under EUR 10/month (NFR-03, AC-14, AC-15).
8. **The bootstrap procedure succeeds on a clean host** — steps 1–11 from Doc 2 §13.3 complete without error (M7 smoke test).
9. **No `[CONFLICT]` markers remain** in any file in the repository.
10. **Every module from Doc 2 §2 exists** at its specified path and has at least one specified caller per Doc 2 §15.2 (AC-44, verified by `check_docs.py`).

These criteria mirror Doc 2 §14 and are the project-level definition of done.
