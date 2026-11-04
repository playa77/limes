# BE-54 extraction evidence-span geometry

Selected before coding on 2026-11-04. Branch:
`codex/be-54-extraction-span-geometry`, live main `029f2fceea1d`.
Prerequisites: BE-41 documentation gate passed; deployed BE-52/53 operator report,
feeds2 poll and full-output evidence read (the poll file is at the report root,
not under evidence/). No paid call or live acquisition.

## Acceptance checklist

- Trace document slicing, prompt serialization, wire schema and validator coordinates.
- Version a passage-bounded generation contract without weakening independent
  rejection, archival, cache/provenance or checkpoint semantics.
- Reproduce item 1, span 547:631 outside passage 0 deterministically with mocked
  transport; cover Unicode, nonzero document origins and batch-local bounds.
- Run affected tests/shared guards, then one authoritative frozen full candidate.
- Review the main diff and commit the entire BE-54 locally; never push.
- Record operator pin/redeploy/live measurement obligations; never claim measured
  zero rejections from offline evidence.

## Diagnosis

Feeds normalize title/body into document text. The gate selects dense sentence
windows; window_passages takes exact document slices and enumerates them from zero.
Batching preserves these indices. Serialization previously added `[n]` headers and
nested PASSAGES delimiters (both template and renderer supplied the outer block).
Prompt 1.1.0 requested Unicode passage-local offsets excluding headers, but supplied
no explicit length. Schema 1.1.0 allowed any nonnegative integer, with no connection
between passage_index and offset bounds. The validator correctly checks the exact
Python passage text length and surface containment, then adds doc_start for storage.
There is no supported document-global or whole-prompt coordinate interpretation.

The operator reports item 1 span 547:631 outside passage 0; item 1 is the second
assertion, not the second passage. Repeated poll snapshots are not proof of distinct
responses. Decoding the 11 concatenated poll snapshots yields one unique rejection
at 19:38:03.016982Z for content hash
`584b0809f4ce60b10aa66452d7777c19fb3de0ef4e743b3518e0a401cc352131`.
That event appears in four snapshots. The call accepted one assertion and rejected
one; its preceding normalization reports 522 body characters and windowing reports
four sentences, three centers and one passage. The exact serialized passage length
is not logged (title and window boundaries matter), so it cannot be recovered from
body length alone. Model/reasoning logs confirm the operator pins. Its archived diagnostic hash is
`ae920c3b9b7e7c3ea350464b30366aca69de6fd21baa8c2bf43962a59ae3ec3f`.
The supplied 32 KiB full-output tail has already lost that event. The evidence does not contain the model's reasoning or a complete prompt/
response pair, so its precise alternate coordinate system cannot be established.
The confirmed contract gap is unconstrained generation geometry despite strict
post-generation geometry. Do not clamp, shift or silently salvage bad offsets.

## Implemented contract and operator obligations

Prompt/schema **1.2.0** keeps unqualified assertion semantics and the same local
coordinate system. The prompt uses one outer block, explicit per-passage length L
and PASSAGE_TEXT boundaries. It distinguishes Python Unicode code points from
bytes/UTF-16/tokens and requires coordinates to reset for each assertion. Reusing
a supporting sentence's offsets across assertions is correct. No source text is
trimmed, normalized or renumbered during serialization.

The wire schema retains ontology-derived constraints and adds a oneOf branch for
each passage in the current batch: its exact index and that passage's own maximum
start/end. A short passage cannot borrow the longest passage's bound or select an
absent batch index. Both transports receive the same schema. The parser remains
unchanged in behavior and independently checks bounds, ordering, surface inclusion,
ontology and dates. Schema hints cannot guarantee provider compliance; reversed,
empty/unsupported and out-of-bounds spans remain deterministic errors. No offsets
are repaired, no rejection is cached as success and processing errors still block
checkpoint advancement. Existing archival coverage retains the observed reason.
Historical prompts/schemas and qualified 2.x selection remain reproducible.

Defaults and the public example select 1.2.0. Existing explicit pins override them.
The operator must set these two lines in **config/settings.env** (not edited here):

```dotenv
LIMES_EXTRACTION_PROMPT_VERSION=1.2.0
LIMES_EXTRACTION_SCHEMA_VERSION=1.2.0
```

Redeploy the eventual delivered revision, verify worker-effective versions, retain
`z-ai/glm-5.3-flash` and reasoning `xhigh`, then manually run feeds and preserve the
full output/rejection diagnostics before job-tail roll-off. Record fetched, written,
rejected, record errors, checkpoint behavior, usage/cost and exact versions. A new
version pair changes the cache key: previously successful 1.1.0 entries are not
1.2.0 cache hits, so the next run may re-extract eligible unchanged documents and
cost more than the approximately EUR 0.01 recovery run. Historical cache/provenance
is not rewritten. This implementation does not authorize that live run.

Live absence of out-of-passage spans and overall extraction quality remain
**unmeasured** until the operator supplies that rerun. OI-32 retains this obligation;
upstream OSM/TED/FSD and other historical issue ownership is unchanged.

## Acceptance evidence mapping

| Checklist | Evidence |
|---|---|
| End-to-end coordinates | Diagnosis above; feeds normalization, gate/window_passages, shared serializer, schema parser and doc_start mapping reviewed |
| Bounded generation, preserved rejection | 1.2.0 prompt and response_schema_for_version; both transports; independent validator unchanged |
| Observed second-item regression | test_observed_second_assertion_overflow_is_rejected_without_repair: raw transcript retained, first assertion mapped, second rejected with exact observed reason |
| Unicode/batches/transport parity | test_geometry_contract_is_shared_and_scoped_to_each_batch: literal 43-character passage, nonzero origin, unequal lengths, absent-index refusal and identical OpenRouter/Ollama contracts |
| Archive/checkpoint/cache invariants | Existing pipeline rejection-archive test now retains the observed overflow reason; affected/shared checks and full candidate below |
| Delivery/live boundary | Local commit only; operator settings/redeploy/measurement instructions above |

## Development verification

Canonical environment: `UV_PROJECT_ENVIRONMENT=venv uv sync --frozen --all-packages`.
Affected extraction/schema/Ollama/pipeline unit checks: **58 passed in 36.03 s**.
Affected feeds graph checks: **9 passed in 50.00 s**, fixture-owned disposable graph.
Lint, mypy and C1–C9/G1–G4 pass. Initial unit invocation stopped before collection
because libEGL was unavailable; the existing ignored BE-53 Qt library bundle supplies
it via `LD_LIBRARY_PATH=$PWD/work/be53/qt-libs/root/usr/lib/x86_64-linux-gnu`.
The next development run exposed one incorrect new fixture expectation (44 instead
of 43 Unicode characters); corrected before the passing affected run and freeze.
Two new tests cover distinct observed-overflow and shared geometry behaviors;
existing archive/provenance tests are extended, not duplicated.

The full candidate runs through `tools/qualify.py` in this checkout with the same
Qt library path; it freezes all implementation/tests/tools/dependencies via its
source manifest. Headless flags are set by the runner. Independent hosted CI lanes
remain on separate runners; local full suites run sequentially. No service restart,
production endpoint, real model call or source acquisition is used.

## Final local disposition and commit map

All local implementation checklist items pass. The authoritative frozen candidate
passes all six lanes, including isolated runtime: **1,350 cumulative cases**, zero
failures/errors/skips; validation elapsed **828.681 seconds**.
[Exact lane results and source fingerprint](VERIFICATION.md) retain evidence.
Live absence of out-of-passage output remains the explicitly unrun operator gate,
not a completed measurement. No production or zero-rejection claim is made.

One local BE-54 delivery commit, `fix(extraction): bind evidence offsets to passage geometry`,
contains the complete checklist: transport/prompt/schema/default changes, the two
new regression tests, existing archive/provenance expectation updates and this
handoff/specification/ledger reconciliation. No child is delivered separately.
The commit's implementation manifest matches the frozen source above; only
handwritten evidence documentation follows the candidate. No push is authorized.
