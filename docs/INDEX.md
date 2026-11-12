# Documentation map and authority

Updated 2026-11-12 for BE-58 source acquisition scope and the mandatory complete
source set. Start with the product purpose in README, then this map.

| Question | Authoritative document | Boundary |
|---|---|---|
| What does the complete product do? | [README](../README.md) | Intended finished product; not proof of current readiness |
| What is the integrated system design? | [Core design](LIMES_Design_Document_v2.0.0.md) | Integrated registries, news, coded events and Wikipedia/Yahoo Finance enrichment; German and European policy scope |
| What must modules/data/API deliver? | [Technical specification](LIMES_Technical_Specification_v2.1.0.md) | Current contracts plus explicitly assigned target obligations |
| Where are we in each sequence? | [Delivery index](ROADMAP.md), [backend](BACKEND_ROADMAP.md), [desktop](DESKTOP_ROADMAP.md) | Package status and dependencies; BE and DC never share an ambiguous ID |
| What must the desktop display/do? | [Desktop requirements](LIMES_Desktop_Client_Requirements_v1.0.0.md), [architecture](LIMES_Desktop_Client_Architecture_v1.0.0.md) | HTTP consumer with shared claim semantics; acceptance gaps stay explicit |
| What is shipped/configured today? | [Runtime architecture](ARCHITECTURE.md), [operations](OPERATIONS.md), [testing](TESTING_PHASE.md) | Generated from renderer and checked runtime JSON; current topology/access facts |
| What qualifies the current desktop? | [DC-14 qualification](DESKTOP_QUALIFICATION.md) | Current re-review, direct requirement evidence and named external blockers |
| Why are evidence offsets rejected? | [BE-54 span geometry](EXTRACTION_SPAN_GEOMETRY.md) | Passage-local Unicode bounds, versioned generation and live measurement obligation |
| What does the 2020 boundary apply to? | [Source data scope](SOURCE_DATA_SCOPE.md) | All sources retained; acquisition history versus internal fact dates, scoped recovery and acceptance |
| How are partial feeds and source retries repaired? | [BE-52 source repair](INGEST_SOURCE_REPAIR.md) | Checkpoint semantics, extraction versions, bounded transport evidence and operator limits |
| Can corpus ingestion finish and recover? | [BE-57 corpus reliability](CORPUS_INGESTION_RELIABILITY.md) | All-source audit, bulk TED, durable load receipts, partial outcomes and unresolved corpus acceptance |
| What failed in the third full ingest? | [BE-49 repair](INGEST_THIRD_RUN_REPAIR.md) | Supplied deployment evidence, Wikidata defect and resumable OSM acquisition; local qualification remains distinct |
| How are embedding credentials isolated? | [Dedicated embedding credential](EMBEDDING_CREDENTIALS.md) | BE-51 role authentication, pricing, diagnostics and operator deployment |
| What is OSM transport and dead-feed policy? | [BE-53 policy](OSM_TRANSPORT_POLICY.md) | Timeout, mirror retries, bounded transport subdivision and cursor compatibility |
| How are GDELT gaps and failed OSM leaves resumed? | [BE-55 recovery](GDELT_BACKLOG_OSM_LEAVES.md) | Checkpoint addressing, per-leaf cursor state and explicit resubmission |
| How does OSM recover overloaded cells? | [Adaptive acquisition](OSM_ADAPTIVE_ACQUISITION.md) | BE-50 subdivision, resume, completeness and finite limits |
| What failed in the second full ingest? | [BE-48 rerun repair](INGEST_RERUN_REPAIR.md) | Supplied job evidence, fixes, qualification and remaining limits |
| What failed in the first full ingest? | [BE-47 diagnosis](INGEST_RUN_DIAGNOSIS.md) | Current source contracts, acceptance and bounded evidence; no production-success claim |
| Is the current release ready for human testing? | [Current-release readiness](CURRENT_RELEASE_READINESS.md) | Package/ingestion-defect audit, browser repairs and full candidate evidence; live ingestion is separate |
| What defects and external evidence remain? | [OPEN_ISSUES](../OPEN_ISSUES.md) | Current disposition index plus append-only history; direct closure evidence required |
| Why were decisions made? | [DECISIONS](../DECISIONS.md), [CHANGELOG](../CHANGELOG.md) | Historical records, not current blanket acceptance |
| What supports the status audit? | [Baseline audit](BASELINE_AUDIT.md), [news investigation](NEWS_REVIEW.md) | Artifact/ancestry/source evidence and limits; not competing architecture |
| What were the original plans? | [Backend archive](archive/backend-roadmap-2026-08-01.md), [desktop archive](archive/desktop-plan-2026-09-09.md) | Historical definitions only; old commands, ceremonies and boxes are inactive |
| What is proposed for the next version? | [GraphRAG future work](next-version/GRAPHRAG_WORK_PACKAGES.md) | Proposed packages only, after scoped ingestion stability; outside the current release sequence |
| How are German public officeholders acquired? | [BE-56 implementation plan](GERMAN_PARLIAMENT_MEMBERS.md) | Bundestag, all 16 state parliaments, both Bundesverfassungsgericht Senates, Bundesrat and Bundespräsident/in; implemented acquisition and qualified fixtures, separate from deployed coverage |

## Maintenance and precedence

User decisions and AGENTS.md govern delivery. Current runtime JSON/Compose/source
are evidence of implementation; core/desktop specifications define required
behavior, while roadmaps explicitly identify unsupported requirements and defects.
Do not silently weaken a requirement to match code. An intentional requirement
change needs a decision/disposition such as retired budget enforcement or HTTP
backup. No “historical reference” banner excuses contradictory active instructions.

Existing versioned filenames are stable link identities, maintained in place with
review/reconciliation dates. Ontology, prompts and gold data retain independent
version/migration rules. Earlier document states remain available in Git. Archived
plans are not AGENTS.md files and their execution instructions are not active.

Edit tools/generate_runtime_docs.py for generated README/runtime/operations/testing
text, regenerate, then run its --check and tools/check_docs.py. Review package rows,
links and issue dispositions alongside any contract change. Add no new runtime
service, standalone extractor, vector store or shadow roadmap implicitly.
