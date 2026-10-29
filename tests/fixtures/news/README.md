# BE-43 news fixtures

`discovery.xml` preserves the first two item elements and channel metadata of a
public Google News RSS response fetched read-only on 2026-10-28 from
https://news.google.com/rss/search?q=Bundestag&hl=de&gl=DE&ceid=DE%3Ade .
Full original response: 53,216 bytes, SHA-256
`af652041659624a12471be06146992d3b6273a02a7bc1cc35527fda8212e528d`.
The original is retained locally under ignored work/be43/discovery.xml.
The transport needed `Accept-Encoding: identity` in the managed proxy environment.
These are index headlines/snippets and publisher links, not licensed agency full
text. Source terms and publisher copyright remain applicable; no right to scrape
or redistribute linked articles is inferred. Automated tests never fetch publishers.

`behavior.json` is an independently authored, synthetic bilingual behavior fixture.
Expected modality/lifecycle/precision/attribution labels were written from its
sentences, independently of the extractor output. It is regression evidence, not
a representative quality score. Acquired documents enter an unreviewed evaluation
pool; operator annotations can grow that pool during investigations. Paid model
quality measurement remains a separately requested operator run.
