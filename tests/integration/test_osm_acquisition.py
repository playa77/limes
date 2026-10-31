"""Real acquisition/archive/load/checkpoint lifecycle on disposable Neo4j."""

import json

import pytest

from limes.composition import build_run_context
from limes.errors import GraphWriteError, SourceFetchError, SourceParseError
from limes.graph.driver import GraphDriver
from limes.pipeline import run
from limes.pipeline.run import RunSpec, execute_run
from limes.sources import osm
from limes.sources.osm_acquisition import OsmAcquisition
from tests.integration.test_pipeline_run_structured import _settings


@pytest.fixture(autouse=True)
def isolated_graph(neo4j_instance):
    instance = neo4j_instance
    driver = GraphDriver(instance.uri, instance.user, instance.password, instance.database)
    try:
        driver.write_batch([('MATCH (n) DETACH DELETE n', {})])
        yield
    finally:
        driver.write_batch([('MATCH (n) DETACH DELETE n', {})])
        driver.close()


def test_osm_interruption_load_failure_resume_and_complete_checkpoint(
    neo4j_instance, tmp_path, monkeypatch,
):
    monkeypatch.setattr(osm, 'OVERPASS_QUERIES', ('west', 'east'))
    monkeypatch.setattr(osm.time, 'sleep', lambda _: None)
    calls = []
    failed = True
    first = json.dumps({'elements': [
        {'id': 7, 'type': 'node', 'lat': 52.5, 'lon': 13.4,
         'tags': {'power': 'plant', 'operator': 'Utility'}},
    ]}).encode()
    second = json.dumps({'elements': [
        {'id': 7, 'type': 'node', 'lat': 52.5, 'lon': 13.4,
         'tags': {'power': 'plant', 'operator': 'Utility'}},
        {'id': 7, 'type': 'way', 'center': {'lat': 52.5, 'lon': 13.4},
         'tags': {'power': 'plant', 'operator': 'Utility'}},
    ]}).encode()

    def fetch(url, data):
        calls.append(data['data'])
        if data['data'] == 'west':
            return first
        if failed:
            return b'{"elements": [], "remark": "runtime error: Query timed out"}'
        return second

    monkeypatch.setattr(osm, 'fetch_bytes_form', fetch)
    settings = _settings(neo4j_instance, tmp_path)
    cursor = settings.archive_path / '.acquisition' / 'osm' / 'active.json'
    spec = RunSpec(source_id='osm', mode='ingest')
    ctx = build_run_context(settings, needs_inference=False)
    ctx.driver.write_batch([('MATCH (n) DETACH DELETE n', {})])
    try:
        with pytest.raises(SourceParseError, match='remark'):
            execute_run(spec, ctx)
        assert calls == ['west', 'east']
        assert ctx.driver.read('MATCH (n:Asset) RETURN count(n) AS c', {}, 30)[0]['c'] == 0
        assert ctx.driver.read(
            'MATCH (s:Source {source_id:"osm"}) RETURN s.last_success_at AS at', {}, 30,
        )[0]['at'] is None
        assert set(json.loads(cursor.read_bytes())['partitions']) == {'0'}
    finally:
        ctx.driver.close()

    # Rebuild every production dependency: no process-local resume state.
    failed = False
    calls.clear()
    ctx = build_run_context(settings, needs_inference=False)
    actual_load = run.load
    loads = 0

    def failing_load(*args, **kwargs):
        nonlocal loads
        loads += 1
        contender = OsmAcquisition(ctx.archive, cursor.parent)
        with pytest.raises(SourceFetchError, match='active'), contender.locked():
            pytest.fail('acquisition lock must remain held while loading')
        if loads == 2:
            raise GraphWriteError('simulated graph outage')
        return actual_load(*args, **kwargs)

    monkeypatch.setattr(run, 'load', failing_load)
    try:
        with pytest.raises(GraphWriteError):
            execute_run(spec, ctx)
        assert calls == ['east']
        assert len(json.loads(cursor.read_bytes())['partitions']) == 2
        assert ctx.driver.read(
            'MATCH (s:Source {source_id:"osm"}) RETURN s.last_success_at AS at', {}, 30,
        )[0]['at'] is None
    finally:
        ctx.driver.close()

    monkeypatch.setattr(run, 'load', actual_load)
    monkeypatch.setattr(osm, 'fetch_bytes_form', lambda *args: pytest.fail('must use archive'))
    ctx = build_run_context(settings, needs_inference=False)
    actual_normalize = osm.OsmAdapter.normalize

    def parse_failure(*args, **kwargs):
        raise SourceParseError('simulated normalization failure')

    try:
        monkeypatch.setattr(osm.OsmAdapter, 'normalize', parse_failure)
        rejected = execute_run(spec, ctx)
        assert rejected.errors == 2
        assert cursor.exists()
        assert ctx.driver.read(
            'MATCH (s:Source {source_id:"osm"}) RETURN s.last_success_at AS at', {}, 30,
        )[0]['at'] is None
        monkeypatch.setattr(osm.OsmAdapter, 'normalize', actual_normalize)
        result = execute_run(spec, ctx)
        assert result.errors == result.assertions_rejected == 0
        assert result.assertions_written == 1  # new way; cached node replays idempotently
        assert result.assertions_skipped == 1
        assert not cursor.exists()
        rows = ctx.driver.read(
            'MATCH (a:Asset) RETURN a.entity_id AS id ORDER BY id', {}, 30)
        assert [row['id'] for row in rows] == ['osm_id:node/7', 'osm_id:way/7']
        rows = ctx.driver.read(
            'MATCH ()-[r:OPERATES]->() RETURN r.evidence_document_id AS document, '
            'r.evidence_manifest_hash AS manifest', {}, 30)
        assert len(rows) == 2
        assert {ctx.archive.get(row['document']) for row in rows} == {first, second}
        for row in rows:
            context = json.loads(ctx.archive.get(row['manifest']))['context']
            manifest = json.loads(ctx.archive.get(context['acquisition_manifest_hash']))
            assert len(manifest['partitions']) == 2
        assert ctx.driver.read(
            'MATCH (s:Source {source_id:"osm"}) RETURN s.last_success_at AS at', {}, 30,
        )[0]['at'] is not None
        runs = ctx.driver.read(
            'MATCH (r:IngestionRun {source_id:"osm"}) RETURN r.errors AS errors '
            'ORDER BY r.started_at', {}, 30)
        assert [r['errors'] for r in runs] == [1, 1, 2, 0]
    finally:
        ctx.driver.close()
