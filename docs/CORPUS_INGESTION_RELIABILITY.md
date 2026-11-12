# BE-57 — Corpus ingestion reliability and source audit

## Current acquisition scope — BE-58, 2026-11-12

[The approved source-scope contract](SOURCE_DATA_SCOPE.md) limits historical
acquisition to 2020-01-01 onward and preserves every existing source. Current
snapshots retain older internal facts, observations and dates. TED starts January
2020. EUR-Lex and DIP refresh current complete catalogues without excluding old
acts/persons by adoption/update dates. Legacy scope-unversioned completeness and
journals cannot certify this policy. Historical BE-57 measurements below remain
unchanged evidence, including the now out-of-scope 2011 samples; they are not
instructions to download or replay those editions.

Selected 2026-11-10 on `codex/be-57-corpus-ingestion-reliability`, verified live
baseline `5f6456b2b40c`. The user requests repairing full ingestion and auditing
equivalent failures across sources. BE-41 is accepted. The archive remains the
system of record; topology, authorization, ontology validation and manual job
resubmission remain intact. No production run, restart or paid inference is included.

## Acceptance

1. TED corpus acquisition uses official monthly/daily XML packages, retaining
   original compressed artifacts and notice/member provenance. Initial structured
   corpora do not inherit the news lookback or a legacy recent-window success.
2. Acquisition windows, successful HTTP responses, successful record loads and
   completed packages survive process interruption and time budgets. Failed records
   remain pending; only complete clean windows advance the graph checkpoint.
3. Remove fixed non-resumable page ceilings, preserve cycle detection and continue
   bounded normal windows until the invocation's safe target is reached.
   Productive durable time slices continue inside the same operation; rate-limit
   stalls, processing errors, cancellation and interruption never trigger that loop.
4. Failed publishers, malformed required identities and structured ontology/loader
   rejections block complete outcomes.
   Missing optional facets do not justify inventing facts or dropping the entity.
5. Show acquisition/processing progress, rate limiting, transport/upstream failures,
   stale progress and final failure separately from infrastructure health.
6. Audit every registered source and qualify recovery against a real disposable
   graph. Record public acquisition evidence separately from fixture qualification
   and a reconciled production corpus.

These are implementation/qualification criteria. The product requirement remains
a completed, reconciled corpus and maintained freshness; a passing candidate does
not satisfy that requirement by itself. FSD availability and a complete stopped-run
replacement remain blockers until actual acquisition evidence closes them.

## Evidence from the interrupted initial ingest

The supplied README identifies revision `5f6456b`, an initially empty ingestion
history, a driver started at 10:47 UTC, TED failure at 11:28 UTC and a user stop
at approximately 11:44 UTC. GLEIF/OffeneRegister/OSM/GDELT/feeds/rosters were not
reached. The document's purported 10.5/11.5-hour snapshot expectations conflict
with the generic 1,800-second source-run limit. The record alone establishes
neither successful throughput nor a seven-year estimate. Eight consecutive failed
HTTP attempts, four attempts per request and a 30-minute invocation deadline are
different limits, not a successful-notices quota.

The record calls the first load full while describing a 90-day first lookback.
Code inspection confirms that TED/EUR-Lex/DIP inherited that lookback. TED's
individual notice traversal stopped after 20,000 notices; EUR-Lex after 200,000
result bindings; DIP after 100 pages. The old TED path has no package acquisition.
The standalone driver/ticker mentioned in the attachment is not present in this
checkout; its behavior is not attributed to a file that has not been inspected.

## Source-by-source audit

| Source | Actual acquisition/coverage | Confirmed defect and disposition | Evidence boundary |
|---|---|---|---|
| TED | XML packages from January 2020; daily packages for partial/recent months | Replace per-notice corpus GETs with monthly/daily packages; retain an explicit individual-repair method. Durable package/load receipts; canonical legacy IDs/date/country/title parsing; shared settled-contract award joins. | Official package GETs succeeded for 2011, 2023, 2026. Three complete daily editions: 1,817 + 2,256 + 1,749 notices, zero normalization errors. Complete January 2011 monthly package: 32,511 notices, 325,124 assertions, zero normalization errors or ontology rejections. Not an all-years corpus reconciliation. |
| EUR-Lex | Current complete Cellar metadata snapshot including old/undated acts | Every refresh observes the current catalogue; internal act dates do not govern source eligibility; no 40-page ceiling, durable response/load replay. Union relation facets instead of multiplying citations × amendments × topics. Malformed/missing CELEX rows count as errors. | Actual initial query returns 20 bindings / 23 assertions / two standalone acts without normalization errors; all CELEX inventory still requires reconciliation. Current snapshot refresh replaces adoption-date incrementals; live update reconciliation still needs evidence. |
| Bundestag DIP | All current API person pages on each snapshot refresh; historical participation metadata, not current membership | Current snapshots unfiltered by internal update/term dates; remove 100-page ceiling; preserve distinct terminal pages even when cursor repeats. Repeated-page/cursor checks remain. | Recorded current-shape fixtures and configured-key path; this executor has no attached DIP credential. |
| Gesetze im Internet | Full current index and linked law ZIPs | Cache downloaded index/ZIPs and loaded-record receipts. Missing index links fail coverage. Laws without a gazette citation retain a source-URL/member-derived entity identity instead of disappearing. | Official index HEAD 200; law ZIP fixtures. Current law texts are snapshots, not all historical text versions. |
| GLEIF | Latest coherent legal-entity/relationship golden-copy publication | Stream ZIP artifacts to disk/archive; bounded CSV chunks and successful-load receipts; completed ZIPs skipped on resume. Missing entity IDs/unmaterializable required relationship endpoints count as errors. | Catalogue GET and both artifact HEADs 200: about 509 MB + 24 MB. ACTIVE-entity selection is an explicit existing projection, not complete historical corporate coverage. |
| OffeneRegister | Published historical company snapshot | Stream bzip2 artifact; bounded JSONL chunks and load receipts. Original source row/publication vintage remains authoritative, never current fetch time. | Artifact HEAD 200, about 260 MB. This snapshot cannot establish a current German company/officer corpus. |
| GISCO/NUTS | Full 2024 hierarchy and postcode correspondence | Retain hierarchy together; stream/chunk the large postcode table, retaining original artifact. Invalid postcode identities count as errors; source progress survives a later-file failure. | Official HEADs 200: hierarchy 92 KB, postcode table 127 MB. Static-vintage coverage is explicit. |
| Transparency Register | Full current XML export | Archive original; validate export count; normalize/load bounded 250-organization chunks so one entire export need not fit a processing budget. Durable HTTP and chunk replay. | HEAD 200, about 118 MB; current XML fixture/count tests. Current export omits historical meetings/heads; those facts are not fabricated. |
| FSD | Full current Commission sanctions export | Add actual namespaced FSF 1.1 export parser; legacy archive support retained. Missing required identity/name/type blocks clean completion. The old parser expected an unrelated `Sanctions/Sanction` shape. | Official endpoint GET returned empty HTTP 500; HEAD returned 403, including persistent-session/token-encoding probes; alternate official CSV and PDF exports also return empty HTTP 500. Public mirror original XML: 6,269 distinct records, 18,807 assertions, zero normalization errors; checksum matches mirror metadata. Underlying export is dated October 23, despite November 10 republication. Current official acquisition/freshness remains blocked; the dated mirror is not silently certified as current. |
| GDELT | Selected coded-event window; default configured lookback | Normal ingestion drains bounded prefixes through a publication-safe cutoff. Explicit historical requests no longer fail solely for exceeding 96 slots; budgets and durable per-file receipts bound/resume work. | Export fixtures; this does not acquire article bodies, all GDELT history, or recover an already lost historical checkpoint automatically. |
| Feeds | Each configured publisher's currently exposed RSS/Atom entries | Retain healthy publishers' entries, then fail incomplete acquisition if any publisher failed. No success checkpoint for partial acquisition. Re-poll every publisher on resubmission; archive original RSS alongside entry envelopes. | Mocked mixed/dead/empty publisher cases. Live configured feeds returned 10 Commission, 20 Bundesregierung and 40 tagesschau entries. Rolling RSS cannot reconstruct entries that expired before acquisition. |
| All 21 public-office scopes | Official current roster/profile observations | Existing bounded, archived per-scope acquisition and coverage reconciliation retained. Generic corpus journaling does not replace its evidence/identity lifecycle. | BE-56 fixture/source evidence; all scopes' current loaded population remains unproven. The attachment says 20 but enumerates 21; registry-derived submission avoids hard-coded roster counts. |
| Wikidata | Selection/enrichment only | Excluded from ingest-all; not a bulk corpus source. | Existing tests; no all-Wikidata claim. |
| Wikipedia / Yahoo Finance | Reviewed entity selections and dated sections | Excluded from ingest-all; existing incomplete-section/freshness semantics retained. | Existing tests; no full site/market history claim. |
| News investigations | Bounded search cycles | Excluded from generic ingest-all; requires an investigation. | Existing tests; search indexes do not equal complete article coverage. |
| OSM | German KRITIS bbox via partitioned Overpass | Preserve archived partitions, failed-leaf ledger and subdivision; retain generic load receipts as well. Productive acquisition/request slices continue; budget boundaries do not become failed upstream leaves. Retire the acquisition cursor after the complete checkpoint. | Recovery/slice tests; live nationwide capacity is still a blocker. A regional extract may be necessary if measured Overpass capacity cannot meet the target. |

## Recovery and completeness contract

Composition supplies `AcquisitionStore` under the existing archive volume's
`.acquisition/sources` directory. Each source has a lock and SQLite journal. The
request identity includes mode, explicit window and graph target; an unfinished
different request fails explicitly rather than discarding its progress. The
resolved window is pinned; each response retains its original observation timestamp
for replay, while new responses get their actual acquisition time. HTTP cache keys
persist only hashes, not authorization header values. Replayed snapshots preserve
the original observation timestamp; changed processing versions invalidate load
receipts while preserving downloaded evidence.

The archive is durable before recording a response receipt. Graph writes finish
before a load receipt is committed. A crash between those steps can repeat an
idempotent graph write; it cannot mark unwritten data loaded. Failed normalized
records and structured ontology/loader rejections receive no receipt and block
the source success checkpoint. The latter false-success path is reproduced in
`work/be57/structured-rejection-before.log`. Package completion compares every current traversal record key against its
receipt, including provenance/position in record identity. Equally many obsolete
receipts from an invalidated, corrected package cannot certify its new inventory. Completed TED packages
are skipped without re-downloading or re-decompressing the historical prefix.
The graph checkpoint commits before journal retirement. OSM keeps its specialized
validated partition cache and failed-leaf protocol, with the generic journal
tracking successful loads. Its HTTP responses are not cached before Overpass body
validation. Roster acquisition keeps its own evidence/identity protocol;
re-extraction/selection-only jobs do not use the corpus journal.

Structured loading uses parameterized UNWIND groups of ontology-generated queries.
TED accumulates bounded deterministic notice batches, flushing at 50 notices,
500 assertions or 8 MiB input; a notice can cross the trigger but is capped at
16 MiB, and graph transactions remain bounded to 500 assertions. Each notice
retains its own archived payload/manifest, and successful load receipts follow
the complete batch write. Pending work flushes at package completion and on
interruption; a failed batch receives no receipts. MERGE prevents duplicate
identities inside a batch; interval closure chooses each relationship's nearest
later observation of the same source/channel. The graph write gate applies to
these transactions too.

A standalone real-data pipeline sample (1,000 January 2011 notices, retained input,
512 MiB heap + 512 MiB page cache, disposable Neo4j) improved from 82.952 to
29.551 seconds, preserving exactly 2,671 graph nodes and 2,673 relationships,
with zero errors/rejections and no inference. This is a bounded small-graph
measurement, not a full-corpus ETA. Its naive intermediate batch attempt failed
independent relationship-count validation and is retained as failed evidence.
Receipts: `work/be57/ted-real-graph-sample-before-batching.json`,
`ted-real-graph-sample-failed-naive-batch.json` and `ted-real-graph-sample.json`.

Ingest/ingest-all/backfill jobs use a separate
`LIMES_CORPUS_JOB_TIMEOUT_SECONDS` envelope (default/max seven days), since even
the small-graph sample implies a multi-day load even for the 7.1-million-notice
visible index, which excludes part of the available archive history.
Other jobs retain `LIMES_JOB_TIMEOUT_SECONDS` (default 24 hours). This prevents
the default outer deadline from predictably killing productive initial work;
it does not replace measured full-scale capacity or change cancellation/replay.
Timeouts still fail the operation with durable work retained for explicit resume.

The 1,800-second source budget bounds a productive slice, not the whole initial
snapshot. Only a clean slice with newly retained loads/responses and no outstanding
transport failure can return `continuing`; it does not certify the window or
advance its checkpoint. The existing operation continues from durable receipts,
under its outer operation deadline. A rate-limited/stalled slice remains a failed
outcome even if it processed some earlier records. Worker crash/cancel recovery
still requires explicit resubmission; no new jobs are automatically created.

Completed acquisition inventories and receipts are retained as archived SQLite
artifacts with a JSON summary. The source and run retain the manifest hash even
after the active journal retires. Invalid downloaded payloads remain archived but
their HTTP cache entry is invalidated so resubmission can obtain a corrected copy.

An interrupted download restarts that individual artifact; completed artifacts
are retained. This is package-level recovery, not HTTP byte-range continuation.
The archive and journal must be backed up/restored with the corresponding graph.
Restoring only an older graph while keeping newer load receipts is unsupported:
preserve the journal and invalidate load receipts before reloading that graph.
No acquisition is automatically resubmitted after an operator stop.

TED packages retain their full compressed source hash and member name. Archive
members are bounded, not extracted to paths; duplicate/unsafe/nonregular members,
empty packages, invalid member identity, size overflow and truncated gzip fail.
Historical monthly packages containing daily tar.gz files are traversed as that
bounded nested layout, with the full outer/daily/member chain retained. Public
HEAD inventory verified all 190 monthly packages from January 2011 through
October 2026, totalling 37,649,868,153 compressed bytes. Availability is not
content reconciliation or a measured graph-load completion estimate. A separate
November 10 Search API count for January 2011–November 10, 2026 returned
7,110,933 visible notices (`work/be57/ted-corpus-count.json`, `timedOut=false`).
That is not a complete archive inventory: the same API reports zero for January
2011 despite its 32,511-notice package. Reconciliation must use the acquired
package/member inventories and graph load receipts, not a search-index total.
`work/be57/ted-independent-package-counts.json` preserves the discrepancy.
The complete January 2011 package (110,462,816 compressed bytes) also passed
normalization and ontology checks for all 32,511 notices / 325,124 assertions.
The 116.477-second check used retained input and no graph writes; it is neither
a network-throughput measurement nor an end-to-end corpus completion estimate.
Receipts: `work/be57/ted-month-quality.json`, `ted-three-eras.jsonl` and
`ted-monthly-inventory.jsonl`.

Current discovery uses one small API request per publication day for partial
months, then a daily package; closed whole months need one package request.
An empty historical search result is not proof of no notices: when the monthly
archive is available, discovery falls back to it and selects members by actual
publication date. Missing/invalid dates block that partial-month result rather
than silently discarding members. Valid historical weekends can be empty only
after checking the nonempty monthly archive. A real January 4, 2011 selection
returns 1,817 notices with exactly the same payload hashes as the separately
downloaded official daily edition (`work/be57/ted-historical-window-quality.json`). The
calendar's observed HTTP 202 WAF challenge is not treated as usable data. A
package service can itself fail or throttle; those outcomes remain failures with
retained completed work.

`Source.corpus_complete` certifies the initial baseline for the three historical
corpus adapters (TED/EUR-Lex/DIP), not universal historical completeness for
rolling feeds/current snapshots. Legacy recent-window timestamps do not set it.
Explicit narrower windows do not certify it. `/ingest/status` exposes a run's
state, progress time, latest transport error and selected window. A completed
window is named `complete_window`, never implicitly all-source coverage.
Service `/health` remains infrastructure health; it is not ingestion readiness.

## Remaining product acceptance

- Obtain a valid current FSD export and qualify its full contents. The independently
  acquired 25,899,600-byte mirrored original validates the parser against the real
  export schema, but its `generationDate` is 2026-10-23 and `globalFileId` is 185833.
  Re-export time is not source freshness. Receipts: `work/be57/fsd-mirror-quality.json`
  and `fsd-session-probe.jsonl`; alternate-format receipts are in
  `fsd-alternate-formats.json`. Official access/current freshness remains unresolved.
- Establish the requested scope for snapshots, finite feeds and historical event
  data without implying unavailable history. Preserve the already selected product
  requirements; this audit does not waive them.
- Run the replacement full ingest only under the appropriate data-run authorization,
  reconcile expected inventories against loaded records, measure sustained throughput,
  storage and lag, and prove incremental catch-up. The stopped production run is
  not restarted by implementation qualification.
- Qualify late modifications to historical EUR-Lex records and live OSM capacity.
  These remain engineering obligations with acquisition evidence required, not
  success classifications delegated to an operator.

Additional live-query/feed receipts: `work/be57/eurlex-initial-undated-quality.json`
and `eurlex-feed-probes.json`. These qualify bounded public acquisition only.

Exact candidate status and retained failed attempts belong in [VERIFICATION](VERIFICATION.md).
