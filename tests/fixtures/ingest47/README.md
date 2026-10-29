# BE-47 current-source format evidence

Collected 2026-10-29 using bounded public metadata/format probes. No paid model
or graph ingestion was used to collect these fixtures. Tests mock all transports.

- `gleif-rr.csv`: unchanged header and three selected complete rows (one fund
  management, one direct consolidation, one ultimate consolidation) from the
  first 64 KiB of the official 20261029-1600 RR golden-copy ZIP. Publication
  catalog: https://goldencopy.gleif.org/api/v2/golden-copies/publishes . ZIP:
  https://goldencopy.gleif.org/storage/golden-copy-files/2026/10/29/1294625/20261029-1600-gleif-goldencopy-rr-golden-copy.csv.zip .
  Selection/order is reduced for tests; no full ZIP checksum/download is claimed.
  GLEIF public data; source definitions distinguish accounting consolidation from
  legal ownership. Fund management is retained in the archive, not relabeled.
- `offeneregister.jsonl`: first two complete unchanged JSONL records decompressed
  from a bounded prefix of https://daten.offeneregister.de/de_companies_ocdata.jsonl.bz2 .
  Attribution: **from OpenCorporates**, published by OffeneRegister under CC-BY 4.0.
  Source/readme: https://offeneregister.de/daten/ . Rows carry 2018 `retrieved_at`
  observations. HTTP Last-Modified (2019-02-05) is not a publication or observation
  timestamp and is not used in assertions. No date of birth is required or used.
- `transparency.xml`: first two complete interest-representative elements from
  https://transparency-register.europa.eu/odplastorganisationxml_en (redirects to
  https://ec.europa.eu/transparencyregister/public/files/ODP/download/XML/latest).
  Export date is unchanged; numberOfIR is adjusted from 18068 to 2 to describe
  this deliberately reduced fixture. Catalog:
  https://data.europa.eu/api/hub/search/datasets/transparency-register .
  License: European Commission reuse notice, Decision 2011/833/EU. Current export
  does not carry the legacy fixture's head-person/meeting relationships.
- `ted-contract.xml`: unchanged public XML for notice 745241-2026, retrieved at
  https://ted.europa.eu/en/notice/745241-2026/xml . EU/TED public notice data;
  see https://ted.europa.eu/en/legal-notice . It has two lots and no awarded result.
- `ted-award.xml`: independently authored synthetic two-lot/consortium example.
  The actual ID/reference and winner-status structure was checked against the
  official eForms SDK `examples/notices/can_24_maximal.xml`:
  https://github.com/OP-TED/eForms-SDK . No SDK source file is redistributed.
  Synthetic identities/publication dates are explicit. One winning result points
  at three party members; a losing lot references a tender but creates no award.
- `eurlex.json`: unchanged two-binding response to the corrected CDM query
  (`_build_query(None, None) LIMIT 2`) at
  https://publications.europa.eu/webapi/rdf/sparql . It contains one standalone
  legal act and one amendment; unknown author identifiers remain unmapped.
  EU Publications Office public metadata. Separate one-row probes proved the
  canonical `resource_legal_id_celex` predicate returns data and the old
  `resource-legal-id-celex` predicate returns none.

Production source availability, full data coverage, redistribution outside the
source's stated terms and production-scale resources are not established by a
small format fixture. No fixture licenses a change to the meaning of its data.

The eForms ISO3-to-ISO2 country reference in src/limes/sources/country_codes.py
is derived from GeoNames countryInfo.txt, retrieved 2026-10-29, CC BY 4.0:
https://download.geonames.org/export/dump/countryInfo.txt . Source SHA-256:
5c710efde90ee4cca15001c9f6a97ae7a74c7020b365504913ddc3afeb6d3671 .
This preserves existing TED buyer and shared address identities; unknown codes
are preserved and never guessed. An independent Austria fixture expectation checks
both the legacy buyer/address digests and the ISO2 postal-correspondence lookup.
