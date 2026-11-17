"""BE-59 recht.nrw.de interface: sitemap discovery, one page per law, history mapping."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
import respx

from limes.errors import SourceParseError
from limes.ontology.registry import load_ontology
from limes.ontology.validator import validate_assertions
from limes.sources import recht_nrw
from limes.sources.recht_nrw import SITEMAP_URL, RechtNrwAdapter
from limes.types import RawRecord

FIXTURES = Path(__file__).parents[1] / "fixtures" / "recht_nrw"
NOW = datetime(2026, 11, 17, 12, tzinfo=UTC)
BASE = "https://recht.nrw.de/lrgv/"
ABGG_SLUG = "gesetz-ueber-die-rechtsverhaeltnisse-der-mitglieder-des-landtags-nordrhein/"
AFOG_SLUG = "gesetz-zur-errichtung-eines-fonds-fuer-die-beteiligung-des-landes-nordrhein/"
ABGG = BASE + "gesetz/31012004-" + ABGG_SLUG
AFOG = BASE + "gesetz/01012025-" + AFOG_SLUG
AFOG_OLD = BASE + "gesetz/18102008-" + AFOG_SLUG
VO = (BASE + "rechtsverordnung/01012024-"
      "verordnung-ueber-die-entschaedigung-der-mitglieder-kommunaler/")


def page(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def law(name: str, url: str) -> RawRecord:
    return RawRecord(payload=page(name), content_type="text/html", source_url=url, fetched_at=NOW)


def routes(afog: bytes | None = None):
    respx.get(SITEMAP_URL).respond(200, content=page("sitemap.xml"))
    respx.get("https://recht.nrw.de/sitemap/page/1/sitemap.xml").respond(
        200, content=page("sitemap_page.xml"))
    respx.get(ABGG).respond(200, content=page("gesetz_2004_pdf.html"))
    respx.get(AFOG).respond(200, content=afog or page("gesetz_2025.html"))
    respx.get(AFOG_OLD).respond(200, content=page("gesetz_2025.html"))
    respx.get(VO).respond(200, content=page("verordnung_2024.html"))


def test_sitemap_discovery_fetches_one_newest_page_per_law(monkeypatch):
    monkeypatch.setattr(recht_nrw, "MIN_INTERVAL_SECONDS", 0)
    with respx.mock:
        routes()
        records = list(RechtNrwAdapter().fetch(None, None))
        requested = [str(call.request.url) for call in respx.calls]
    # Two sitemap documents (archived), then exactly one page per act; the
    # announcement and every older version listed on a fetched page are skipped.
    assert [r.acquisition_context.get("archive_only") for r in records[:2]] == [True, True]
    assert sorted(requested[2:]) == sorted([ABGG, AFOG, VO])
    assert all(r.source_url in (ABGG, AFOG, VO) for r in records[2:])


def test_an_unlisted_older_version_is_fetched_until_the_group_is_covered(monkeypatch):
    monkeypatch.setattr(recht_nrw, "MIN_INTERVAL_SECONDS", 0)
    stripped = page("gesetz_2025.html").replace(b"18102008-gesetz", b"18102099-gesetz")
    with respx.mock:
        routes(afog=stripped)
        list(RechtNrwAdapter().fetch(None, None))
        requested = [str(call.request.url) for call in respx.calls]
    assert AFOG_OLD in requested


def test_change_history_maps_adoption_amendments_and_own_citation():
    ontology = load_ontology(Path("ontology/ontology.yaml"))
    abgg = RechtNrwAdapter().normalize(law("gesetz_2004_pdf.html", ABGG))
    accepted, rejected = validate_assertions(abgg.assertions, ontology)
    assert not rejected
    adopted = [a for a in accepted if a.relation == "ADOPTED"]
    assert [(a.subject.entity_id, a.validity.valid_from) for a in adopted] == [
        ("institution_id:DE:nw", datetime(1979, 4, 24, tzinfo=UTC))]
    amendments = {(a.subject.entity_id, a.validity.valid_from.date().isoformat())
                  for a in accepted if a.relation == "AMENDS"}
    assert ("bgb_citation:GV. NRW. 2004 S. 30", "2004-01-27") in amendments
    assert ("bgb_citation:GV. NRW. 2000 S. 754", "2000-12-12") in amendments
    # An amending act's citation never becomes the amended law's own identity.
    target = adopted[0].object
    assert target.entity_id.startswith("legal-act-recht-nrw:") and target.deterministic_key is None
    assert all(a.object.entity_id == target.entity_id for a in accepted if a.relation == "AMENDS")

    afog = RechtNrwAdapter().normalize(law("gesetz_2025.html", AFOG))
    assert {(a.subject.entity_id, a.relation) for a in afog.assertions} == {
        ("institution_id:DE:nw", "ADOPTED"),
        ("bgb_citation:GV. NRW. 2024 S. 1220", "AMENDS"),
    }


def test_ordinance_uses_its_linked_promulgation_and_counts_unlinked_repeal():
    result = RechtNrwAdapter().normalize(law("verordnung_2024.html", VO))
    assert not result.assertions  # no ADOPTED for ordinances; repeal is unlinked
    assert [(e.entity_id, e.deterministic_key) for e in result.entities] == [
        ("bgb_citation:GV. NRW. 2024 S. 1140", ("bgb_citation", "GV. NRW. 2024 S. 1140"))]
    assert result.entities[0].label.startswith("Verordnung über die Entschädigung")


def test_non_law_pages_fail_loudly():
    with pytest.raises(SourceParseError):
        RechtNrwAdapter().normalize(law("gesetz_2025.html", "https://recht.nrw.de/impressum/"))
    with pytest.raises(SourceParseError):
        RechtNrwAdapter().normalize(RawRecord(payload=b"<html><main></main></html>",
                                              content_type="text/html", source_url=AFOG,
                                              fetched_at=NOW))
