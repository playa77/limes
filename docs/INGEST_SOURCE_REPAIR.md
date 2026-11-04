# BE-52 ingest source repair

Selected 2026-11-04, live baseline `4ef67c89ae67`, branch
`codex/be-52-ingest-source-repair`. This is one complete work package.
Prerequisites: BE-41 documentation gate passed; supplied deployed BE-50/BE-51
report and handoff revision `4ef67c8` reviewed, especially sections 4–7.
No production acquisition or paid inference is authorized. The feed URL remains
an owner/operator decision; `ontology/feeds.yaml` must remain unchanged.

## Acceptance checklist (defined before implementation)

- A failed feed cannot abort a run that yields entries from another feed.
  Only failure of every configured feed raises an aggregate naming each failure.
  Healthy empty feeds are not failures. Zero-entry runs never advance the feeds
  checkpoint. Partial acquisition is explicitly logged, never called full coverage.
- Define and test `last_success_at` for partial feeds; retain replay on processing
  failures and content-addressed archive/cache deduplication for live entries.
- Both extraction transports use ontology-derived wire constraints and clear
  evidence-offset instructions. Deterministic rejection and archival remain intact;
  no fabricated ontology relations, silent rejection or paid verification.
  Version material prompt/schema behavior to preserve cache provenance.
- TED 429 without Retry-After and FSD 500 receive bounded shared backoff,
  visible per-attempt outcomes including final failure, and clear terminal errors.
  Respect server cooldowns; permanent client errors are never retried. Endpoints
  and credentials remain unchanged. Verify with mocked transports.
- Run affected unit tests and shared guards, then one authoritative complete
  frozen candidate. Preserve exact results and blockers, including unavailable
  infrastructure; implementation acceptance does not establish upstream recovery.
- Review diff against live main, commit this package locally, never push.

## Root causes and implemented contract

BE-48 intentionally raised an aggregate at generator exhaustion even after yielding
healthy feeds. BE-52 supersedes that policy: failure of every configured feed is
terminal, naming all failed URLs; otherwise the adapter finishes and logs an
`acquisition incomplete` warning with failed URLs and entry count. A healthy empty
feed is not a failed feed. The feed table remains byte-for-byte unchanged.

For feeds, `last_success_at` is the start of the last nonempty, cleanly processed
acquisition (or the explicit window end under the existing pipeline contract),
not certification that every feed was available. Partial transport failure alone
does not increment record errors. Zero entries never advance it. Normalization,
extraction rejection or loading errors still prevent advancement and successful
cache markers, so failed work stays replayable. The reported run's 15 extraction
errors would therefore still prevent checkpoint advancement even after removing
the terminal dead-feed error; BE-52 does not hide those errors to claim success.

RSS/Atom has no shared resumable cursor: the bounded feed documents must still be
polled on subsequent invocations, including the failed URL. Entries are retained
by content hash and successful extraction cache; unchanged successfully processed
entries do not incur another extraction. `last_success_at` is not used as a
publisher-date filter, which could lose undated, delayed or corrected entries.
Neither a checkpoint nor cache deduplication claims full historical coverage or
recovery of entries lost while a feed was down. Rejected entries remain uncached
and intentionally retryable. No URL disposition or OSM timeout decision is made.

The prior wire schema accepted arbitrary strings for endpoint types and relations;
only the post-generation validator enforced ontology domains/ranges. New schema
versions 1.1.0 and 2.1.0 derive concrete enums and relation-conditional endpoint
constraints from the loaded ontology, including inherited domains/ranges. Both
transports send the same constraints. New prompts require an exact permitted
relation/direction and specify zero-based Unicode offsets, exclusive ends and
verbatim surfaces. Ollama now loads the requested prompt instead of silently
using v1.0.0 under any version stamp. Deterministic validation remains independent;
all rejection reasons and bounded raw response diagnostics stay archived. Providers
can ignore schema hints, so reduced live rejection rates require separately
permitted measurement; no zero-rejection quality claim is made.

Defaults and the settings example now select prompt/schema 1.1.0, preserving the
existing unqualified-claim semantics. Qualified paths can explicitly select the
paired 2.1.0 versions; historical 1.0.0/2.0.0 prompts and schemas remain supported
without rewriting old cache/provenance. Existing environment settings override
defaults: the operator must change `LIMES_EXTRACTION_PROMPT_VERSION` and
`LIMES_EXTRACTION_SCHEMA_VERSION` to `1.1.0` to enable the repair on an installation
explicitly pinned to 1.0.0. No existing configuration or model pins were edited. Final qualification uses a
clean checkout without local configuration files.
The separate news/enrichment CLI's explicit 2.0.0 selection remains reproducible.

TED and FSD already used the shared bounded policy: four total attempts, timeout
60 seconds per request, exponential delays 2/4/8 seconds plus up to 2 seconds
jitter when no valid Retry-After exists. There is no nested adapter retry loop.
Valid Retry-After is a minimum delay; values above 300 seconds fail immediately
with retry-later rather than retrying before the cooldown. Permanent client
errors (including 401/403) fail on the first attempt. Upstream status is not
proof of credential validity or invalidity. No endpoint or credential changed.
The missing observability was structured per-attempt outcomes, particularly the
last attempt where tenacity emits no before-sleep message. Every response now
logs attempt/max, method/URL, HTTP status, classification and parsed cooldown;
transport failures log their type. Existing retry warnings and terminal errors
retain status/attempt count. A 429 without Retry-After is visibly rate limiting;
500 is visibly upstream failure; client failures are separately classified.

## Verification and remaining obligations

Affected tests cover mixed/dead/all-failed/healthy-empty feeds, nonempty/empty/error
checkpoint decisions, ontology-generated schema direction/inheritance and both
transports, preserved rejection archives, and actual TED/FSD adapters with mocked
persistent 429/500. Shared retry tests retain cooldown and permanent-error checks.
No live acquisition or paid provider call is part of verification.

Full candidate results and exact source manifest are recorded in
[VERIFICATION](VERIFICATION.md). Operator obligations remain: dead-feed ownership,
separately authorized deployed feeds observation and extraction-quality measurement,
TED/FSD availability, and OSM timeout/capacity policy. The supplied report's healthy
VPS deployment and successful embedding probe are operational evidence for revision
4ef67c8; they do not repair the older failed frozen qualification reports.

## Acceptance evidence mapping

| Obligation | Implementation evidence | Qualification boundary |
|---|---|---|
| Dead feed isolation and all-failed aggregate | `test_dead_feed_does_not_fail_entries_from_later_feed`, all-failed and healthy-empty adapter cases | Mocked feed transports; dead URL unchanged |
| Honest checkpoints and replay | `test_feeds_checkpoint_requires_entries_and_clean_processing`, existing cache/replay and end-to-end feeds graph tests | Empty/error runs retain checkpoint; successful unchanged entries use cache; feed polling still required |
| Ontology and evidence conformance | Both extractor wire-schema tests, independent parser ontology/span tests, rejection archive regression | Versioned constraints and instructions accepted; live quality unmeasured |
| TED/FSD transport and diagnostics | Actual adapters under persistent mocked 429/500; shared cooldown/permanent-error tests | Four attempts maximum; no early cooldown retry or credential/endpoint changes; upstream recovery unclaimed |
| Complete candidate and local delivery | Exact frozen source/report in VERIFICATION; final source equality check and reviewed local commit | No push, deployment, live ingest or paid verification |


All implementation acceptance items above pass locally. The authoritative full
candidate passes 1,337 cases, including runtime stack, with no failures/errors/skips;
see VERIFICATION for the source fingerprint, earlier failures and timings. The
branch is delivered as one local BE-52 commit; no push or deployment is authorized.
Remaining obligations are operator/live evidence, not inferred from fixture results.
