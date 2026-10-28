"""Official-format coded observations survive the real pipeline, archive and API."""

import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from limes.composition import build_run_context
from limes.pipeline.run import RunSpec, execute_run
from tests.fixtures.graph_data import make_api_client, wipe_graph
from tests.integration.test_pipeline_run_unstructured import _settings


def test_upstream_export_pipeline_graph_archive_api(neo4j_instance, tmp_path, monkeypatch):
    wipe_graph(neo4j_instance)
    stream = io.BytesIO()
    data = (Path(__file__).parents[1] / "fixtures/gdelt/upstream.tsv").read_bytes()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("20261027183000.export.CSV", data)
    payload = stream.getvalue()
    monkeypatch.setattr("limes.sources.gdelt.fetch_bytes", lambda url, **kw: payload)
    ctx = build_run_context(_settings(neo4j_instance, tmp_path), needs_inference=False)
    try:
        slot = datetime(2026, 10, 27, 18, 30, tzinfo=UTC)
        spec = RunSpec(source_id="gdelt", mode="backfill", since=slot, until=slot)
        first = execute_run(spec, ctx)
        assert first.errors == 0 and first.assertions_written > 0
        second = execute_run(spec, ctx)
        assert second.assertions_written == 0
        assert second.assertions_skipped == first.assertions_written
        assert (
            ctx.driver.read("MATCH (e:ExtractionCacheEntry) RETURN count(e) AS c", {}, 30)[0]["c"]
            == 0
        )
        rows = ctx.driver.read(
            'MATCH (s)-[r]->() WHERE r.evidence_channel = "coded" '
            "RETURN s.entity_id AS id, properties(r) AS props",
            {},
            30,
        )
        assert len(rows) == first.assertions_written
        p = rows[0]["props"]
        assert ctx.archive.get(p["evidence_document_id"]) == payload
        source_row = data.decode().splitlines()[p["evidence_row"] - 1].split("\t")
        assert p["source_event_id"] == source_row[0]
        assert p["report_url"] == source_row[60]
        assert p["article_text_available"] is False
        assert p["evidence_member"] == "20261027183000.export.CSV"
        assert (
            ctx.driver.read(
                'MATCH (s:Source {source_id: "gdelt"}) RETURN s.last_success_at AS at', {}, 30
            )[0]["at"]
            == slot
        )
        # An older backfill must not move the durable checkpoint backward.
        execute_run(
            RunSpec(
                source_id="gdelt",
                mode="backfill",
                since=slot.replace(hour=18, minute=15),
                until=slot.replace(hour=18, minute=15),
            ),
            ctx,
        )
        assert (
            ctx.driver.read(
                'MATCH (s:Source {source_id: "gdelt"}) RETURN s.last_success_at AS at', {}, 30
            )[0]["at"]
            == slot
        )
        with make_api_client(neo4j_instance, tmp_path) as client:
            result = client.get(f"/entity/{rows[0]['id']}/neighbors")
            assert result.status_code == 200
            edge = next(
                n["edge"]
                for n in result.json()["neighbors"]
                if n["edge"]["assertion_id"] == p["assertion_id"]
            )
            for key in (
                "evidence_document_id",
                "evidence_row",
                "evidence_member",
                "source_event_id",
                "report_url",
                "article_text_available",
            ):
                assert edge[key] == p[key]
    finally:
        ctx.driver.close()
