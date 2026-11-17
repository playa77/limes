# BE-59 — Nordrhein-Westfalen rescope

Approved 2026-11-17. Branch `claude/gracious-sagan-hfh9fq`, live GitHub base
`846ef04e6a13`. This is the complete geographic-scope package. It supersedes the
German/European geographic scope and the "every source stays" rule of
[BE-58](SOURCE_DATA_SCOPE.md) (D-105) for the sources listed as retired below. The
2020-01-01 inclusive UTC acquisition floor, the ontology's entity and relation
types and every non-geographic invariant are unchanged.

## Why

LIMES is a portfolio/demonstration system. Ingesting Germany- and EU-wide corpora
(TED packages, GLEIF and OffeneRegister bulk files, global GDELT exports, all 17
parliaments) made a complete, reproducible corpus unviable for its purpose. The
product is now **Nordrhein-Westfalen (NRW) only**: NUTS-1 `DEA`, ISO 3166-2
`DE-NW`, Wikidata `Q1198`, OSM relation `62761`.

## Acquisition principle

Select NRW **at the source**, not after a nationwide download. Each retained
source must use a server-side NRW filter or a bounded request set that only names
NRW objects. Where no NRW slice exists and the source is a large corpus, it is
retired rather than downloaded and filtered. The only permitted exceptions are
small single-file references or registers with no query interface (named below),
filtered during normalization by an authoritative NRW criterion and recorded as
such. `limes.geo_scope` owns every NRW constant; adapters never restate them.

## Source disposition

| Source | Disposition | NRW selection |
|---|---|---|
| GISCO/NUTS | Retarget | Hierarchy keeps `DE` and `DEA*` only. The German postcode correspondence (~8k rows, one small reference file; GISCO publishes no per-Land file) keeps rows mapping into `DEA*`. |
| GLEIF | Retarget | LEI API `filter[entity.addresses.region]=DE-NW` (≈44k records, ≈222 pages of 200) with `include=direct-parent,ultimate-parent`. The global golden copy is no longer downloaded. |
| TED | Retarget | Search API expert query `place-of-performance IN (DEA)` restricted to result/award notice types from 2020-01-01, then one XML per listed notice (≈76k notices instead of ≈2.2M EU-wide). Monthly/daily EU packages are no longer downloaded. |
| OpenStreetMap | Retarget | Overpass queries restricted to the NRW administrative area inside NRW bounding-box cells. |
| Official public offices | Retarget | `nw` (Landtag NRW, all members); `bt` (Bundestag members whose official profile states an NRW constituency or NRW Landesliste mandate); `br` (Bundesrat members representing Nordrhein-Westfalen). |
| Wikidata NRW organisations | **New** | SPARQL, one bounded query per organisation class (business, enterprise, voluntary association, nonprofit, foundation) whose headquarters is located (P131*) in `Q1198`. Supplies companies and Vereine without any registry bulk download. |
| EU sanctions (FSD) | Keep, filtered | One current consolidated file with no query interface; only entries with an address whose postcode the GISCO correspondence places in `DEA*`, or whose city is an NRW municipality name in that address, are emitted. |
| EU Transparency Register | Keep, filtered | One current export with no query interface; only organisations whose head-office address is in NRW by the same criterion are emitted. |
| Curated feeds | Retarget | Landesregierung NRW (land.nrw) and WDR "Politik in NRW". EU Commission, Bundesregierung and tagesschau feeds are removed. |
| Investigation news, Wikipedia, Yahoo Finance | Unchanged | Already driven by reviewed graph identities, which are now NRW identities. |
| Wikidata identity enrichment | Unchanged | Resolver enrichment only. |
| EUR-Lex | **Retired** | No NRW slice; complete EU catalogue. |
| GDELT | **Retired** | Global 15-minute exports with no server-side geographic filter; NRW events come from NRW feeds and investigation news. |
| OffeneRegister | **Retired** | Nationwide 2018 bulk dump; query endpoint unavailable. Companies/Vereine come from GLEIF and Wikidata. |
| Gesetze im Internet | **Retired** | Federal law. NRW state law (recht.nrw.de) exposes no documented machine interface; see open gap OI-37. |
| Bundestag DIP | **Retired** | Person catalogue has no Land/constituency field; NRW MdBs come from the official roster. |
| 15 other Landtage, both BVerfG Senates, Bundespräsident | **Retired** | Outside NRW. |

The ontology keeps every entity and relation type (for example `LegalAct`,
`Event`, `bgb_citation`, `bundestag_id`): retiring a source removes a producer,
not a type. Archived evidence from retired sources stays content-addressed and
readable; no archive purge, graph deletion or deployed reconciliation is part of
this package.

## Acceptance checklist

- **N1** `limes.geo_scope` defines the NRW identifiers once; `DATA_SCOPE_VERSION`
  changes so legacy Germany/EU journals cannot certify the NRW corpus.
- **N2** The registry contains exactly the retained and new sources above; retired
  adapters, their fixtures and tests are removed and no runtime path names them.
- **N3** Each retargeted adapter selects NRW at the source as tabled, with tests
  on recorded or constructed fixtures and no live calls in tests.
- **N4** The Wikidata NRW organisation source emits ontology-valid `Corporation`
  and `InterestGroup` entities with QID identity and NRW headquarters locations.
- **N5** FSD and Transparency Register emit only NRW-addressed records and count
  what they skip.
- **N6** README, documentation index, core design, technical specification,
  roadmaps, OPEN_ISSUES, DECISIONS, CHANGELOG and AGENTS source scope describe the
  NRW product; generated runtime docs are regenerated, not hand-edited.
- **N7** Lint, type checks, documentation checks and the affected test lanes pass.

## Not included

Production ingestion, purge of archived non-NRW evidence, deployed graph
reconciliation, an NRW state-law adapter (blocked on a documented interface) and
municipal councils.
