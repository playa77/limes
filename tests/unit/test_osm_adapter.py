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

import pytest
import respx
import structlog
from httpx import Response

from limes.archive.store import ArchiveStore
from limes.errors import SourceParseError
from limes.sources import osm
from limes.sources.osm import OVERPASS_URL, OsmAdapter
from limes.sources.osm_acquisition import OsmAcquisition
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


def test_fetch_posts_bounded_queries_and_preserves_original_bytes(tmp_path, monkeypatch):
    queries = osm.OVERPASS_QUERIES[:2]
    monkeypatch.setattr(osm, "OVERPASS_QUERIES", queries)
    monkeypatch.setattr(osm.time, "sleep", lambda _: None)
    archive = ArchiveStore(tmp_path / "archive")
    adapter = OsmAdapter(OsmAcquisition(archive, tmp_path / "cursor"))
    with respx.mock:
        routes = [respx.post(OVERPASS_URL, data={"data": query}).mock(
            return_value=Response(200, content=_fixture())) for query in queries]
        records = list(adapter.fetch(None, None))
        assert all(route.call_count == 1 for route in routes)
    assert len(records) == 2
    assert all(record.payload == _fixture() for record in records)
    assert all(record.source_url == OVERPASS_URL for record in records)
    assert len(adapter.normalize(records[0]).assertions) == 2
    assert adapter.normalize(records[1]).assertions == []
    manifest = records[0].acquisition_context["acquisition_manifest_hash"]
    assert len(json.loads(archive.get(manifest))["partitions"]) == 2
    assert (tmp_path / "cursor" / "active.json").exists()
    adapter.complete_fetch()
    assert not (tmp_path / "cursor" / "active.json").exists()
    # A completed load retires the acquisition: the next explicit run is fresh.
    requests = []
    monkeypatch.setattr(osm, 'fetch_bytes_form', lambda url, data: (
        requests.append(data['data']) or _json_payload([])))
    list(adapter.fetch(None, None))
    assert requests == list(queries)


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
    assert set(operated) == {"osm_id:node/123456789", "osm_id:way/987654321"}
    assert operated["osm_id:node/123456789"].entity_id == _OPERATOR_SUBSTATION
    assert operated["osm_id:way/987654321"].entity_id == _OPERATOR_WATER
    assert operated["osm_id:node/123456789"].label == "Stromnetz Berlin GmbH"
    assert operated["osm_id:way/987654321"].label == "Berliner Wasserbetriebe"

    # Name where present, else the "OSM <type> <id>" fallback.
    assets = {a.object.entity_id: a.object.label for a in normalized.assertions}
    assert assets["osm_id:node/123456789"] == "Umspannwerk Neuenhagen"
    assert assets["osm_id:way/987654321"] == "Wasserwerk Tegel"


def test_kritis_topics_and_locations_are_standalone_entities():
    normalized = ADAPTER.normalize(_record())

    standalone = {(e.entity_id, e.type) for e in normalized.entities}
    assert standalone == {
        ("osm_id:node/123456789", "Asset"),
        ("osm_id:way/987654321", "Asset"),
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
    assert assertion.subject.entity_id == "osm_id:node/123456789"
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


def _json_payload(elements: list) -> bytes:
    return json.dumps({"version": 0.6, "elements": elements}).encode("utf-8")


def test_element_without_id_is_skipped_and_counted():
    elements = [
        {"type": "node", "tags": {"power": "substation"}},
        {
            "id": 1,
            "type": "node",
            "lat": 52.5,
            "lon": 13.4,
            "tags": {"power": "substation", "operator": "Strom GmbH"},
        },
    ]
    with structlog.testing.capture_logs() as captured:
        normalized = ADAPTER.normalize(
            RawRecord(
                payload=_json_payload(elements),
                content_type="application/json",
                source_url=OVERPASS_URL,
                fetched_at=NOW,
            )
        )
    assert len(normalized.assertions) == 1
    skipped = [e for e in captured if e.get("event") == "osm: element without id skipped"]
    assert len(skipped) == 1


def test_element_with_malformed_tags_is_skipped_and_counted():
    elements = [
        {"id": 2, "type": "node", "tags": {"power": 123}},
        {"id": 3, "type": "node"},
        {
            "id": 4,
            "type": "node",
            "lat": 52.5,
            "lon": 13.4,
            "tags": {"power": "substation", "operator": "Strom GmbH"},
        },
    ]
    with structlog.testing.capture_logs() as captured:
        normalized = ADAPTER.normalize(
            RawRecord(
                payload=_json_payload(elements),
                content_type="application/json",
                source_url=OVERPASS_URL,
                fetched_at=NOW,
            )
        )
    assert len(normalized.assertions) == 1
    skipped = [
        e for e in captured if e.get("event") == "osm: element tags malformed; element skipped"
    ]
    assert len(skipped) == 2


def test_non_object_element_is_skipped_and_counted():
    elements = [
        "garbage",
        {
            "id": 5,
            "type": "node",
            "lat": 52.5,
            "lon": 13.4,
            "tags": {"power": "substation", "operator": "Strom GmbH"},
        },
    ]
    with structlog.testing.capture_logs() as captured:
        normalized = ADAPTER.normalize(
            RawRecord(
                payload=_json_payload(elements),
                content_type="application/json",
                source_url=OVERPASS_URL,
                fetched_at=NOW,
            )
        )
    assert len(normalized.assertions) == 1
    skipped = [e for e in captured if e.get("event") == "osm: non-object element skipped"]
    assert len(skipped) == 1


def test_element_without_usable_coordinates_skips_location():
    # A boolean "lat" is not a JSON number (bool is an int subclass); a center
    # without a longitude is unusable. Both rows classify as assets but get
    # no Location.
    elements = [
        {"id": 6, "type": "node", "lat": True, "lon": 13.4, "tags": {"power": "substation"}},
        {"id": 7, "type": "way", "center": {"lat": 52.5}, "tags": {"power": "substation"}},
        {
            "id": 8,
            "type": "node",
            "lat": 52.5,
            "lon": 13.4,
            "tags": {"power": "substation", "operator": "Strom GmbH"},
        },
    ]
    with structlog.testing.capture_logs() as captured:
        normalized = ADAPTER.normalize(
            RawRecord(
                payload=_json_payload(elements),
                content_type="application/json",
                source_url=OVERPASS_URL,
                fetched_at=NOW,
            )
        )
    assert len(normalized.assertions) == 1
    skipped = [
        e
        for e in captured
        if e.get("event") == "osm: element without coordinates; location skipped"
    ]
    assert len(skipped) == 2


def test_grid_exactly_covers_original_bbox_without_interior_gaps():
    import re
    from decimal import Decimal

    boxes = []
    for query in osm.OVERPASS_QUERIES:
        assert '[timeout:25]' in query
        clauses = re.findall(r'\]\(([-\d.,]+)\);', query)
        assert len(clauses) == 7
        assert len(set(clauses)) == 1
        boxes.append(tuple(map(Decimal, clauses[0].split(','))))
    assert len(boxes) == 80
    assert boxes[0][:2] == (Decimal('47.27'), Decimal('5.87'))
    assert boxes[-1][2:] == (Decimal('55.06'), Decimal('15.04'))
    for row in range(8):
        for col in range(10):
            s, w, n, e = boxes[row * 10 + col]
            assert 0 < n - s < 1 and 0 < e - w < 1
            if col < 9:
                assert e == boxes[row * 10 + col + 1][1]
            if row < 7:
                assert n == boxes[(row + 1) * 10 + col][0]


def test_restart_resumes_only_missing_partitions_and_replays_stable_records(tmp_path, monkeypatch):
    from limes.errors import SourceFetchError

    monkeypatch.setattr(osm, 'OVERPASS_QUERIES', ('first', 'second'))
    waits = []
    monkeypatch.setattr(osm.time, 'sleep', waits.append)
    archive = ArchiveStore(tmp_path / 'archive')
    cursor = tmp_path / 'cursor'
    calls = []

    def fetch(url, data):
        calls.append(data['data'])
        if data['data'] == 'second':
            raise SourceFetchError('upstream unavailable')
        return _fixture()

    monkeypatch.setattr(osm, 'fetch_bytes_form', fetch)
    with pytest.raises(SourceFetchError):
        list(OsmAdapter(OsmAcquisition(archive, cursor)).fetch(None, None))
    assert calls == ['first', 'second']
    assert waits == [1]
    old = json.loads((cursor / 'active.json').read_text())
    assert set(old['partitions']) == {'0'}
    calls.clear()
    monkeypatch.setattr(osm, 'fetch_bytes_form', lambda url, data: (
        calls.append(data['data']) or _json_payload([])))
    restarted = OsmAdapter(OsmAcquisition(archive, cursor))
    records = list(restarted.fetch(None, None))
    assert calls == ['second']
    assert records[0].fetched_at.isoformat().replace('+00:00', 'Z') == (
        old['partitions']['0']['fetched_at'])
    assert records[0].payload == _fixture()
    monkeypatch.setattr(osm, 'fetch_bytes_form', lambda *args: pytest.fail('must replay archive'))
    replay = list(OsmAdapter(OsmAcquisition(archive, cursor)).fetch(None, None))
    assert [r.model_dump() for r in replay] == [r.model_dump() for r in records]


@pytest.mark.parametrize('payload', [
    b'{"elements": [], "remark": "runtime error: Query timed out"}',
    b'{"elements": [{"id": 1, "type": "node", "tags": {"power": "plant"}}],'
    b' "remark": "runtime error: out of memory"}',
    b'{"elements": [null]}',
    b'{"elements": [{"id": true, "type": "node", "tags": {}}]}',
    b'{"elements": [{"id": 1, "type": "invalid", "tags": {}}]}',
    b'{"elements": [{"id": 1, "type": "node", "tags": {"power": 3}}]}',
    b'{"remark": "timeout"}',
    b'<html>unavailable</html>',
])
def test_incomplete_partition_never_enters_cursor_or_yields_data(tmp_path, monkeypatch, payload):
    monkeypatch.setattr(osm, 'OVERPASS_QUERIES', ('only',))
    monkeypatch.setattr(osm, 'fetch_bytes_form', lambda *args: payload)
    archive = ArchiveStore(tmp_path / 'archive')
    cursor = tmp_path / 'cursor'
    with pytest.raises(SourceParseError):
        list(OsmAdapter(OsmAcquisition(archive, cursor)).fetch(None, None))
    assert json.loads((cursor / 'active.json').read_text())['partitions'] == {}
    assert archive.get(osm.payload_hash(payload)) == payload


def test_typed_ids_do_not_merge_nodes_ways_and_relations_and_keep_unoperated_assets():
    elements = [dict(id=123, type=kind, tags={'power': 'plant'})
                for kind in ('node', 'way', 'relation')]
    record = RawRecord(payload=_json_payload(elements), content_type='application/json',
                       source_url=OVERPASS_URL, fetched_at=NOW)
    result = ADAPTER.normalize(record)
    assert {e.entity_id for e in result.entities if e.type == 'Asset'} == {
        'osm_id:node/123', 'osm_id:way/123', 'osm_id:relation/123'}


def test_cursor_lock_plan_mismatch_and_archive_corruption_fail_closed(tmp_path, monkeypatch):
    from limes.errors import SourceFetchError

    monkeypatch.setattr(osm, 'OVERPASS_QUERIES', ('only',))
    monkeypatch.setattr(osm, 'fetch_bytes_form', lambda *args: _fixture())
    archive = ArchiveStore(tmp_path / 'archive')
    store = OsmAcquisition(archive, tmp_path / 'cursor')
    with store.locked(), pytest.raises(SourceFetchError, match='active'):
        list(OsmAdapter(store).fetch(None, None))
    records = list(OsmAdapter(store).fetch(None, None))
    monkeypatch.setattr(osm, 'OVERPASS_QUERIES', ('changed',))
    with pytest.raises(SourceFetchError, match='plan changed'):
        list(OsmAdapter(store).fetch(None, None))
    monkeypatch.setattr(osm, 'OVERPASS_QUERIES', ('only',))
    archive.path_for(osm.payload_hash(records[0].payload)).unlink()
    with pytest.raises(SourceFetchError, match='archive is unavailable'):
        list(OsmAdapter(store).fetch(None, None))
