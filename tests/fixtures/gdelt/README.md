# GDELT fixtures

`upstream.tsv` contains the first three unchanged rows from
https://data.gdeltproject.org/gdeltv2/20261027183000.export.CSV.zip,
retrieved read-only on 2026-10-28. The original ZIP SHA-256 is
`73e556ac8829c3e16e2ba041b36ae49832715179419141938437225931df8a6c`;
member `20261027183000.export.CSV` has 1,178 rows of 61 TSV fields.
The field positions used by tests are independently specified by the
[GDELT 2.0 codebook](https://data.gdeltproject.org/documentation/GDELT-Event_Codebook-V2.0.pdf).
The fixture retains actual URLs and DATEADDED values, without article text.
Tests create a ZIP envelope around the sample; its hash is
intentionally different from the complete upstream export.

`events.tsv` is the repaired synthetic actor-typing regression fixture, not
an upstream compatibility oracle. The historical 55-column comma fixture was
removed because it encoded the format defect. ZIP/row limits and positional
expectations have separate upstream-derived tests.

The country crosswalk in `gdelt_countries.py` comes from GeoNames countryInfo,
retrieved 2026-10-28. Attribution: [GeoNames](https://www.geonames.org/),
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The module records
its source URL/hash. Unsupported FIPS codes are never interpreted as ISO codes.
