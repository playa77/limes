"""BE-46 distinct provenance, identity, availability and quantity regressions."""

import json
from datetime import timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from limes.enrichment.models import EnrichmentSelection
from limes.enrichment.service import prepare_targets
from limes.errors import LimesError, SourceFetchError, SourceParseError
from limes.graph.loader import _entity_properties
from limes.operations.models import JobRequest
from limes.sources.registry import build_default_registry
from limes.sources.wikipedia import WikipediaAdapter
from limes.sources.yahoo_finance import MODULES, YahooFinanceAdapter
from tests.fixtures.enrichment_data import altered_record, record, target
from tests.fixtures.graph_data import load_ontology_artifact


def observations(normalized):
    return [e.properties for e in normalized.entities if e.type == "EnrichmentObservation"]


@pytest.mark.parametrize(
    "language,page,revision", [("de", 2679650, 271660062), ("en", 168632, 1381981748)]
)
def test_wikipedia_original_revision_context_and_qualified_document(language, page, revision):
    adapter = WikipediaAdapter()
    raw = record("wikipedia", language, language=language)
    output = adapter.normalize(raw)
    context = observations(output)[0]
    assert context["page_id"] == page and context["revision_id"] == revision
    assert context["wikidata_qid"] == "Q81230"
    assert "creativecommons.org/licenses/by-sa/4.0" in context["license_url"]
    assert context["text_format"] == "wikitext" and context["body"]
    assert output.document is None  # Context does not depend on inference output.
    adapter.configure([target()], extract=True)
    doc = adapter.normalize(raw).document
    assert doc.body == context["body"]
    assert doc.news_metadata["revision_id"] == revision
    assert f"oldid={revision}" in doc.url
    replay = adapter.normalize(
        raw.model_copy(update={"fetched_at": raw.fetched_at + timedelta(days=1)})
    )
    assert replay.entities[0].entity_id == output.entities[0].entity_id
    # Non-revision MediaWiki metadata cannot invent a new text version.
    changed = json.loads(raw.payload)
    changed["query"]["pages"][str(page)]["pageprops"]["unrelated"] = "changed"
    variant = adapter.normalize(raw.model_copy(update={"payload": json.dumps(changed).encode()}))
    assert variant.entities[0].entity_id == output.entities[0].entity_id


@pytest.mark.parametrize("change", ["missing", "disambiguation", "wrong_qid", "multiple"])
def test_wikipedia_never_guesses_pages(change):
    raw = record("wikipedia", "de")
    data = json.loads(raw.payload)
    page = next(iter(data["query"]["pages"].values()))
    if change == "missing":
        page["missing"] = ""
    elif change == "disambiguation":
        page["pageprops"]["disambiguation"] = ""
    elif change == "wrong_qid":
        page["pageprops"]["wikibase_item"] = "Q1"
    else:
        data["query"]["pages"]["another"] = page
    raw.payload = json.dumps(data).encode()
    output = WikipediaAdapter().normalize(raw)
    assert not observations(output) and output.document is None
    assert output.entities[0].properties["status"] in ("missing", "ambiguous")


def test_wikipedia_sitelinks_and_transport_partial_failure(monkeypatch):
    adapter = WikipediaAdapter()
    adapter.configure([target()])
    payload = record("wikipedia", "de").payload
    monkeypatch.setattr(
        adapter,
        "_get",
        Mock(
            side_effect=[
                b'{"entities":{"Q81230":{"id":"Q81230","sitelinks":{"dewiki":{"title":"Siemens"}}}}}',
                payload,
            ]
        ),
    )
    records = list(adapter.fetch(None, None))
    assert len(records) == 3
    assert records[1].payload == payload
    assert records[2].acquisition_context["status"] == "missing"
    assert records[2].acquisition_context["language"] == "en"


def test_yahoo_independent_holdings_units_and_unknown_currency():
    output = YahooFinanceAdapter().normalize(record())
    row = observations(output)[0]
    assert row["name"] == "Generali Investments Cee, Investicni Spolecnost, A.s."
    assert row["shares"] == 53457 and row["ratio"] == 0.0001
    assert row["value"] == 14436062 and row["currency"] is None
    assert row["ratio_basis"] == "unknown" and row["ratio_unit"] == "fraction"
    assert row["source_as_of"].isoformat() == "2026-09-30T00:00:00+00:00"
    assert row["identity_status"] == "unresolved" and row["overlap_policy"] == "do_not_sum"
    assert row["evidence_field"] == "institutionOwnership.ownershipList[0]"
    assert row["complete"] is False
    aggregate = observations(
        YahooFinanceAdapter().normalize(record(section="majorHoldersBreakdown"))
    )
    assert {r["name"]: r["ratio"] for r in aggregate} == {
        "insidersPercentHeld": 0.06004,
        "institutionsPercentHeld": 0.46365002,
        "institutionsFloatPercentHeld": 0.49326,
    }
    assert (
        next(r for r in aggregate if r["name"] == "institutionsFloatPercentHeld")["ratio_basis"]
        == "float"
    )
    assert all(r["kind"] == "aggregate_ratio" for r in aggregate)


def test_calendar_estimates_are_not_reports_and_officers_are_not_complete_board():
    adapter = YahooFinanceAdapter()
    raw = altered_record(
        "calendarEvents",
        {"earnings": {"earningsDate": [1794501000], "isEarningsDateEstimate": True}},
    )
    calendar = observations(adapter.normalize(raw))[0]
    assert calendar["event_status"] == "estimated" and calendar["publication_date"] is None
    assert calendar["report_kind"] is None
    officer = observations(
        adapter.normalize(
            altered_record(
                "assetProfile",
                {
                    "companyOfficers": [
                        {"name": "Officer Example", "title": "Chief Executive Officer"}
                    ]
                },
            )
        )
    )[1]
    assert officer["role_title"] == "Chief Executive Officer"
    assert officer["body"] is None and officer["term_start"] is None
    assert officer["role_kind"] == "executive"
    supervisory = observations(
        adapter.normalize(
            altered_record(
                "assetProfile",
                {
                    "companyOfficers": [
                        {"name": "Example Person", "title": "Chair of the Supervisory Board"}
                    ]
                },
            )
        )
    )[1]
    assert supervisory["role_kind"] == "supervisory" and supervisory["body"] == "supervisory_board"
    assert supervisory["term_start"] is None and supervisory["complete"] is False
    filing = observations(
        adapter.normalize(
            altered_record(
                "secFilings",
                {
                    "filings": [
                        {
                            "type": "20-F",
                            "date": "2026-02-01",
                            "edgarUrl": "https://www.sec.gov/test",
                            "fiscalPeriod": "FY2025",
                        }
                    ]
                },
            )
        )
    )[0]
    assert filing["event_status"] == "published" and filing["fiscal_period"] == "FY2025"
    assert filing["report_kind"] == "20-F"


def test_unknowns_unsupported_and_empty_lists_are_not_zero_holdings():
    adapter = YahooFinanceAdapter()
    for state in ("unsupported", "failed", "missing"):
        result = adapter.normalize(record(state=state))
        assert result.entities[0].properties["status"] == state
        assert not observations(result)
    result = adapter.normalize(altered_record("institutionOwnership", {"ownershipList": []}))
    assert not observations(result) and result.entities[0].properties["complete"] is False
    row = observations(
        adapter.normalize(
            altered_record(
                "institutionOwnership",
                {"ownershipList": [{"organization": "Unknown fund", "position": None}]},
            )
        )
    )[0]
    assert row["shares"] is None and row["ratio"] is None


def test_multiple_listings_and_share_classes_preserve_company_id():
    adapter = YahooFinanceAdapter()
    primary = adapter.normalize(record(section="price", selected=target(isin="DE0007236101")))
    adr = adapter.normalize(record(section="price", symbol="SIEGY", exchange="PNK"))
    a = next(e for e in primary.entities if e.type == "SecurityListing")
    b = next(e for e in adr.entities if e.type == "SecurityListing")
    assert a.entity_id == "yahoo:GER:SIE.DE" and b.entity_id == "yahoo:PNK:SIEGY"
    assert (
        next(e for e in primary.entities if e.type == "Security").entity_id == "isin:DE0007236101"
    )
    assert not [e for e in adr.entities if e.type == "Security"]
    assert primary.assertions[0].subject.entity_id == adr.assertions[0].subject.entity_id
    ordinary = adapter.normalize(
        record(
            section="price",
            symbol="VOW.DE",
            selected=target(
                "VOW.DE",
                isin="DE0007664005",
                entity_id="be46-vw",
                qid="Q156578",
                label="Volkswagen",
            ),
        )
    )
    preference = adapter.normalize(
        record(
            section="price",
            symbol="VOW3.DE",
            selected=target(
                "VOW3.DE",
                isin="DE0007664039",
                entity_id="be46-vw",
                qid="Q156578",
                label="Volkswagen",
            ),
        )
    )
    ordinary_security = next(e.entity_id for e in ordinary.entities if e.type == "Security")
    preference_security = next(e.entity_id for e in preference.entities if e.type == "Security")
    assert ordinary_security == "isin:DE0007664005"
    assert preference_security == "isin:DE0007664039"
    assert ordinary.assertions[0].subject.entity_id == preference.assertions[0].subject.entity_id
    mismatch = adapter.normalize(record(section="price", selected=target("BMW.DE")))
    assert mismatch.errors == 1 and not observations(mismatch)


def test_yahoo_partial_transport_and_identity_failure_do_not_hide_other_sections():
    transport = Mock()
    transport.get.side_effect = [
        (record(section="price").payload, "available"),
        SourceFetchError("failure"),
        *[(record().payload, "available") for _ in MODULES[2:]],
    ]
    adapter = YahooFinanceAdapter(transport)
    adapter.configure([target()])
    records = list(adapter.fetch(None, None))
    assert len(records) == len(MODULES)
    assert records[1].acquisition_context["status"] == "failed"
    assert records[2].acquisition_context["status"] == "available"
    transport.get.side_effect = None
    transport.get.return_value = (record(section="price", symbol="BMW.DE").payload, "available")
    assert all(
        r.acquisition_context["status"] == "failed" for r in list(adapter.fetch(None, None))[1:]
    )


def test_property_boundary_is_ontology_typed_and_protects_registry_fields():
    ontology = load_ontology_artifact()
    for adapter, raw in [
        (WikipediaAdapter(), record("wikipedia", "de")),
        (YahooFinanceAdapter(), record(section="assetProfile")),
    ]:
        for entity in adapter.normalize(raw).entities:
            _entity_properties(entity, ontology)
    from limes.enrichment.service import validate_normalized_section

    malformed = altered_record("assetProfile", {"fullTimeEmployees": "unexpected scalar"})
    adapter = YahooFinanceAdapter()
    failed = validate_normalized_section(adapter, malformed, adapter.normalize(malformed), ontology)
    assert failed.errors == 1 and failed.entities[0].properties["status"] == "failed"
    assert not observations(failed)
    entity = target().entity
    entity.properties = {"entity_id": "overwrite"}
    with pytest.raises(ValueError, match="protected"):
        _entity_properties(entity, ontology)
    entity.properties = {"legal_form": 100}
    with pytest.raises(ValueError, match="invalid"):
        _entity_properties(entity, ontology)


def test_operator_job_bounds_and_no_generic_bulk_fetch():
    request = JobRequest(
        request_id=uuid4(), command="enrich", source="wikipedia", selections=[target().selection]
    )
    args = request.argv()
    assert args[:2] == ["limes", "enrich"]
    assert json.loads(args[args.index("--selections") + 1])[0]["qid"] == "Q81230"
    assert {"wikipedia", "yahoo_finance"} <= set(build_default_registry().source_ids())
    with pytest.raises(ValidationError):
        JobRequest(
            request_id=uuid4(),
            command="enrich",
            source="wikipedia",
            selections=[target().selection] * 11,
        )
    with pytest.raises(ValidationError):
        JobRequest(request_id=uuid4(), command="ingest", source="wikipedia")
    with pytest.raises(ValidationError):
        EnrichmentSelection(
            entity_id="a",
            symbol="SIE.DE",
            evidence_url="https://test.org",
            rationale="No exchange must fail",
        )
    driver = Mock()
    driver.read.return_value = [
        {
            "id": "be46-siemens",
            "label": "Siemens",
            "labels": ["Entity", "Agent", "Corporation"],
            "qid": "Q1",
        }
    ]
    with pytest.raises(LimesError, match="conflicts"):
        prepare_targets(driver, [target().selection], "wikipedia")


def test_parsing_and_selection_bounds_fail_closed():
    for adapter in (WikipediaAdapter(), YahooFinanceAdapter()):
        with pytest.raises(SourceFetchError):
            list(adapter.fetch(None, None))
        output = adapter.normalize(record(payload=b"invalid json"))
        assert output.errors == 1 and output.entities[0].properties["status"] == "failed"
        invalid = record(payload=b"invalid json").model_copy(update={"acquisition_context": None})
        with pytest.raises(SourceParseError):
            adapter.normalize(invalid)


def test_yahoo_transport_bounds_decompressed_body_before_buffering(monkeypatch):
    from types import SimpleNamespace

    from curl_cffi.requests import Session

    from limes.enrichment.transport import MAX_BYTES, BoundedYahooSession

    def reply(self, method, url, **kwargs):
        assert kwargs["max_redirects"] == 3
        consume = kwargs["content_callback"]
        consume(b"a" * MAX_BYTES)
        consume(b"x")
        return SimpleNamespace(content=b"")

    monkeypatch.setattr(Session, "request", reply)
    with BoundedYahooSession() as session, pytest.raises(ValueError, match="4 MiB"):
        session.get("https://finance.yahoo.com/test")
