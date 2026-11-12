# BE-58 — Source acquisition from 2020-01-01

Approved 2026-11-12. Branch `codex/be-58-data-scope-2020`, live GitHub base
`7ccdd365fc80`. This is the complete source-scope package; it changes neither the
ontology's temporal semantics nor the required set of sources.

## Product contract

Imagine the same sources first became available on **2020-01-01**. Build the best
system from their publications and observations from that date onward. **Every
existing source remains mandatory and enabled.** A source may not be removed or
disabled without the user's explicit approval.

The lower boundary is inclusive UTC. Historical acquisition calendars, export
windows, explicit backfills and resumed checkpoints cannot start before it.
Current source snapshots remain fully usable: entities, relationships, references,
article text and internal observations may concern any earlier date. Do not clip
validity intervals, rewrite original dates, discard old entities, or treat an old
row's timestamp as grounds for disabling its source. Query/as-of/believed time
controls remain able to express the older facts carried by eligible evidence.

For a current snapshot, the acquisition observation records what the source exposes
now; the original dataset/row/revision dates remain separately authoritative for
vintage and freshness. A snapshot is not evidence that every old fact is still
true. In particular OffeneRegister's 2018 `retrieved_at` remains 2018; it is not
replaced with today's download date and it does not exclude the source. No
historical edition or archive is selected merely to reconstruct a pre-2020 state.

## Every-source acquisition policy

| Source | Supported acquisition and retained content |
|---|---|
| TED | Publication packages from January 2020 onward. Explicit individual repair uses the same lower publication bound. Older contract/entity/legal dates inside eligible notices remain intact. |
| GDELT | Export/coding slots from 2020 onward; keep earlier SQLDATE/event validity inside those eligible exports. DATEADDED, SQLDATE and article publication are distinct. |
| EUR-Lex | Observe the complete current Cellar metadata catalogue. Act adoption dates, old citations and undated acts remain usable; do not filter those facts by the acquisition floor. Each refresh is a complete snapshot, not adoption-date incremental acquisition. |
| Bundestag DIP | Observe the complete current person catalogue, retaining older participation/term evidence and unchanged persons. Internal update/term dates do not exclude people. Each refresh is a snapshot, not a filter on the last internal update. |
| Gesetze im Internet | Current index and consolidated texts, including laws originally enacted before 2020. No historical text-version backfill. |
| GLEIF | Latest coherent entity/relationship export. Older registration, accounting and relationship dates remain unchanged. |
| OffeneRegister | Current exposed dataset through the existing adapter. Preserve original per-company observation and officer interval dates, including pre-2020 dates. Staleness is explicit; no source exclusion or claim of current directorship follows from download time. |
| GISCO/NUTS | Configured 2024 reference edition and postcode correspondence. Existing regions and codes are not filtered by age. |
| Transparency Register | Current export, retaining internal entry/update dates and available historical relationships. Do not fabricate absent meetings or heads. |
| FSD | Current consolidated sanctions export, retaining older regulations and source dates. Current availability/freshness blockers remain independent of this scope decision. |
| OpenStreetMap | Current bounded map observations and coherent partition acquisition, retaining old objects/tags. No historical map-state downloads. |
| Official public offices | All 21 current serving-roster scopes. Preserve source-backed earlier term/office/history dates; never infer current membership from old DIP history. |
| Wikidata | Current identity/classification lookups, with old identities and aliases allowed. No historical revision traversal. |
| Wikipedia | Latest available DE/EN article revisions through reviewed identities. Preserve original revision timestamps and all historical text; a latest revision with an old timestamp is still the page exposed by the current observation. No revision-history backfill. |
| Yahoo Finance | Current selected company/listing sections, preserving earlier officer/report/filing dates. No historical series backfill is introduced. |
| Feeds | Current bounded RSS/Atom observations, retaining their old, undated or corrected entries. Do not filter a current snapshot's internal publication dates. |
| Investigation news | Current bounded DE/EN discovery with a 2020-forward search boundary; retain original returned feed/report contents and internal event dates. No agency full-text or historical edition traversal is inferred. |

## Windows, recovery and completeness

`limes.data_scope` owns the immutable boundary and scope identity. Requested lower
bounds and old checkpoints clamp to it; wholly pre-boundary or inverted windows
fail before source I/O. Static snapshots retain full current acquisition rather
than applying the floor to internal fact dates. GDELT's first unconsumed in-scope
slot must not be lost when clamping an old checkpoint.

Generic acquisition journals now live under a scope-version namespace inside the
existing acquisition root. Legacy journals and archives remain intact but are not
silently reused as proof of the new scope. New request/version identities include
the policy, and cached responses preserve their original acquisition timestamps.
Pre-2020 acquisition observations fail before archive replay/loading. Specialized
OSM/public-office evidence continues to retain original observation times. OSM
preserves a pre-2020 cursor as metadata and reacquires a current collection before
reading old cached partitions; no source is disabled.

Source completeness is stamped with the scope version. An unversioned legacy
`corpus_complete` flag cannot certify the new baseline or suppress its acquisition.
Only a complete clean default initial window can establish scoped completeness;
explicit partial/historical bounds cannot. `/sources` reports the earliest source
acquisition date and exposes completeness only for this policy. The desktop states
the source boundary without restricting fact/query dates.

Archived news replay checks the original saved acquisition observation before
reading the payload. It never gives an old acquisition a fresh timestamp merely
because re-extraction runs today. Missing legacy observation provenance is skipped,
with the page cursor still progressing; historical dates inside eligible reports
remain usable.

## Acceptance and operational boundary

1. All registered sources remain present and available through their existing
   ingest, tracked-news or reviewed-enrichment workflows.
2. Default, explicit, checkpoint, bounded and resumed acquisition cannot select
   historical windows before 2020; time-zone boundary comparisons use UTC.
3. Current snapshots retain older facts and original dates, including
   OffeneRegister observations, old legal acts and parliamentary terms.
4. Scope-specific receipt and completeness identities prevent legacy coverage and
   caches from silently certifying the new source corpus.
5. Active specifications, generated runtime docs, source audit, API and desktop
   agree on source scope. Historical evidence is preserved as historical.
6. Distinct regression checks and one full candidate qualify the implementation.

This implementation runs no production ingestion, migration, deletion, paid
inference, deployment, staging or publication. Existing graph/archive data is not
purged. Before claiming a fully scoped deployed corpus, the operator must separately
reconcile legacy acquisitions and rebuild/reconcile any out-of-scope evidence with
explicit authorization. Existing source availability, corpus inventory, freshness
and extraction-quality obligations remain open; a narrower acquisition calendar
is not evidence that those obligations have passed.

Local implementation/qualification acceptance: A1–A6 pass in the unchanged full
`work/be58/candidate-final-2` candidate. [Exact evidence and retained failed
candidate](VERIFICATION.md) distinguish this from deployed corpus acceptance.
