"""BE-53 real shared transport with mocked endpoints; no network acquisition."""
import json

import httpx
import pytest
import respx

from limes.archive.store import ArchiveStore
from limes.config import Settings
from limes.errors import SourceFetchError
from limes.sources import osm
from limes.sources.osm_acquisition import OsmAcquisition

PRIMARY = osm.OVERPASS_URL
MIRROR = 'https://overpass.kumi.systems/api/interpreter'


def test_osm_mirror_timeout_and_attempt_logging(tmp_path, monkeypatch):
    monkeypatch.setattr('time.sleep', lambda _: None)
    monkeypatch.setattr(osm, 'OVERPASS_QUERIES', osm.OVERPASS_QUERIES[:1])
    attempts = []

    def primary(request):
        attempts.append(str(request.url))
        assert request.extensions['timeout'] == {
            'connect': 60, 'read': 240, 'write': 60, 'pool': 60}
        raise httpx.ReadTimeout('busy', request=request)

    def mirror(request):
        attempts.append(str(request.url))
        return httpx.Response(200, json={'elements': []})

    logs = []
    monkeypatch.setattr('limes.sources.base.logger.info',
                        lambda event, **fields: logs.append((event, fields)))
    store = OsmAcquisition(ArchiveStore(tmp_path / 'archive'), tmp_path / 'cursor')
    with respx.mock:
        respx.post(PRIMARY).mock(side_effect=primary)
        respx.post(MIRROR).mock(side_effect=mirror)
        assert len(list(osm.OsmAdapter(store, read_timeout_s=240).fetch(None, None))) == 1
    assert attempts == [PRIMARY, MIRROR]
    assert [fields['endpoint'] for event, fields in logs
            if event == 'source HTTP attempt'] == attempts
    assert [fields['attempt'] for event, fields in logs
            if event == 'source HTTP attempt'] == [1, 2]


@pytest.mark.parametrize('failure,split', [
    (502, True), (503, True), (504, True), ('read', True),
    (401, False), (403, False), (429, False), (500, False), ('connect', False),
])
def test_transport_split_policy_and_restart(tmp_path, monkeypatch, failure, split):
    monkeypatch.setattr('time.sleep', lambda _: None)
    monkeypatch.setattr(osm, 'OVERPASS_QUERIES', osm.OVERPASS_QUERIES[:1])
    store = OsmAcquisition(ArchiveStore(tmp_path / 'archive'), tmp_path / 'cursor')
    adapter = osm.OsmAdapter(store)
    seen = []

    def fail(request):
        seen.append(str(request.url))
        if failure == 'read':
            raise httpx.ReadTimeout('busy', request=request)
        if failure == 'connect':
            raise httpx.ConnectTimeout('busy', request=request)
        return httpx.Response(failure)

    with respx.mock:
        respx.post(PRIMARY).mock(side_effect=fail)
        respx.post(MIRROR).mock(side_effect=fail)
        with pytest.raises(SourceFetchError):
            list(adapter.fetch(None, None))
    before = (store.root / 'active.json').read_bytes()
    state = json.loads(before)
    assert state['splits'] == (['0'] if split else [])
    assert state['partitions'] == {}
    assert len(seen) == (20 if split else 1 if failure in (401, 403) else 4)
    # Neither repeated failure nor a tiny failed child grows the split tree.
    with respx.mock:
        respx.post(PRIMARY).mock(side_effect=fail)
        respx.post(MIRROR).mock(side_effect=fail)
        with pytest.raises(SourceFetchError):
            list(adapter.fetch(None, None))
    resumed = json.loads((store.root / 'active.json').read_bytes())
    assert resumed['splits'] == state['splits']
    assert resumed['partitions'] == {}
    assert set(resumed['failed_leaves']) == set(state['failed_leaves'])
    assert all(entry['state'] == 'failed' for entry in resumed['failed_leaves'].values())
    with respx.mock:
        respx.post(PRIMARY).respond(200, json={'elements': []})
        records = list(adapter.fetch(None, None))
    assert len(records) == (4 if split else 1)


def test_osm_configuration(monkeypatch):
    monkeypatch.setenv('LIMES_OSM_HTTP_TIMEOUT_SECONDS', '240')
    monkeypatch.setenv('LIMES_OSM_OVERPASS_ENDPOINTS', '["https://mirror.invalid/api/interpreter"]')
    settings = Settings(
        _env_file=None, archive_path='/tmp/archive', neo4j_uri='bolt://test:7687',
        neo4j_user='test', neo4j_password='test', ontology_path='ontology',
        feeds_config_path='ontology/feeds.yaml', gold_set_path='gold_set', baseline_path='gold_set')
    assert settings.osm_http_timeout_seconds == 240
    assert settings.osm_overpass_endpoints == ('https://mirror.invalid/api/interpreter',)
    assert settings.http_timeout_seconds == 60
    with pytest.raises(ValueError, match='nonempty'):
        osm.OsmAdapter(endpoints=())


def test_failed_child_continues_siblings_and_resumes_legacy_cursor(tmp_path, monkeypatch):
    """Four real rotated attempts fail one child; sibling responses survive restart."""
    from limes.sources.base import payload_hash
    from limes.sources.osm_acquisition import AcquisitionState

    monkeypatch.setattr('time.sleep', lambda _: None)
    root = osm._overpass_query('0,0,2,2')
    monkeypatch.setattr(osm, 'OVERPASS_QUERIES', (root,))
    children = osm._split_query(root)
    store = OsmAcquisition(ArchiveStore(tmp_path / 'archive'), tmp_path / 'cursor')
    plan_hash = payload_hash(json.dumps([osm.OVERPASS_URL, root]).encode())
    # Actual old JSON shape: neither split tree nor hash is migrated.
    with store.locked():
        state = AcquisitionState(plan_hash=plan_hash, splits=['0'])
        legacy = state.model_dump(mode='json', exclude={'failed_leaves'})
        (store.root / 'active.json').write_text(json.dumps(legacy))
    attempts = []

    def respond(request):
        from urllib.parse import parse_qs

        query = parse_qs(request.content.decode())['data'][0]
        attempts.append((str(request.url), query))
        return httpx.Response(502 if query == children[1] else 200,
                              json={'elements': []})

    with respx.mock:
        respx.post(PRIMARY).mock(side_effect=respond)
        respx.post(MIRROR).mock(side_effect=respond)
        with pytest.raises(SourceFetchError, match='1 failed leaves'):
            list(osm.OsmAdapter(store).fetch(None, None))
    saved = json.loads((store.root / 'active.json').read_bytes())
    assert saved['acquisition_id'] == legacy['acquisition_id']
    assert saved['plan_hash'] == plan_hash
    assert saved['splits'] == ['0']
    assert set(saved['partitions']) == {'0/0', '0/2', '0/3'}
    assert set(saved['failed_leaves']) == {'0/1'}
    assert [url for url, query in attempts if query == children[1]] == [
        PRIMARY, MIRROR, PRIMARY, MIRROR]
    assert [query for _, query in attempts][-2:] == list(children[2:])
    attempts.clear()
    with respx.mock:
        respx.post(PRIMARY).mock(side_effect=lambda request: (
            attempts.append(str(request.url)) or httpx.Response(200, json={'elements': []})))
        records = list(osm.OsmAdapter(store).fetch(None, None))
    assert len(attempts) == 1 and len(records) == 4
    assert json.loads((store.root / 'active.json').read_bytes())['failed_leaves'] == {}
