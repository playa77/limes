# CHANGELOG — LIMES Ontology Artifact

The ontology is a declarative, independently versioned artifact
(`ontology/ontology.yaml`), validated by `ontology.schema.json` and consumed
by the loader, the Cypher validator, the builder projection, and the API.
Bump the version here per NFR-08; additive changes are minor bumps, breaking
changes are major bumps with a numbered migration (Doc 1 §9.6).

---

## 1.3.0 — 2026-10-29

BE-47 adds DIRECTLY_CONSOLIDATED_BY and ULTIMATELY_CONSOLIDATED_BY from
Corporation to Corporation. Both are temporal accounting-consolidation evidence,
not shareholding percentages or legal subsidiary status. Existing relations and
stamps remain unchanged; normal additive provisioning applies. No destructive
migration is required.

## 1.2.0 — 2026-10-29

BE-46 additive migration: EnrichmentSnapshot, EnrichmentObservation, Security and
SecurityListing, four evidence/listing connections, Corporation QID support and
typed immutable observation properties. Quantities, roles, source dates and field/
row evidence remain queryable without changing official registry assertions.
Existing stamps remain valid; schema provisioning adds constraints/indexes under
the existing lock. No destructive rewrite or inferred snapshot retraction.

## 1.1.0 — 2026-10-28

BE-43 additive NewsDocument/NewsClaim artifacts, typed qualifications and shared
prompt/schema 2.0.0. Existing qualifiers/stamps remain unknown/unchanged.

## 1.0.0 — 2026-08-01

Initial version. 17 entity types under 3 supertypes (Agent, Place, Artifact),
30 relations with declared domains and ranges from Technical Specification
§5.4, nine of them non-temporal (AMENDS, REPEALS, CITES, ESTABLISHED_BY,
OCCURRED_IN, ACTOR_IN, TARGET_OF, PARTICIPANT_IN, MENTIONS), and the three
vocabularies EuroVoc, CPV, KRITIS. Introduced by WP-03.
