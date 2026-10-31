# BE-48 — second full-ingest repair

Branch: `codex/be-48-ingest-rerun-repair`. Live GitHub baseline verified at
`a0ec26f92c7e` before implementation. Scope: the supplied second-run report,
error record and five final job JSON records. The three large job outputs start
mid-log at about 32 KiB; they are tails, not complete execution traces.
The pre-coding acceptance checklist is retained in `work/be48/acceptance.md`.

## Delivered behavior and acceptance mapping

- **Extraction contract:** the provider-facing extraction schema incorrectly
  described a single assertion object, while the prompt/parser required an array.
  Both HTTP and local extractors now send an array schema containing the existing
  version-specific item schema. No arbitrary response unwrapping or relaxed
  ontology/evidence validation. Tests validate wire arrays, empty arrays, malformed
  items and rejection of a single object for both supported schema versions.
  This is a concrete cause consistent with nine `RESPONSE_NOT_ARRAY` errors;
  the actual historical response bodies are unavailable, so exclusivity is unknown.
- **Provider identity and diagnostics:** the operator identifies OpenCode Go as
  the provider. Legacy OpenRouter class/config names are compatibility identifiers,
  not proof of provider identity. Call log events now say `inference`. Failed
  extraction diagnostics store a bounded 65,536-character response prefix, parse
  errors, document hash, model and prompt/schema versions in the local archive;
  logs contain its hash, not response text or credentials. No provider-side access
  is needed. Rejected output remains retryable and cannot mark a success cache.
  The array/item schema separation preserves existing parsed-data versions and
  cache keys; failed no-assertion responses were already excluded from the cache.
- **Feeds:** per-feed acquisition/parse failures are logged while later feeds
  continue. After iteration an aggregate failure closes the durable run and
  preserves its checkpoint; prior successful work is not rolled back. The failure
  counter counts the aggregate fetch failure, with individual feeds listed in its
  error. Unparseable feeds no longer silently certify a complete run. Regression
  covers a dead first feed followed by a healthy feed and final aggregate failure.
- **Bundesregierung URL:** the official RSS directory at
  `https://www.bundesregierung.de/breg-de/service/newsletter-und-abos/rss-newsfeed`
  links the Pressemitteilungen feed at
  `https://www.bundesregierung.de/service/rss/breg-de/1151244/feed.xml`.
  A public read on 2026-10-31 returned HTTP 200, 23,817 bytes and RSS channel title
  `Pressemitteilungen`; curated configuration now uses that verified endpoint.
- **TED/shared retries:** evidence already proves jittered backoff (3.6, 4.42,
  9.96 seconds). The shared transport now additionally honors `Retry-After` seconds
  or HTTP dates for transient statuses, taking the larger of server delay and
  normal backoff. Invalid values use ordinary backoff. Cooldowns above 300 seconds
  fail with a retry-later outcome rather than retrying early or occupying a worker
  indefinitely. Four-attempt bound is unchanged. Tests cover 429/503 server delays,
  HTTP dates, invalid values and excessive cooldowns. This does not certify TED
  availability, a particular rate quota or absence of upstream blocking.
- **Transparency XML:** narrowly replace forbidden C0 controls and their decimal/
  hexadecimal references with spaces before strict XML parsing; count repairs in
  logs. Preserve legal whitespace/references and literal references in CDATA and
  comments. Do not recover broken structure or enable DTD/entity resolution.
  Original archived bytes/content hashes remain unchanged. Existing export-date
  and exact row-count checks remain mandatory; tests prove a repaired export still
  rejects a mismatched declared count and malformed structure.

## Anomalies resolved or bounded by evidence

**GDELT:** `GdeltAdapter.kind` is structured; its documented input is coded events,
not article text. `_process_structured` writes the supplied event assertions;
provenance explicitly records `article_text_available=False`. Zero inference cost
is expected for this adapter. Do not add paid extraction of nonexistent article
text. Unsupported actor types are logged by design; they are not missing model
calls. The shared structured-only context intentionally loads no embedder, so null
label embeddings are not a newly diagnosed inference failure. Any separately
requested embedding backfill is an operator action, not part of this repair.
The existing 96-slot prefix/checkpoint policy remains intact.

**Laws:** retained normalization entries explicitly say `standalone_entity=True`;
final loader counters report zero created and 6,146 matched nodes. Those are match
operations, not a certified unique-law count. Zero assertion writes is consistent
with existing standalone laws and missing topic metadata. Adapter `no_sachgebiet`
diagnostics differ from loader assertion-skip counts; no fabricated relationship
or assertion skip is introduced. Full unique-law coverage still needs a graph
query against operator data; this session does not access that data.

**FSD/OSM:** supplied 500/timeout evidence remains an availability observation;
no source schema or timeout change is justified by these five records. Shared
retry improvements apply when the upstream supplies a cooldown.

**DIP configuration:** this checkout cannot establish which ignored secrets file
was present in an external deployment. No key is read, copied or claimed deployed.

## Qualification

Affected regressions and static checks are run before the full candidate. The
complete frozen candidate is invoked with `venv/bin/python tools/qualify.py
--output work/be48/candidate-3`; the report, per-check logs, JUnit and source
manifest retain exact results. See VERIFICATION for its final disposition.
No paid inference call, production ingestion, deployment or publication is used.


The first full candidate passed unit/desktop and 172 graph integration cases,
but failed one runtime-image build and two later database setups. A standalone
worker build then passed; the executor had only 562 MiB free after image builds.
Disposable test Neo4j instances now disable transaction-log preallocation and use
16 MiB rotation; production settings are unchanged. Only unused test images/cache
were cleaned, and the full candidate is repeated with these test resource bounds.
The initial failures remain recorded in `work/be48/candidate-1`.


Candidate-2 still failed at the worker build while the shared graph was running,
then the graph could no longer append transactions. Smaller logs alone did not
resolve the qualification resource conflict. Local and hosted qualification now
execute the runtime-stack test in its own required pytest session after the other
graph suites have released their database. The test is still mandatory, not skipped;
its build exceptions now include bounded build stderr. Candidate-3 repeats every
lane with this isolation. The first two failed reports remain preserved.


Final disposition: candidate-3 has 889 backend and 147 desktop unit/contract passes,
173 graph integration passes and one failed backup test. Acceptance (85) and desktop
integration (3) pass separately. After unused test-image cleanup, the backup test
passes in isolation (120.50 seconds). The remaining isolated runtime-stack test
fails extracting the worker language-model wheel with explicit `No space left on
device (os error 28)`. Full parent qualification is **not accepted**; it requires a
runner with sufficient disk. The final source still matches candidate-3's source
manifest. No failing check is skipped or relabeled passing, and earlier failed
candidate reports remain available. See VERIFICATION for exact evidence paths.
