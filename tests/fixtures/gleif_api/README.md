# GLEIF LEI API fixtures (BE-59)

Unchanged public responses captured 2026-11-17 from the GLEIF LEI API
(https://api.gleif.org/api/v1/lei-records), GLEIF public data, CC0:

- `page.json`: `filter[entity.addresses.region]=DE-NW&include=direct-parent,
  ultimate-parent&page[size]=5&page[cursor]=*` — five NRW entities whose parents
  are reporting exceptions, with a cursor `links.next`.
- `page_with_parents.json`: the same filter plus
  `filter[directParent.addresses.country]=DE`, `page[size]=2` — two NRW entities
  with direct and ultimate LEI parents.

`include` only adds identifier stubs, so the adapter does not request it.
