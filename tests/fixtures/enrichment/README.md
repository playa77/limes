# BE-46 independent source fixtures

Retrieved read-only on 2026-10-29 before schema implementation. Wikipedia Action
API `query`, `prop=revisions|pageprops`, `rvprop=ids|timestamp|content`,
`rvslots=main`, titles=Siemens, languages DE/EN. DE page 2679650 revision
271660062 (2026-10-27); EN page 168632 revision 1381981748 (2026-10-25).
Both pageprops identify Q81230. Original responses, including attribution/history
links implicit in revision identity, are unchanged. Text is wikitext, not rendered
plain prose. Wikipedia text is CC BY-SA 4.0; authors/history:
https://de.wikipedia.org/w/index.php?title=Siemens&action=history and
https://en.wikipedia.org/w/index.php?title=Siemens&action=history . License:
https://creativecommons.org/licenses/by-sa/4.0/ .

Yahoo quoteSummary responses fetched through yfinance 1.7.0's authenticated
read-only transport. Modules: price, assetProfile, institutionOwnership,
fundOwnership, majorHoldersBreakdown, calendarEvents, secFilings. SIE.DE and SIEGY
are different listings/instruments of Siemens; BMW.DE common versus BMW3.DE
preference (404, not assumed equivalent); ASML.AS supplies a Dutch issuer and
non-German holder names. LIMES_UNLISTED returned 404. QuoteSummary without the
transport cookie/crumb returned 401. No failed response is a zero-holdings result.
Raw integer/ratio/date expectations in tests derive from these responses, not
from adapter output. Missing majorDirectHolders/board/filings are unknown.

Access/retention review: yfinance's pinned README says research/education and
personal use only; its software license grants no Yahoo data rights. Reviewed
https://legal.yahoo.com/us/en/yahoo/terms/product-atos/apiforydn/index.html
(including user-data retention restrictions, not a perpetual financial-data
redistribution license). This is bounded private research format evidence, not
commercial-use or production-retention qualification. No public redistribution,
licensed completeness or historical reconstruction is claimed. Wikipedia's
foundation terms endpoint returned 403; attribution/license follows the published
CC BY-SA link above and must accompany exported context. Original payloads belong
to their respective providers. No paid inference or production ingestion occurred.

Additional bounded transport checks retained Yahoo price-only VOW.DE and VOW3.DE
responses (XETRA/GER) for ordinary and preference shares. Reviewed mapping test
inputs use VW investor-relations ISINs DE0007664005 and DE0007664039; the parser
must preserve separate securities/listings linked to one company. These ISINs are
operator mapping evidence, not fields purportedly supplied by Yahoo price.
Source: https://www.volkswagen-group.com/en/share-information-15951 .

Country-scope qualification uses an unchanged English Germany response, page
11867 revision 1381631157, Q183, collected through the actual bounded MediaWiki
transport. Attribution: Wikipedia contributors, Germany; history:
https://en.wikipedia.org/w/index.php?title=Germany&action=history . CC BY-SA 4.0
applies as above. The compressed HTTP response exposed the shared transport's
old double-decode bug; shared regression coverage now checks gzip decoding once
and enforces the decompressed byte bound. This is a bounded read-only probe.
