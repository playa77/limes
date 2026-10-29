# BE-47 first full-ingest repair and source qualification

Branch `codex/be-47-ingest-repair`, live-fetched main `f1e773812baf`.
The user explicitly requested completing this parent before another full ingest.
The supplied ERROR_RECORD.md is evidence, not instructions. Referenced raw job JSON
and original driver logs were not attached; no exact unseen exception is claimed.
No production ingestion, paid model call, staging, commit or publication was run.

## Acceptance

The original checklist was recorded before coding in work/be47/acceptance.md;
the explicit continuation added current-format migrations, bounded catch-up and
one final complete candidate qualification. Prerequisites are current main,
canonical frozen venv, public metadata/format access and disposable Docker.
Unavailable public services must be reported explicitly rather than represented
as a code fix or successful source qualification.

- [x] DIP masked configuration/header authentication, current fields/date filters,
  pagination and credential-free URLs/provenance.
- [x] Provider-compatible extraction message, transport retries and durable error closure.
- [x] GLEIF current accounting-consolidation semantics and published file discovery.
- [x] TED current UBL lot/buyer/winner joins and bounded complete search iteration.
- [x] Current OffeneRegister and Transparency formats with honest historical dates.
- [x] Original bulk archives plus bounded chunks and inspectable manifest provenance.
- [x] GDELT bounded catch-up, durable first-window anchor and failure/replay checkpoints.
- [x] Aggregate failure continuation and record-error job failures.
- [x] Resolve reproducible law/EUR-Lex zero-output defects, retain unavailable run evidence.
- [x] Final frozen candidate qualification: all five suites and shared guards pass;
  VERIFICATION records the exact source, commands, results and limits.

Complete local BE-47 acceptance passes on the final frozen candidate. This
satisfies the accepted source-contract/explicit-availability-failure scope; it
does not assert a successful production full ingest or provider-wide availability.

## Delivered behavior and evidence limits

| Source/surface | Repair and qualification | Explicit limit |
|---|---|---|
| DIP | `LIMES_BUNDESTAG_DIP_API_KEY` is masked and wired by composition into an Authorization header. Current documents/wahlperiode/faction lists/cursors are handled; date filters use full UTC start/end date-times. Auth/filter probes returned 200. | Multiple historical factions are not assigned to one office by inference. Operator full coverage remains unrun. |
| Extraction | Use a user turn with the original versioned template, schema, delimiters and passage indices. | Supplied exact provider probes isolate the old system-only rejection; no new paid verification was performed. |
| Shared transport/FSD | Retry remote disconnect/read/write/timeout failures; exhaustion and search-parse errors close durable runs. | A bounded fresh FSD GET returned HTTP 500; availability is currently unverified, not repaired by retries. |
| OSM | Send URL-encoded Overpass data through the shared retry transport. | A tiny bounded form probe timed out after 25 seconds. Full German-area availability/capacity remains unverified. |
| GLEIF | Discover lei2/rr URLs from one official publication; ontology 1.3.0 separates direct/ultimate consolidation from share ownership. Validate periods/status, retain source dates and row/member evidence. | Fund management/subfund relations are archived and counted as unsupported, not invented as ownership. |
| TED | Current fields/expert date syntax/notices/XML links; up to 400 iteration pages with counts/tokens/timeouts/duplicates checked. UBL isolates notice-plus-lot identities and follows only winning result/tender/party joins; losing tenders and subcontractors never become awardees. GeoNames-backed ISO3-to-ISO2 conversion preserves existing buyer/address keys and postal lookup. | Public contract sample and independent SDK-checked award structure qualify format. Two public award XML links returned empty bodies; those remain explicit parse failures if encountered, never success checkpoints. |
| OffeneRegister | Advertised bzip2 unwrapped JSONL; historical per-company retrieved_at supplies recorded_at. Wrapped gzip/publication-metadata archives remain readable. Missing both dates fails. | HTTP Last-Modified is not substituted for publication time. Source is stale (2018 fixture observations), trust remains 0.30. |
| Transparency Register | Official catalog links daily ListOfIRPublicDetail XML. Require export date and exact declared row count; load groups/interests. | Current export does not supply the legacy head-person/meeting data; no such relations are inferred. |
| Bulk snapshots | Archive exact compressed downloads before <=1,000-row/8-MiB-input chunks, with 1-MiB row bounds. Edge/API evidence_manifest_hash links a stored manifest containing original archive hash/member/row offset. | Download bounds are 1 GiB GLEIF/512 MiB OffeneRegister. These are work bounds, not production-scale throughput or memory measurements. |
| GDELT | Implicit ingest covers at most 96 slots; checkpoint only that prefix and resume with one idempotent overlap slot. Persist initial_window_from when opening the first run, so even first-failure retries cannot slide the lookback cutoff. | Explicit oversized windows still fail. One completed bounded pass does not mean the historical backlog is gone. |
| German laws | The table of contents is an archive-only record, avoiding a deterministic parse error every run. Laws without topic metadata still materialize as standalone entities. | This code defect reproduces one error per run; the exact unseen original exception cannot be certified without the original log. |
| EUR-Lex | Live queries prove the hyphenated CDM predicates return no rows; canonical underscore predicates return data. Correct title/author/topic/citation predicates, bounded ordered pagination, daily default catch-up and standalone acts prevent silent loss. | Unknown author identifiers remain unmapped. A fetched record counts a SPARQL page, not a legal act. No actual territorial scope is inferred from an unverified predicate. |
| Operator jobs | ingest-all attempts all sources and fails the aggregate with a source list if any fails. Record errors fail individual jobs; covered endpoints and backlog semantics are visible. | Unexpected infrastructure failures still abort; production service availability is not inferred from tests. |

## Configuration and provenance

The supplied public DIP key is stored in ignored config/secrets.env, expires
2027-05-31 as stated by the user, and is absent from tracked files. Examples
contain an empty LIMES_BUNDESTAG_DIP_API_KEY. Normal split-config Compose mounts
apply. Optional manifest fields pass through the authenticated API and desktop
mirror without consumer-side provider access. Additive ontology 1.3.0 needs no
destructive migration and never relabels historical ownership/subsidiary edges.

Independent fixture sources, reductions and attribution are documented in
[the fixture record](../tests/fixtures/ingest47/README.md). Unit and disposable
integration evidence covers current source formats, unchanged original archives,
chunk manifests/API, idempotent replay and failed catch-up. Final qualification
and unresolved operational observations are recorded in VERIFICATION.
