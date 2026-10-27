# LIMES work-package baseline audit — 2026-10-27

Repository baseline: live-fetched `origin/main` = `3f1effd01bd9`. This audit is now incorporated into the BE-41 reconciliation on `codex/core-news-design`. Backend and desktop status are authoritative in their separate roadmaps.

## Findings

The repository does contain substantial implementations merged beyond backend WP-10. This is supported by recovered package definitions, commit content, current source and main ancestry—not only commit titles. This does **not** establish that every original acceptance obligation remains satisfied or that all live inputs work. A blanket “all work packages complete” conclusion is unsupported.

The original roadmap is recoverable with `git show 37a8989^:docs/LIMES_Implementation_Roadmap_v2.1.0.md`. Commit `37a8989` deleted its 2,973 lines on 2026-08-03. It defines WP-01 through WP-39 plus WP-25a (40 packages), across phases 0–10. WP-10 is GISCO/NUTS, not phase 10. Phase 10 is WP-39 acceptance testing. WP-40 was added later for the coverage exercise. The separate desktop plan restarts numbering at WP-01 and reaches WP-13; it is not the backend sequence.

## Backend package evidence

Each commit below was checked with `git merge-base --is-ancestor COMMIT origin/main`. Representative files exist now and were checked against commit diffs; presence alone is not acceptance. The commit file counts exclude merge commits and show substantive changed files, not current test results.

| Backend WP | Defined scope | Implementation commit in main | Files changed in commit | Representative present artifact |
|---|---|---|---|---|
| 01 | Repository/tooling | `1a66814` | 30 | `pyproject.toml` |
| 02 | Configuration/types/errors/logging | `2f8886f` | 9 | `src/limes/config.py` |
| 03 | Ontology | `5476574` | 7 | `src/limes/ontology/registry.py` |
| 04 | Graph/schema/temporal | `f06bce0` | 10 | `src/limes/graph/driver.py` |
| 05 | Archive | `49fe0cb` | 2 | `src/limes/archive/store.py` |
| 06 | Usage ledger/governor | `4411634` | 4 | `src/limes/cost/ledger.py` |
| 07 | Graph loader | `52429d0` | 4 | `src/limes/graph/loader.py` |
| 08 | Graph lookups | `b4db02b` | 3 | `src/limes/graph/lookups.py` |
| 09 | Sources/normalizer | `416de56` | 5 | `src/limes/sources/registry.py` |
| 10 | GISCO/NUTS | `beaa26c` | 4 | `src/limes/sources/gisco_nuts.py` |
| 11 | GLEIF | `f4ad3c8` | 10 | `src/limes/sources/gleif.py` |
| 12 | EUR-Lex | `f4ad3c8` | 10 | `src/limes/sources/eurlex.py` |
| 13 | FSD | `f4ad3c8` | 10 | `src/limes/sources/fsd.py` |
| 14 | TED | `0ddacbc` | 10 | `src/limes/sources/ted.py` |
| 15 | Transparency Register | `0ddacbc` | 10 | `src/limes/sources/transparency_register.py` |
| 16 | Bundestag DIP | `0ddacbc` | 10 | `src/limes/sources/bundestag_dip.py` |
| 17 | Gesetze im Internet | `6cf853c` | 16 | `src/limes/sources/gesetze_im_internet.py` |
| 18 | Wikidata | `6cf853c` | 16 | `src/limes/sources/wikidata.py` |
| 19 | OSM | `6cf853c` | 16 | `src/limes/sources/osm.py` |
| 20 | OffeneRegister | `085e43c` | 4 | `src/limes/sources/offeneregister.py` |
| 21 | GDELT/feeds | `cfe157a` | 9 | `src/limes/sources/gdelt.py` |
| 22 | Extraction | `40d968e` | 10 | `src/limes/extraction/schema.py` |
| 23 | Extraction cache | `031c0a0` | 2 | `src/limes/extraction/cache.py` |
| 24 | Gate/passages | `73a9a49` | 4 | `src/limes/pipeline/gate.py` |
| 25 | Entity resolution | `d51f01a` | 13 | `src/limes/resolution/resolve.py` |
| 26 | Composition | `cce322d` | 9 | `src/limes/composition.py` |
| 27 | Pipeline/window | `cce322d` | 9 | `src/limes/pipeline/run.py` |
| 28 | CLI core | `d8e6370` | 30 | `src/limes/cli/ingest.py` |
| 29 | Model selection | `d8e6370` | 30 | `src/limes/cli/select_models.py` |
| 30 | Evaluation | `d8e6370` | 30 | `src/limes/cli/evaluate.py` |
| 31 | Migration | `d8e6370` | 30 | `src/limes/cli/migrate.py` |
| 32 | API foundation | `ef749e4` | 19 | `src/limes/api/main.py` |
| 33 | NL-to-Cypher | `99146e6` | 9 | `src/limes/nlq/service.py` |
| 34 | Coverage/diagnosis | `4400d1f` | 4 | `src/limes/coverage/report.py` |
| 35 | Query routes/builder | `178bdbb` | 11 | `src/limes/api/routers/query.py` |
| 36 | Dash UI (superseded as shipped UI) | `48556d3` | 14 | `src/limes/ui/app.py` |
| 37 | Images/Compose | `b38a5df` | 10 | `docker-compose.yml` |
| 38 | Make/bootstrap | `b38a5df` | 10 | `Makefile` |
| 39 | Acceptance suite | `228d913` | 30 | `tests/acceptance/conftest.py` |
| 40 | Later coverage exercise | `d22f486` | 46 | `tests/unit/test_loader_logic.py` |

WP-25a implementation history:
- `10ef4b6 WP-25a: label_embedding merge stamp and backfill (spec v2.1.0)`

## Merge and acceptance evidence limits

- Backend phase merges from source-layer `871603c` through pipeline `b927986`, API `15c36f6`, infrastructure `5cb32dc`, acceptance `1aa142f` and coverage `77934db` are in current main first-parent history.
- `DECISIONS.md` contains recorded approvals for phase 3 (WP-21–24), phase 5 (WP-26–27), phase 10 (WP-39) and phase 11 (WP-40), among others. These are repository records attributed to earlier sessions; this audit cannot independently authenticate the original user conversations.
- `CHANGELOG.md` describes implementation and historical test outcomes. Those are historical reports, not fresh verification. The old 100% coverage claim must not be carried forward as a current measurement.
- Original WP-06 monetary governor was deliberately removed in `94052b4`; its absence now is a requirement change, not evidence that WP-06 was never implemented. Dash WP-36 is retained compatibility code and superseded by the desktop. Runtime and backup architecture were subsequently redesigned.
- Original WP-21 and WP-27 have open, reproduced defects OI-19–22: incompatible GDELT format/column map, loss of structured assertions in document routing, missing report granularity, geography and slot-rounding defects. “Implemented/merged” is not “correct and accepted” for these paths.
- Original infrastructure/deployment acceptance is not established by source existence. OPEN_ISSUES retains production smoke/deployed-revision gaps. No live ingestion, paid model quality or production readiness is established here.

## Desktop numbering

The later desktop implementation uses its own WP-01–13 sequence, documented in `docs/superpowers/plans/2026-09-09-desktop-client.md`. Main contains implementation commits from `fb1945c` through `1346847` and merge `5ab2d4e` (2026-09-10). Current `desktop/src/limes_desktop` and its tests contain substantive code. The plan’s “executed in full” banner is not accepted as independent proof of every acceptance condition: OPEN_ISSUES records unresolved map-network and other semantic/evidence items; the original ignored detailed review trail is absent.

## Safe roadmap baseline

Use separate status columns for scope implemented/merged, acceptance evidence, current defects, and superseded requirements. Preserve original and desktop numbering with explicit namespaces. Do not mark all packages complete or postpone news behind an assumed completed original sequence. Position the integrated news work only after identifying its actual reusable dependencies and unresolved repair obligations. A full requirement-by-requirement requalification remains beyond this repository-history audit.

## Verification performed

Recovered original roadmap; inspected first-parent and implementation histories; checked original file-ownership entries against the current tree; verified the table’s artifact content in introducing commits and current files; checked main ancestry; inspected acceptance suite code, current source entry points, decision/changelog records and open defects. An initial sandboxed root-unit invocation was stopped without a result (exit 143). A subsequent network-enabled execution completed: 779 existing root unit cases passed in 137.21s. Desktop unit/contract execution completed: 132 passed in 4.58s. These are separate bounded suite results, not cumulative completion evidence. VERIFICATION.md records exact commands and later document-guard validation. No full integration, acceptance, desktop suite or live-source run is claimed.

## Concrete examples beyond backend WP-10

- WP-11–13: `f4ad3c8` adds actual GLEIF, EUR-Lex and sanctions adapter code, not only roadmap entries.
- WP-26–27: `cce322d` adds composition/run/window implementations and integration tests (9 changed files).
- WP-32: `ef749e4` adds API application/dependencies/models/routes and tests (19 changed files).
- WP-39: `228d913` adds acceptance-suite fixtures and tests plus a plan-parser repair (30 changed files), merged by `1aa142f` on 2026-08-03.
- WP-25a: `10ef4b6` changes embeddings/loader/query implementations and adds unit/integration tests; its ancestry was separately checked.

These are sufficient to reject a repository-history cutoff at backend WP-10. They are not sufficient to grant blanket current acceptance.

PR preparation: the desktop archive normalizes two inherited space-before-tab recipe indentation lines; all other original body content is preserved after its archive notice. The backend archive preserves its original body exactly.
