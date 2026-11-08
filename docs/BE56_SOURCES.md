# BE-56 source qualification

Qualification began on 2026-11-07 against live main `d967bae244dc`.
Exact original responses, retrieval times, URLs and SHA-256 hashes are pinned
under `tests/fixtures/public_offices/`; gzip files decompress to the original
bytes. These are implementation fixtures, not production ingestion evidence.

## Public DIP authentication

A publicly published, currently valid DIP API key was located at
[the public DIP API reference](https://gist.github.com/tilllt/fabbcbb0a53a2d72410ddb0bd256a05c).
That source advertises validity through May 2027. Live validation on 2026-11-07
returned HTTP 200 from the official
[person endpoint](https://search.dip.bundestag.de/api/v1/person?f.wahlperiode=21&format=json),
using the key in `Authorization: ApiKey …`, with a well-formed JSON response
reporting 840 historical/current person records for the selected period.
The period's person records are not a serving-member roster.
The initial unauthenticated 401 was an authentication result, not evidence that
DIP access or a public key was unavailable.

[Official DIP API help](https://dip.bundestag.de/%C3%BCber-dip/hilfe/api) and
[the official OpenAPI interface](https://search.dip.bundestag.de/api/v1/swagger-ui/)
are the authority for authentication and endpoint semantics. The public-reference
expiry is a publisher statement; successful validation establishes that the key
worked on the dated check, not that it cannot be revoked sooner. Retrieve a fresh
published key at expiry and revalidate. Configure `LIMES_BUNDESTAG_DIP_API_KEY`
for runtime DIP acquisition. Authentication belongs in headers, never archived
source URLs. No operator credential file was read or modified during qualification.

## Exact mappings and fixtures

The manifest links below contain exact directory, AJAX/export/API and profile
URLs, retrieval times, SHA-256 hashes, secondary term metadata and published
usage references. Original payloads are gzip-compressed without alteration.
The catalogue starts at stable official directory URLs and discovers the
execution-time API endpoints/terms; it does not freeze today's term numbers.
Fixture counts below describe dated evidence, not a deployed population or
independent legal seat quotas. Bundesrat vote weights are never member counts.

| Scope | Institution | Format / completion path | Fixture serving IDs | Evidence |
|---|---|---|---:|---|
| `bb` | Landtag Brandenburg | HTML table with published count | 88 | [bb.json](../tests/fixtures/public_offices/bb.json) |
| `be` | Abgeordnetenhaus von Berlin | HTML alphabetic directory | 153 | [be.json](../tests/fixtures/public_offices/be.json) |
| `bp` | Bundespräsidialamt | Official incumbent link + current biography | 1 | [bp.json](../tests/fixtures/public_offices/bp.json) |
| `br` | Bundesrat | 16 official Land directories, both classes + individual profiles | 180 | [br.json](../tests/fixtures/public_offices/br.json) |
| `bt` | Deutscher Bundestag | HTML AJAX + dated departure/replacement table | 630 | [bt.json](../tests/fixtures/public_offices/bt.json) |
| `bverfg_1` | Bundesverfassungsgericht — Erster Senat | Official Senate directory + individual judicial profiles | 8 | [bverfg_1.json](../tests/fixtures/public_offices/bverfg_1.json) |
| `bverfg_2` | Bundesverfassungsgericht — Zweiter Senat | Official Senate directory + individual judicial profiles | 8 | [bverfg_2.json](../tests/fixtures/public_offices/bverfg_2.json) |
| `bw` | Landtag von Baden-Württemberg | HTML AJAX + result-count metadata | 157 | [bw.json](../tests/fixtures/public_offices/bw.json) |
| `by` | Bayerischer Landtag | HTML forward pagination | 202 | [by.json](../tests/fixtures/public_offices/by.json) |
| `hb` | Bremische Bürgerschaft (Landtag) | Official temporary static HTML directory | 87 | [hb.json](../tests/fixtures/public_offices/hb.json) |
| `he` | Hessischer Landtag | HTML member cards | 133 | [he.json](../tests/fixtures/public_offices/he.json) |
| `hh` | Hamburgische Bürgerschaft | HTML group sections/member cards | 121 | [hh.json](../tests/fixtures/public_offices/hh.json) |
| `mv` | Landtag Mecklenburg-Vorpommern | HTML searchable cards | 71 | [mv.json](../tests/fixtures/public_offices/mv.json) |
| `ni` | Niedersächsischer Landtag | HTML alphabet partitions; exclude explicit non-mandate ministers | 146 | [ni.json](../tests/fixtures/public_offices/ni.json) |
| `nw` | Landtag Nordrhein-Westfalen | HTML member table | 195 | [nw.json](../tests/fixtures/public_offices/nw.json) |
| `rp` | Landtag Rheinland-Pfalz | Official JSON API discovered from current-period component | 105 | [rp.json](../tests/fixtures/public_offices/rp.json) |
| `sh` | Schleswig-Holsteinischer Landtag | HTML list with two official profile systems | 69 | [sh.json](../tests/fixtures/public_offices/sh.json) |
| `sl` | Landtag des Saarlandes | HTML profile cards | 49 | [sl.json](../tests/fixtures/public_offices/sl.json) |
| `sn` | Sächsischer Landtag | HTML alphabetical cards | 120 | [sn.json](../tests/fixtures/public_offices/sn.json) |
| `st` | Landtag von Sachsen-Anhalt | HTML directory with published count | 83 | [st.json](../tests/fixtures/public_offices/st.json) |
| `th` | Thüringer Landtag | HTML directory with duplicate presentation views | 88 | [th.json](../tests/fixtures/public_offices/th.json) |

All 17 parliamentary scopes have pinned current legislative-period metadata.
Explicit official term labels are preferred; otherwise the separately attributed,
CC0 Abgeordnetenwatch parliament/current-project/legislature response qualifies
the term. Election projects, future starts, missing fields and wrong-parliament
periods fail closed. Abgeordnetenwatch does not enumerate judicial, Bundesrat or
presidential rosters. The first parallel metadata probe encountered HTTP 429;
qualification was completed with paced requests and the shared retry policy.

Official identifiers use provider/scope namespaces. Numeric biography/member
keys are retained where exposed (including Bundestag, Brandenburg, Bremen,
Hamburg, NRW, Sachsen and Schleswig-Holstein's database links). Other official
profile URIs remain scoped identifiers. A renamed URI or Senate/term transfer
without a verified cross-ID remains a visible identity candidate, not a guessed
merge. Exact DIP identifiers and audited evidence-backed reviews can reuse an
existing canonical person, including a company officer. The live DIP fixture
also demonstrates supplied name history and source-update timestamps.

## Fields, freshness and completeness

Every mapping preserves the official label, external identifier, institution,
role, profile URL, original-page hash and exact row/element locator. Supplied
constituency/group fields are retained; a parliamentary group is not a party.
Bundesrat's explicitly labelled party affiliation remains a label rather than an
invented party-membership assertion. Judicial/presidential party membership is
not inferred. Missing fields remain unknown. Judicial leadership uses distinct
offices on the same person; the appropriate Senate and parent court remain separate.

Bundestag's bulk response contains 639 biographies in this fixture. The official
21st-period departure table identifies nine former members and dated replacements;
630 serving IDs remain. Former-member endpoints/dates and the published name-change
aliases remain historical evidence. These numbers are fixture observations.
Niedersachsen also lists ministers explicitly marked without a Landtag mandate;
they are excluded from the serving parliamentary set. Schleswig-Holstein includes
one profile on a different official portal; neither that member nor city-state
members are silently dropped.

Profiles preserve supplied judicial appointment/leadership statements and Bundesrat
service episodes, including month-only dates without invented days. The presidency
biography distinguishes election/re-election from service starts: election dates
are retained as election evidence and never converted to appointment dates.
Rheinland-Pfalz's `datejoined` is preserved at day precision; its timezone-free
`dateupdated` remains source text. Original source responses remain available.
Bremen's linked dated CSV export is retained as a source-update note; it does not
establish a publication timestamp for the HTML directory. Observation age and
provider publication age are distinct; absent provider update times stay unknown.

Directory sets are reconciled against persisted IDs, not only numerical totals.
Where the official source exposes a serving count, count and set must reconcile.
Where no independent count/set is available, the API says **unverified**, even
after successful acquisition/loading. No legal seat count substitutes for an
actual serving set. Each Bundesrat Land and member class is traversed; court
Senates are checked separately. A double semantic read detects changing snapshots.
A missing/failed/unresolved/stale/unverified scope prevents a reconciled national
coverage result. Response truncation is separate from persisted coverage.

## Access, attribution and retention

Roster/profile acquisition uses public HTTPS GETs without operator credentials;
DIP additionally uses its documented API-key header. Every manifest retains the
issuer and the usage/imprint references exposed by the source navigation, with
dated original responses where available. Some links govern media or a particular
publication; those are not a blanket licence for roster reuse. No blanket open
HTML/photo licence is assumed. Preserve institutional attribution, source URL and
dates. Binary photographs are not acquired. Normalization selects public
professional/mandate fields; private contact fields are not graph properties.
The original official response is retained as the evidence archive requires.
