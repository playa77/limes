"""Current formats through production fetch/archive/normalize/load and authenticated reads."""

from __future__ import annotations

import bz2
import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from limes.composition import build_run_context
from limes.errors import SourceFetchError
from limes.pipeline.run import RunSpec, execute_run
from limes.sources.gdelt import GdeltAdapter
from limes.sources.gleif import PUBLICATIONS_URL
from tests.fixtures.graph_data import make_api_client, wipe_graph
from tests.integration.test_pipeline_run_structured import _settings

FIXTURES = Path(__file__).parents[1] / "fixtures/ingest47"
NOW = datetime(2026, 10, 29, 12, tzinfo=UTC)


def zipped(name, payload):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(name, payload)
    return stream.getvalue()


def test_current_structured_sources_preserve_archive_graph_api(
    neo4j_instance, tmp_path, monkeypatch
):
    wipe_graph(neo4j_instance)
    entity_zip = zipped("entities.csv", (FIXTURES.parent / "gleif/entities.csv").read_bytes())
    rr_zip = zipped("rr.csv", (FIXTURES / "gleif-rr.csv").read_bytes())
    off_zip = bz2.compress((FIXTURES / "offeneregister.jsonl").read_bytes())
    urls = {
        "lei2": "https://goldencopy.gleif.org/storage/golden-copy-files/entities.csv.zip",
        "rr": "https://goldencopy.gleif.org/storage/golden-copy-files/rr.csv.zip",
    }
    catalog = json.dumps(
        {"data": [{k: {"full_file": {"csv": {"url": v}}} for k, v in urls.items()}]}
    ).encode()

    def gleif_fetch(url, **kwargs):
        return catalog if url == PUBLICATIONS_URL else entity_zip if url == urls["lei2"] else rr_zip

    monkeypatch.setattr("limes.sources.bulk.CHUNK_ROWS", 1)
    monkeypatch.setattr("limes.sources.gleif.fetch_bytes", gleif_fetch)
    monkeypatch.setattr("limes.sources.gleif.now_utc", lambda: NOW)
    monkeypatch.setattr("limes.sources.offeneregister.fetch_bytes", lambda *a, **kw: off_zip)
    monkeypatch.setattr("limes.sources.offeneregister.now_utc", lambda: NOW)
    monkeypatch.setattr(
        "limes.sources.transparency_register.fetch_bytes",
        lambda *a, **kw: (FIXTURES / "transparency.xml").read_bytes(),
    )
    uri = "https://ted.europa.eu/en/notice/745241-2026/xml"
    monkeypatch.setattr(
        "limes.sources.ted.fetch_bytes_post",
        lambda *a, **kw: json.dumps(
            {
                "notices": [{"publication-number": "745241-2026", "links": {"xml": {"MUL": uri}}}],
                "totalNoticeCount": 1,
                "iterationNextToken": "terminal",
                "timedOut": False,
            }
        ).encode(),
    )
    monkeypatch.setattr(
        "limes.sources.ted.fetch_bytes",
        lambda *a, **kw: (FIXTURES / "ted-contract.xml").read_bytes(),
    )
    ctx = build_run_context(_settings(neo4j_instance, tmp_path), needs_inference=False)
    try:
        for source in ["gleif", "offeneregister", "transparency_register", "ted"]:
            spec = RunSpec(source_id=source, mode="ingest", since=NOW.replace(day=28), until=NOW)
            first = execute_run(spec, ctx)
            assert first.errors == 0 and first.assertions_written > 0
            second = execute_run(spec, ctx)
            assert second.errors == 0 and second.assertions_written == 0
        for payload in [entity_zip, rr_zip, off_zip]:
            assert ctx.archive.get(hashlib.sha256(payload).hexdigest()) == payload
        rows = ctx.driver.read(
            "MATCH (s)-[r:DIRECTLY_CONSOLIDATED_BY]->(o) "
            "RETURN s.entity_id AS id, properties(r) AS p",
            {},
            30,
        )
        assert len(rows) == 1
        assert rows[0]["p"]["ontology_version"] == "1.3.0"
        assert ctx.archive.get(rows[0]["p"]["evidence_document_id"]).startswith(b"Relationship.")
        manifest_hash = rows[0]["p"]["evidence_manifest_hash"]
        manifest = json.loads(ctx.archive.get(manifest_hash))
        assert manifest["context"]["source_archive_hash"] == hashlib.sha256(rr_zip).hexdigest()
        off_dates = ctx.driver.read(
            'MATCH ()-[r:DIRECTOR_OF]->() WHERE r.source_id="offeneregister" '
            "RETURN r.recorded_at AS at",
            {},
            30,
        )
        assert off_dates and all(row["at"].year == 2018 for row in off_dates)
        assert (
            ctx.driver.read(
                'MATCH ()-[r]->() WHERE r.source_id="transparency_register" '
                'AND type(r)<>"LOBBIES_FOR" '
                "RETURN count(r) AS n",
                {},
                30,
            )[0]["n"]
            == 0
        )
        with make_api_client(neo4j_instance, tmp_path) as client:
            response = client.get(f"/entity/{rows[0]['id']}/neighbors")
            assert response.status_code == 200
            edge = next(
                n["edge"]
                for n in response.json()["neighbors"]
                if n["edge"]["assertion_id"] == rows[0]["p"]["assertion_id"]
            )
            assert edge["evidence_manifest_hash"] == manifest_hash
    finally:
        ctx.driver.close()


def test_default_gdelt_catchup_failure_and_resume_preserve_checkpoint(
    neo4j_instance, tmp_path, monkeypatch
):
    wipe_graph(neo4j_instance)
    from limes.pipeline import window

    original = window.resolve_window
    clock = [NOW]
    monkeypatch.setattr(window, "resolve_window", lambda *a, **kw: original(*a, **kw, now=clock[0]))
    captured = []

    def fetch(self, since, until):
        captured.append((since, until))
        return iter(())

    monkeypatch.setattr(GdeltAdapter, "fetch", fetch)
    ctx = build_run_context(_settings(neo4j_instance, tmp_path), needs_inference=False)
    spec = RunSpec(source_id="gdelt", mode="ingest")

    def failed(self, since, until):
        captured.append((since, until))
        raise SourceFetchError("missing export")

    try:
        monkeypatch.setattr(GdeltAdapter, "fetch", failed)
        with pytest.raises(SourceFetchError, match="missing export"):
            execute_run(spec, ctx)
        clock[0] += timedelta(hours=2)
        monkeypatch.setattr(GdeltAdapter, "fetch", fetch)
        first = execute_run(spec, ctx)
        assert captured[0] == captured[1]  # initial retry cannot slide the lookback start
        assert first.window_to < NOW
        monkeypatch.setattr(GdeltAdapter, "fetch", failed)
        with pytest.raises(SourceFetchError, match="missing export"):
            execute_run(spec, ctx)
        at = ctx.driver.read(
            'MATCH (s:Source {source_id:"gdelt"}) RETURN s.last_success_at AS at', {}, 30
        )[0]["at"]
        assert at == first.window_to
        monkeypatch.setattr(GdeltAdapter, "fetch", fetch)
        second = execute_run(spec, ctx)
        assert second.window_from == first.window_to
        assert captured[2] == captured[3]
        assert second.window_to > first.window_to
    finally:
        ctx.driver.close()
