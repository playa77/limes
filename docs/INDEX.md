# Documentation map and authority

Updated 2026-10-28. Start with the product purpose in README, then this map.

| Question | Authoritative document | Boundary |
|---|---|---|
| What does the complete product do? | [README](../README.md) | Intended finished product; not proof of current readiness |
| What is the integrated system design? | [Core design](LIMES_Design_Document_v2.0.0.md) | Integrated registries, news, coded events and Wikipedia/Yahoo Finance enrichment; German and European policy scope |
| What must modules/data/API deliver? | [Technical specification](LIMES_Technical_Specification_v2.1.0.md) | Current contracts plus explicitly assigned target obligations |
| Where are we in each sequence? | [Delivery index](ROADMAP.md), [backend](BACKEND_ROADMAP.md), [desktop](DESKTOP_ROADMAP.md) | Package status and dependencies; BE and DC never share an ambiguous ID |
| What must the desktop display/do? | [Desktop requirements](LIMES_Desktop_Client_Requirements_v1.0.0.md), [architecture](LIMES_Desktop_Client_Architecture_v1.0.0.md) | HTTP consumer with shared claim semantics; acceptance gaps stay explicit |
| What is shipped/configured today? | [Runtime architecture](ARCHITECTURE.md), [operations](OPERATIONS.md), [testing](TESTING_PHASE.md) | Generated from renderer and checked runtime JSON; current topology/access facts |
| What qualifies the current desktop? | [DC-14 qualification](DESKTOP_QUALIFICATION.md) | Current re-review, direct requirement evidence and named external blockers |
| What failed in the first full ingest? | [BE-47 diagnosis](INGEST_RUN_DIAGNOSIS.md) | Current source contracts, acceptance and bounded evidence; no production-success claim |
| What defects and external evidence remain? | [OPEN_ISSUES](../OPEN_ISSUES.md) | Current disposition index plus append-only history; direct closure evidence required |
| Why were decisions made? | [DECISIONS](../DECISIONS.md), [CHANGELOG](../CHANGELOG.md) | Historical records, not current blanket acceptance |
| What supports the status audit? | [Baseline audit](BASELINE_AUDIT.md), [news investigation](NEWS_REVIEW.md) | Artifact/ancestry/source evidence and limits; not competing architecture |
| What were the original plans? | [Backend archive](archive/backend-roadmap-2026-08-01.md), [desktop archive](archive/desktop-plan-2026-09-09.md) | Historical definitions only; old commands, ceremonies and boxes are inactive |
| What is proposed for the next version? | [GraphRAG future work](next-version/GRAPHRAG_WORK_PACKAGES.md) | Proposed packages only, after scoped ingestion stability; outside the current release sequence |

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
