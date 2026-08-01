# tests/unit/test_osm_adapter.py | v1.0.0 | introduced by WP-19
"""OSM adapter tests per Doc 2 §8.5.2 and the WP-19 roadmap.

Recorded fixture (a realistic Overpass `out center` response: a power
substation node with address, a water_works way without one, and an element
without KRITIS tags) pinned with respx - no live network. Asserts the exact
expected record set: deterministic keys (`osm_id`, `coordinate_hash`,
`nuts_code`), the KRITIS topic multi-key identity convention, source
attribution, the lookup behavior of `postal_lookup` (absent or a miss -> no
`LOCATED_IN`, never guessed, counted), and deterministic assertion ids.
"""

import json
from datetime import UTC, datetime

import respx
import structlog
from httpx import Response

from limes.errors import SourceParseError
from limes.sources.osm import OVERPASS_QUERY, OVERPASS_URL, OsmAdapter
from limes.types import RawRecord

FIXTURES = __import__("pathlib").Path(__file__).parents[1] / "fixtures" / "osm"
NOW = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)

ADAPTER = OsmAdapter()

# Digest values pinned here so an identity-scheme change fails loudly instead
# of silently re-keying existing nodes.
_OPERATOR_SUBSTATION = "operator:6043feadc459754b6f6e769617a5d13e"
_OPERATOR_WATER = "operator:19120002071d4a5486ec9d4836ce32f8"
_LOCATION_SUBSTATION = (
    "coordinate_hash:5e9c9c11ddb2fe55852c2b3c2873cd37221ac0046dd0cbf5ae464a66e6575f39"
)
_LOCATION_WATER = "coordinate_hash:86baf8ead19ccaa51cc6a4bff88b84ff1201575103599971c09f78565ac899a2"


def _fixture() -> bytes:
    return (FIXTURES / "overpass_response.json").read_bytes()


def _record() -> RawRecord:
    return RawRecord(
        payload=_fixture(),
        content_type="application/json",
        source_url=OVERPASS_URL,
        fetched_at=NOW,
    )


def test_fetch_posts_the_overpass_query_and_yields_one_record():
    with respx.mock:
        respx.post(OVERPASS_URL, json={"data": OVERPASS_QUERY}).mock(
            return_value=Response(200, content=_fixture())
        )
        records = list(ADAPTER.fetch(None, None))
    assert len(records) == 1
    assert records[0].content_type == "application/json"
    assert records[0].source_url == OVERPASS_URL
    assert records[0].payload == _fixture()


def test_normalize_produces_the_expected_record_set():
    normalized = ADAPTER.normalize(_record())

    assert normalized.kind == "structured"
    assert normalized.lookup_rows == []

    # Two KRITIS elements, two OPERATES assertions; the bakery matches no
    # sector and contributes nothing.
    assert len(normalized.assertions) == 2
    for assertion in normalized.assertions:
        assert assertion.relation == "OPERATES"
        assert assertion.subject.type == "Corporation"
        assert assertion.subject.deterministic_key is None
        assert assertion.object.type == "Asset"
        assert assertion.object.deterministic_key[0] == "osm_id"
        assert assertion.provenance.source_id == "osm"
        assert assertion.provenance.source_trust == 0.75
        assert assertion.provenance.confidence == 1.0
        assert assertion.validity.valid_from == NOW
        assert assertion.validity.recorded_at == NOW
        assert assertion.validity.valid_to is None

    operated = {a.object.entity_id: a.subject for a in normalized.assertions}
    assert set(operated) == {"osm_id:123456789", "osm_id:987654321"}
    assert operated["osm_id:123456789"].entity_id == _OPERATOR_SUBSTATION
    assert operated["osm_id:987654321"].entity_id == _OPERATOR_WATER
    assert operated["osm_id:123456789"].label == "Stromnetz Berlin GmbH"
    assert operated["osm_id:987654321"].label == "Berliner Wasserbetriebe"

    # Name where present, else the "OSM <type> <id>" fallback.
    assets = {a.object.entity_id: a.object.label for a in normalized.assertions}
    assert assets["osm_id:123456789"] == "Umspannwerk Neuenhagen"
    assert assets["osm_id:987654321"] == "Wasserwerk Tegel"


def test_kritis_topics_and_locations_are_standalone_entities():
    normalized = ADAPTER.normalize(_record())

    standalone = {(e.entity_id, e.type) for e in normalized.entities}
    assert standalone == {
        ("topic:KRITIS:energie", "Topic"),
        ("topic:KRITIS:wasser", "Topic"),
        (_LOCATION_SUBSTATION, "Location"),
        (_LOCATION_WATER, "Location"),
    }

    topics = {e.entity_id: e for e in normalized.entities if e.type == "Topic"}
    assert topics["topic:KRITIS:energie"].label == "Energie"
    assert topics["topic:KRITIS:energie"].deterministic_key == ("code", "energie")
    assert topics["topic:KRITIS:wasser"].label == "Wasser"
    assert topics["topic:KRITIS:wasser"].deterministic_key == ("code", "wasser")

    locations = {e.entity_id: e for e in normalized.entities if e.type == "Location"}
    assert locations[_LOCATION_SUBSTATION].label == "52.52000, 13.70000"
    assert locations[_LOCATION_WATER].label == "52.58333, 13.25000"


def test_normalize_without_postal_lookup_emits_no_located_in_and_counts():
    with structlog.testing.capture_logs() as captured:
        normalized = ADAPTER.normalize(_record())
    assert all(a.relation != "LOCATED_IN" for a in normalized.assertions)
    assert any(
        event["event"].startswith("gisco correspondence missing") and event["addresses"] == 1
        for event in captured
    )


def test_normalize_with_postal_lookup_emits_located_in():
    def lookup(country: str, postcode: str) -> str | None:
        return "DE405" if (country, postcode) == ("DE", "15366") else None

    normalized = ADAPTER.normalize(_record(), postal_lookup=lookup)

    located = [a for a in normalized.assertions if a.relation == "LOCATED_IN"]
    assert len(located) == 1
    assertion = located[0]
    assert assertion.subject.entity_id == "osm_id:123456789"
    assert assertion.subject.type == "Asset"
    assert assertion.object.entity_id == "nuts_code:DE405"
    assert assertion.object.type == "AdministrativeRegion"
    assert assertion.object.label == "DE405"
    assert assertion.object.deterministic_key == ("nuts_code", "DE405")
    assert assertion.provenance.source_id == "osm"


def test_assertion_ids_are_deterministic_across_calls():
    first = [a.assertion_id for a in ADAPTER.normalize(_record()).assertions]
    second = [a.assertion_id for a in ADAPTER.normalize(_record()).assertions]
    assert first == second
    assert len(set(first)) == len(first)


def test_normalize_rejects_malformed_json():
    for payload in (b"not json", b'{"version": 0.6}', b"[1, 2]"):
        record = RawRecord(
            payload=payload,
            content_type="application/json",
            source_url=OVERPASS_URL,
            fetched_at=NOW,
        )
        try:
            ADAPTER.normalize(record)
        except SourceParseError:
            pass
        else:
            raise AssertionError("expected SourceParseError")


def test_fixture_is_the_shape_the_adapter_parses():
    data = json.loads(_fixture())
    assert data["version"] == 0.6
    assert len(data["elements"]) == 3
