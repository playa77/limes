# Wikidata NRW organisation fixture (BE-59)

`organisations.json` is a constructed SPARQL 1.1 JSON results document in the
shape the Wikidata Query Service returns for `wikidata_nrw.build_query()`. It is
not a live capture: Wikimedia rate-limited this development host on 2026-11-17,
so no further live probes were made. One unrecorded live run of the same query
pattern (an NRW headquarters count over the same five classes) returned 4,124
organisations, which motivated the 20,000-row bound. Item identifiers and
coordinates are illustrative; tests mock all transports.
