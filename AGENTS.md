<!-- LIMES — AGENTS.md | v2.0.0 | 2026-07-28 -->

# AGENTS.md — LIMES

Operating contract for coding agents working in this repository. Applies to every session and takes precedence over general habits, defaults, and training priors.

---

## 1. Read This First

This repository is implemented from a complete specification set. You are not designing anything. Read, in order:

| Order | Document | What it gives you |
|---|---|---|
| 1 | `docs/LIMES_Design_Document_v2.0.0.md` | Why the system is shaped this way; requirements, constraints, non-goals, decisions |
| 2 | `docs/LIMES_Technical_Specification_v2.0.0.md` | What to build; module contracts, schemas, endpoints, thresholds, acceptance criteria. **§15 is the seam register — read it before writing any wiring.** |
| 3 | `docs/LIMES_Implementation_Roadmap_v2.0.0.md` | The work package you are executing |

**Precedence on conflict:** Roadmap → Technical Specification → Design Document. If the Roadmap and the Specification disagree, the Specification wins and the Roadmap is defective — report it (§5).

**Version discipline.** All three documents are v2.0.0. If you find a v1.x file anywhere in `docs/`, stop and report it. The v1.x set was withdrawn for the reasons in §2 and must not be present.

---

## 2. Why v1.x Was Withdrawn, and What It Means For You

The previous document set passed complete traceability, an acyclic dependency graph, a full coverage matrix, and cross-reference checks. Implementation stalled three times regardless, because every one of those checks passes for a specification whose modules cannot reach each other.

Fifteen defects were found: twelve seams with no named constructor or invoker, and three sections designing against constraints stated earlier in the same document set.

Two artifacts now close that class, and both bind you:

- **Technical Specification §15** — a seam register derived from end-to-end call traces. Every cross-module handoff has a named owner. **A seam absent from §15.2 is a specification defect. Report it; do not resolve it locally.**
- **`tools/check_docs.py`** — mechanically verifies type closure, requirement traceability, acceptance-criteria numbering, constraint honoring, and seam coverage. Run it before and after any document change.

---

## 3. Session Model

**One work package per session.** You receive the repository in its current state and the three documents. No conversational history; no work package assumes any.

A session ends in one of three states:

- **Complete** — every acceptance criterion passes, every verification command produces its stated result, §4 is satisfied.
- **Partial** — report exactly what is done, what is not, and what blocked you. Do not proceed to the next package.
- **Blocked by conflict** — report per §5 and stop.

Never begin a package whose dependencies are unmet. Never work ahead. Never bundle two packages because they seem related.

---

## 4. Definition of Done

1. Every file in the package scope exists at the exact path in Technical Specification §2. **No file outside that scope was created or modified**, except the single registry line permitted in §6.1.
2. Every acceptance criterion in the package passes.
3. Every verification command produces the stated result. **Run them.** Do not assert they would pass.
4. `ruff check`, `ruff format --check`, and `mypy src/limes` exit clean.
5. Unit tests for the package's own modules exist and pass. Integration tests exist where the package touches Neo4j or HTTP.
6. `CHANGELOG.md` records the package by identifier.
7. Public functions and classes carry type annotations and docstrings stating *behavior*, not restating the signature.
8. No `TODO`, `FIXME`, stub, or placeholder value remains.
9. No secret, host path, or environment-specific value in any committed file.

---

## 5. When the Specification Is Wrong

It will be, somewhere. Fifteen instances are already documented.

1. Stop work on the affected task.
2. Report as `[CONFLICT]`, naming document, version, and section, and stating precisely why the specification cannot be satisfied as written.
3. Propose a resolution if you have one. **Do not apply it.**
4. Wait.

**Do not:** invent a resolution, pick "the obvious interpretation," add a helper the spec does not describe, extend a schema, add a configuration key, add a dependency, or silently widen scope. A local workaround for a specification defect propagates into every downstream package and costs far more than a stopped session.

The same applies to genuine ambiguity. Ambiguity resolved by guessing is indistinguishable from correctness until it is very expensive.

---

## 6. Conventions

**Language.** Python for all scripting. No shell scripts beyond a single command; a Makefile target needing logic calls a Python module. Comments explain why, not what. Explicit error handling everywhere.

**Environments.** Host tooling in `./venv/`. `--break-system-packages` is prohibited under all circumstances. Container images install directly; no virtual environment inside an image. Everything headless. No GPU dependency, ever.

**Versioning.** Every module header carries a version comment naming the work package that introduced it and the last that modified it. Four independent version lines exist — project, ontology, gold set, prompts. Bump the right one.

**Never call anything final.** Not in filenames, comments, commit messages, or changelog entries.

**Delivery.** When asked to show a file, show the complete current file. No diffs, no fragments, no omitted sections.

**Git.** One branch per work package, `wp-NN-short-slug`. Conventional commits with the identifier in scope.

**Artifact language.** All code, comments, docstrings, logs, documentation, and UI text in American English. German source data is stored and displayed verbatim, never translated.

### 6.1 The One Permitted Cross-Package Modification

Every adapter package may add **one import and one `register()` call** to `src/limes/sources/registry.py`. Nothing else. This is granted because the registry is the authoritative source list and must be greppable in one file; import-time self-registration is rejected for that reason.

---

## 7. Traps Specific to This Repository

These are the failure modes that matter here. Most are invisible in tests that only check the happy path, and several are drawn from defects that actually occurred.

### 7.1 Order of construction is load-bearing

- **The cost governor exists before anything that can spend money.** During extractor development you will call real endpoints repeatedly. Without the governor in place, one defective loop consumes a year of budget overnight. Do not stub it "for now."
- **The entity backbone loads before extraction runs.** Extraction against an empty graph produces mentions with nothing to resolve against; every one becomes a fresh canonical entity and the work is paid for twice. Runtime rule as much as build rule.

### 7.2 Silence is the enemy

Nothing may be dropped without being counted. Every skipped record, gated-out document, rejected assertion, and refused call is logged with a reason and counted in the run record. A pipeline that quietly discards ten percent of its input is indistinguishable from one working correctly. If you write `except: pass` or a bare `continue` without a counter, stop.

### 7.3 Two assertion types, and they are not interchangeable

`ExtractedAssertion` carries `Mention` endpoints and is what the extractor returns. `Assertion` carries `EntityEndpoint` and is what the loader accepts. The extractor cannot produce the latter because it runs before resolution and cannot assign an `entity_id`. The named converter is `resolution/resolve.py::resolve_assertions`. Conflating the two was a v1.x defect that failed on first type-check.

### 7.4 The loader is the sole writer of ontology-typed nodes and relationships

Not adapters. Not the resolver. The resolver mints an `entity_id` and returns an `EntityEndpoint`; the loader materializes it, so a new entity is created in the same transaction as the assertion justifying it. If you write a `MERGE` on an ontology type outside `graph/loader.py`, you have misread the spec. See §15.2 for the complete node ownership table.

### 7.5 Merges are links, never absorptions

Entity resolution creates a scored `SAME_AS` relationship. It never deletes, absorbs, or rewrites a node. Unmerging is retracting the link. A `DETACH DELETE` outside a test fixture teardown is a defect.

Nothing is deleted during ingestion. A fact ceasing to be true sets `valid_to`. A belief being corrected sets `retracted_at`. Different fields, different meanings; do not conflate them.

### 7.6 Interval closure is scoped to a source

The loader closes a superseded validity interval only for assertions from the **same** `source_id`. Closing across sources destroys the disagreement between them, and in this domain the disagreement is frequently the signal. There is a test for both branches; run it if you touch the loader.

### 7.7 `recorded_at` must be honest

For OffeneRegister, `recorded_at` is the **dataset's publication date**, not the ingestion timestamp. Setting it to ingestion time makes multi-year-stale directorships look current and defeats the entire trust-ranking design. The principle generalizes to any source that publishes its own vintage.

### 7.8 Evidence spans are checked, not trusted

An extracted assertion whose evidence span does not contain its subject or object surface is rejected. Model-returned offsets are passage-local and must be mapped to document offsets before the check. Getting the mapping wrong makes the check pass vacuously.

### 7.9 Cross-process state lives in the graph

Every CLI invocation is a fresh process (C-07). Module-level state does not survive. Any value one command produces and another consumes goes into Neo4j as a system node with provenance — never a module global, never a derived cache file, never a re-download. If you are about to write a module-level dict as a lookup table, stop.

### 7.10 The read path is not protected by the database

Neo4j Community has no RBAC (C-01); a read-only user is not creatable. What protects the graph is parse-level rejection, driver session access mode, and the API having exactly three enumerated writes. **Do not add a fourth write path to `src/limes/api/`** — there is a grep-based acceptance test, and it exists because the database cannot do this job.

### 7.11 The UI knows nothing

No module under `src/limes/ui/` may contain a hardcoded entity type name, relation name, or Cypher fragment, or perform HTTP anywhere except `api_client.py`. The builder is generated entirely from `GET /builder/schema`. A single hardcoded `"Corporation"` breaks the property that keeps the ontology authoritative.

### 7.12 There are no query templates

Not in docs, code, fixtures, or the NL-to-Cypher prompt as "helpful examples." The five reference questions in `reference_questions/questions.yaml` are ontology-expressibility fixtures and a generation-quality metric. They must not surface in the UI as suggestions.

### 7.13 Distinctions that look redundant are not

`ACTOR_IN`, `TARGET_OF`, and `PARTICIPANT_IN` are three relations, not one with a role property — GDELT encodes directional asymmetry, the Transparency Register encodes symmetric attendance. `TARGETS`, `IMPOSED_BY`, and `ESTABLISHED_BY` are three relations because a sanction's target, imposing authority, and establishing instrument are three facts with three sources and three validity intervals. Read Design Document §5.4 before proposing a simplification.

### 7.14 Region assignment is a lookup, not geometry

Regions come from the postal-code correspondence or a source's own NUTS field. Never compute point-in-polygon; Neo4j cannot, and adding a spatial engine is an explicit non-goal. No postal code means the region stays unassigned and counted — never approximated from coordinates.

### 7.15 Ingested text is untrusted input

Document text goes to the model inside an explicitly delimited block, never concatenated into the instruction portion. Extraction calls carry no tool definitions. Do not "improve" a prompt by inlining document text for readability.

---

## 8. Test Construction Rules

Both are mandatory and both come from defects that shipped.

**8.1 A test may not hand-build the state the code under test is supposed to produce.** Loader tests construct assertions and assert on the resulting graph; they do not pre-create endpoint nodes by direct Cypher. Where pre-existing state is needed, establish it by calling the production path. A test that pre-builds its inputs verifies arithmetic while proving nothing about whether the pipeline can produce them — this is exactly how the v1.x node-creation gap survived its own suite for eight work packages.

**8.2 A cross-process test must cross a real process boundary.** Use `subprocess`, not a fresh object in the same interpreter. An in-process test of cross-process state passes vacuously.

---

## 9. Forbidden Without Explicit Approval

- Adding, removing, or upgrading a dependency
- Adding a configuration key not in `.env.example`
- Adding a directory not in Technical Specification §2
- Modifying `ontology/ontology.yaml` outside a migration
- Modifying a prompt file without bumping its version
- Changing a threshold, limit, or default stated in the specification
- Modifying files outside the current package's scope, except §6.1
- Adding a write path to `src/limes/api/`
- Committing a real API key, a host path, or a `.env` file
- Marking a test skipped or expected-to-fail to make a suite pass
- Running the bootstrap out of order
- Running `backfill` or `reextract` without an explicit budget argument

---

## 10. Verification Discipline

Run the commands. Report their actual output. Never write "tests should pass" or "this would produce" — either you ran it and it did, or you did not run it and you say so.

Bring up a live stack where a verification needs one. Use recorded fixtures where an adapter needs network — no test in this repository may hit a live external service.

When a verification fails and you believe the verification itself is wrong, that is a `[CONFLICT]` per §5, not licence to adjust the test.

---

## 11. Session Report Format

```
WORK PACKAGE: WP-NN — <title>
STATUS: complete | partial | blocked

FILES CREATED:   <paths>
FILES MODIFIED:  <paths>

VERIFICATION:
  <command>  →  <actual result>

ACCEPTANCE CRITERIA:
  AC-NN  pass | fail | not applicable

CHANGELOG: <entry added>

NOTES / CONFLICTS:
  <anything the next session needs, or [CONFLICT] reports>
```

If status is anything other than `complete`, be specific about what remains. The next session has no memory of this one and will believe your report.
