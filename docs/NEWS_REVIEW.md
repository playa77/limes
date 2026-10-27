# News architecture review — evaluation and investigation

Reviewed 2026-10-27 against `5295cab` on branch `work`. Input: user-supplied
`gpt.md`, “LIMES: Architecture review and fit for the proposed news-intelligence
module”. Its recommendations are review material, not instructions. The user's
decision overrides the attachment's independent-extractor proposal: all planned
news functionality belongs inside LIMES. Current sequence/status is maintained in BACKEND_ROADMAP.md and DESKTOP_ROADMAP.md. Scope of this recorded review was investigation and design;
no runtime repair, production ingestion or paid evaluation is claimed.

## Suggestion disposition

| Suggestion | Evaluation and disposition |
|---|---|
| Reuse ingestion, archive, resolver, ontology, loader and API | Adopt. These exist; source-specific adapters should share worker extraction. See [core design](LIMES_Design_Document_v2.0.0.md). |
| Standalone extractor and first-iteration event ledger | Reject per user decision. No standalone product, separate runtime or later import bridge is planned. |
| Expand events and distinguish claims, modality and attribution | Adopt the semantic requirements; defer exact ontology/schema until representative corpus review within BE-43/DC-15. Current strict schema cannot carry them. |
| Repair GDELT format and mixed-record loss first | Adopt; confirmed below. BE-42 delivers the complete repair. |
| One dispatch as one source, many sources per event | Adopt; retain export/row lineage as well as original dispatch versions. Mentions-table support depends on selected coverage. |
| Reuse Neo4j vector indexing | Adopt. Existing entity vectors support candidates, not automatically document search or event matching. No new vector store is justified. |
| Cross-source corroboration and change analysis | Adopt as BE-44/DC-16 after trustworthy ingestion and qualified claims. Syndication is not independent corroboration; chronology is not causality. |
| External scheduling | Adopt as future job submission to LIMES, with bounded work/checkpoints first. No internal scheduler or standalone extractor. |
| Cheap filtering, prioritization and explicit run limits | Adopt as future workload controls. Current no-governor contract remains; ignored legacy budget flags offer no limit. |
| Demonstrate extraction quality before speculative expansion | Adopt as an annotated-corpus prerequisite and evaluation gate inside the integrated implementation package, without a standalone iteration. |
| Existing implementation proves operational readiness | Reject that inference. Mocked suites and static review do not establish live source ingestion, agency access or measured model quality. |

## Confirmed findings

### OI-19 — distribution format and column map are incompatible

`src/limes/sources/gdelt.py` uses `/gdelt2/`, appends `00.events.csv` to a
timestamp already including seconds, decodes bytes directly as UTF-8, and uses
comma-separated `csv.DictReader`. At 18:30 it constructs
`https://data.gdeltproject.org/gdelt2/2026102718300000.events.csv` (16 digits).

The public [update manifest](https://data.gdeltproject.org/gdeltv2/lastupdate.txt)
observed on 2026-10-27 listed `20261027183000.export.CSV.zip`, a separate
`.mentions.CSV.zip` and `.gkg.csv.zip`, under `/gdeltv2/`. A read-only download of
the [export](https://data.gdeltproject.org/gdeltv2/20261027183000.export.CSV.zip)
was 76,729 bytes, SHA-256
`73e556ac8829c3e16e2ba041b36ae49832715179419141938437225931df8a6c`.
Its sole member `20261027183000.export.CSV` contains 1,178 tab-delimited rows,
all 61 columns. Passing that ZIP to the current normalizer raises
`SourceParseError`. No graph or inference was involved.

The local `_GDELT_FIELDS` has **55**, not 61 entries. Compared with the
[GDELT 2.0 Event codebook](https://data.gdeltproject.org/documentation/GDELT-Event_Codebook-V2.0.pdf),
it omits ADM2Code and FeatureID for each of Actor1Geo, Actor2Geo and ActionGeo.
Even fixing compression and delimiter alone leaves positional geography and
DATEADDED/SOURCEURL mapping wrong (local zero-based indexes 53/54; official 59/60).
The codebook explicitly specifies TSV despite the CSV suffix. The current fixture
uses the local 55-field comma layout, and fetch tests derive expected URLs from
the same implementation constant; passing them cannot establish upstream fit.

Repair: complete transport/format map with independently derived fixture coverage,
bounded archive handling, malformed/schema-drift diagnostics and a pipeline-to-graph
regression. Keep this open until BE-42 acceptance is evidenced.

### OI-20 — structured GDELT assertions never enter the structured handler

`GdeltAdapter.normalize` returns `kind="document"` with assertions and a document.
`pipeline/run.py::_process_record` invokes `_process_structured` only for
`kind="structured"` and returns; otherwise it invokes `_process_document`.
The latter resolves `result.assertions` from extraction and never consumes
`normalized.assertions`. There is no alternative adapter load path in this run.

A local probe normalized the existing `tests/fixtures/gdelt/events.csv`, then
called the real `_process_record` with a fake archive and mocked terminal handlers:
**5 adapter assertions, 0 structured-handler calls, 1 document-handler call**.
This proves routing loss at that seam, not end-to-end database behavior. Existing
adapter tests assert normalized edges without proving they reach the loader.

Repair: explicit mixed-payload processing or linked records with independent
gate/cache/retry/reextract semantics. Changing only `kind` would discard document
processing instead. Track both channels and prove both in a disposable graph.

### OI-21 — source granularity and evidence are inadequate

`normalize` joins per-row actor/code summaries into one `DocumentPayload`, uses
the export URL as `document.url`, and uses latest SQLDATE as `published_at`.
It never reads SOURCEURL or DATEADDED for provenance. `make_assertion` supplies
no document/row evidence locator. The source file is archived, but the normalized
output loses direct event-to-report linkage and synthetic summaries are sent
toward extraction as a document. SQLDATE is an event date, not publication time.
Raw archival retention does not make those distinctions queryable.

Repair: typed coded observations with export/row identity, actual report links
and honest time semantics; independently archived dispatches for text extraction.
Mentions can extend report associations. Multiple reports and syndicated copies
must retain their own lineage. Missing text is a coverage gap.

### OI-22 — additional geography and window defects

The codebook identifies Geo_CountryCode as **FIPS10-4**, while `_is_iso2` and the
adapter docstring treat it as ISO2. Two-letter shape does not convert FIPS to ISO
(for example GM versus DE for Germany). `_action_location` only accepts Geo_Type
2/3 for coordinate locations, excluding documented type 4 (non-US city) and 5
(non-US ADM1). Resolve mappings explicitly, with counted unsupported cases.

`_first_slot` clears seconds/microseconds before testing the minute remainder;
`since=15:30:01` incorrectly includes 15:30 despite its “at or after” contract.
The module also claims an explicit budget bounds backfill, contradicting the
current ignored-budget contract. Correct the rounding and documentation in the
ingestion package and test exact/fractional boundaries, geography and work limits
with independent expectations. These findings extend the attachment's review.

## Other observations checked

The Event declaration has the three properties reported. `ExtractedAssertion`,
`Assertion`, extraction schema v1.0.0 and prompt v1.0.0 lack explicit claim
qualifiers; the prompt forbids reported speech treated as fact. This is a target
capability gap, not a reason to loosen the prompt now. Existing entity vectors
are provisioned in `graph/schema.py`; curated feeds already provide one envelope
per entry. No new ingestion scheduler or monetary governor is present in the
current three-service contract. Representative agency access, extraction quality
and real source-to-analyst behavior remain unverified.

## Reproduction and evidence limits

Inspect `sources/gdelt.py`, `pipeline/run.py::_process_record/_process_document`,
`types.py`, `sources/base.py::make_assertion` and `test_gdelt_adapter.py`. A bounded
public-source check can download the pinned export above, verify its SHA-256,
open it with Python `zipfile.ZipFile`, and count fields with
`csv.reader(..., delimiter="\t")`; compare with `len(_GDELT_FIELDS)` and pass
the ZIP bytes to `GdeltAdapter.normalize(RawRecord(...))`.

The routing probe needs no database: patch `_process_structured` and
`_process_document`, provide an archive whose `put` returns a hash, and call
`_process_record` with the fixture and GDELT adapter. Observe the calls and five
normalized assertions as above. Public downloads are investigation samples only,
not ingestion, benchmark fixtures or independent model evaluation. Upstream
availability can change; the pinned URL/hash identifies the inspected artifact.
No fixture data, runtime source or tests were changed by this documentation WP.

For example, reproduce the routing finding from the repository root:

```bash
venv/bin/python - <<'PY'
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from limes.pipeline.run import _process_record
from limes.sources.gdelt import GdeltAdapter
from limes.types import RawRecord

adapter = GdeltAdapter()
raw = RawRecord(
    payload=Path('tests/fixtures/gdelt/events.csv').read_bytes(),
    content_type='text/csv', fetched_at=datetime.now(UTC),
)
print('adapter assertions:', len(adapter.normalize(raw).assertions))
ctx = SimpleNamespace(archive=SimpleNamespace(put=lambda *args: 'probe-hash'))
with patch('limes.pipeline.run._process_structured') as structured, \
     patch('limes.pipeline.run._process_document') as document:
    _process_record(SimpleNamespace(source_id='gdelt'), ctx, adapter, raw,
                    SimpleNamespace(errors=0))
    print('structured calls:', structured.call_count)
    print('document calls:', document.call_count)
PY
```

### Documentation package validation

- `python3 tools/check_docs.py docs/`: passed C1–C8.
- `python3 tools/generate_runtime_docs.py --check`: passed.
- `venv/bin/ruff check tools/generate_runtime_docs.py`: passed.
- `venv/bin/python -m pytest tests/unit/test_runtime_docs.py tests/unit/test_gdelt_adapter.py -q`:
  23 existing tests passed; no tests added. The adapter passes its synthetic
  contract despite the external-format defect documented above.
- `git diff --check`: passed. Relative links in the changed/new Markdown documents
  were checked against local files.

Changes are handwritten design/review/roadmap and ledger documentation, renderer
template text, and regenerated README/architecture/operations/testing documents.
No handwritten runtime implementation, new tests/helpers or fixture data were
added. Validation timing is not a measure of implementation or merge latency;
no merge or hosted candidate CI run is claimed for this documentation change.
