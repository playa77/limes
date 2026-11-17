# BE-60–BE-62 — NRW entity expansion

Recorded 2026-11-17 (D-110) on branch `claude/trusting-mendel-j3aiz6`, live base
`6aae817063a7`. BE-59 ([NRW scope](NRW_SCOPE.md)) fixed the geographic scope and
source set; it excluded municipal councils and left several categories of NRW
power-holders unmodelled. The user split the follow-up into three parent work
packages. Each is delivered as one complete package on its own branch and PR.
**Status of all three: planned, not started.** Nothing below is implemented,
and no source listed here is registered.

All three inherit BE-59's rules unchanged: NRW selected at the source, the
2020-01-01 inclusive acquisition floor with original dates preserved, bitemporal
assertions, ontology as the single type source, and no live calls in tests.
Every new source requires the user's explicit approval before it is registered
(AGENTS.md source scope); naming a candidate here is not that approval.

## BE-60 — Officeholders: municipal government and Landesregierung

**Scope.**

- Landesregierung NRW: Ministerpräsident, ministers, Staatssekretäre, with the
  ministries as `PublicBody` nodes (today's rosters cover only Landtag, NRW
  Bundestag and NRW Bundesrat members).
- Every NRW Großstadt (≥100,000 inhabitants by IT.NRW population figures; the
  city list is owned by `limes.geo_scope`, not restated by adapters):
  Oberbürgermeister; the honorary Bürgermeister (OB deputies elected by the Rat);
  the Verwaltungsvorstand (Beigeordnete, Stadtdirektor, Kämmerer); the Rat with
  members, Fraktionen and committees; Bezirksvertretungen and
  Bezirksbürgermeister.
- Both council terms inside the window: the 2020 and the September 2025
  Kommunalwahl, as dated memberships.

**Candidate sources (approval pending).** OParl endpoints of the cities'
Ratsinformationssysteme where offered; official city pages where not; IT.NRW
municipal election results; the Landesregierung's official cabinet pages.

**Decisions required before coding.** Source approval per city/channel; how a
city without OParl is covered; whether Kreise/Landräte and Regierungsbezirke join
this package or remain out of scope.

## BE-61 — Ownership and boards: city and state holdings, corporate boards

**Scope.**

- City holdings of each Großstadt: Stadtwerke, transport, housing, Messe/airport
  and other companies, with ownership shares and Aufsichtsrat seats (including
  council members sent by the Rat), and the city's Sparkasse with its
  Verwaltungsrat.
- State holdings: the Land's Beteiligungen (for example NRW.BANK, BLB NRW,
  Unikliniken) with ownership and board seats.
- Corporate boards of large NRW companies: Vorstand/Geschäftsführung and
  Aufsichtsrat.
- Ontology changes, each with migration and its own decision record:
  executive versus supervisory board roles; offices at `InterestGroup`
  (Vorstand, Kuratorium, Präsidium of foundations and Vereine); a
  delegation/nomination relation (who sent a member to a board); `OPERATES`
  for `InterestGroup`. Funding and founder relations are considered here and
  added only if a BE-61 or BE-62 source populates them.

**Candidate sources (approval pending).** The cities' mandatory
Beteiligungsberichte (§117 GO NRW, mostly PDF); the Land's Beteiligungsbericht;
company governance reports and Wikidata board properties. Automated bulk
retrieval from handelsregister.de is excluded by its terms of use.

**Decisions required before coding.** The threshold for a "large" company
(employees, revenue, index membership); source approvals; the final relation
names and cardinalities.

## BE-62 — Civil society: media, churches, Kammern, foundations, sport, culture

**Scope.**

- Media: WDR (Intendant, directors, Rundfunkrat and Verwaltungsrat with the
  delegating organisations, subsidiaries such as WDR mediagroup, ensembles) and
  the ARD/ZDF/Deutschlandradio Beitragsservice in Köln; Deutschlandradio,
  Deutsche Welle, Landesanstalt für Medien NRW, the NRW local-radio
  Veranstaltergemeinschaften; large private media groups.
- Churches and welfare: Erzbistum/Bistümer and Landeskirchen in NRW; Caritas,
  Diakonie, AWO, DRK, Paritätischer.
- Kammern and social partners: IHKs, Handwerkskammern, professional chambers;
  unions and employer associations.
- Foundations and large Vereine, including the party foundations headquartered
  in NRW.
- Sport: large clubs as e.V. and their spun-off companies, stadium operators,
  Landessportbund and the regional football associations.
- Culture: opera houses, theatres, concert halls and museums with their
  operating bodies (gGmbH, Eigenbetrieb, Stiftung) and holding companies or
  foundations, including LVR/LWL cultural institutions.
- Fix `wikidata_nrw` to follow subclasses (`P31/P279*`) of its organisation
  classes and add the classes this scope needs, within its row bound.

**Candidate sources (approval pending).** `wikidata_nrw` (already registered;
its query change is in scope); official pages of WDR and the named bodies.

**Decisions required before coding.** Thresholds for "large" Vereine,
foundations and clubs; which categories in this list stay in; source approvals;
whether water associations (Ruhrverband, Emschergenossenschaft, Lippeverband)
and universities belong here.

## Order and dependencies

BE-61's ontology changes are a prerequisite for the board parts of BE-62
(foundation and Verein boards, WDR bodies). BE-60 has no dependency on either
and is the recommended first package. The user has not yet fixed the order.
