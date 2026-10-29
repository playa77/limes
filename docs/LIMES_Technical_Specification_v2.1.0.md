> Core product specification, including integrated news intelligence (D-79).
> This document specifies the complete intended product; implementation status,
> completed packages and remaining dependencies are recorded in [ROADMAP](ROADMAP.md).
> [ARCHITECTURE](ARCHITECTURE.md), [OPERATIONS](OPERATIONS.md) and
> [TESTING_PHASE](TESTING_PHASE.md) describe the shipped runtime and supersede
> legacy runtime/configuration examples. [NEWS_REVIEW](NEWS_REVIEW.md) retains
> investigation evidence; open defects remain in [OPEN_ISSUES](../OPEN_ISSUES.md).

<!-- LIMES — Technical Specification | v2.1.0 | 2026-08-01 | Status: Maintained -->

# LIMES — Technical Specification

| Field | Value |
|---|---|
| Document | LIMES — Technical Specification (Document 2 of 3) |
| Version | 2.1.0 |
| Date | 2026-08-01; reconciled 2026-10-28 |
| Status | Maintained implementation contract; acceptance status in both roadmaps |
| Depends on | LIMES — Design Document v2.0.0 (all sections) |
| Supersedes | v2.0.0 (amended in §5.2, §5.3, §5.6, §8.3, §13.3, §15.2); v1.0.0 – v1.3.0, all withdrawn |

## Revision History

| Version | Date | Changes |
|---|---|---|
| 2.1.0 | 2026-08-01 | Embedding merge-stamp amendment (WP-25a). §5.6 stamps `label_embedding = embed(label)` in the loader's merge — the single choke point every entity creation passes through — closing the seam conflict found during WP-25: the §5.3 vector index previously had no registered writer. §5.2 and §15.2 attribute the property to the shared merge routine, not a new writer; §8.3 documents the `embedder` seam and the one-shot backfill `stamp_missing_embeddings`; §13.3 orders the backfill before the first unstructured backfill. The resolver remains read-only against the index (§8.8.3). |
| 2.0.0 | 2026-07-28 | Clean re-issue. Resolves all six open questions in Design Document v2.0.0 §11.2 and all fifteen defects found in the v1.x set. §15 is new and mandatory: a seam register derived from end-to-end call traces, which is the artifact whose absence allowed the v1.x defects. |

### Resolution of Design Document v2.0.0 §11.2

| Question | Resolved in |
|---|---|
| OQ-01 model identifiers | §8.7.2, §12.5 |
| OQ-02 resolution thresholds | §8.8.3 |
| OQ-03 batching and evidence spans | §8.7.4 |
| OQ-04 Neo4j memory | §4.2, §13.4 |
| OQ-05 gold set composition and match semantics | §12.5 |
| OQ-06 plan-gate rules | §8.10.4 |

### Defects Carried Forward From v1.x

Recorded so the same ground is not re-covered. Each is resolved in the section named.

| # | v1.x defect | Resolved in |
|---|---|---|
| 1 | No module created canonical entity nodes | §5.6, §8.3 |
| 2 | Nothing called `SourceRegistry.register` | §8.5.1, §15.2 |
| 3 | `postal_code_to_nuts` was module state, unreachable across processes | §5.9, §8.16 |
| 4 | `ExtractionResult.assertions` typed as resolved assertions the extractor cannot build | §5.5, §8.7.1, §8.9 |
| 5 | `load()` signature omitted lookup rows | §8.3 |
| 6 | Nothing computed the ingestion window | §8.6.2 |
| 7 | `NlqContext`, `CostContext`, `RunContext` referenced but undefined | §8.15, §15.1 |
| 8 | `:Mention` creation policy unspecified | §8.8.5 |
| 9 | `make evaluate` had no construction path | §8.15, §12.6 |
| 10 | Regression baseline stored in markdown | §12.5 |
| 11 | No owner for `source_id` and `content_hash` | §15.2 |
| 12 | Gold-set match semantics undefined | §12.5 |
| 13 | Read-only enforcement assumed RBAC the engine lacks | §7 |
| 14 | API required an inference key it was denied | §7.4 |
| 15 | API required writes it had no credentials for | §7.3 |

---

## 1. Implementation Scope

| ID | Scope item |
|---|---|
| S-01 | Configuration loading, validation, startup failure semantics |
| S-02 | Ontology artifact, schema, registry, self-validation |
| S-03 | Neo4j driver, session modes, schema and index provisioning |
| S-04 | Raw archive store, content addressing, compression |
| S-05 | `SourceAdapter` protocol, source registry, registry population |
| S-06 | Structured adapters: GISCO/NUTS, GLEIF, EUR-Lex, FSD, TED, Transparency Register, Bundestag DIP, Gesetze im Internet, Wikidata, OSM, OffeneRegister |
| S-07 | Integrated inputs: GDELT coded observations, curated DE/EN feeds and agency dispatches |
| S-08 | Normalizer: independent structured/document channels, source/version lineage, language and precise times |
| S-09 | Gate: hash deduplication, spaCy NER, passage selection |
| S-10 | Shared extractor protocol, model implementations, qualified claim/event schema, attribution and evidence |
| S-11 | Extraction cache |
| S-12 | Passive usage/cost ledger and explicit workload limits |
| S-13 | Entity/event resolution: keys, candidate blocking, adjudication, minting, reversible linking |
| S-14 | Graph loader: validation, node materialization, bitemporal merge, lookup rows |
| S-15 | Query API |
| S-16 | NL-to-Cypher: generate, validate, plan, execute |
| S-17 | Coverage report and empty-result diagnosis |
| S-18 | Builder schema projection |
| S-19 | Native desktop: network/map/timeline, console, builder, coverage, qualified claims and versioned evidence |
| S-20 | Saved-query persistence |
| S-21 | CLI and make targets |
| S-22 | Gold set, calibration set, evaluation harness |
| S-23 | Ontology migration |
| S-24 | Images, Compose topology, bootstrap |
| S-25 | Structured logging, run records, status endpoints |
| S-26 | Two-stage model selection |
| S-27 | Composition root and run-context construction |
| S-28 | Cross-process reference data |
| S-29 | Wikipedia revision-linked entity context, DE/EN, shared document processing (planned BE-46) |
| S-30 | Yahoo Finance governance, shareholder structure and earnings/report metadata; identity, schema/loader/API migration and availability semantics (planned BE-46) |

**Out of scope:** Design Document §2.4 applies. CI already exists. Agency/news processing is core scope; no separate extractor product, event-ledger application or second vector database is included.

---

## 2. Project Structure

Paths are authoritative. The desktop client documents reference files by these paths.

```
limes/
├── README.md                    # includes the personal-artifact disclaimer
├── CHANGELOG.md
├── AGENTS.md
├── Makefile
├── pyproject.toml
├── uv.lock
├── .env.example                 # legacy compatibility example
├── config/{secrets,settings,models}.env.example
├── docker-compose.yml
├── docker-compose.override.yml
├── docker/{api,neo4j,worker}.Dockerfile
├── docker/neo4j_control.py      # private lifecycle supervisor
├── docs/                        # INDEX, core/desktop specs, BE/DC roadmaps, evidence, archive
├── ontology/
│   ├── ontology.yaml
│   ├── ontology.schema.json
│   ├── feeds.yaml
│   ├── CHANGELOG.md
│   └── migrations/0001_initial.py
├── gold_set/
│   ├── gold_set.jsonl
│   ├── gold_set.schema.json
│   ├── calibration_set.jsonl
│   ├── baseline.json            # machine-readable regression baseline
│   └── CHANGELOG.md
├── reference_questions/questions.yaml
├── tools/{check_docs,generate_runtime_docs,check_git_baseline,deploy,init_config}.py
├── desktop/                     # uv workspace member: PySide6 desktop client
│   ├── pyproject.toml
│   ├── src/limes_desktop/**     # api/, views/, resources/web/
│   └── tests/{unit,contract,integration}/
├── src/limes/
│   ├── config.py  errors.py  logging_setup.py  types.py
│   ├── composition.py           # THE composition root
│   ├── ontology/{model,registry,validator}.py
│   ├── graph/{driver,schema,loader,temporal,lookups,queries,embeddings}.py
│   ├── archive/store.py
│   ├── sources/{base,registry}.py
│   ├── sources/{gisco_nuts,gleif,eurlex,fsd,ted,transparency_register,
│   │            bundestag_dip,gesetze_im_internet,wikidata,osm,
│   │            offeneregister,gdelt,feeds}.py
│   ├── pipeline/{run,normalize,gate,passages,idempotency,window}.py
│   ├── extraction/{base,openrouter_client,openrouter,ollama,schema,cache}.py
│   ├── extraction/prompts/{extraction,adjudication,nl2cypher}_v1.0.0.md
│   ├── resolution/{keys,blocking,adjudicate,link,resolve}.py
│   ├── cost/{ledger,recorder}.py
│   ├── nlq/{generate,validate,plan,service}.py
│   ├── coverage/{report,diagnose}.py
│   ├── api/{main,deps,models,builder}.py
│   ├── api/routers/{health,ontology,query,entity,search,coverage,
│   │                saved_queries,sources,cost,ingest_status,operations}.py
│   ├── api/auth.py
│   ├── operations/{models,store,worker,client}.py
│   ├── ui/{app,layout,api_client}.py   # retained Dash compatibility, not shipped
│   ├── ui/components/*.py   ui/callbacks/*.py
│   └── cli/{main,ingest,backfill,reextract,select_models,evaluate,migrate,backup,remote}.py
└── tests/{conftest.py,fixtures/,unit/,integration/,acceptance/}
```

Four modules exist that v1.x lacked and whose absence caused defects: `composition.py` (S-27), `pipeline/window.py` (window resolution), `resolution/resolve.py` (mention-to-entity conversion), and `graph/lookups.py` (cross-process reference reads).

---

## 3. Dependencies

Minimum compatible ranges; the committed lock file is authoritative thereafter.

| Package | Constraint | Used by |
|---|---|---|
| `python` | `>=3.12,<3.14` | all |
| `fastapi` | `>=0.115` | api |
| `uvicorn[standard]` | `>=0.30` | api |
| `pydantic` | `>=2.8` | all |
| `pydantic-settings` | `>=2.4` | config |
| `neo4j` | `>=5.24` | graph |
| `httpx` | `>=0.27` | sources, extraction |
| `tenacity` | `>=9.0` | sources, extraction |
| `dash` | `>=2.18` | ui |
| `dash-cytoscape` | `>=1.0` | ui network pane |
| `dash-leaflet` | `>=1.0` | ui map pane |
| `plotly` | `>=5.24` | ui timeline |
| `spacy` | `>=3.7,<4` | gate |
| `de_core_news_md`, `en_core_web_md` | matching spaCy | gate |
| `lxml` | `>=5.3` | sources |
| `feedparser` | `>=6.0` | feeds |
| `pyyaml` | `>=6.0` | ontology, cli |
| `jsonschema` | `>=4.23` | ontology, extraction |
| `orjson` | `>=3.10` | all |
| `structlog` | `>=24.4` | all |
| `python-dateutil` | `>=2.9` | normalize |
| `pandas` | `>=2.2` | sources |
| `typer` | `>=0.12` | cli |
| `pyside6`, `pyside6-addons` | `>=6.7` | desktop client |
| `pytest`, `pytest-asyncio`, `respx` | `>=8.3`, `>=0.24`, `>=0.21` | tests |
| `pytest-qt` | `>=4.4` | desktop client tests |
| `ruff`, `mypy` | `>=0.6`, `>=1.11` | dev |
| `coverage` | `>=7.15` | dev |

Host tooling installs into `./venv/`. `--break-system-packages` is prohibited. Container images install directly; no virtual environment inside an image.

---

## 4. Configuration

### 4.1 Principles

All configuration by environment variable, loaded and validated once at startup. A missing or invalid required key is a startup failure naming the key. Host bind paths are declared deployment/configuration inputs; credentials are never committed.

### 4.2 Split configuration and compatibility

Canonical examples are `config/secrets.env.example`, `config/settings.env.example`
and `config/models.env.example`; config.py is the typed key authority. Initialize
missing private files with tools/init_config.py (host ACL utility required), then
set secrets privately. Configuration binds are read-only in services. Tool-written
model pins and evaluation reports use the models volume; model-only pin validation,
file locking and atomic replacement apply. Empty values are unset; explicit env
values override file pins. Legacy `.env` remains supported for migration only.
No monthly ceiling/envelope is enforced. See OPERATIONS for exact commands.

### 4.3 Startup Validation

Startup fails when: a required key is absent or empty; the ontology artifact is missing, unparsable, or fails its JSON Schema; a pinned model identifier is empty; `LIMES_EMBEDDING_DIMENSIONS` does not match the existing vector index; or the ontology artifact version is *older* than the maximum version stamped in the graph.

There is no read-user write probe. C-01 makes it meaningless — the check would always report that the user can write, because it can. Claiming otherwise was a v1.x defect.

---

## 5. Data Layer

### 5.1 Ontology Artifact

Validated against `ontology.schema.json` at load, then self-validated.

```yaml
version: "1.0.0"
supertypes: [Agent, Place, Artifact]
entity_types:
  - name: Corporation
    supertype: Agent
    identifying_keys: [lei, german_register_number]
    properties:
      - {name: label, type: string, required: true}
      - {name: lei, type: string, required: false, unique: true}
      - {name: legal_form, type: string, required: false}
relation_types:
  - name: SUBSIDIARY_OF
    domain: [Corporation]
    range: [Corporation]
    temporal: true
vocabularies:
  - {name: EuroVoc, applies_to: Topic}
  - {name: CPV, applies_to: Topic}
  - {name: KRITIS, applies_to: Topic}
```

Self-validation rejects: a relation naming an undeclared type in domain or range; an entity naming an undeclared supertype; duplicate names; an identifying key absent from the property list; a property marked unique that is not an identifying key.

`temporal: false` relations are immutable statements of record — `AMENDS`, `REPEALS`, `CITES`, `ESTABLISHED_BY`, `OCCURRED_IN`, `ACTOR_IN`, `TARGET_OF`, `PARTICIPANT_IN`, `MENTIONS`. They carry full provenance but never have `valid_to` set.

### 5.2 Node Labeling and Ownership

Canonical entities carry concrete type, supertype, and `:Entity`: a corporation is `:Entity:Agent:Corporation`. Mentions carry `:Mention` plus inferred type. System nodes carry one label and never `:Entity`.

**Node ownership is partitioned and exclusive.** The complete table is in §15.2. Summary: `graph/loader.py` writes ontology-typed nodes and relationships plus lookup rows and the `label_embedding` merge stamp (§5.6); `resolution/link.py` writes `:Mention` and `SAME_AS`; `pipeline/run.py` writes `:Source` and `:IngestionRun`; `cost/ledger.py` writes `:CostLedgerEntry`; `extraction/cache.py` writes `:ExtractionCacheEntry`; `api/routers/saved_queries.py` writes `:SavedQuery`; `cli/main.py` writes `:AdvisoryLock`. No other module writes any node. **Source adapters write nothing.**

### 5.3 Constraints and Indexes

Provisioned idempotently from the ontology.

```cypher
CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (n:Entity) REQUIRE n.entity_id IS UNIQUE;
CREATE CONSTRAINT mention_id IF NOT EXISTS FOR (n:Mention) REQUIRE n.mention_id IS UNIQUE;
CREATE CONSTRAINT document_hash IF NOT EXISTS FOR (n:Document) REQUIRE n.content_hash IS UNIQUE;

CREATE CONSTRAINT corporation_lei IF NOT EXISTS FOR (n:Corporation) REQUIRE n.lei IS UNIQUE;
CREATE CONSTRAINT legalact_celex IF NOT EXISTS FOR (n:LegalAct) REQUIRE n.celex IS UNIQUE;
CREATE CONSTRAINT country_iso2 IF NOT EXISTS FOR (n:Country) REQUIRE n.iso2 IS UNIQUE;
CREATE CONSTRAINT region_nuts IF NOT EXISTS FOR (n:AdministrativeRegion) REQUIRE n.nuts_code IS UNIQUE;
CREATE CONSTRAINT contract_ted IF NOT EXISTS FOR (n:Contract) REQUIRE n.ted_notice_id IS UNIQUE;
CREATE CONSTRAINT asset_osm IF NOT EXISTS FOR (n:Asset) REQUIRE n.osm_id IS UNIQUE;
CREATE CONSTRAINT interestgroup_tr IF NOT EXISTS FOR (n:InterestGroup) REQUIRE n.transparency_register_id IS UNIQUE;

CREATE CONSTRAINT postal_code_key IF NOT EXISTS
  FOR (p:PostalCode) REQUIRE (p.country_code, p.postal_code) IS UNIQUE;
CREATE CONSTRAINT source_id IF NOT EXISTS FOR (n:Source) REQUIRE n.source_id IS UNIQUE;
CREATE CONSTRAINT run_id IF NOT EXISTS FOR (n:IngestionRun) REQUIRE n.run_id IS UNIQUE;
CREATE CONSTRAINT cache_key IF NOT EXISTS FOR (n:ExtractionCacheEntry) REQUIRE n.cache_key IS UNIQUE;
CREATE CONSTRAINT ledger_id IF NOT EXISTS FOR (n:CostLedgerEntry) REQUIRE n.ledger_id IS UNIQUE;
CREATE CONSTRAINT saved_query_id IF NOT EXISTS FOR (n:SavedQuery) REQUIRE n.saved_query_id IS UNIQUE;
CREATE CONSTRAINT lock_source IF NOT EXISTS FOR (n:AdvisoryLock) REQUIRE n.source_id IS UNIQUE;

CREATE INDEX entity_label IF NOT EXISTS FOR (n:Entity) ON (n.label);
CREATE INDEX entity_wikidata IF NOT EXISTS FOR (n:Entity) ON (n.wikidata_qid);
CREATE INDEX event_timestamp IF NOT EXISTS FOR (n:Event) ON (n.occurred_at);
CREATE INDEX document_published IF NOT EXISTS FOR (n:Document) ON (n.published_at);
CREATE INDEX topic_vocab_code IF NOT EXISTS FOR (n:Topic) ON (n.vocabulary, n.code);
CREATE INDEX ledger_period IF NOT EXISTS FOR (n:CostLedgerEntry) ON (n.period);

CREATE FULLTEXT INDEX document_text IF NOT EXISTS FOR (n:Document) ON EACH [n.title, n.body];
CREATE FULLTEXT INDEX entity_names IF NOT EXISTS FOR (n:Entity) ON EACH [n.label, n.aliases];
CREATE VECTOR INDEX entity_label_embedding IF NOT EXISTS
  FOR (n:Entity) ON (n.label_embedding)
  OPTIONS { indexConfig: { `vector.dimensions`: $dims, `vector.similarity_function`: 'cosine' } };
```

The index is populated by the merge stamp of §5.6 — every entity creation passes through the loader's merge, which is the choke point that stamps `label_embedding` — and by the one-shot backfill `stamp_missing_embeddings` (§8.3); there is no other writer. An empty index is not an error: resolution falls through to minting. A partially populated index silently under-recalls, which is why the backfill runs before the first unstructured backfill (§13.3) and why `load` without an `embedder` logs the omission.

Relationship property indexes on `valid_from`, `valid_to`, `recorded_at` are generated from the ontology for every `temporal: true` relation.

### 5.4 Relation Domains and Ranges

| Relation | Domain | Range | Temporal |
|---|---|---|---|
| `MEMBER_OF` | Person, Corporation, Country | PoliticalParty, InterestGroup, PublicBody, IGO | yes |
| `HOLDS_OFFICE` | Person | Office | yes |
| `OFFICE_AT` | Office | PublicBody, IGO, Corporation, PoliticalParty | yes |
| `DIRECTOR_OF` | Person | Corporation | yes |
| `OWNS_STAKE_IN` | Agent | Corporation | yes |
| `SUBSIDIARY_OF` | Corporation | Corporation | yes |
| `HEADQUARTERED_IN` | Corporation, PublicBody, IGO, InterestGroup, PoliticalParty | Location | yes |
| `LOCATED_IN` | Location, Asset | AdministrativeRegion | yes |
| `PART_OF_REGION` | AdministrativeRegion | AdministrativeRegion, Country | yes |
| `TARGETS` | Sanction | Person, Corporation, Country, Topic | yes |
| `IMPOSED_BY` | Sanction | Country, IGO | yes |
| `ESTABLISHED_BY` | Sanction | LegalAct | no |
| `ADOPTED` | PublicBody, IGO | LegalAct, Document | yes |
| `AMENDS` | LegalAct | LegalAct | no |
| `REPEALS` | LegalAct | LegalAct | no |
| `CITES` | LegalAct, Document | LegalAct, Document | no |
| `APPLIES_TO` | LegalAct | Topic, Corporation, PublicBody | yes |
| `AWARDED_TO` | Contract | Corporation | yes |
| `BUYER_OF` | PublicBody, IGO | Contract | yes |
| `SUPPLIES` | Corporation | Corporation | yes |
| `LOBBIES_FOR` | InterestGroup | Corporation, PoliticalParty, Topic | yes |
| `MET_WITH` | Person, InterestGroup | Person, PublicBody | yes |
| `PARTICIPANT_IN` | Agent | Event | no |
| `ACTOR_IN` | Agent | Event | no |
| `TARGET_OF` | Agent | Event | no |
| `OCCURRED_IN` | Event | Location, AdministrativeRegion, Country | no |
| `OPERATES` | Corporation, PublicBody | Asset | yes |
| `ABOUT_TOPIC` | LegalAct, Contract, Document, Event | Topic | yes |
| `MENTIONS` | Document | Agent, Place, Asset, LegalAct, Topic | no |
| `REPRESENTS` | Person | Country, Agent | yes |

### 5.5 Core Types

Defined once here; every signature in §8 uses these names.

The type listings below describe the implemented baseline. The normative
qualified-claim and source-version fields in this section must be delivered with
BE-43/DC-15, including migrations and every API/desktop consumer. They are part
of the product specification, not optional post-project extensions.

| Payload | Required fields and semantics beyond the baseline listing |
|---|---|
| DocumentPayload | Provider/external dispatch ID, canonical URL, immutable version hash, publication/update time with precision/fallback markers, correction and syndication lineage |
| Provenance | Text version/span or coded export/row locator; report URL, original agency and attribution, distinct from extraction confidence/source trust |
| ExtractedAssertion and Assertion | Statement kind, modality, attributed speaker/proposition, assessment with evidence/rule version and temporal precision; qualifiers survive resolution and persistence |
| Event endpoints | Namespaced source identity, event type/lifecycle and occurrence precision; old Event keys remain compatible |
| NormalizedRecord | Independent structured payload and document payload processing; kind is a routing hint and cannot suppress a populated channel |

Exact enum serialization and graph property/reification choices are selected from
the annotated corpus before implementation, with a versioned migration. Denials
and conditional propositions must not create unqualified factual edges. Missing
historical qualifiers remain unknown, not retroactively inferred. Publication and
fetch timestamps cannot silently substitute for unknown occurrence times.



```python
class Mention(BaseModel):
    """An entity as named in text, before identity is assigned."""

    surface: str
    type: str  # inferred concrete ontology type
    deterministic_key: tuple[str, str] | None = None


class EntityEndpoint(BaseModel):
    """An entity with identity assigned. Everything the loader needs to
    materialize its node. Built by adapters (structured) or the resolver
    (extracted). Never inferred by the loader."""

    entity_id: str
    type: str
    label: str
    deterministic_key: tuple[str, str] | None = None
    aliases: list[str] = []


class Provenance(BaseModel):
    """Where an assertion came from and how much it is trusted."""

    source_id: str
    source_trust: float
    confidence: float
    extractor_model: str | None = None
    prompt_version: str | None = None
    schema_version: str | None = None
    ontology_version: str
    evidence_document_id: str | None = None
    evidence_start: int | None = None
    evidence_end: int | None = None
    evidence_channel: str | None = None
    evidence_member: str | None = None
    evidence_row: int | None = None
    source_event_id: str | None = None
    source_url: str | None = None
    report_url: str | None = None
    source_recorded_at: datetime | None = None
    article_text_available: bool | None = None


class Validity(BaseModel):
    """Bitemporal interval: validity time and belief time, independently
    queryable (Doc 1 §5.6)."""

    valid_from: datetime
    valid_to: datetime | None = None
    recorded_at: datetime
    retracted_at: datetime | None = None


class ExtractedAssertion(BaseModel):
    """Pre-resolution. What the extractor returns. Endpoints are mentions."""

    passage_index: int
    subject: Mention
    relation: str
    object: Mention
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    confidence: float
    evidence_start: int
    evidence_end: int


class Assertion(BaseModel):
    """Resolved. What the loader accepts. Endpoints are identified."""

    assertion_id: str
    subject: EntityEndpoint
    relation: str
    object: EntityEndpoint
    validity: Validity
    provenance: Provenance


class LookupRow(BaseModel):
    """Reference data materialized as system nodes. Cross-process state per
    C-07; never module state, never a derived file."""

    kind: Literal["postal_code"]
    key: dict[str, str]
    value: dict[str, str]


class DocumentPayload(BaseModel):
    """A normalized document ready for gating and extraction."""

    content_hash: str
    title: str
    body: str
    language: str
    published_at: datetime
    url: str | None = None


class Passage(BaseModel):
    """A selected passage within a document, with offsets into the original
    document text."""

    index: int
    text: str
    doc_start: int  # offset in the source document
    doc_end: int


class RawRecord(BaseModel):
    """A raw payload as fetched from a source."""

    payload: bytes
    content_type: str
    source_url: str | None = None
    fetched_at: datetime


class NormalizedRecord(BaseModel):
    """The adapter's normalized output: assertions plus entities that are
    named but appear in no relationship, plus reference data and optionally a
    document payload."""

    content_hash: str
    kind: Literal["structured", "document"]
    assertions: list[Assertion] = []
    entities: list[EntityEndpoint] = []  # named but in no relationship
    lookup_rows: list[LookupRow] = []
    document: DocumentPayload | None = None
    errors: int = 0  # partial normalization failures block checkpoint advancement


class NerSpan(BaseModel):
    """A named-entity recognition span."""

    text: str
    label: str
    start: int
    end: int


class GateDecision(BaseModel):
    """The gate's verdict on a document."""

    passed: bool
    reason: str
    passages: list[Passage]


class ValidationError(BaseModel):
    """One rejected assertion: its index in the input, the reason, and any
    detail the validator can provide."""

    assertion_index: int
    reason: str
    detail: dict[str, object]


class WriteResult(BaseModel):
    """Outcome counters for a batch of graph writes."""

    statements_executed: int
    nodes_created: int
    relationships_created: int
    properties_set: int


class PlanSummary(BaseModel):
    """A parsed query plan from `EXPLAIN`, used by the plan gate."""

    operators: list[str]
    max_estimated_rows: int
    total_estimated_rows: int
    has_cartesian_product: bool
    max_varlength_hops: int | None


class CostLedgerEntry(BaseModel):
    """One paid API call, recorded as a `:CostLedgerEntry` node."""

    ledger_id: str
    period: str  # YYYY-MM
    run_id: str | None = None
    purpose: Literal["extraction", "adjudication", "embedding", "nl2cypher"]
    model_id: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    cost_eur: Decimal
    created_at: datetime


class SourceRecord(BaseModel):
    """In-memory view of a `:Source` node, read by window resolution."""

    source_id: str
    name: str
    kind: Literal["structured", "unstructured"]
    trust_rank: float
    last_success_at: datetime | None = None
    last_run_id: str | None = None


class IngestionRunRecord(BaseModel):
    """The durable record of one ingestion run (`:IngestionRun` node)."""

    run_id: str
    source_id: str
    mode: Literal["ingest", "backfill", "reextract"]
    started_at: datetime
    finished_at: datetime | None = None
    window_from: datetime | None = None
    window_to: datetime | None = None
    records_fetched: int = 0
    nodes_created: int = 0
    nodes_matched: int = 0
    assertions_written: int = 0
    assertions_skipped: int = 0
    assertions_rejected: int = 0
    documents_gated_out: int = 0
    errors: int = 0
    cost_eur: Decimal = Decimal("0")
```

Three further types are defined at their owning module rather than here, because their construction is inseparable from it: `ArchiveStore` (§8.4), `SourceRegistry` (§8.5.1), and `OpenRouterClient` (§8.7.6). Each carries a `class` definition in its section.

`ExtractedAssertion` and `Assertion` are distinct because the extractor runs before resolution and cannot assign an `entity_id`. Conflating them was a v1.x defect that would have failed on first type-check.

### 5.6 Merge Semantics

Per batch, in one transaction:

1. **Materialize endpoint nodes.** For each `EntityEndpoint`, merge on `entity_id` and apply the concrete type label plus every supertype from `Ontology.labels_for`. `ON CREATE` stamps `label`, the deterministic key property, `label_embedding` — the L2-normalized embedding of the label, exactly `LIMES_EMBEDDING_DIMENSIONS` long, cosine-compatible with the §5.3 index — `ontology_version`, `created_at`. `ON MATCH` adds unseen aliases and nothing else — an existing label, key, `label_embedding`, and original ontology version are never overwritten, so a lower-trust source cannot degrade an entity a higher-trust source established. The embedding is a function of the stored label, which the merge never changes, so it is immutable on re-merge; a node created before this contract (null `label_embedding`) is stamped by the one-shot backfill (§8.3) — the only path that fills a null embedding.
2. **Materialize lookup rows** as system nodes per `LookupRow.kind`.
3. If a relationship with the same `assertion_id` exists, skip. This is the idempotency path.
4. Otherwise create it with `recorded_at` now and `valid_from` from the source.
5. Close a superseded interval **only from the same `source_id`**: an existing relationship of the same type between the same endpoints with null `valid_to` and earlier `valid_from` gets `valid_to` set.
6. Never modify relationships from a different `source_id`.

Steps 1 and 2 run for non-temporal relations and for standalone entities with no relationship. An entity in no relationship is real and common — a GLEIF corporation with no parent and no parseable address — and would be invisible to a loader that only materialized assertion endpoints.

**Cypher cannot parameterize labels in the general case.** Group endpoints by label set and issue one statement per distinct set; with 17 types this is at most 17 groups per batch, in practice two or three. The label segment is built from `Ontology.labels_for` and never from source data. If dynamic label syntax is available on the running engine, verify it against the container before adopting — do not assume it.

### 5.7 Temporal Query Fragments

`graph/temporal.py` exposes composable builders, never string concatenation at call sites: `as_of(alias, instant)`, `as_believed(alias, instant)`, `currently(alias)`. The NL-to-Cypher prompt emits these; the validator verifies a temporal relation carries one and injects `currently()` if absent.

### 5.8 System Node Schemas

| Node | Key properties | Written by |
|---|---|---|
| `Source` | `source_id`, `name`, `kind`, `trust_rank`, `last_success_at`, `last_run_id` | `pipeline/run.py` |
| `IngestionRun` | `run_id`, `source_id`, `started_at`, `finished_at`, `window_from`, `window_to`, `records_fetched`, `nodes_created`, `nodes_matched`, `assertions_written`, `assertions_skipped`, `assertions_rejected`, `documents_gated_out`, `errors`, `cost_eur`, `mode` | `pipeline/run.py` |
| `ExtractionCacheEntry` | `cache_key`, `content_hash`, `prompt_version`, `schema_version`, `model_id`, `result_json`, `created_at` | `extraction/cache.py` |
| `CostLedgerEntry` | `ledger_id`, `period`, `run_id`, `purpose`, `model_id`, `input_tokens`, `output_tokens`, `cost_usd`, `cost_eur`, `created_at` | `cost/ledger.py` |
| `SavedQuery` | `saved_query_id`, `question`, `cypher`, `ontology_version`, `result_count`, `created_at`, `pinned` | `api/routers/saved_queries.py` |
| `GoldSetItem` | `item_id`, `language`, `passage`, `expected_json`, `gold_set_version` | `cli/evaluate.py` |
| `PostalCode` | `country_code`, `postal_code`, `nuts_code`, `source_id`, `recorded_at` | `graph/loader.py` |
| `Mention` | `mention_id`, `surface`, `type`, `document_id`, `start`, `end` | `resolution/link.py` |
| `AdvisoryLock` | `source_id`, `run_id`, `acquired_at` | `cli/main.py` |

### 5.9 Cross-Process State

C-07 prohibits relying on module globals between commands. Domain reference
lookups and graph provenance are stored as system nodes. The source archive is
content-addressed filesystem state; extraction caches and usage records are graph
state. Operational jobs use a bounded local SQLite queue on a named volume;
model pins/reports use locked atomic files on a separate models volume. Desktop
profiles use XDG configuration and contain no credentials. These are explicit
state owners, not competing entity stores. No network filesystem/multi-host queue
or in-memory-only checkpoint is assumed.

---

## 6. API Specification

All responses carry `X-LIMES-Ontology-Version`. Error envelope:

```json
{"error": {"code": "CYPHER_VALIDATION_FAILED", "message": "...", "details": {}}}
```

| Method | Path | Purpose | Errors |
|---|---|---|---|
| GET | `/health` | Authenticated liveness, Neo4j reachability, ontology version | 503 |
| GET | `/version` | Authenticated image revision, independent of graph availability | — |
| POST | `/operations/jobs` | Operator-only validated idempotent job submission | 403, 409, 429 |
| GET | `/operations/jobs/{job_id}` | Operator-only status and bounded output | 403, 404 |
| GET | `/operations/capabilities` | Operator job/backup capability | 403 |
| GET | `/ontology` | Full serialized ontology | — |
| GET | `/ontology/versions` | Versions present in the graph with counts | — |
| GET | `/builder/schema` | Ontology projection for UI builder generation | — |
| POST | `/query/cypher` | Execute operator-supplied Cypher after validation | 400, 422, 504 |
| POST | `/query/nl` | Generate, validate, plan, execute from a question | 400, 422, 503, 504 |
| POST | `/query/builder` | Execute a structured builder specification | 400 |
| GET | `/entity/{id}` | Entity with properties, provenance, edge summary | 404 |
| GET | `/entity/{id}/neighbors` | One-hop expansion, relation and temporal filters | 404 |
| GET | `/search` | Full-text over entity labels and document text | — |
| POST | `/coverage` | Coverage report for a query or relation set | 400 |
| GET/POST/DELETE | `/saved-queries` | Self-accreting query library | 409, 404 |
| GET | `/sources` | Registry with trust rank and last refresh | — |
| GET | `/cost/ledger` | Passive period usage/spend entries; no remaining-budget field | — |
| GET | `/ingest/status` | Last run per source, counts, errors | — |

Response models `GraphResult`, `CoverageReport`, `Diagnosis`, `EntityRef`, `EdgeRef`, `NlqOutcome`, `BuilderSpec` are defined in `api/models.py` and compose the §5.5 core types.

`BuilderSpec` is a starting type with property filters plus an ordered hop list of `{relation, direction, target_type, filters, temporal_qualifier}`. The API rejects any spec whose relation is not permitted between adjacent types, making an invalid query unrepresentable rather than merely rejected.

---

Query, entity, neighbor, search and evidence responses expose qualified claims,
source/version locators, correction/syndication lineage and temporal precision.
Builder/NL queries support reported/documented and lifecycle filters plus validity
versus recorded time. Desktop response mirrors and provenance/network/timeline
views consume the same contract; no direct database access. Read a proposal,
denial, agreement and later registry confirmation without treating chronology as
causation. Missing evidence and dependent sources remain visible.

## 7. Authentication, Authorization, and Write Control

Every API route, docs and health requires a bearer token. Consumer/operator tokens must differ; operator tokens can query and submit/read operational jobs. This is a single-operator credential model, not multi-user account management (NG-01).

### 7.1 What C-01 Removes

Neo4j Community Edition has no role-based access control. Additional users can be created; their privileges cannot be restricted. A read-only database user is not creatable. Any design premising an enforcement layer on database privileges is unimplementable on this engine, and stating one was a v1.x defect.

### 7.2 What Enforces Read-Only Instead

1. **Parse-level rejection.** `nlq/validate.py` refuses any statement containing `CREATE`, `MERGE`, `DELETE`, `DETACH`, `SET`, `REMOVE`, `LOAD CSV`, a writing `CALL {}` subquery, or an `apoc.` procedure outside an explicit read-only allowlist. Detection is by inspection of the parsed statement, not substring search. This is the primary defense and the only one that inspects intent.
2. **Driver session mode.** All query-path sessions are opened with read access mode; the driver refuses writes client-side. Weaker than a server privilege, but a real barrier against a validator defect, which is the failure mode of concern.
3. **Enumerated write surface.** §7.3.

### 7.3 The API's Complete Write Surface

Query paths write parameterized usage entries and saved queries. Query Cypher
is validated and executed in read-mode sessions. Operator-only `/operations/jobs`
additionally persists validated commands to the local SQLite queue, with request
UUID idempotency, bounded arguments/output/capacity and no shell. Worker execution
owns ingestion graph changes and physical backup orchestration. The historical
exact-three graph-write count does not prohibit the dedicated operator queue.
No user query can become an arbitrary graph write or host command (AC-18).
Community Edition's lack of RBAC remains a stated residual risk (C-01).

### 7.4 Secrets

`LIMES_OPENROUTER_API_KEY` is held by `api` and `worker`. Both make paid calls — the worker for extraction and resolution, the API for query generation. No UI service is shipped. Desktop credentials are session-only; HTTPS or loopback transport is required. `logging_setup.py` redacts configured secret keys before emission.

### 7.5 Untrusted Ingested Content

Document text is supplied to the model as explicitly delimited data, never concatenated into the instruction portion. Extraction calls carry no tool definitions. Output is schema-constrained. Every assertion is validated against the ontology before reaching the graph and carries its evidence span, so an injected claim is traceable and retractable.

---

## 8. Module Specifications

### 8.1 `config.py`
`Settings` with one typed field per §4.2 key; `load_settings() -> Settings`. Loaded once per process by the composition root (§8.15) or the API startup handler. No module-level singleton read from business logic. Versioned qualified-claim fields remain target requirements; see backend/desktop roadmap dependencies.

### 8.2 Ontology
```python
class Ontology(BaseModel):
    version: str
    supertypes: list[str]
    entity_types: dict[str, EntityTypeSpec]
    relation_types: dict[str, RelationTypeSpec]
    def labels_for(self, type_name: str) -> list[str]: ...
    def permits(self, relation: str, subject_type: str, object_type: str) -> bool: ...
    def serialize_for_prompt(self) -> str: ...

def load_ontology(path: Path) -> Ontology: ...
def validate_assertions(assertions: list[Assertion], ontology: Ontology
                        ) -> tuple[list[Assertion], list[ValidationError]]: ...
```
`permits` resolves supertypes. `serialize_for_prompt` logs its token estimate at startup and warns above 3,000 (A-04). `validate_assertions` partitions rather than raising.

### 8.3 Graph
```python
class GraphDriver:
    def read(self, cypher: str, params: dict, timeout_s: int) -> list[dict]: ...
    def write_batch(self, statements: list[tuple[str, dict]]) -> WriteResult: ...
    def explain(self, cypher: str, params: dict) -> PlanSummary: ...

def provision(driver: GraphDriver, ontology: Ontology, embedding_dimensions: int) -> None: ...

class LoadResult(BaseModel):
    nodes_created: int
    nodes_matched: int
    lookup_rows_written: int
    written: int
    skipped: int
    closed_intervals: int
    rejected: int

def load(driver: GraphDriver, assertions: list[Assertion], ontology: Ontology,
         standalone_entities: list[EntityEndpoint] | None = None,
         lookup_rows: list[LookupRow] | None = None,
         embedder: Callable[[list[str]], list[list[float]]] | None = None) -> LoadResult: ...
def retract(driver: GraphDriver, assertion_ids: list[str], at: datetime) -> int: ...
def stamp_missing_embeddings(driver: GraphDriver,
                             embedder: Callable[[list[str]], list[list[float]]],
                             batch_size: int = 500) -> int: ...
```
`GraphDriver.read` opens sessions in read access mode (§7.2). `load` applies §5.6 in batches of at most 500 assertions per transaction and is the sole writer of ontology-typed nodes, relationships, lookup rows — and, since v2.1.0, the `label_embedding` merge stamp. The `embedder` contract: one vector per input text, in order, each exactly `LIMES_EMBEDDING_DIMENSIONS` long; `load` embeds only endpoints whose node does not exist yet (one read per batch), normalizes every vector defensively, and logs when it runs without an `embedder` — new nodes then carry a null `label_embedding`. `stamp_missing_embeddings` is the one-shot backfill: it pages over `(:Entity) WHERE label_embedding IS NULL`, embeds and stamps each page, returns the count stamped, and is idempotent. An assertion whose endpoint lacks an `entity_id` is rejected as `ENDPOINT_UNIDENTIFIED`, counted, never written.

### 8.4 Archive
```python
class ArchiveStore:
    def __init__(self, root: Path) -> None: ...
    def put(self, source_id: str, payload: bytes, content_type: str) -> str: ...
    def get(self, content_hash: str) -> bytes: ...
    def exists(self, content_hash: str) -> bool: ...
    def path_for(self, content_hash: str) -> Path: ...
```
SHA-256 content addressing, gzip, two-level hex prefix directories, atomic write by temporary name and rename. `put` returns the content hash and is idempotent — an existing hash is a no-op returning the same value.

### 8.5 Sources

#### 8.5.1 Protocol and Registry
```python
class SourceAdapter(Protocol):
    source_id: str
    name: str
    kind: Literal["structured", "unstructured"]
    trust_rank: float
    supports_backfill: bool
    supports_incremental: bool          # governs window resolution, §8.6.2
    def fetch(self, since: datetime | None, until: datetime | None) -> Iterator[RawRecord]: ...
    def normalize(self, record: RawRecord) -> NormalizedRecord: ...

class SourceRegistry:
    def register(self, adapter: SourceAdapter) -> None: ...
    def get(self, source_id: str) -> SourceAdapter: ...      # raises SourceFetchError
    def source_ids(self) -> list[str]: ...
    def trust_rank(self, source_id: str) -> float: ...

def build_default_registry() -> SourceRegistry:
    """The authoritative list of live sources. Adding an adapter means adding
    exactly one line here. This is the only place the ingestable source set
    is defined."""
```

`get` on an unknown identifier raises `SourceFetchError` naming both the unknown source and the registered ones (AC-38).
Import-time self-registration is rejected: it makes the live source set answerable only by listing a directory. Each adapter work package adds one import and one `register()` call to this file — the sole permitted cross-package modification in the project.

Adapters emit records and **write nothing to the graph**.

#### 8.5.2 Source Table

| `source_id` | Access | Emits | Incremental | Trust |
|---|---|---|---|---|
| `gisco_nuts` | Static CSV | `AdministrativeRegion`, `PART_OF_REGION`, `LookupRow(postal_code)` | no | 1.00 |
| `gleif` | Golden copy CSV | `Corporation`, `HEADQUARTERED_IN`, `SUBSIDIARY_OF`, `OWNS_STAKE_IN` | yes | 1.00 |
| `eurlex` | Cellar SPARQL | `LegalAct`, `Topic`, `ADOPTED`, `AMENDS`, `REPEALS`, `CITES`, `ABOUT_TOPIC` | yes | 1.00 |
| `fsd` | Consolidated XML | `Sanction`, `TARGETS`, `IMPOSED_BY`, `ESTABLISHED_BY` | yes | 1.00 |
| `ted` | Bulk XML | `Contract`, `AWARDED_TO`, `BUYER_OF`, `ABOUT_TOPIC` | yes | 1.00 |
| `transparency_register` | Export XML | `InterestGroup`, `LOBBIES_FOR`, `MET_WITH`, `MEMBER_OF` | yes | 1.00 |
| `bundestag_dip` | DIP API | `Person`, `PoliticalParty`, `Office`, `HOLDS_OFFICE`, `OFFICE_AT`, `Document` | yes | 1.00 |
| `gesetze_im_internet` | Index + XML | `LegalAct`, `APPLIES_TO`, `Topic` | yes | 1.00 |
| `wikidata` | SPARQL, read-only enrichment | aliases and QIDs; never bulk-loaded | n/a | 0.90 |
| `osm` | Overpass, DE bbox | `Asset`, `LOCATED_IN`, `OPERATES`, KRITIS `Topic` | no | 0.75 |
| `offeneregister` | Bulk JSON | `Corporation`, `DIRECTOR_OF`, `OWNS_STAKE_IN` | no | 0.30 |
| `gdelt` | 15-min ZIP containing 61-column TSV | Coded `Event` observations, role/location edges, export/row/report provenance; original report documents only when separately acquired | yes | 0.50 |
| `feeds` | RSS/Atom per `feeds.yaml` | One source-versioned document per entry | yes | 0.60–0.70 |
| `wikipedia` (planned BE-46) | MediaWiki API, verified Wikidata sitelinks | Revision-linked entity context and optional evidence-linked extracted claims | Revision-aware refresh, not full history | Source-specific rank set in BE-46 |
| `yahoo_finance` (planned BE-46) | Yahoo Finance through pinned `yfinance` transport | Company/security identity, available officers/board roles, shareholder structure, earnings/report metadata | Dated snapshots, not reconstructed history | Source-specific rank set in BE-46 |
| `news` (BE-43/DC-15) | Dynamic DE/EN public search RSS | Archived index responses and report versions, qualified NewsClaim artifacts; full article text unavailable | Investigation-driven bounded cycles | 0.50 index trust |

The two BE-46 rows are target contracts, absent from the current registry.
Wikipedia must not be confused with the existing enrichment-only Wikidata adapter.
German and European policy remains the scope; neither new adapter promises
comprehensive EU-27 coverage. Core design §3.6 defines the enrichment semantics.

#### 8.5.3 BE-46 adapter, identity and persistence contract (planned)

- `wikipedia`: acquire selected DE/EN article revisions through verified entity/page
  associations. Archive original responses and retain QID, page/revision IDs,
  language, revision timestamp, retrieval time, URLs and attribution/license.
  Deduplicate by source/page/language/revision and content; redirect, disambiguation,
  ambiguous match and missing page cases cannot silently select another entity.
  Context retrieval survives empty extraction. Shared extraction/cache versions and
  exact text spans bind claims to the archived revision, not the latest live page.
- `yahoo_finance`: selected provider is Yahoo Finance. Encapsulate a pinned
  `yfinance` client; register fetch/normalize with existing composition and jobs.
  Preserve company versus exchange-qualified listing/security identity. Link LEI,
  ISIN, QID or provider IDs only when verified and declared in the ontology; names
  and bare tickers alone cannot force a cross-source merge. Resolve unidentified
  officers/holders through the existing resolver before loading.
- Governance observations retain supplied role titles and board/body distinctions,
  with as-of and term dates independently nullable. Shareholding observations retain
  holder and issuer, security/share class, shares, percentage and its denominator,
  value/currency, reporting/as-of date and field/row evidence locator when supplied.
  Model aggregate ownership ratios separately from named holdings; overlapping
  institutional/fund lists and multiple listings cannot be summed as independent
  stakes. Unknown or absent values are not zero; holdings do not establish control.
- Earnings calendars retain estimated/confirmed status where supplied. Report
  metadata retains report kind, fiscal period, publication date and URL when
  available. Never synthesize a published report from a calendar entry, or a
  resignation/disposal from missing snapshot rows. No historical backfill beyond
  the provider's actually available observations is promised.
- Before coding, inspect representative payloads and define versioned ontology,
  migration, assertion/property, loader, cache and API schemas together. Current
  EntityEndpoint/Assertion and label/key-only property stamping cannot preserve
  the proposed enrichment simply by adding a parser. Preserve bitemporal history,
  source-section identity, field units and unknown dates without overwriting
  registry evidence. Numeric fields must remain queryable and source-attributed.
- Operator jobs use bounded selections/pagination, retry/backoff, checkpoints and
  explicit partial results; no fetch on consumer reads. Review applicable provider
  access/retention terms and Wikipedia attribution before live qualification.
  API contracts expose section status, source scope, timestamps, evidence locators
  and unresolved identity. Keep ontology-generated queries and desktop API mirrors
  compatible. Tests mock providers and inference; live upstream availability and
  production ingestion are separate evidence, never inferred from fixtures.

Verified source specifics, adopted from live checks rather than assumed: the NUTS hierarchy file carries no level column, so level derives from `NUTS_ID` length and parent by prefix; the postcode correspondence is at `/v2/pcode/csv/`, not `/postalcodes/`; that file uses mixed single and double quoting requiring explicit quote handling.

`offeneregister` sets `recorded_at` to the **dataset's publication date**, never the ingestion timestamp. Setting it to ingestion time makes multi-year-stale directorships look current and defeats the trust ranking entirely.

`wikidata` does not ingest. It exposes `enrich(entity_type, label) -> WikidataMatch | None` for the resolver, returning `None` on ambiguity rather than guessing.

GDELT acquisition uses `/gdeltv2/YYYYMMDDHHMMSS.export.CSV.zip`, bounded ZIP
inspection/decompression, tab parsing and the complete 61-column map including
ADM2Code/FeatureID for all three geography groups. Decode FIPS10-4 explicitly into
ontology country keys; handle geographic types 1–5 or count unsupported cases.
SQLDATE, DATEADDED, fetch time and report publication are distinct. First slot is
the first boundary at or after `since`, including seconds/microseconds correctly.
SOURCEURL and optional Mentions rows link coded observations to reports; neither
proves availability of article text. No extraction over fabricated summaries.
Malformed archives/schema drift fail or produce explicit counted rejections.
BE-42 implements this export contract. Only export SOURCEURL coverage is claimed;
Full GDELT Mentions coverage and licensed full-article retrieval remain explicit
source-coverage gaps; BE-43 discovers and acquires public investigation search
feeds with missing full text visible. No index response establishes article access.
The adapter is structured-only because exports contain no article text. Maximum
request: 96 slots, 16 MiB compressed, 128 MiB expanded and 250,000 rows per export.
Oversized windows fail before acquisition; submit consecutive explicit windows.
Provenance adds nullable `evidence_channel`, `evidence_member`, `evidence_row`,
`source_event_id`, `source_url`, `report_url`, `source_recorded_at` and
`article_text_available` across loader/API/desktop mirrors. Old absent fields stay
unknown. Row-scoped coded IDs retain separate export/report observations; generic
mixed structured payload has a separate identity from extracted assertions.
Document cache never suppresses structured output; partial normalization/extraction
or validation errors prevent checkpoint advancement and document success caching.
Successful checkpoints use `until` or the run start (not completion), never regress,
and reextract cannot retract coded/structured evidence. Retraction follows successful
replacement loading; a successful empty extraction can retract prior extracted
assertions. Reextract bypasses document cache hits, including retries.

### 8.6 Pipeline

#### 8.6.1 Run Orchestration
```python
class RunSpec(BaseModel):
    source_id: str
    mode: Literal["ingest", "backfill", "reextract"]
    since: datetime | None = None
    until: datetime | None = None
    budget_eur: Decimal | None = None      # legacy compatibility; ignored

def execute_run(spec: RunSpec, ctx: RunContext) -> IngestionRunRecord: ...
```
`execute_run` constructs nothing (§8.15). It proceeds: resolve adapter from `ctx.registry` → merge `:Source` → resolve window (§8.6.2) → open `:IngestionRun` → fetch → archive → normalize → **stamp `source_id` and `source_trust` on every assertion from the registry** → process each populated structured payload through validation/loading and each document payload through gate, extract, resolve and load; never choose one channel exclusively → close the run record with all counts.

Record-level failures are counted and skipped. Fetch and configuration failures
abort the run. Structured writes must survive document cache hits, gating and
empty extraction. Checkpoints and counters identify each channel; advance a source
checkpoint only after its required channels complete. Retry uses idempotent writes;
cache publication follows successful document loading. Reextract retracts only
superseded assertions owned by that document/channel, never independent coded
observations. Work limits stop at durable boundaries with explicit deferred counts;
legacy budget flags cannot terminate or protect a run.

#### 8.6.2 Window Resolution
```python
def resolve_window(spec: RunSpec, adapter: SourceAdapter,
                   source_node: SourceRecord | None) -> tuple[datetime | None, datetime | None]: ...
```
An explicit `since` in the `RunSpec` always wins. Otherwise: if `adapter.supports_incremental`, the window starts at `Source.last_success_at`, or at `now - LIMES_BACKFILL_DAYS_UNSTRUCTURED` if the source has never run; if not incremental, the window is `(None, None)` meaning a full load. This is why `supports_incremental` exists on the protocol and why `Source.last_success_at` is read and not merely written.

#### 8.6.3 Gate
```python
def gate_document(doc: DocumentPayload, ctx: GateContext) -> GateDecision: ...
def select_passages(text: str, language: str, entities: list[NerSpan],
                    window_sentences: int, min_mentions: int) -> list[Passage]: ...
```
Cache-hit check on the current version triple short-circuits at zero cost. spaCy model matches detected language. Passages are merged overlapping windows centered on sentences with at least `min_mentions` recognized entities, each carrying document offsets. A document producing zero passages is recorded as gated-out with the reason and counted in `/ingest/status` — never silently dropped.

### 8.7 Extraction

#### 8.7.1 Protocol
```python
class Extractor(Protocol):
    model_id: str
    def extract(self, passages: list[Passage], ontology: Ontology,
                prompt_version: str, schema_version: str) -> ExtractionResult: ...

class ExtractionResult(BaseModel):
    assertions: list[ExtractedAssertion]      # pre-resolution; see §5.5
    input_tokens: int
    output_tokens: int
    raw_response: str
    parse_errors: list[str]
```

#### 8.7.2 Model Selection
No identifier is asserted here. Two stages, because gold-set evaluation needs a corpus and the corpus needs a pinned model.

**Stage 1, provisional** — `make select-models --provisional` filters the OpenRouter catalogue by role criteria below, ranks by published cost and declared structured-output support, writes the top candidate per role with `LIMES_MODEL_PIN_STAGE=provisional` after operator confirmation. Sufficient to run the backfill and build the corpus, and nothing else.

**Stage 2, measured** — `make select-models --measured` requires a gold set at version 1.0.0 or higher, evaluates the top three candidates per role, writes the winner with stage `measured`. On a change to the extraction or embedding model it reports affected source and document counts with a re-extraction cost estimate and performs no re-extraction; an embedding change additionally requires a vector index rebuild.

| Role | Capability | Cost ceiling | Selected by |
|---|---|---|---|
| Extraction | JSON-schema-constrained output; competent German and English | ≤ USD 0.50/M blended | Gold-set F1 |
| Adjudication | Short-form reasoning, JSON output | ≤ USD 0.30/M | Calibration-set accuracy |
| Embedding | Multilingual, German-competent, ≤ 1536 dims | ≤ USD 0.20/M | Calibration recall@10 |
| NL-to-Cypher | Strong instruction following, code output | ≤ USD 1.00/M blended | Reference-question validation-pass rate |

#### 8.7.3 Output Schema
Versioned JSON Schema, `additionalProperties: false` throughout, requiring `passage_index`, `subject`, `relation`, `object`, `confidence`, `evidence_start`, `evidence_end`; mentions require `surface` and `type`. `relation` and mention `type` are validated against the ontology after parsing, so an out-of-ontology value yields a precise rejection rather than a generic schema error.

The schema additionally requires the qualified-claim fields specified in §5.5.
Validate proposition scope and attribution so an announcement, denial or proposal
cannot become an unqualified completed relationship. Preserve unknown speakers,
dates and assessment. Extraction confidence measures text fidelity; source trust
and corroboration remain separate. Version schema/prompt, cache, ontology and
consumer serialization together. Do not loosen the old prompt's reported-speech
rule before the complete qualified path and migration work.

#### 8.7.4 Batching and Evidence Spans
One call per document carrying up to `LIMES_EXTRACTION_MAX_PASSAGES_PER_CALL` passages, capped at `LIMES_EXTRACTION_MAX_INPUT_TOKENS`; documents exceeding either bound split into multiple calls with independent cache entries.

Returned offsets are passage-local and are mapped to document offsets using each passage's recorded `doc_start`. **An assertion whose mapped span does not contain its subject or object surface is rejected as `EVIDENCE_SPAN_MISMATCH` and counted.** This deterministic check catches the most common extraction failure — a plausible assertion attached to the wrong sentence — at zero cost.

#### 8.7.5 Cache
`cache_key = SHA-256(content_hash | prompt_version | schema_version | model_id)`. A hit costs nothing and is recorded as cached, which is what makes a full rebuild from the archive free while the version triple is unchanged.

#### 8.7.6 OpenRouter Client
```python
class OpenRouterClient:
    def __init__(self, settings: Settings, recorder: CostRecorder) -> None: ...
    def complete(self, messages: list[dict], model_id: str,
                 purpose: str, json_schema: dict | None = None) -> tuple[str, int, int]: ...
    def embed(self, texts: list[str], model_id: str) -> list[list[float]]: ...
    def catalogue(self) -> list[dict]: ...
```
One client for all OpenRouter interaction: chat completions, embeddings, and the model catalogue. It records reported token usage and cost through `CostRecorder.commit` and the ledger. No pre-call spend check exists. Retry policy per §11. Ledger entries are written only for attempts that returned token usage. The API key never reaches a log line.

### 8.8 Resolution

#### 8.8.1 Deterministic Keys
`deterministic_key(mention, ontology) -> tuple[str, str] | None`. When present, resolution terminates with confidence 1.0 — no embedding, no vector query, no adjudication. Structured sources resolve almost entirely through this path, which is why the structured backbone costs nothing.

#### 8.8.2 Blocking
`embed(texts, client)` over mention surface plus type plus one contextual qualifier, with a permanent cache keyed by text and model. `candidates(driver, embedding, entity_type, limit)` queries the vector index.

#### 8.8.3 Thresholds
| Condition | Action | Confidence |
|---|---|---|
| Deterministic key match | Link | 1.00 |
| `cosine ≥ 0.93` and margin ≥ 0.05 | Link automatically | cosine |
| `0.82 ≤ cosine < 0.93`, or `≥ 0.93` with margin < 0.05 | One adjudication call | adjudicator, capped 0.90 |
| `cosine < 0.82` | Mint a new `entity_id`, return an `EntityEndpoint` | 1.00 for the new entity |

Calibrated by `make evaluate --resolution` against 100 hand-labeled pairs: 50 German, 50 English; 40 true matches, 40 hard negatives such as parent-versus-subsidiary name pairs, 20 cross-language.

**The resolver never writes an entity node.** In the mint branch it returns an `EntityEndpoint` and the loader materializes it, so a new entity is created in the same transaction as the assertion that justified it — an entity cannot exist without its evidence.

#### 8.8.4 Conversion
```python
class ResolutionStats(BaseModel):
    deterministic: int
    auto_linked: int
    adjudicated: int
    minted: int

def resolve_assertions(extracted: list[ExtractedAssertion], ctx: RunContext,
                       doc: DocumentPayload) -> tuple[list[Assertion], ResolutionStats]: ...
```
The named converter from pre-resolution to resolved assertions. It creates `:Mention` nodes, resolves each to an `EntityEndpoint`, links them, and assembles `Assertion` objects with full provenance. Its absence in v1.x meant no module owned the step §3.5 described in prose.

Event matching uses source namespace, type/lifecycle, actors/roles, location and
time precision. Candidate retrieval may use existing Neo4j vectors; label/date
similarity alone cannot merge events. Return evidence-backed non-destructive
matches or unresolved alternatives to the loader. Source event and dispatch IDs
are not global event identities. Preserve qualifiers unchanged through conversion.

#### 8.8.5 Mention Policy
**A `:Mention` node is created for every extracted endpoint**, including deterministic-key hits. Without it, an unlink has nothing to detach and an extracted assertion has no traceable surface form. `link` creates a scored `SAME_AS` with method, score, and decision timestamp; `unlink` retracts it. No node is ever deleted or absorbed.

### 8.9 Cost

```python
class CostRecorder:
    def __init__(self, driver: GraphDriver) -> None: ...
    def commit(self, actual: CostLedgerEntry) -> None: ...
```
The recorder writes the durable ledger before incrementing its process total.
Ledger failures cannot falsely increase recorded spend. There is no check,
remaining-budget calculation or refusal based on spend. Legacy budget parameters
are accepted/ignored; they do not bound acquisition. BE-43 adds explicit work
limits, filtering and deferred-item accounting without a monetary governor.

### 8.10 NL-to-Cypher

`answer(question, ctx: NlqContext, execute) -> NlqOutcome`. Four stages per §6.2, at most one regeneration with the failure reason supplied verbatim.

**Validation codes:** `UNKNOWN_LABEL`, `UNKNOWN_RELATION`, `DOMAIN_VIOLATION`, `RANGE_VIOLATION`, `WRITE_CLAUSE`, `DISALLOWED_PROCEDURE`, `LIMIT_EXCEEDS_MAX`. Where a pattern position is untyped, the domain/range check is skipped and a note is attached recording partial verification — silent partial verification would be worse than none.

**Plan-gate rejections:** `CARTESIAN_PRODUCT`; `UNBOUNDED_EXPANSION`; `EXPANSION_TOO_DEEP` above `LIMES_QUERY_MAX_VARLENGTH_HOPS`; `OPERATOR_ROWS_EXCEEDED`; `TOTAL_ROWS_EXCEEDED`. Rejections return the plan summary and leave the Cypher editable.

The generation prompt carries the serialized ontology, the temporal helpers, and no example questions (NG-08).

### 8.11 Coverage
`report_for_relations(driver, relation_types) -> CoverageReport` attaches to every result. `diagnose(driver, cypher, params) -> Diagnosis` runs automatically on zero rows, executing each decomposed clause independently and naming the first that returns nothing, with graph-wide counts and a plain-language note.

### 8.12 API
`api/main.py` loads settings and ontology once at startup, verifies Neo4j reachability, and registers routers. `api/deps.py` injects driver, ontology, settings, and the `NlqContext`. Routers contain no business logic.

### 8.13 UI

The shipped client is PySide6, specified by the desktop architecture/requirements
and DC sequence. src/limes/ui is retained Dash compatibility code, not a service.
`ui/api_client.py` is the only module performing HTTP; one function per endpoint. No UI module holds ontology knowledge, a type name, or a Cypher fragment — the builder is generated entirely from `/builder/schema`. State lives in `dcc.Store`: `current-result`, `selection`, `temporal-filter`, `builder-spec`. The timeline brush triggers a re-query rather than client-side filtering, so no pane shows a subset the graph cannot reproduce.

The desktop client (`desktop/src/limes_desktop/`) is a second API consumer with the same invariants: `api/client.py` is its only module performing HTTP, and `desktop/tests/contract/test_no_ontology_literals.py` enforces that no client module carries an ontology type name, relation name, or Cypher fragment.

### 8.14 CLI

Canonical remote invocation is `limes remote run COMMAND OPTIONS`; remote mode
loads no server secrets/Neo4j credentials. Commands and bounded parameters are
listed in OPERATIONS: ingest, ingest-all, backfill, reextract, select-models,
evaluate, migrate, backup and stamp-embeddings. Save the printed request UUID,
reuse it with identical payload after an uncertain response, and use remote
status UUID --wait to observe. No automatic replay. Ingest/backfill remain real
operator data runs, not implementation verification. Deprecated budget arguments
are ignored. Local CLI commands acquire/release a source advisory lock with stale
lock handling. Operational Make targets use the same authenticated HTTP path.

### 8.15 Composition Root

```python
@dataclass(frozen=True)
class RunContext:
    settings: Settings
    ontology: Ontology
    driver: GraphDriver
    registry: SourceRegistry
    archive: ArchiveStore
    recorder: CostRecorder | None = None
    client: OpenRouterClient | None = None
    extractor: Extractor | None = None
    gate: GateContext | None = None

@dataclass(frozen=True)
class GateContext:
    settings: Settings
    driver: GraphDriver
    nlp_de: Language
    nlp_en: Language

@dataclass(frozen=True)
class NlqContext:
    settings: Settings
    ontology: Ontology
    driver: GraphDriver
    client: OpenRouterClient
    recorder: CostRecorder

def build_run_context(settings: Settings, *, needs_inference: bool,
                      budget_eur: Decimal | None = None) -> RunContext: ...
def build_nlq_context(settings: Settings, ontology: Ontology,
                      driver: GraphDriver) -> NlqContext: ...
```

`composition.py` is the only module that instantiates infrastructure. Nothing below the CLI or the API startup handler constructs a driver, registry, archive, recorder, client, extractor, or gate.

`needs_inference` governs spaCy model loading and extractor construction: a structured-only run loads no models and constructs no extractor, which is what keeps it inside the resource contract.

`build_run_context` calls `provision()` on every construction — idempotent, one round trip — and applies the ontology downgrade guard of §4.3. `make evaluate` uses `build_run_context(needs_inference=True)` and ignores the unused slots; there is one construction path.

### 8.16 Lookups
```python
def postal_code_to_nuts(driver: GraphDriver, country_code: str,
                        postal_code: str) -> str | None: ...
```
Graph query with an in-process LRU cache. A miss returns `None`; the caller leaves the field unassigned and counts it, never guessing and never blocking. Consumers do not import from any adapter module.

---

## 9. Background Jobs

Use the existing API's operator-only durable SQLite job queue and worker.
Acquisition, filtering, extraction and loading execute inside LIMES. The queue
allowlist accepts bounded parameters; external timers submit authenticated jobs,
reuse request UUIDs after uncertain responses, observe status and avoid overlapping
windows. Interrupted paid work is never automatically replayed. Provider access,
retention/display terms, document/byte/window limits and per-channel checkpoints
bound unattended acquisition. Active investigations schedule fresh bounded cycles
in the existing worker (D-82). No fourth service is introduced. Usage/cost accounting is passive; timeout is not a spend cap.

---

## 10. Observability

`structlog` JSON with `run_id`, `source_id`, `module`, `event` on every line, and a redaction processor masking secrets. Mandatory events: run started and finished with counts; adapter fetch completed; document gated out with reason; extraction call issued with tokens and cost; cache hit; assertion rejected with reason; adjudication issued; work deferred and job failure; query validated; plan rejected; query executed with duration.

Durable surfaces: `:IngestionRun` records, the cost ledger, per-source refresh timestamps, and the coverage report on every query. No monitoring stack.

---

## 11. Error Handling

```python
class LimesError(Exception): ...
class ConfigurationError(LimesError): ...        # fatal at startup
class OntologyError(LimesError): ...             # fatal at startup
class SourceFetchError(LimesError): ...          # retryable
class SourceParseError(LimesError): ...          # record-level
class ExtractionError(LimesError): ...           # retryable
class ExtractionSchemaError(LimesError): ...     # record-level
class BudgetExhausted(LimesError): ...           # legacy compatibility; not a spend gate
class ValidationRejected(LimesError): ...        # assertion-level
class EndpointUnidentified(LimesError): ...      # assertion-level
class GraphWriteError(LimesError): ...           # transaction-level
class CypherValidationFailed(LimesError): ...    # request-level, 400
class QueryPlanRejected(LimesError): ...         # request-level, 422
```

**Governing principle: nothing is silently dropped.** Every skip is counted and every count is visible in `/ingest/status`. A pipeline that quietly discards ten percent of its input is indistinguishable from one working correctly.

Retry policy applies to HTTP fetches and inference calls only: exponential backoff from 2 s, factor 2, jittered, maximum 4 attempts, on connection errors, timeouts, 429, and 5xx. Never on other 4xx. Never more than once for a graph write.

HTTP mapping: `CypherValidationFailed` 400, `QueryPlanRejected` 422, legacy `BudgetExhausted` compatibility 402 (no current spend refusal), not found 404, Neo4j timeout 504, unreachable 503, unhandled 500.

---

## 12. Testing Strategy

### 12.1 Unit
Ontology loading and every rejection case; `permits` supertype resolution; assertion validation partitioning; hash stability across processes; passage offsets; evidence-span mapping and mismatch rejection; every validation code; every plan-gate rejection; passive accounting and failed-ledger-write behavior; window resolution for both incremental branches; retry policy.

### 12.2 Integration
Against a disposable Neo4j container. Schema provisioning idempotency; node materialization from assertion endpoints and standalone lists; non-destructive re-merge; supertype labeling; lookup-row materialization; bitemporal merge with within-source closure and cross-source non-closure; idempotent re-ingest with zero new nodes and edges; resolution linking and unlinking; cache-hit path costing nothing; coverage accuracy; empty-result diagnosis naming the correct clause; composition-root construction; cross-process lookup.

**Two construction rules, both mandatory:**

1. **No test may hand-build the state the code under test is supposed to produce.** Loader tests construct assertions and assert on the resulting graph; they do not pre-create endpoint nodes by direct Cypher. Where pre-existing state is needed, it is established by calling the production path. A test that pre-builds its inputs verifies arithmetic while proving nothing about whether the pipeline can produce them — this is precisely how the v1.x node-creation gap survived its own suite.
2. **A cross-process test must cross a real process boundary.** Use `subprocess`, not a fresh object in the same interpreter.

### 12.3 Adapter
Every adapter tested against recorded fixtures with `respx`. No test performs live network access. Each asserts that a known input produces the exact expected record set including deterministic keys and source attribution.

### 12.4 Acceptance
`tests/acceptance/` asserts every criterion in §14 mechanically where possible.

### 12.5 Gold Set

`gold_set/gold_set.jsonl`, independently versioned. 200 items: 90 positive with at least 3 per relation type; 40 hard negatives (hypotheticals, negations, denials, reported speech); 70 uniform random. Balanced 100 German, 100 English. Constructed from the archive after the 90-day backfill, under the provisional model pin. **Labeled from passage text, never from model output**, so the instrument stays neutral.

**Match semantics.** A true positive is an exact match on `(subject.surface_normalized, relation, object.surface_normalized)`, where normalization is casefold plus whitespace collapse. Evidence span is ignored for matching. Comparison is on surfaces, not entity identifiers, because extraction runs pre-resolution. Without a fixed definition the 0.05 regression threshold is meaningless.

**Baseline storage.** `make evaluate` writes machine-readable results to `gold_set/baseline.json` — the gate's sole source of truth — and a human-readable entry to `gold_set/CHANGELOG.md`. It exits non-zero when per-relation-type F1 regresses by more than 0.05 absolute against the baseline. A release gate whose baseline lives in prose is disabled by the first reformatting.

The worker container mounts the repository's `gold_set/` directory read-write; this is declared in the Compose file.

The corpus must cover dispatch versions/corrections, syndication, denials,
proposals, unknown attribution/time, and false cross-source event matches. Report
quality by distinct behavior, evidence fidelity and failure mode, separately from
truth assessment and source trust. Compare news value beyond feeds/GDELT on
matched coverage. Independently sourced ZIP/TSV fixtures validate real field order;
implementation-generated URLs and synthetic CSV cannot be the oracle. A disposable
source-to-graph-to-API/desktop scenario proves both channels and evidence survive.
Automated tests mock paid transports; paid evaluation is an explicit operator run.

### 12.6 Reference Questions

`reference_questions/questions.yaml` holds the five operator questions. They are not templates and not a specification of intended use (NG-08). Two roles:

**Expressibility, data-independent.** Each has hand-written reference Cypher that passes validation and planning against an empty graph, proving the ontology can express the question shape. Must pass regardless of ingested data.

**Generation quality, measured not gated.** `make evaluate --nl2cypher` reports validation-pass rate and structural agreement with the reference query.

### 12.7 Coverage Target
Add coverage for distinct behaviors, regressions and failure modes, sharing invariant checks. The historical BE-40 exercise is not a current 100% target or quota. Preserve independently derived numerical expectations and avoid copied pair suites.

---

## 13. Build, Run, Deploy

### 13.1 Images

The api/worker images use allowlisted build contexts, packaged ontology/prompts/
reference material and non-root UID/GID 7474. spaCy is worker-only. The Neo4j image
includes the private lifecycle supervisor. No image has Docker host-control tools.

### 13.2 Compose

Base topology: api, neo4j, worker, local named mutable volumes, loopback API port
8000 only; internal database/backup endpoints. The development override mounts
source/reload and is excluded from releases. Drop all capabilities and prohibit
new privileges. Exact contract is docs/runtime-contract.json and OPERATIONS.

### 13.3 Bootstrap

Initialize split configuration and secrets privately; build/start via administrator
commands in OPERATIONS. An operator first ingests the structured geography/entity
backbone, then stamps missing embeddings before unstructured extraction. Select
provisional model pins, build independently annotated corpus and calibration data,
then run measured selection/evaluation explicitly. A submitted GDELT command is
not a successful source run: OI-19..OI-22 must be repaired before it is treated as
working coverage. Agency feed/corpus terms and bounded work precede unattended
news. None of these production/data steps is run by documentation verification.

### 13.4 Neo4j Runtime
Heap 2 GB initial and max, page cache 2 GB, transaction memory cap 512 MB, transaction timeout 120 s. Total resident near 4.5 GB, consistent with Design Document §8.2.

### 13.5 Promotion

Deploy only clean committed source using tools/deploy.py, recording revision,
OCI labels and immutable image IDs. Base API publication remains loopback; remote
clients use HTTPS termination or an SSH tunnel. GET /version is authenticated and
works while Neo4j is unavailable. Existing production revision/smoke evidence is
still missing; a clean-source tool is not a deployed-state claim.

### 13.6 Backup

Operator API job → worker → private supervisor POST /backup. Clean stop must
complete within 180 seconds before offline dump; empty dump or failed recovery
fails the job. Restart/readiness occurs even after dump failure. Dumps and source
archive share a volume but a dump does not back up archive/model/queue/config.
Restore on an isolated stopped database and validate recovery before replacing
operator data. Desktop backup is HTTP only.

---

## 14. Acceptance Criteria

These are current requirements, not a declaration that every criterion passes.
D-75/D-77 supersede old monetary, publication and host-backup semantics without
erasing their historical tests/decisions. BE-42/43 and DC-14/15 assign missing
behavior; BE-45 assigns unmeasured release conditions.

| ID | Criterion |
|---|---|
| AC-01 | Startup fails with a named key when any required configuration is absent, and when the ontology artifact is older than the version stamped in the graph. |
| AC-02 | The ontology loads, self-validates, and rejects each malformed case in §5.1. |
| AC-03 | Schema provisioning is idempotent; running it twice produces no error and no duplicate index. |
| AC-04 | All thirteen adapters produce the expected record set from recorded fixtures, with correct deterministic keys and source attribution. |
| AC-05 | Re-running an ingest over an identical window writes zero new relationships and zero new nodes, and reports the skip count. |
| AC-06 | Interval closure occurs within a source and does not occur across sources. |
| AC-07 | Every relationship carries complete non-null assertion metadata; every ontology-typed node carries its type label, supertype labels, and ontology version. Graph-wide audit returns zero rows. |
| AC-08 | Loading into an empty graph materializes endpoint nodes with labels, deterministic keys, and ontology version; standalone entities are materialized identically. No test pre-creates them. |
| AC-09 | Re-merging from a lower-trust source does not overwrite label, deterministic key, or original ontology version; a second identical load reports `nodes_created = 0`. |
| AC-10 | An assertion whose endpoint lacks an `entity_id` is rejected as `ENDPOINT_UNIDENTIFIED`, counted, never written. |
| AC-11 | The gate rejects documents below the mention threshold and records the reason; counts appear in `/ingest/status`. |
| AC-12 | A cache hit on the current version triple issues no paid call and is recorded as cached. |
| AC-13 | An assertion whose evidence span does not contain its subject or object surface is rejected as `EVIDENCE_SPAN_MISMATCH`. |
| AC-14 | Every inference call records usage/cost without monetary enforcement; zero legacy budget does not suppress calls. |
| AC-15 | Backfill/reextract accept legacy budget arguments without enforcing them; usage/run accounting remains durable. |
| AC-16 | Deterministic keys short-circuit resolution with no embedding and no vector query issued. |
| AC-17 | Resolution routes correctly across all four bands in §8.8.3; the mint branch writes no node directly. |
| AC-18 | Read-only validation and query session mode remain independent; dedicated bounded operator jobs require separate authentication and cannot execute arbitrary commands. |
| AC-19 | `unlink` retracts a `SAME_AS` without deleting any node; prior assertions remain attributed. |
| AC-20 | Every validation code in §8.10 is produced by a crafted query and blocks execution. |
| AC-21 | Every plan-gate rejection in §8.10 is produced by a crafted query and blocks execution. |
| AC-22 | A query returning zero rows automatically produces a diagnosis naming the correct failing clause. |
| AC-23 | Every result carries a coverage report with correct graph-wide relation counts and source refresh timestamps. |
| AC-24 | The builder cannot construct a query violating domain or range; every rejection is precise. |
| AC-25 | All five reference questions have hand-written Cypher passing validation and planning against an empty graph. |
| AC-26 | Generated Cypher is returned, displayed, and editable for every natural-language query, including failed ones. |
| AC-27 | Node click expands one hop and merges into the current view without re-running the original query. |
| AC-28 | Edge selection displays full provenance including the originating sentence for news-extracted assertions. |
| AC-29 | All three panes react to a selection change and to a timeline brush within one interaction cycle. |
| AC-30 | Every executed query is persisted with question, Cypher, ontology version, result count. |
| AC-31 | `make evaluate` produces per-relation-type precision, recall, F1, writes `baseline.json`, and exits non-zero on a regression beyond 0.05 read from that file. |
| AC-32 | Total resident memory of all services under a full backfill stays below 11 GB. |
| AC-33 | A full rebuild from the archive with an unchanged version triple issues zero paid calls. |
| AC-34 | Base Compose publishes only loopback API port 8000; database and backup-control ports are never host-published, including development override. |
| AC-35 | The repository contains the personal-artifact disclaimer required by Design Document §7.5. |
| AC-36 | Provisional selection validates catalogue IDs and writes a complete dated pin set without gold-set scoring; confirmation is opt-in. |
| AC-37 | `make select-models --measured` refuses without a gold set, and on re-pinning reports affected counts and cost without re-extracting. |
| AC-38 | `build_default_registry()` returns every delivered adapter; an unknown source fails naming both the unknown and the registered ones. No production module constructs an empty `SourceRegistry`. |
| AC-39 | A value written as a `LookupRow` by one CLI invocation is readable by `postal_code_to_nuts` in a **separate operating-system process**; a miss returns `None` without raising. |
| AC-40 | Composition owns resource construction with the documented API startup exception; pipeline consumers construct no infrastructure. |
| AC-41 | A structured-only run loads no spaCy model and constructs no extractor. |
| AC-42 | Window resolution returns a full load for a non-incremental adapter and a `last_success_at`-anchored window for an incremental one that has run before. |
| AC-43 | `resolve_assertions` converts `ExtractedAssertion` to `Assertion`, creates a `:Mention` per endpoint, and returns stats matching the four resolution bands. |
| AC-44 | Every type named in a §8 signature is defined in §5.5 or §8.15. Verified by `tools/check_docs.py`. |

---

## 15. Seam Register and Call Traces

This section is the executability record. It is built from the call traces in §15.3, not from the module list — building it from the module list is what produced the second round of v1.x defects after the first was fixed.

**A seam absent from §15.2 is a specification defect and must be reported as `[CONFLICT]`, not resolved locally.**

### 15.1 Context Types

Every context type used in a signature anywhere in §8 is defined in §8.15: `RunContext`, `GateContext`, `NlqContext`. There are no others. A context referenced only inside a signature is a defect (AC-44).

### 15.2 Seam Register

| Seam | Constructed or invoked by |
|---|---|
| `Settings` | `build_run_context`; API startup handler |
| `Ontology` | `build_run_context`; API startup handler |
| `GraphDriver` | `build_run_context`; `api/deps.py` |
| `provision()` | `build_run_context`, every invocation |
| Ontology downgrade guard | `provision()` |
| `SourceRegistry` population | `build_default_registry()` |
| `ArchiveStore` | `build_run_context` |
| `OpenRouterClient` | `build_run_context`; `build_nlq_context` |
| `CostRecorder` | `build_run_context`, `build_nlq_context`; client records usage |
| Operator queue | API operations router persists; operations worker claims/runs; source locks remain |
| `Extractor` | `build_run_context` when `needs_inference` |
| `GateContext` and spaCy models | `build_run_context` when `needs_inference` |
| `NlqContext` | `build_nlq_context`, called by `api/deps.py` |
| Ingestion window | `pipeline/window.py::resolve_window`, called by `execute_run` |
| `:Source` lifecycle | `execute_run` |
| `:IngestionRun` lifecycle | `execute_run` |
| `:AdvisoryLock` | `cli/main.py` |
| `Assertion.source_id` | `execute_run`, from the registry |
| `Assertion.source_trust` | `execute_run`, from the registry |
| `NormalizedRecord.content_hash` | `execute_run`, from `ArchiveStore.put` |
| `ExtractedAssertion` → `Assertion` | `resolution/resolve.py::resolve_assertions` |
| `:Mention`, `SAME_AS` | `resolution/link.py` |
| Ontology-typed nodes and relationships; `label_embedding` merge stamp | `graph/loader.py::load` |
| `label_embedding` backfill (nulls only) | `graph/loader.py::stamp_missing_embeddings` |
| `:PostalCode` and lookup rows | `graph/loader.py::load` |
| Lookup reads | `graph/lookups.py` |
| `:ExtractionCacheEntry` | `extraction/cache.py` |
| `:CostLedgerEntry` | `cost/ledger.py`, called by `OpenRouterClient` |
| `:SavedQuery` | `api/routers/saved_queries.py` |
| `:GoldSetItem` | `cli/evaluate.py` |
| `build_run_context` | `cli/ingest.py`, `cli/backfill.py`, `cli/reextract.py`, `cli/evaluate.py` |
| `build_nlq_context` | `api/deps.py`, from the application built by `api/main.py` |
| `execute_run` | `cli/ingest.py`, `cli/backfill.py`, `cli/reextract.py` |
| `pipeline/gate.py::gate_document` | `pipeline/run.py::execute_run` |
| `Extractor.extract` | `pipeline/run.py::execute_run` |
| `resolve_assertions` | `pipeline/run.py::execute_run` |
| `load` | `pipeline/run.py::execute_run` |
| `nlq/service.py::answer` | `api/routers/query.py` |
| `coverage/report.py`, `coverage/diagnose.py` | `api/routers/query.py` |
| FastAPI application | `api/main.py`, documented composition exception; constructs settings, ontology, driver |

The `label_embedding` property is part of the merge choke point's stamp (§5.6): every entity creation — structured loads and resolver-approved mints alike — passes through `graph/loader.py::load`, so the property is attributed to the shared routine through which all writers create entities, not to an eighth writer. Its null-filling path is the one-shot backfill `stamp_missing_embeddings`, also in `graph/loader.py`; the resolver only reads the index.

The integrated news path adds these obligations to the existing owners:

| Handoff | Owner/invoker and required behavior |
|---|---|
| Dispatch versions and coded-row evidence | Source adapters normalize; execute_run archives and stamps authoritative provenance |
| Mixed structured/document output | execute_run processes both channels, independently of document gate/cache outcomes |
| Qualified claims | Extractor.extract produces; resolve_assertions preserves; graph loader validates/persists |
| Event candidates | Resolution returns matched or unresolved endpoints with evidence; loader alone writes |
| Analyst evidence and temporal views | API query/entity serializers project; desktop API models and views consume |
| Schema evolution | Migration and versioned replay update storage, caches and API/desktop together |

### 15.3 Call Traces

**Integrated agency/coded-source trace:** operator HTTP job → existing worker
CLI/run context → adapter fetch → archive → normalize → deterministic payload
validation/load independently of document gate/cache → qualified extraction →
entity/event resolution → ontology validation/load → durable channel completion
and counters → API query/evidence projection → desktop network/timeline evidence.
Corrections preserve old versions; retry/reextract cannot suppress the other
channel. BE-42 and BE-43/DC-15 must demonstrate this trace.

Each primary path, entry point to committed state. Every callee named here has an owning module in §8 and an invoker in §15.2.

**Trace 1 — `make ingest SOURCE=gisco_nuts`**
```
Makefile → authenticated remote CLI → operator API/queue → worker → cli/main.py → cli/ingest.py::ingest_source
  composition.build_run_context(settings, needs_inference=False)
    load_settings · load_ontology · GraphDriver · build_default_registry
    ArchiveStore · provision(+ downgrade guard)
  cli/main.py: acquire :AdvisoryLock
  pipeline/run.py::execute_run(RunSpec, RunContext)
    registry.get → MERGE :Source → window.resolve_window → open :IngestionRun
    adapter.fetch → ArchiveStore.put → adapter.normalize
    stamp source_id, source_trust, content_hash
    ontology.validate_assertions
    graph.loader.load(assertions, entities, lookup_rows)
      materialize nodes → materialize :PostalCode → merge relationships
    close :IngestionRun → release lock
```

**Trace 2 — `make backfill SOURCE=feeds DAYS=90`**
```
cli/backfill.py
  composition.build_run_context(needs_inference=True)
    + CostRecorder + OpenRouterClient + OpenRouterExtractor + GateContext
  execute_run
    adapter.fetch → archive → normalize → DocumentPayload
    pipeline/gate.py::gate_document(doc, ctx.gate)
      cache.get → spaCy NER → select_passages
    extractor.extract → ExtractionResult(list[ExtractedAssertion])
      OpenRouterClient: call → CostRecorder.commit → durable ledger → process total
      map passage offsets → document offsets; reject EVIDENCE_SPAN_MISMATCH
    resolution/resolve.py::resolve_assertions(extracted, ctx, doc)
      create :Mention per endpoint
      keys.deterministic_key → else blocking.embed + candidates → else adjudicate → else mint
      link.link(SAME_AS) → assemble list[Assertion]
    validate_assertions → loader.load → close run
```

**Trace 3 — `POST /query/nl`**
```
api/main.py startup: load_settings · load_ontology · verify reachability
api/deps.py: GraphDriver(read mode) · build_nlq_context
routers/query.py::query_nl
  nlq/service.py::answer(question, NlqContext, execute)
    generate → OpenRouterClient.complete
      call → CostRecorder.commit → ledger (:CostLedgerEntry write, §7.3)
    validate.validate(cypher, ontology, settings)   [+1 regeneration on failure]
    plan.explain_gate(driver, cypher)
    driver.read(cypher)                              [read session mode]
    coverage.report_for_relations → attach
    if empty: coverage.diagnose
    saved_queries.persist (:SavedQuery write, §7.3)
```

**Trace 4 — `make evaluate`**
```
cli/evaluate.py
  composition.build_run_context(needs_inference=True)
  load gold_set.jsonl → validate against gold_set.schema.json
  for each item: extractor.extract → list[ExtractedAssertion]
  compare on (subject.surface_normalized, relation, object.surface_normalized)
  compute precision · recall · F1 per relation type
  read gold_set/baseline.json → compare → write baseline.json
  append human entry to gold_set/CHANGELOG.md
  exit non-zero if any per-relation F1 regressed > 0.05
```

---

## 16. Final Consistency Checklist

### 16.1 Requirement Traceability

| Requirement | Scope items | Verified by |
|---|---|---|
| FR-01 structured ingestion, no inference | S-05, S-06 | AC-04 |
| FR-02 DE/EN agency/news extraction | S-07, S-09, S-10 | AC-04, AC-13; BE-43/DC-15 acceptance |
| FR-03 ontology mapping and rejection | S-02, S-14 | AC-02, AC-07 |
| FR-04 entity resolution, reversible | S-13 | AC-16, AC-17, AC-19 |
| FR-05 bitemporal assertions | S-14 | AC-06, AC-07 |
| FR-06 qualified claims and versioned evidence | S-07, S-10, S-13, S-14, S-19 | AC-07; BE-42/EXTRACT acceptance |
| FR-07 contradictions retained | S-14 | AC-06 |
| FR-08 NL querying with validation | S-16 | AC-20, AC-21 |
| FR-09 ontology-generated builder | S-18 | AC-24 |
| FR-10 empty-result diagnosis | S-17 | AC-22 |
| FR-11 coverage report | S-17 | AC-23 |
| FR-12 three synchronized views | S-19 | AC-29 |
| FR-13 editable generated Cypher | S-19 | AC-26 |
| FR-14 query persistence | S-20 | AC-30 |
| FR-15 usage accounting and workload limits | S-12, S-21 | TESTING_PHASE; BE-43/DC-15 acceptance |
| FR-16 deterministic gating | S-09 | AC-11, AC-12 |
| FR-17 extraction cache | S-11 | AC-12, AC-33 |
| FR-18 bounded operator jobs, external scheduling | S-21, S-24 | TESTING_PHASE; BE-43/DC-15 acceptance |
| FR-19 gold-set gate | S-22 | AC-31 |
| FR-20 Wikipedia entity context | S-29 | §8.5.3; BE-46 revision/evidence acceptance (planned) |
| FR-21 Yahoo Finance company/shareholder enrichment | S-30 | §8.5.3; BE-46 identity/holdings/API acceptance (planned) |

### 16.2 Status and acceptance boundaries

Requirements FR-01–FR-21 and constraints C-01–C-07 remain traceable above.
AC-01–AC-44 are requirements, not a current blanket pass claim. Retired monetary,
Dash and publication semantics have been reconciled under D-75/D-77. The package
matrices in BACKEND_ROADMAP.md and DESKTOP_ROADMAP.md distinguish merged artifacts,
historical evidence, open repairs and unmeasured obligations. API/desktop qualified
claim responses, event matching, per-channel checkpoints and work limits remain
unimplemented, with the next packages and acceptance specified there.

NFR memory/storage/latency goals, provider access, live ingestion, paid-model
quality and production revision/recovery are not certified by mocked tests or
this document check. No current 100% coverage claim is made. New behavior must
satisfy the integrated traces and acceptance gates before its package is closed.

## Investigation-driven reporting contract (BE-43 / D-82)

Tracked means an entity or relation is part of an ongoing investigation that LIMES
actively keeps informed about. Tracking is explicit durable investigation state;
viewing an entity is read-only. The existing worker automatically submits bounded
acquisition cycles for active investigations, refreshes current graph labels and
aliases, and sets up DE/EN search feeds for entity names or both relation endpoints.
Edits change future discovery; pause stops future cycles without deleting evidence.
Failed or interrupted jobs require explicit replay. No fourth service is added.

Public Google News RSS supplies discovery metadata, publisher/report links and
headlines/snippets. Only that fixed HTTPS origin is fetched. Arbitrary linked
publisher pages and paywalls are not fetched; no agency subscription or full-text
license is claimed. All original RSS responses, stable entry envelopes and
acquisition manifests are content-addressed in the archive. Whole-feed changes
must not force re-extraction of unchanged entries. Missing publication times and
article text stay explicitly unknown/unavailable. Publisher plus dispatch ID
identifies dependent reporting; versions coexist and correction status stays
unknown unless the source establishes it.

Ontology 1.1.0 adds NewsDocument and NewsClaim artifacts. It is an additive
migration: existing entity/assertion stamps are retained, and old qualifiers are
unknown. New news extraction uses prompt/schema 2.0.0 with separate attribution,
modality, assessment, event lifecycle, temporal precision and event candidates.
The shared resolver identifies participants; the loader stores NewsClaim artifacts
rather than unqualified factual edges, including for asserted reporting. Thus an
ordinary relation query cannot turn a denial/proposal into a completed fact.
Machine assessment is unassessed; confidence measures extraction fidelity, source
trust is the discovery index's 0.5, and neither supplies corroboration. Event
candidates remain non-destructive hypotheses for BE-44.

Bounds: 256 investigations; four targets and eight DE/EN feeds per cycle; 2 MiB
per response, 25 entries per feed, 15-minute minimum interval; existing worker
job timeout and extraction passage/token caps apply. Fresh cycles are automatic;
failures do not advance the investigation checkpoint and require manual replay.
Partial successes retain evidence/cache and replay idempotently. Archive-only
news-reextract jobs cover at most 200 reports per explicitly paged request, replace
only their own document's claims after successful extraction, and retain retracted
versions with recorded/retraction times. Other sources/channels are untouched.

Authenticated consumers read /news/investigations, /news/claims (investigation,
entity and modality filters), /news/documents/{id}, and /news/evaluation. Operator
credentials change tracking, replay failed acquisition, annotate evidence or submit
news-refresh/news-reextract jobs. Consumer reads never acquire news. The desktop
provides investigation controls and qualified evidence, source spans, unavailable
text, prior versions, unknown event matching and dependent-dispatch explanations.
Ontology-generated queries can inspect claim properties without assuming facts.

Each acquired document enters an unreviewed evaluation pool. Independent DE/EN
behavioral fixtures cover proposal, denial, attribution, conditional statements,
completion, cancellation and unknown precision. Human annotations can grow from
actual investigations; automated extraction is not its own gold annotation.
Representative model-quality measurement is an explicit operator run, separate
from mocked implementation verification.
