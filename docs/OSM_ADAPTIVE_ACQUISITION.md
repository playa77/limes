# BE-50 — adaptive OSM acquisition

Branch `codex/be-50-adaptive-osm-acquisition`; live base `54c6a1a3efa2`.
Prerequisites: BE-49 archive, acquisition cursor and pipeline lifecycle.
The complete package repairs overloaded fixed cells; deployment and live nationwide
qualification require an identified operator environment and remain unmeasured.

## Acceptance and behavior

- Explicit Overpass runtime query timeouts and out-of-memory remarks subdivide the
  failed cell into four adjoining quadrants. All seven selectors and the exact
  parent extent survive. Generic remarks, invalid JSON, HTTP failures and rate
  limits remain failures; smaller queries cannot establish a remedy for those.
- The original failed response is archived. The cursor records the split before
  requesting a child, then records each validated child's original archive hash
  and fetch instant. A restart derives the same tree and reuses completed leaves.
- All leaves must validate before any load records are yielded. Stable depth-first
  leaf order and `(type,id)` deduplication cover shared boundaries. Complete
  manifests contain the split tree and leaf entries; raw payloads are unchanged.
- Subdivision is limited to three levels below each original cell (at most 5,120
  leaves). An invocation makes at most 200 acquisition fetch calls, sequentially
  spaced by one second; shared transport retries remain separately bounded.
  Reaching either bound fails with an explicit retained-progress message and no
  checkpoint advance. A later explicit invocation reuses completed leaves.
- Existing BE-49 cursors have an empty split tree by default and keep the same
  root query-plan hash. Unknown/orphan splits, duplicate splits, excessive depth,
  and cached entries outside the derived leaf coverage fail closed.
- Acquisition and graph checkpoint semantics remain separate. Interrupted child
  fetches and failed loading retain state; cursor retirement still follows fully
  successful loading and precedes checkpoint advancement.

Direct coverage: `test_adaptive_split_restart_coverage_and_dedup` checks exact
quadrants, interrupted-child restart, original manifest and deduplication;
`test_adaptive_depth_and_request_limits_preserve_progress` checks finite limits;
`test_adaptive_cursor_rejects_invalid_tree` checks corrupt topology. The disposable
Neo4j `test_adaptive_children_must_all_complete_before_graph_load` checks failure
with no assets/checkpoint followed by restart, complete loading and retirement.
Existing BE-49 graph failure/replay coverage remains active.

## Operational limits

This is a collection over an interval, not an atomic OSM snapshot. No absence,
removal or historical coverage is inferred. A smallest allowed cell may still
exceed upstream capacity; the explicit depth failure requires inspection. HTTP
429/5xx, malformed responses and network failures do not trigger endpoint rotation
or automatic job replay. No production acquisition, deployment, legacy numeric-ID
migration or paid inference is performed by implementation verification.

Validation results and remaining qualification blockers are recorded in
[VERIFICATION](VERIFICATION.md). OI-28's earlier qualification and live-capacity
obligations are not closed by new fixture tests.


## Candidate disposition

Implementation and affected acquisition/graph behavior pass. The complete candidate
passes 1,321 backend/desktop/graph/acceptance cases; its sole runtime-stack case
fails from reproduced executor disk exhaustion during container creation.
The package is not fully qualified. VERIFICATION retains the frozen source digest,
exact failure, timings and cleanup. Nationwide live capacity remains unmeasured.
