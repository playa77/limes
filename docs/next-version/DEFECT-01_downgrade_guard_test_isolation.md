# DEFECT-PA1-R1: `test_provision_runs_the_downgrade_guard` fails under combined integration runs

Status: routed to codex (default LIMES owner), opened by Hermes 2026-11-08 after the
PA-1 implementation session surfaced it. Pre-existing on main `af403c4` — verified
identically on a clean worktree at that commit; NOT caused by PA-1 (branch
`wp-57-parallel-downloads-cancel`).

## Observed failure

- Command: `pytest tests/integration/test_pipeline_run_structured.py tests/integration/test_composition_root.py`
- Failure: `tests/integration/test_composition_root.py::test_provision_runs_the_downgrade_guard`
  asserts `MATCH (n:Source) RETURN count(n)` == 0 and sees 1 — `test_pipeline_run_structured`
  (which runs first, alphabetically `pipeline…` > `composition…`? no — composition earlier;
  reproduced in both orderings when the file containing pipeline runs in the same session)
  leaves `:Source {source_id: "gisco_nuts"}` in the shared session container, and the guard
  test assumes a fresh graph without cleaning it.
- Full-suite run 2026-11-08 pre-fix (`pytest tests/unit tests/integration`): 36 failed,
  14 errors — most share a second root (a GraphDriver fake lacking a new attribute); that
  cluster is fixed on the PA-1 branch. The downgrade-guard failure is the remaining
  pre-existing one and reproduces on base alone.

## Root cause

The session-scoped Neo4j container (`tests/integration/conftest.py::neo4j_instance`) is
shared by every file in `tests/integration`; most files clean per test (the sanctioned
fixture-teardown exception), but `test_provision_runs_the_downgrade_guard` assumes an
untouched graph instead of cleaning before its count. Any earlier file that legitimately
leaves data (pipeline structured run writes a real `:Source`) breaks it.

## Suggested fix (owner's call)

- Minimal: in that test, `DETACH DELETE` before the count (same sanctioned-exception
  pattern its sibling files use), so it proves "guard passes on a fresh graph" rather
  than "graph is currently empty".
- Alternative: give `test_composition_root` its own disposable container via the
  existing `Neo4jInstance` fixture if a clean-graph guarantee is wanted semantically.

## Acceptance

`pytest tests/integration/test_pipeline_run_structured.py tests/integration/test_composition_root.py -q`
passes in one session; the guard's fresh-graph claim is stated by construction, not by
luck of ordering.

## 2026-11-09 — Current disposition: repaired and targeted requalification passed

The current-release readiness pass reproduced the exact two-module command on
main `1dd2d8241a84`: **1 failed, 13 passed**, 522.24 seconds; the failure was the
reported `Source` count of one. `test_composition_root.py` now requests a
function-scoped `fresh_graph` fixture backed by the session-owned disposable
Neo4j instance. It deletes test data before the composition build, preserving
the fresh-graph premise and the production guard. The repaired exact command
passes **14 tests**, 395.47 seconds. Evidence: `work/readiness/defect-pa1-before.xml`
and `defect-pa1-after.xml` with matching logs. No assertion was removed, and no
production schema/guard code changed. Whole-candidate qualification is recorded
separately in [VERIFICATION](../VERIFICATION.md).
