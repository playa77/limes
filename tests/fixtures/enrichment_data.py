"""Independent provider fixtures and reviewed test selections (not production identities)."""

import json
from datetime import UTC, datetime
from pathlib import Path

from limes.enrichment.models import AcquisitionTarget, EnrichmentSelection
from limes.types import EntityEndpoint, RawRecord

FIXTURES = Path(__file__).parent / "enrichment"
FETCHED = datetime(2026, 10, 29, 12, tzinfo=UTC)


def target(
    symbol="SIE.DE",
    exchange="GER",
    *,
    entity_id="be46-siemens",
    isin=None,
    qid="Q81230",
    label="Siemens",
):
    return AcquisitionTarget(
        selection=EnrichmentSelection(
            entity_id=entity_id,
            qid=qid,
            symbol=symbol,
            exchange=exchange,
            isin=isin,
            evidence_url="https://www.siemens.com/investor-relations/",
            rationale="Fixture operator review of issuer and listing; no name-based company merge.",
        ),
        entity=EntityEndpoint(entity_id=entity_id, type="Corporation", label=label),
    )


def record(
    source="yahoo_finance",
    section="institutionOwnership",
    *,
    symbol="SIE.DE",
    exchange="GER",
    language="de",
    state="available",
    payload=None,
    selected=None,
):
    selected = selected or target(symbol, exchange)
    name = f"yahoo_{symbol}.json" if source == "yahoo_finance" else f"wikipedia_{language}.json"
    return RawRecord(
        payload=payload if payload is not None else (FIXTURES / name).read_bytes(),
        fetched_at=FETCHED,
        content_type="application/json",
        source_url=f"https://finance.yahoo.com/quote/{symbol}/"
        if source == "yahoo_finance"
        else f"https://{language}.wikipedia.org/w/api.php",
        acquisition_context={
            "target": selected.model_dump(mode="json"),
            "section": section,
            "language": language,
            "status": state,
        },
    )


def altered_record(section, data):
    return record(
        section=section,
        payload=json.dumps({"quoteSummary": {"result": [{section: data}], "error": None}}).encode(),
    )
