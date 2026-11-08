# BE-56 — German parliamentary members and federal officeholders: implementation plan

Status: implementation candidate on `codex/be-56-german-parliament-members`,
from live-verified main `d967bae244dc` (2026-11-07). This session implements the
full A1–A8 contract; final qualification is recorded in [VERIFICATION](VERIFICATION.md).
D-97 preserves the planning decision; D-98 records implementation. Exact qualified
sources and public DIP authentication are in [BE56_SOURCES](BE56_SOURCES.md).
Production acquisition/deployment remains an operator action, separate from this
implementation and its dated fixtures.

Local implementation acceptance: A1–A6 and A8 have direct evidence. A7 remains
open: all static guards and five test lanes (1,397 tests) pass, but the final
runtime-stack lane exhausts this environment’s 8 GB filesystem. The Docker daemon
reports `no space left on device` creating its fixture volume. A larger filesystem
is required for a complete passing frozen candidate; see VERIFICATION. No full
acceptance or production-coverage claim is made.

## Goal and completion boundary

Make every serving member of the German Bundestag and all 16 state parliaments
available as a canonical `Person`, with evidence-backed parliamentary mandates,
the relevant parliament and legislative term, and supplied party/group information.
Also include every serving judge in the Bundesverfassungsgericht's First and
Second Senates, all regular and deputy Bundesrat members, and the serving
Bundespräsident or Bundespräsidentin. The court's two Senates are the intended
scope here; its smaller judicial Kammern are not two additional chambers.
This is the next person-coverage priority after company officers. Completing a
current DAX board roster is not a prerequisite.

Initial scope means serving members at an explicitly recorded acquisition/as-of
date in each chamber's then-current legislative term. Select terms at execution
time, not from today's hard-coded term numbers. Retain former members and source
history when encountered; exhaustive historical rosters, municipal councils
and the European Parliament are outside this package.
Berlin's Abgeordnetenhaus and the Bremen/Hamburg Bürgerschaften are included.

Deliver one full BE-56 package covering all 17 parliamentary chambers and the
additional federal officeholders above, including any required
API/desktop compatibility work. Internal steps below are not separate deliveries.
Implementation acceptance and actual deployed population are separate results:
all required source mappings and their qualification must work before calling the
package implemented; a nationwide loaded-roster claim additionally requires a
successful, dated acquisition and reconciliation report for every coverage scope:
the 17 parliamentary chambers, each of the two court Senates, the Bundesrat and
the federal presidency. These are 21 coverage scopes, not 21 parliaments.

## Baseline before BE-56 (live main d967bae244dc)

- `src/limes/sources/bundestag_dip.py` already fetches paginated DIP persons,
  archives responses and produces `Person`, `Office` and membership assertions.
  `bundestag_id` must remain compatible with existing canonical person IDs.
- Baseline DIP turned `fraktion` into `PoliticalParty` and links `Office` to that
  party, rather than to a parliamentary `PublicBody`. It uses known term starts
  for mandates without individual entry dates and leaves end dates open. Those
  records alone cannot establish current membership or correct party affiliation.
- `wikidata` is enrichment-only. Its name search is not a roster-discovery source
  or sufficient proof for joining a legislator to a similarly named company officer.
- The baseline had no all-state roster adapters or 17-chamber completeness contract.
  BE-56 extends ontology, loader, resolution and API together; implementation and
  operational handoff below supersede these baseline gaps.

## Source register and acquisition strategy

Use official parliamentary member directories and their structured exports/APIs
as primary roster evidence. Reuse DIP where its fields are sufficient and reconcile
it with the Bundestag's official current-member directory. For state parliaments,
prefer official machine-readable data; parse bounded official directory/profile
pages where no suitable export exists. Reuse transport/parsing components across
chambers with the same actual format, with explicit per-chamber mappings.

The portal table below remains the discovery index. Exact qualified directory,
AJAX/API/profile endpoints, pagination, identifiers, fields, term evidence,
usage references and raw fixture hashes are recorded in [the source matrix](BE56_SOURCES.md)
and its linked scope manifests. Public source/fixture qualification was performed
in this implementation session; no production graph was populated.

| Jurisdiction | Chamber | Official discovery portal |
|---|---|---|
| Federal | Deutscher Bundestag | https://www.bundestag.de/; existing DIP at https://search.dip.bundestag.de/ |
| Baden-Württemberg | Landtag von Baden-Württemberg | https://www.landtag-bw.de/ |
| Bayern | Bayerischer Landtag | https://www.bayern.landtag.de/ |
| Berlin | Abgeordnetenhaus von Berlin | https://www.parlament-berlin.de/ |
| Brandenburg | Landtag Brandenburg | https://www.landtag.brandenburg.de/ |
| Bremen | Bremische Bürgerschaft (state parliament) | https://www.bremische-buergerschaft.de/ |
| Hamburg | Hamburgische Bürgerschaft | https://www.hamburgische-buergerschaft.de/ |
| Hessen | Hessischer Landtag | https://hessischer-landtag.de/ |
| Mecklenburg-Vorpommern | Landtag Mecklenburg-Vorpommern | https://www.landtag-mv.de/ |
| Niedersachsen | Niedersächsischer Landtag | https://www.landtag-niedersachsen.de/ |
| Nordrhein-Westfalen | Landtag Nordrhein-Westfalen | https://www.landtag.nrw.de/ |
| Rheinland-Pfalz | Landtag Rheinland-Pfalz | https://www.landtag.rlp.de/ |
| Saarland | Landtag des Saarlandes | https://www.landtag-saar.de/ |
| Sachsen | Sächsischer Landtag | https://www.landtag.sachsen.de/ |
| Sachsen-Anhalt | Landtag von Sachsen-Anhalt | https://www.landtag.sachsen-anhalt.de/ |
| Schleswig-Holstein | Schleswig-Holsteinischer Landtag | https://www.landtag.ltsh.de/ |
| Thüringen | Thüringer Landtag | https://www.thueringer-landtag.de/ |
| Federal judiciary | Bundesverfassungsgericht — First Senate, all serving judges | https://www.bundesverfassungsgericht.de/ |
| Federal judiciary | Bundesverfassungsgericht — Second Senate, all serving judges | https://www.bundesverfassungsgericht.de/ |
| Federal | Bundesrat — regular and deputy members, distinguished explicitly | https://www.bundesrat.de/ |
| Federal | Bundespräsident/Bundespräsidentin — serving officeholder | https://www.bundespraesident.de/ |

Abgeordnetenwatch's public API may be assessed as a consolidated secondary source
or explicit fallback. Its coverage, terms, freshness, term filters and identity
links must be checked for all 17 chambers before selection; do not assume that
one provider covers all chambers. Record secondary provenance/trust separately.
Do not assume this API covers the court, Bundesrat or presidency; qualify their
official sources independently.
Provider selection and acquiring public fixtures are implementation work, not an
operator-supplied dataset prerequisite. An unavailable chamber stays a named
blocker rather than silently shrinking nationwide scope.

## Identity and graph contract

1. Namespace every external person ID by provider and chamber where IDs are local.
   Keep multiple external identifiers attached to one canonical `Person` through
   the shared resolution path. Preserve existing `bundestag_id` and canonical IDs;
   never replace or duplicate an existing DIP person simply to adopt a new key.
2. Reuse verified cross-source IDs/profile links or reviewed identity evidence.
   A shared name, party or biography keyword is insufficient to merge people.
   Support aliases, umlauts, name changes and title removal for matching while
   preserving official labels. Record ambiguous cross-source matches explicitly.
3. Represent each parliament as a `PublicBody` with a stable chamber identity and
   jurisdiction. Reify the parliamentary role/term as `Office`:
   `Person → HOLDS_OFFICE → Office → OFFICE_AT → PublicBody`. Scope office identity
   by chamber, role and legislative term, not a term number alone. Audit the
   current body-only deterministic lookup to prevent collapsing different terms.
   Individual mandate episodes belong to dated assertions; repeat entry must
   retain separate episodes instead of filling a gap in service.
4. Keep `PoliticalParty` and parliamentary group/Fraktion distinct. Introduce a
   chamber-and-term-scoped `ParliamentaryGroup` type and appropriate ontology
   relations if needed; freeze exact additive schema after inspecting fixtures.
   Store party membership only when explicitly sourced. A CDU/CSU group, a joint
   group, independent status or absence of group data never implies party identity.
5. Preserve supplied constituency/list mandate and role information without
   inventing missing fields. Public office identity, evidence and supplied mandate
   dates are required; unavailable constituency or party data remains unknown.
   Acquire public professional information needed for identity/mandates; private
   addresses and contact details are not roster requirements.
6. Version ontology, property validation, constraints, lookups, resolver, loader,
   API models and desktop mirrors together. Preserve old entity IDs and assertion
   history. Correct legacy DIP interpretation through a documented source-owned
   migration/supersession with retained evidence, not global deletion or retraction
   of unrelated sources. Prove idempotent migration and rollback compatibility.

## Additional federal officeholder contract

- **Bundesverfassungsgericht:** enumerate every serving judge separately for the
  First and Second Senates from official court membership/profile evidence. Keep
  the court and its Senate identities distinct and queryable, with judicial offices
  linked to the appropriate body. Preserve supplied appointment, service and
  Senate-assignment dates and leadership roles without duplicating the person.
  Do not treat a judicial appointment as an elected legislative mandate, infer
  party membership from an appointing body, or hard-code a nominal seat count as
  proof that the acquired current roster is complete.
- **Bundesrat:** enumerate regular members and deputy members (stellvertretende
  Mitglieder), retaining that distinction and the represented Land. Membership
  derives from state-government service, not an independently elected legislative
  term. Preserve source-provided membership/role dates; state-government membership
  alone does not establish Bundesrat membership. A Land's voting weight is not a
  person count. A person with several institutional roles remains one canonical
  Person with separate offices and evidence.
- **Federal presidency:** represent the serving Bundespräsident or Bundespräsidentin
  as a Person holding the presidential Office, with the relevant institutional
  PublicBody and source-provided tenure dates. Keep the office separate from its
  holder and preserve consecutive terms or future succession as dated episodes.
  A biographical list of former presidents does not establish the incumbent.

Extend the acquisition, migration, current/as-of queries, provenance and coverage
contracts below to all 21 scopes. Apply legislative-term/group fields only where
relevant; court and presidential appointments and Bundesrat service must not receive
fabricated parliamentary terms or party/group memberships. Archive original
official officeholder evidence and reconcile each Senate, Bundesrat member class
and presidential incumbent separately. An unavailable additional institution is
a full-package blocker just as an unavailable state parliament is.

## Time, evidence and coverage contract

- Archive original roster pages/exports and profile responses before normalization.
  Retain provider, chamber, term, source URL/ID, content hash, exact row/field/page
  locator, source update/as-of date where supplied, retrieval and graph recording
  times. Authentication headers/secrets never enter evidence URLs.
- Separate legislative-term boundaries, each person's actual mandate interval,
  and when current membership was observed. A term start is not an individual's
  entry date; acquisition time is not an appointment date. Preserve unknown dates
  and their basis in persistence and query responses.
- Current membership must use explicit current-roster evidence and its freshness;
  an old open-ended `HOLDS_OFFICE` assertion is not proof of current service. Do
  not fabricate resignation dates from missing rows or failed/partial snapshots.
  Preserve complete historical evidence and conflicts when later observations differ.
- Handle replacements, vacancies, resignations, deaths, party/group changes,
  election turnover and changed names. Source-provided dates close mandate episodes;
  roster changes without dates remain dated observations with unknown transition time.
- Report coverage separately for each chamber and term: expected official serving
  roster/count and its evidence, distinct acquired IDs, resolved/loaded persons,
  mandates, duplicates, unresolved matches, failed rows/pages, freshness, truncation
  and acquisition status. Nominal legal seat counts are not serving-member counts;
  they cannot establish completeness when vacancies or other seat rules apply.
- Reconcile the actual official member set, not just a matching count. Every row
  must map to a persisted person/mandate or a visible failure. Where an independent
  count/set is unavailable, record the weaker check and leave completeness unverified.
  A national total must distinguish mandate count from distinct-person count.
- Persist bounded, resumable progress by provider/chamber/term. Use finite page,
  byte, time and retry limits, cycle detection and explicit overflow. Failed or
  incomplete chamber acquisition cannot advance its successful coverage checkpoint.
  Completed chambers may remain usable while the national result reports partial.
  Changes during pagination require a stable snapshot/version or a bounded
  consistency recheck; never certify a mixed-time roster as one coherent snapshot.

## Implementation sequence and evidence contract

| Step | Concrete work | Exit evidence |
|---|---|---|
| 1. Re-entry and source qualification | Fetch live main, inspect local changes, create the proposed branch; validate and pin sources and raw fixtures for all 21 coverage scopes. Record current terms or office/service intervals as applicable, access/usage requirements and unavailable fields. | Completed source matrix for 17 parliamentary chambers, both court Senates, Bundesrat and presidency; exact fields, endpoint/fixture hashes and completeness method. |
| 2. Schema and migration | Design source-scoped IDs, parliament/term/mandate identities and group semantics; extend ontology/types/keys/constraints/loader/API as needed; specify DIP correction and current-membership observation semantics. | Versioned migration/design contract and meaningful collision/history regressions before adapter loading. |
| 3. Acquisition and normalization | Extend DIP and add official state roster, court, Bundesrat and presidency adapters/configuration with shared bounded transports/parsers; retain raw manifests and per-scope progress. | Every coverage scope's pinned fixture traverses acquisition/normalization; failures, profile joins and pagination limits stay explicit. |
| 4. Resolution and persistence | Join verified existing people, retain unresolved identities, load mandates/groups/evidence idempotently and apply compatible migrations. | Disposable graph proves existing DIP identity reuse, same-name separation, repeated office episodes, replay and source-isolated history. |
| 5. Operator and consumer integration | Register through composition and existing bounded operator jobs; expose chamber/term selection and coverage. Extend authenticated API/query coverage and generic desktop views/mirrors where necessary. | End-to-end API/desktop evidence navigation, current/as-of membership queries, coverage and partial/error states; consumer reads perform no acquisition. |
| 6. Qualification and handoff | Run affected/shared checks, then one full frozen candidate; update implementation status and provide explicit acquisition/deployment instructions. | Exact source manifest, acceptance mapping, remaining source blockers and separate local-versus-deployed coverage results. |

Likely touchpoints: `sources/bundestag_dip.py`, new state roster modules and chamber
configuration, `sources/registry.py`, `composition.py`, ontology/migrations,
resolution/lookups/loader, existing operational job models/worker/API, coverage,
desktop API mirrors and generic evidence/entity views. Reuse the three-service
runtime and shared structured channel. Deterministic roster parsing requires no
LLM extraction; it must not depend on a paid inference run to enumerate members.

Actual prerequisites are source-format/access qualification, frozen environment,
existing source/archive/resolver/loader/job/query contracts and disposable Neo4j
for persistence tests. Existing unrelated OSM/GDELT/operator issues remain tracked
but are not prerequisites for parliamentary implementation. Missing credentials
or inaccessible required rosters must identify the precise chamber and blocker.

## Acceptance checklist — one full BE-56 delivery

- [x] A1: All 21 coverage scopes have qualified current sources, exact raw fixtures
  and explicit completeness/freshness rules: 17 parliamentary chambers, both court
  Senates, Bundesrat regular/deputy members and the presidential incumbent.
  City-state parliaments are included; Bremen state and municipal membership are
  not confused. Legislative terms apply only to relevant institutions.
- [x] A2: Each acquired serving member persists as a `Person` with stable scoped
  identifiers, canonical reuse and an institution-appropriate mandate/office;
  judicial Senate, Bundesrat member class/Land and presidency are queryable; no silent row loss
  or name-only merging, including links to existing company-person entities.
- [x] A3: Parliament, office/term, mandate episode, party and parliamentary group
  semantics round-trip correctly; legacy DIP identity/history survives migration.
  Judicial appointments, Senate assignments, Bundesrat service and presidential
  tenure round-trip without fabricated legislative terms or party membership.
- [x] A4: Actual dates, unknown dates, current-roster observations, source evidence
  and both time axes survive archive→normalizer→resolver→graph→API; no false mandate
  start/end or inferred party membership is introduced.
- [x] A5: Per-chamber bounded acquisition, resume/replay, failure/checkpoint handling
  and idempotency work; a partial or changing roster cannot claim national completion.
- [x] A6: Per-chamber member-set reconciliation, counts, freshness, unresolved rows
  and missing coverage are visible through authenticated APIs and usable generic
  desktop evidence/query flows, including empty and failed cases.
- [ ] A7: Independent fixture cases cover all chamber mappings and distinct failure
  modes; disposable graph/API scenarios prove identity, migration and temporal
  updates. Affected/shared checks and one full frozen candidate pass, with exact
  results and source identity recorded in VERIFICATION.
- [x] A8: Documentation, configuration examples and operator handoff distinguish
  implemented acquisition capability from measured loaded coverage for all 21
  scopes; any unavailable required scope prevents an unqualified full-delivery claim.

Validation must include colliding local IDs, same-name people, Bundestag↔Landtag
transfers, cross-provider identity, unknown term/mandate dates, mid-term replacement,
independent/joint-group membership, chamber turnover, partial/empty pages, cursor
cycles, changed markup, inconsistent counts/member sets, and changing paginated
snapshots. Share invariant tests; add chamber-specific cases only for distinct
mapping behavior. Do not use fixed test quotas or cumulative passes as acceptance.
Also cover both Senate assignments, judicial replacement/leadership without person
duplication, Bundesrat regular versus deputy membership and represented Land,
state-government turnover, federal-presidential succession/repeated terms, and
one person holding roles across institutions. Do not mix Bundesrat vote totals
with member counts or infer judicial/presidential party affiliation.

## Implementation and operator handoff

The three-service runtime now registers `public_offices_SCOPE` for each of the
21 scope codes in [the source matrix](BE56_SOURCES.md). Use the existing authenticated
operator job `ingest` with one such source; `ingest-all` includes them. No consumer
read performs acquisition. Each job archives original pages before parsing, retains
bounded per-source progress, performs an independent semantic consistency recheck,
and leaves success unchanged on parse/transport/count/cycle/load failures. Bounds
are 512 directory pages per pass, 5 MB per response, 40 MB per pass, a 1,800-second
scheduling budget and the shared finite four-attempt transport policy; an outstanding
bounded retry/cooldown can finish after that scheduling budget. Federal profile
joins share the total read/byte/time bounds. Explicit resubmission resumes progress;
interrupted work is not automatically replayed. Completed scopes remain usable.

Ontology 1.4.0 adds `ParliamentaryGroup`, `PersonIdentifier`, `RosterSnapshot` and
`RosterMembership`, compound office/institution identifiers and additive relations.
`HOLDS_OFFICE` roster edges have `validity_basis=roster_observation`; their validity
start is an observation, not an invented mandate start. Source service dates,
precision, profile episodes, original evidence and graph recording/belief times
remain distinct. Snapshot membership distinguishes serving rows from encountered
former-member episodes. Absence never invents an exit date or fills a service gap.
A `RosterLoadCheck` associates successful loading with the actual run, including
successful replay after an earlier failed load of the same immutable snapshot.

Before production acquisition, back up the graph/archive and run the explicit
operator migration `migrate --version 1.4.0` through the remote CLI/job API.
The additive version has a declared source-owned data repair: it runs even if
other nodes are already stamped 1.4.0. It preserves legacy person/office IDs and
raw history, adds the proper compound office keys and supersedes only legacy DIP
party/body/current-interval interpretations. DIP now emits historical term/group
references without inventing personal service dates. The source-isolated migration
is replayable; its rollback restores only its own retractions/added keys. Running
an older binary after new 1.4.0 entities exist requires restoring the pre-migration
backup, because the downgrade guard remains in force.

Configure `LIMES_BUNDESTAG_DIP_API_KEY` from the [validated public source](BE56_SOURCES.md)
when using DIP. Update existing operator settings to
`LIMES_NL2CYPHER_PROMPT_VERSION=1.1.0`; the new default/example has roster-aware
current/as-of guidance while the historical 1.0.0 prompt remains unchanged.
Do not infer serving membership from an old open-ended assertion.

`GET /public-offices` returns all 21 coverage scopes and a bounded member response.
Filters are `scope`, `term`, timezone-aware `as_of`, `believed`, `limit` (1–1000)
and `include_members=false` for coverage-only reads. It exposes missing/failed/
partial/unverified/reconciled states, actual-set reconciliation, observation age,
unknown/source dates, unresolved candidates, source conflicts and truncation.
An as-of date before any acquired observation remains missing rather than
extrapolating a retrospective complete roster. Canonical identity reviews are
belief-sensitive. Historical raw assertions and original entity IDs remain intact.

The desktop's existing Coverage panel has an asynchronous **Public office coverage**
read, with error/empty/partial states and navigation to generic snapshot/entity/
evidence views. A connection change rejects late replies. Ontology-driven query
and evidence flows expose office, group, Land/member-class, Senate and presidency
properties without desktop ontology constants or direct provider/database access.

If a source identifier has an unresolved candidate, inspect the archived evidence
and the existing person before submitting the bounded operator command
`public-offices-identify --identity-reviews JSON` (also available through
`remote run public-offices-identify`). Each of up to 100 explicit decisions carries
`request_id`, acquired `external_id`, existing `person_id`, archived `evidence_hash`
and a review `note`. The job verifies archive existence; the loader transaction
retains immutable audit decisions and prior bindings. Reusing a decision ID with
changed content is rejected. Reads and future loading reuse the reviewed canonical
person; a shared name, group or biography keyword never authorizes a merge.

Local validation/acceptance and exact source fingerprints are recorded in
[VERIFICATION](VERIFICATION.md). Production population requires a separately
successful dated acquisition/reconciliation for every scope; unverified or missing
coverage is not converted into a nationwide loaded-roster claim. Existing unrelated
operator obligations remain tracked in OPEN_ISSUES. The subsequent PR request
authorizes staging, commit, push and a draft PR for this full implementation. A7
remains open; merge, deployment and production data runs remain separate actions.
