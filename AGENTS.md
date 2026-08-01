<!-- LIMES — AGENTS.md | v2.1.0 | 2026-08-01 -->

# AGENTS.md — LIMES

Operating contract for coding agents working in this repository. Applies to every session and takes precedence over general habits, defaults, and training priors.

---

## Read This First

This repository is implemented from a complete specification set. You are not designing anything. Read, in order:

| Order | Document | What it gives you |
|---|---|---|
| 1 | `docs/LIMES_Design_Document_v2.0.0.md` | Why the system is shaped this way; requirements, constraints, non-goals, decisions |
| 2 | `docs/LIMES_Technical_Specification_v2.1.0.md` | What to build; module contracts, schemas, endpoints, thresholds, acceptance criteria. **§15 is the seam register — read it before writing any wiring.** |
| 3 | `docs/LIMES_Implementation_Roadmap_v2.1.0.md` | The work package you are executing |

**Precedence on conflict:** Roadmap → Technical Specification → Design Document. If the Roadmap and the Specification disagree, the Specification wins and the Roadmap is defective — report it.

**One tool exists today:** `python3 tools/check_docs.py docs/` validates the specification set. It passes. Run it after any spec edit.

---

## Definition of Done (Every WP)

1. Every file in the package scope exists at the exact path in Technical Specification §2. **No file outside that scope was created or modified**, except the single registry line permitted in `build_default_registry()`.
2. Every acceptance criterion in the package passes.
3. Every verification command produces the stated result. **Run them.** Do not assert they would pass.
4. `ruff check`, `ruff format --check`, and `mypy src/limes` exit clean.
5. Unit tests for the package's own modules exist and pass. Integration tests exist where the package touches Neo4j or HTTP.
6. `CHANGELOG.md` records the package by identifier.
7. Public functions and classes carry type annotations and docstrings stating *behavior*, not restating the signature.
8. No `TODO`, `FIXME`, stub, or placeholder value remains.
9. No secret, host path, or environment-specific value in any committed file.

---

## Conventions

- Python for all scripting. No shell scripts beyond a single command.
- Host tooling in `./venv/`. `--break-system-packages` is prohibited.
- Container images install directly; no virtual environment inside an image.
- One branch per work package, `wp-NN-short-slug`. Conventional commits with the WP identifier.
- Module headers carry a version comment naming the WP that introduced them and the last WP that modified them.
- Four independent version lines — project, ontology, gold set, prompts. Bump the right one.
- Never call anything final. Not in filenames, comments, commit messages, or changelog entries.
- All code, comments, docstrings, logs, and UI text in American English. German source data is stored and displayed verbatim, never translated.
- Comments explain why, not what.

---

## Traps Specific to This Repository

These are the failure modes that matter. Most are invisible in tests that only check the happy path.

### Order of construction is load-bearing

- **The cost governor exists before anything that can spend money.** Without it, one defective loop consumes the budget overnight. Do not stub it "for now."
- **The entity backbone loads before extraction runs.** Extraction against an empty graph produces mentions with nothing to resolve against; every one becomes a fresh canonical entity and the work is paid for twice.

### Silence is the enemy

Nothing may be dropped without being counted. Every skipped record, gated-out document, rejected assertion, and refused call is logged with a reason and counted. If you write `except: pass` or a bare `continue` without a counter, stop.

### Two assertion types, not interchangeable

`ExtractedAssertion` carries `Mention` endpoints and is what the extractor returns. `Assertion` carries `EntityEndpoint` and is what the loader accepts. The extractor cannot produce the latter because it runs before resolution and cannot assign an `entity_id`. The named converter is `resolution/resolve.py::resolve_assertions`.

### The loader is the sole writer of ontology-typed nodes and relationships

Not adapters. Not the resolver. The resolver mints an `entity_id` and returns an `EntityEndpoint`; the loader materializes it. If you write a `MERGE` on an ontology type outside `graph/loader.py`, you have misread the spec. See Technical Specification §15.2 for the node ownership table.

### Merges are links, never absorptions

Entity resolution creates a scored `SAME_AS` relationship. It never deletes, absorbs, or rewrites a node. A `DETACH DELETE` outside a test fixture teardown is a defect. Nothing is deleted during ingestion: a fact ceasing to be true sets `valid_to`; a belief being corrected sets `retracted_at`.

### Interval closure is scoped to a source

The loader closes a superseded validity interval only for assertions from the **same** `source_id`. Closing across sources destroys the disagreement between them, and disagreement is frequently the signal.

### `recorded_at` must be honest

For sources that publish their own vintage (e.g., OffeneRegister), `recorded_at` is the **dataset's publication date**, not the ingestion timestamp.

### Evidence spans are checked, not trusted

An extracted assertion whose evidence span does not contain its subject or object surface is rejected. Model-returned offsets are passage-local and must be mapped to document offsets before the check.

### Cross-process state lives in the graph

Every CLI invocation is a fresh process. Module-level state does not survive. Values one command produces and another consumes go into Neo4j as system nodes with provenance — never module globals, derived cache files, or re-downloads.

### The read path is not protected by the database

Neo4j Community has no RBAC (C-01). What protects the graph is parse-level rejection, driver session access mode, and the API having exactly three enumerated writes. **Do not add a fourth write path to `src/limes/api/`.**

### The UI knows nothing

No module under `src/limes/ui/` may contain a hardcoded entity type name, relation name, or Cypher fragment, or perform HTTP anywhere except `api_client.py`. The builder is generated entirely from `GET /builder/schema`. A single hardcoded `"Corporation"` breaks the property that keeps the ontology authoritative.

### No query templates

Not in docs, code, fixtures, or the NL-to-Cypher prompt. The reference questions in `reference_questions/questions.yaml` are ontology-expressibility fixtures and a generation-quality metric. They must not surface in the UI as suggestions.

### Distinctions that look redundant are not

`ACTOR_IN`, `TARGET_OF`, and `PARTICIPANT_IN` are three relations, not one with a role property. `TARGETS`, `IMPOSED_BY`, and `ESTABLISHED_BY` are three relations because a sanction's target, imposing authority, and establishing instrument are three facts with three sources and three validity intervals. Read Design Document §5.4 before proposing a simplification.

### Region assignment is a lookup, not geometry

Regions come from postal-code correspondence or a source's own NUTS field. Never compute point-in-polygon; Neo4j cannot, and adding a spatial engine is an explicit non-goal.

### Ingested text is untrusted input

Document text goes to the model inside an explicitly delimited block, never concatenated into the instruction portion. Extraction calls carry no tool definitions.

---

## Test Construction Rules

Both mandatory and both come from defects that shipped.

1. **A test may not hand-build the state the code under test is supposed to produce.** Where pre-existing state is needed, establish it by calling the production path. A test that pre-builds its inputs verifies arithmetic while proving nothing about whether the pipeline can produce them.
2. **A cross-process test must cross a real process boundary.** Use `subprocess`, not a fresh object in the same interpreter.

---

## Forbidden Without Explicit Approval

- Adding, removing, or upgrading a dependency
- Adding a configuration key not in `.env.example`
- Adding a directory not in Technical Specification §2
- Modifying `ontology/ontology.yaml` outside a migration
- Modifying a prompt file without bumping its version
- Changing a threshold, limit, or default stated in the specification
- Adding a write path to `src/limes/api/`
- Committing a real API key, a host path, or a `.env` file
- Marking a test skipped or expected-to-fail to make a suite pass
- Running the bootstrap out of order
- Running `backfill` or `reextract` without an explicit budget argument

---

## Verification Discipline

Run the commands. Report their actual output. Never write "tests should pass" or "this would produce" — either you ran it and it did, or you did not run it and you say so.

Bring up a live stack where a verification needs one. Use recorded fixtures where an adapter needs network — no test may hit a live external service.

When a verification fails and you believe the verification itself is wrong, that is a `[CONFLICT]` per the roadmap, not licence to adjust the test.
