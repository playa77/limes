<!-- LIMES — README | v2.1.1 | 2026-08-03 -->

# LIMES

An ontology-driven knowledge graph for German and European policy and geostrategic analysis.

LIMES ingests official registries and unstructured German- and English-language text, maps both onto a fixed ontology of real-world entities and relationships, and provides network, geographic, and temporal views over the result. It does not count transactions. It records that a specific corporation was a subsidiary of a specific parent during a specific interval, according to a specific source, with a specific confidence — and lets you traverse outward from there.

---

## Disclaimer

**LIMES is a personal research artifact.** It is not operated as a service, not distributed, and not intended for third-party access. Single operator, local machine.

It stores information about named natural persons in public roles — office holders, registered directors, registered interest representatives — with relationships inferred between them. It implements no person-scope rule, no retention policy, and no pseudonymization. These are explicit non-goals (Design Document §2.4, NG-03); the architecture reserves insertion points but implements nothing.

No warranty of accuracy. A substantial fraction of the graph comes from language-model extraction over news text and is wrong some of the time. Every assertion carries its source, confidence, and where applicable the sentence that produced it, precisely so no claim has to be taken on faith. Use the provenance panel.

---

## Design Principles

**The structured backbone costs no inference.** Eleven of thirteen sources are deterministic parsers over official registries — GLEIF, EUR-Lex, the EU sanctions database, TED, the Transparency Register, Bundestag DIP. They produce the most valuable and most reliable edges: ownership, sanctions, contracts, office-holding, legal citation. They cost nothing per record and cannot hallucinate. Language-model extraction is a supplement over news text, not the engine.

**Every assertion is bitemporal.** Validity time — when a fact was true in the world — is recorded independently of belief time, when the system came to believe it. That makes "who controlled this company in March 2025" and "what did the graph believe in March 2025" two separately answerable questions. The second is how extraction quality is measured over time.

**Contradictions are retained, not resolved.** Two sources disagreeing persist as two assertions under different source identifiers; a trust ranking picks a default at query time. In this domain, disagreement is frequently the signal.

**An empty result is diagnosed, never merely returned.** The characteristic failure of a system like this is absence of evidence reading as evidence of absence. When a query returns nothing, LIMES decomposes it, executes each clause independently, and reports which hop emptied the set alongside graph-wide counts. Every result — empty or not — carries a coverage report.

---

## Architecture

```
Sources ──► Adapters ──► Archive (system of record)
                            │
                            ▼
            Normalize ──► Gate ──► Extract ──► Resolve ──► Load
            (structured records bypass Gate and Extract)
                            │
                            ▼
              Neo4j — graph · vectors · full text · points
                            │
                            ▼
              FastAPI query API ──► Dash UI
                                    network · map · timeline
```

One composition root (`src/limes/composition.py`) constructs every component. Nothing below the CLI or the API startup handler instantiates infrastructure.

| Component | Choice | Reason |
|---|---|---|
| Storage | Neo4j Community | Graph, vectors, full text, point geometry in one engine |
| Inference | OpenRouter | Extraction, adjudication, embedding, Cypher generation |
| Local NLP | spaCy | Free deterministic gate before any paid call |
| API | FastAPI | The contract that keeps the UI replaceable |
| Interface | Dash + Cytoscape + Leaflet + Plotly | Real event model; supports incremental graph expansion |
| Runtime | Docker Compose | Single host, no orchestrator |

The ontology is a declarative, independently versioned YAML artifact — 17 entity types under 3 supertypes, 30 relations with declared domain and range — consumed by the loader, the Cypher validator, the query builder, and the API. One definition, not four drifting copies.

---

## Querying

**Natural language.** A German or English question is sent with the complete serialized ontology, small enough to include in full. Generated Cypher is then validated deterministically: labels and relations must exist, domain and range must be satisfied, write clauses are refused at parse level, `EXPLAIN` runs before execution. The generated query is always displayed and always editable.

**Query builder.** Generated from the ontology at runtime, not authored. It cannot construct an invalid query and costs nothing per use.

**Cypher console.** Direct, validated, read-only.

No query templates exist, by design. Templates encode anticipated questions; the instrument is for unanticipated ones. The saved-query list accretes from what you actually ask.

---

## Requirements

Docker and Docker Compose · 12 GB RAM available to the Docker host · 100 GB free disk · an OpenRouter API key · no GPU.

---

## Bootstrap

Order is a hard dependency chain. See Technical Specification §13.3.

```bash
cp .env.example .env                            # 1. populate secrets
make up                                         # 2. starts the four services; builds the images on first run
make select-models ARGS="--provisional"         # 3. catalogue criteria only, operator confirmation
make ingest SOURCE=gisco_nuts                   # 4. geography + postal correspondence
make ingest SOURCE=gleif                        # 5. legal-entity backbone
make ingest-all                                 # 6. remaining structured sources
make stamp-embeddings                           # one-shot embedding backfill (§13.3)
make backfill SOURCE=feeds DAYS=90 BUDGET=3.00  # 7. unstructured backfill, explicit envelope
make backfill SOURCE=gdelt DAYS=90 BUDGET=2.00  # 8.
# 9. build the gold set and calibration set from the archive, then:
make select-models ARGS="--measured"            # 10. measure the candidates
make evaluate                                   # 11. records the regression baseline
```

**Ordering constraints.** Steps 4–6 must precede 7–8: extraction against an empty entity backbone produces mentions with nothing to resolve against; every one becomes a fresh canonical entity and the work is paid for twice — the single most expensive avoidable mistake in the bootstrap. The one-shot embedding backfill runs after step 6 and before step 7, so the vector index is fully populated before the first unstructured backfill; a partially populated index silently under-recalls. Step 9 precedes 10 precedes 11 — a measurement taken before the corpus exists is not a measurement. There is no separate `bootstrap-db` step: Community Edition offers no roles to create (C-01), and schema provisioning runs on every context build. The `limes` database user is created by the Neo4j service's own boot wrapper on every fresh data volume (see DECISIONS.md).

UI at `http://127.0.0.1:8050`, published to loopback only by the local override file. The base Compose file publishes no ports at all (AC-34); promotion to a server is removal of the override, not a rewrite (§13.5).

---

## Operation

All ingestion is manual. No scheduler, which also means nothing spends money without you initiating it. Every command runs inside the worker container; configuration flows from `.env`.

| Command | Purpose |
|---|---|
| `make up` / `make down` | Start / stop the four services |
| `make bootstrap-db` | No-op: C-01 offers no roles; provisioning runs on every context build |
| `make ingest SOURCE=<id>` | Ingest one source |
| `make ingest-all` | Every registered source |
| `make backfill SOURCE=<id> DAYS=<n> BUDGET=<eur>` | Historical load; budget mandatory |
| `make reextract PROMPT_VERSION=<v> BUDGET=<eur>` | Re-extract archived content; budget mandatory |
| `make select-models ARGS="--provisional"` | Rank and pin by criteria; operator confirmation |
| `make select-models ARGS="--measured"` | Measure the candidates against the gold set |
| `make evaluate ARGS="--resolution"` | Measure extraction quality against the gold set |
| `make migrate ONTOLOGY_VERSION=<v>` | Apply ontology migrations |
| `make backup` | Offline database dump into the archive volume |
| `make stamp-embeddings` | One-shot `label_embedding` backfill (§13.3) |
| `python3 tools/check_docs.py docs/` | Validate specification consistency |
| `python3 tools/smoke_test.py` | Clean-host smoke test of the bootstrap core (up, ingest, count, down) |

### Budget

A hard governor, not discipline: every call is metered, and a call that would breach the monthly ceiling is refused and its document queued. Backfill and re-extraction run under separate authorized envelopes and never draw on the monthly budget. `/cost/ledger` and the UI indicator show current spend.

### Versioned artifacts

| Artifact | Changelog |
|---|---|
| Project | `CHANGELOG.md` |
| Ontology | `ontology/CHANGELOG.md` |
| Gold set | `gold_set/CHANGELOG.md` (baseline in `gold_set/baseline.json`) |
| Prompts and extraction schema | filename-embedded, recorded in `CHANGELOG.md` |

Every assertion records the ontology version, prompt version, schema version, and model that produced it. A model or prompt change is a versioned, re-runnable, costed event with a measurable effect — not silent drift.

---

## Security Posture, Stated Honestly

Neo4j Community Edition has **no role-based access control**. A read-only database user is not creatable. Read-only on the query path is enforced by parse-level rejection of write clauses, by driver session access mode, and by the API having exactly three enumerated writes — a cost ledger entry, a saved query, and a saved-query delete — verified mechanically.

**Residual risk:** a defect in the Cypher validator combined with a defect in session-mode selection can write to the graph. On Community Edition the database cannot prevent this. For a single-operator local system this is accepted, and it is recorded here rather than concealed behind a privilege claim the engine cannot honor.

---

## Known Coverage Limitations

Properties of the available data, not defects. Read the coverage report before drawing a conclusion from an empty result.

1. **Supplier relationships have no structured source.** `SUPPLIES` edges come from news extraction only — sparse, low-confidence, biased toward what was reported.
2. **Current German directorships are structurally weak.** OffeneRegister is materially stale and is ingested at the lowest trust rank with its own publication date as `recorded_at`, not the ingestion date.
3. **OpenStreetMap infrastructure coverage is uneven** in completeness and tagging discipline.

---

## Documentation

| Document | Location |
|---|---|
| Design Document v2.0.0 | `docs/LIMES_Design_Document_v2.0.0.md` |
| Technical Specification v2.1.0 | `docs/LIMES_Technical_Specification_v2.1.0.md` |
| Coding agent contract | `AGENTS.md` |

The v1.x document set is withdrawn. It passed every internal consistency check and still stalled implementation three times, because those checks all pass for a specification whose modules cannot reach each other. Technical Specification §15 — a seam register derived from end-to-end call traces — is the artifact whose absence allowed it.

The initial Implementation Roadmap is deleted: it was the plan for a one-time delivery, and that plan is now executed. The Design Document and Technical Specification are the two remaining, authoritative artifacts.

---

## Non-Goals

Multi-user access, authentication, authorization. Scheduled ingestion. Personal-data scoping and pseudonymization. Paid data sources. Quantitative economic series. Polygon geospatial operations. Production deployment. Distribution.
