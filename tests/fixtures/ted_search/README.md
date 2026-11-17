# TED Search API fixtures (BE-59)

Unchanged responses from https://api.ted.europa.eu/v3/notices/search captured
2026-11-17 for result notices performed in Nordrhein-Westfalen
(`place-of-performance IN (DEA)`), EU/TED public notice data
(https://ted.europa.eu/en/legal-notice):

- `results_2020.json`: 2020-03-01..02, legacy-schema notices (no winner fields
  in the index), `limit` 3, first iteration page.
- `results_2024.json`: 2024-01-02..03, `limit` 3, first iteration page.
- `results_2025.json`: 2025-06-01..02 with the adapter's exact field list,
  `limit` 2; eForms notices with winner names and identifiers.

The 2020 and 2024 captures predate the final field list and lack a few fields;
tests use them for legacy shape and pagination tokens.
