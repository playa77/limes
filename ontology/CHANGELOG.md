# CHANGELOG — LIMES Ontology Artifact

The ontology is a declarative, independently versioned artifact
(`ontology/ontology.yaml`), validated by `ontology.schema.json` and consumed
by the loader, the Cypher validator, the builder projection, and the API.
Bump the version here per NFR-08; additive changes are minor bumps, breaking
changes are major bumps with a numbered migration (Doc 1 §9.6).

---

## 1.0.0 — 2026-08-01

Initial version. 17 entity types under 3 supertypes (Agent, Place, Artifact),
30 relations with declared domains and ranges from Technical Specification
§5.4, nine of them non-temporal (AMENDS, REPEALS, CITES, ESTABLISHED_BY,
OCCURRED_IN, ACTOR_IN, TARGET_OF, PARTICIPANT_IN, MENTIONS), and the three
vocabularies EuroVoc, CPV, KRITIS. Introduced by WP-03.
