"""Current NRW formats through production fetch/archive/normalize/load and reads (BE-59)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import respx

from limes.composition import build_run_context
from limes.pipeline.run import RunSpec, execute_run
from limes.sources.gleif import first_page_url
from limes.sources.ted_search import SEARCH_URL
from tests.fixtures.graph_data import make_api_client, wipe_graph
from tests.integration.test_pipeline_run_structured import _settings

FIXTURES = Path(__file__).parents[1] / "fixtures"
NOW = datetime(2026, 11, 17, 12, tzinfo=UTC)


@respx.mock
def test_current_structured_sources_preserve_archive_graph_api(
    neo4j_instance, tmp_path, monkeypatch
):
    wipe_graph(neo4j_instance)
    gleif_page = (FIXTURES / "gleif_api/page_with_parents.json").read_bytes()
    ted_page = json.loads((FIXTURES / "ted_search/results_2025.json").read_text())
    ted_page.pop("iterationNextToken", None)
    ted_page["totalNoticeCount"] = len(ted_page["notices"])
    ted_payload = json.dumps(ted_page).encode()
    respx.get(first_page_url()).respond(200, content=gleif_page)
    respx.post(SEARCH_URL).respond(200, content=ted_payload)
    monkeypatch.setattr(
        "limes.sources.transparency_register.fetch_bytes",
        lambda *a, **kw: (FIXTURES / "ingest47/transparency.xml").read_bytes(),
    )
    for module in ("gleif", "ted_search"):
        monkeypatch.setattr(f"limes.sources.{module}.now_utc", lambda: NOW)
    ctx = build_run_context(_settings(neo4j_instance, tmp_path), needs_inference=False)
    try:
        for source in ["gleif", "transparency_register", "ted"]:
            spec = RunSpec(source_id=source, mode="ingest", since=datetime(2025, 6, 1, tzinfo=UTC),
                           until=datetime(2025, 6, 2, tzinfo=UTC))
            first = execute_run(spec, ctx)
            assert first.errors == 0 and first.assertions_written > 0, source
            second = execute_run(spec, ctx)
            assert second.errors == 0 and second.assertions_written == 0, source
        for payload in [gleif_page, ted_payload]:
            assert ctx.archive.get(hashlib.sha256(payload).hexdigest()) == payload
        rows = ctx.driver.read(
            "MATCH (s)-[r:DIRECTLY_CONSOLIDATED_BY]->(o) "
            "RETURN s.entity_id AS id, properties(r) AS p ORDER BY id",
            {},
            30,
        )
        assert [row["id"] for row in rows] == ["lei:213800128CEQCC37AF74",
                                              "lei:2138001EMROZHYY91387"]
        assert rows[0]["p"]["ontology_version"] == "1.4.0"
        assert ctx.archive.get(rows[0]["p"]["evidence_document_id"]) == gleif_page
        awarded = ctx.driver.read(
            "MATCH (:Contract)-[r:AWARDED_TO]->(c:Corporation) RETURN c.label AS label", {}, 30
        )
        assert [row["label"] for row in awarded] == ["Bosch Sicherheitssysteme"]
        regions = ctx.driver.read(
            "MATCH (:Location)-[:LOCATED_IN]->(n:AdministrativeRegion) "
            "RETURN DISTINCT n.entity_id AS id",
            {},
            30,
        )
        assert regions and all(row["id"].startswith("nuts_code:DEA") for row in regions)
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
            assert any(
                n["edge"]["assertion_id"] == rows[0]["p"]["assertion_id"]
                for n in response.json()["neighbors"]
            )
    finally:
        ctx.driver.close()
