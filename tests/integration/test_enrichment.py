"""BE-46 archive→pipeline→graph→API plus existing desktop evidence compatibility.

Provider and model calls are mocked; source fixtures are independent original
responses. Registry facts, failed sections, source versions and unknown identities
must coexist. This test owns and cleans its disposable graph.
"""

import json
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import uuid4

from limes.composition import build_run_context
from limes.enrichment.models import EnrichmentSelection
from limes.enrichment.service import prepare_targets
from limes.errors import SourceFetchError
from limes.graph.loader import load
from limes.pipeline.run import RunSpec, execute_run
from limes.resolution.resolve import reviewed_corporation
from tests.fixtures.enrichment_data import FIXTURES, record, target
from tests.fixtures.graph_data import (
    api_settings,
    assertion,
    endpoint,
    make_api_client,
    wipe_graph,
)


def test_company_enrichment_pipeline_history_api_and_desktop(neo4j_instance, tmp_path, monkeypatch):
    from limes_desktop.api.client import ApiClient
    from limes_desktop.api.models import EntityDetail
    from limes_desktop.state import SessionState
    from limes_desktop.views.entity import EntityView
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    wipe_graph(neo4j_instance)
    settings = api_settings(neo4j_instance, tmp_path).model_copy(
        update={"jobs_path": tmp_path / "jobs.db"}
    )
    ctx = build_run_context(settings, needs_inference=False)
    try:
        company = endpoint("be46-siemens", "Corporation", "Registry Siemens", ("lei", "BE46-LEI"))
        person = endpoint("be46-director", "Person", "Registry Director")
        old = assertion(
            "be46-registry-director",
            person,
            "DIRECTOR_OF",
            company,
            source_id="offeneregister",
            valid_from=datetime(2020, 1, 1, tzinfo=UTC),
        )
        old.provenance.ontology_version = "1.1.0"
        load(ctx.driver, [old], ctx.ontology)
        selected = prepare_targets(
            ctx.driver, [target(isin="DE0007236101").selection], "yahoo_finance"
        )
        yahoo = ctx.registry.get("yahoo_finance")
        yahoo.configure(selected)
        payload = (FIXTURES / "yahoo_SIE.DE.json").read_bytes()
        transport = Mock()
        transport.get.return_value = (payload, "available")
        yahoo.transport = transport
        first = execute_run(RunSpec(source_id="yahoo_finance", mode="ingest"), ctx)
        assert first.errors == 0 and first.assertions_written > 0
        replay = execute_run(RunSpec(source_id="yahoo_finance", mode="ingest"), ctx)
        assert replay.errors == 0 and replay.assertions_written == 0
        checkpoint = ctx.driver.read(
            "MATCH (s:Source {source_id:'yahoo_finance'}) RETURN s.last_success_at AS at", {}, 30
        )[0]["at"]
        transport.get.side_effect = lambda symbol, module: (
            (_ for _ in ()).throw(SourceFetchError("mock provider failure"))
            if module == "fundOwnership"
            else (payload, "available")
        )
        partial = execute_run(RunSpec(source_id="yahoo_finance", mode="ingest"), ctx)
        assert partial.errors == 1
        assert (
            ctx.driver.read(
                "MATCH (s:Source {source_id:'yahoo_finance'}) RETURN s.last_success_at AS at",
                {},
                30,
            )[0]["at"]
            == checkpoint
        )
        transport.get.side_effect = None
        transport.get.return_value = (payload, "available")
        assert execute_run(RunSpec(source_id="yahoo_finance", mode="ingest"), ctx).errors == 0
        updated = json.loads(payload)
        updated["quoteSummary"]["result"][0]["institutionOwnership"]["ownershipList"][0][
            "position"
        ] = {"raw": 60000}
        updated_payload = json.dumps(updated).encode()
        transport.get.side_effect = None
        transport.get.return_value = (updated_payload, "available")
        assert execute_run(RunSpec(source_id="yahoo_finance", mode="ingest"), ctx).errors == 0
        malformed = json.loads(updated_payload)
        malformed["quoteSummary"]["result"][0]["assetProfile"]["fullTimeEmployees"] = "bad type"
        malformed_payload = json.dumps(malformed).encode()
        transport.get.side_effect = lambda symbol, module: (
            malformed_payload if module == "assetProfile" else updated_payload,
            "available",
        )
        invalid = execute_run(RunSpec(source_id="yahoo_finance", mode="ingest"), ctx)
        assert invalid.errors == 1 and invalid.finished_at is not None
        wiki = ctx.registry.get("wikipedia")
        wiki.configure(selected)
        qid_payload = json.dumps(
            {
                "entities": {
                    "Q81230": {
                        "id": "Q81230",
                        "sitelinks": {
                            "dewiki": {"title": "Siemens"},
                            "enwiki": {"title": "Siemens"},
                        },
                    }
                }
            }
        ).encode()
        monkeypatch.setattr(
            wiki,
            "_get",
            Mock(
                side_effect=[
                    qid_payload,
                    (FIXTURES / "wikipedia_de.json").read_bytes(),
                    (FIXTURES / "wikipedia_en.json").read_bytes(),
                ]
            ),
        )
        assert execute_run(RunSpec(source_id="wikipedia", mode="ingest"), ctx).errors == 0
        mapped = reviewed_corporation(ctx.driver, "Q81230", "Siemens")
        assert mapped.endpoint.entity_id == company.entity_id
        assert ctx.driver.read("MATCH (n:Corporation) RETURN count(n) AS n", {}, 30)[0]["n"] == 1

        # Wikipedia context also serves non-agent entities; Yahoo remains corporation-only.
        country = endpoint("iso2:DE", "Country", "Germany", ("iso2", "DE"))
        load(ctx.driver, [], ctx.ontology, standalone_entities=[country])
        country_targets = prepare_targets(
            ctx.driver,
            [
                EnrichmentSelection(
                    entity_id=country.entity_id,
                    qid="Q183",
                    evidence_url="https://www.wikidata.org/wiki/Q183",
                    rationale="Reviewed country identity; no company/name-based merge.",
                )
            ],
            "wikipedia",
        )
        wiki.configure(country_targets)
        country_raw = record(
            "wikipedia",
            "en",
            language="en",
            selected=country_targets[0],
            payload=(FIXTURES / "wikipedia_country_en.json").read_bytes(),
        )
        monkeypatch.setattr(wiki, "fetch", lambda since, until: iter([country_raw]))
        assert execute_run(RunSpec(source_id="wikipedia", mode="ingest"), ctx).errors == 0
        with make_api_client(
            neo4j_instance, tmp_path, operator_token="operator", jobs_path=tmp_path / "jobs.db"
        ) as client:
            response = client.get("/entity/be46-siemens/enrichment", params={"limit": 100})
            assert response.status_code == 200
            desktop_client = ApiClient("http://localhost")
            desktop_client.close()
            desktop_client._client = client
            result = desktop_client.enrichment("be46-siemens", limit=100)

            country_result = desktop_client.enrichment("iso2:DE")
            assert country_result.snapshots[0]["target_id"] == "iso2:DE"
            assert country_result.snapshots[0]["observations"][0]["page_id"] == 11867
            assert country_result.snapshots[0]["observations"][0]["wikidata_qid"] == "Q183"
            holding_snapshots = [
                s for s in result.snapshots if s["section"] == "institutionOwnership"
            ]
            shares = {s["observations"][0]["shares"] for s in holding_snapshots}
            assert shares == {53457, 60000}
            assert any(
                s["section"] == "fundOwnership" and s["status"] == "failed"
                for s in result.snapshots
            )
            assert all(s["complete"] is False for s in result.snapshots)
            assert any(
                s["section"] == "assetProfile" and s["status"] == "failed" for s in result.snapshots
            )
            recovered = desktop_client.enrichment("be46-siemens", section="fundOwnership", limit=1)
            assert recovered.snapshots[0]["status"] == "available"
            assert (
                recovered.snapshots[0]["last_checked_at"] >= recovered.snapshots[0]["recorded_at"]
            )
            context = next(s for s in result.snapshots if s["section"] == "de")
            assert context["observations"][0]["revision_id"] == 271660062
            assert context["observations"][0]["body"]
            observation_id = context["observations"][0]["entity_id"]
            detail = EntityDetail.from_api(client.get(f"/entity/{observation_id}").json())
            view = EntityView(SessionState())
            view.show_entity(detail)
            rendered = [
                view.property_table.item(i, 1).text() for i in range(view.property_table.rowCount())
            ]
            assert "271660062" in rendered
            assert any("creativecommons.org" in v for v in rendered)
            view.close()
            # Evidence edges carry the unchanged original archive hash and source section.
            snapshot_id = holding_snapshots[0]["entity_id"]
            edge = client.get(f"/entity/{snapshot_id}/neighbors").json()["neighbors"][0]["edge"]
            preview = client.get(f"/news/assertions/{edge['assertion_id']}/evidence").json()
            assert preview["archive_status"] == "available"
            assert preview["provenance"]["evidence_member"] == "institutionOwnership"
            assert ctx.archive.get(preview["provenance"]["evidence_document_id"]) in (
                payload,
                updated_payload,
            )
            history = client.get(
                "/entity/be46-siemens/enrichment", params={"believed": "2000-01-01T00:00:00Z"}
            ).json()
            assert not history["snapshots"] and history["diagnosis"]
            limited = client.get("/entity/be46-siemens/enrichment", params={"limit": 1}).json()
            assert limited["truncated"] is True
            assert (
                client.get(
                    "/entity/be46-siemens/enrichment", headers={"Authorization": ""}
                ).status_code
                == 401
            )
            job = {
                "request_id": str(uuid4()),
                "command": "enrich",
                "source": "wikipedia",
                "selections": [target().selection.model_dump()],
            }
            assert client.post("/operations/jobs", json=job).status_code == 403
            assert (
                client.post(
                    "/operations/jobs", json=job, headers={"Authorization": "Bearer operator"}
                ).status_code
                == 202
            )
            schema = client.get("/builder/schema").json()
            assert "HAS_ENRICHMENT" in str(schema) and "EnrichmentObservation" in str(schema)
            registry = client.get("/entity/be46-director/neighbors").json()["neighbors"]
            prior = next(
                n["edge"] for n in registry if n["edge"]["assertion_id"] == old.assertion_id
            )
            assert prior["ontology_version"] == "1.1.0" and prior["valid_to"] is None
        assert app is not None
    finally:
        ctx.driver.close()
        wipe_graph(neo4j_instance)


def test_wikipedia_shared_resolution_cache_and_exact_revision_claims(
    neo4j_instance, tmp_path, monkeypatch
):
    from types import SimpleNamespace

    from limes.extraction.base import ExtractionResult
    from limes.news.models import ClaimQualifiers
    from limes.pipeline.gate import GateContext
    from limes.types import ExtractedAssertion, Mention

    wipe_graph(neo4j_instance)
    settings = api_settings(neo4j_instance, tmp_path).model_copy(
        update={
            "extraction_model": "mock/wikipedia",
            "embedding_model": "mock/embed",
            "adjudication_model": "mock/adjudicator",
            "extraction_prompt_version": "2.0.0",
            "extraction_schema_version": "2.0.0",
        }
    )
    ctx = build_run_context(settings, needs_inference=False)
    try:
        load(ctx.driver, [], ctx.ontology, standalone_entities=[target().entity])
        wiki = ctx.registry.get("wikipedia")
        wiki.configure([target()], extract=True)
        raw = record("wikipedia", "en", language="en")
        doc = wiki.normalize(raw).document
        start = min(doc.body.index("Siemens"), doc.body.index("Munich"))
        end = max(
            doc.body.index("Siemens") + len("Siemens"), doc.body.index("Munich") + len("Munich")
        )
        extracted = ExtractedAssertion(
            passage_index=0,
            subject=Mention(
                surface="Siemens", type="Corporation", deterministic_key=("wikidata_qid", "Q81230")
            ),
            relation="HEADQUARTERED_IN",
            object=Mention(
                surface="Munich",
                type="Location",
                deterministic_key=("coordinate_hash", "be46-munich"),
            ),
            confidence=0.9,
            evidence_start=start,
            evidence_end=end,
            qualifiers=ClaimQualifiers(modality="reported", time_precision="unknown"),
        )
        extractor = Mock(model_id="mock/wikipedia")
        extractor.extract.return_value = ExtractionResult(
            assertions=[extracted],
            input_tokens=1,
            output_tokens=1,
            raw_response="mock",
            parse_errors=[],
        )

        def ner(text):
            return SimpleNamespace(
                ents=[
                    SimpleNamespace(
                        text=word,
                        label_="ORG",
                        start_char=text.index(word),
                        end_char=text.index(word) + len(word),
                    )
                    for word in ("Siemens", "Munich")
                ]
            )

        client = Mock()
        client.embed.side_effect = lambda labels, model: [[1.0] + [0.0] * 1023 for _ in labels]
        ctx = replace(
            ctx,
            extractor=extractor,
            client=client,
            gate=GateContext(settings=settings, driver=ctx.driver, nlp_de=ner, nlp_en=ner),
        )
        monkeypatch.setattr(wiki, "fetch", lambda since, until: iter([raw]))
        first = execute_run(RunSpec(source_id="wikipedia", mode="ingest"), ctx)
        assert first.errors == 0
        second = execute_run(RunSpec(source_id="wikipedia", mode="ingest"), ctx)
        assert second.errors == 0 and extractor.extract.call_count == 1
        assert (
            ctx.driver.read("MATCH (c:EnrichmentCheck) RETURN count(c) AS n", {}, 30)[0]["n"] == 1
        )
        variant = json.loads(raw.payload)
        next(iter(variant["query"]["pages"].values()))["pageprops"]["unrelated"] = "updated"
        variant_raw = raw.model_copy(update={"payload": json.dumps(variant).encode()})
        monkeypatch.setattr(wiki, "fetch", lambda since, until: iter([variant_raw]))
        assert execute_run(RunSpec(source_id="wikipedia", mode="ingest"), ctx).errors == 0
        assert extractor.extract.call_count == 1
        monkeypatch.setattr(wiki, "fetch", lambda since, until: iter([raw]))
        rows = ctx.driver.read(
            "MATCH (c:NewsClaim {source_id:'wikipedia'}) RETURN properties(c) AS c", {}, 30
        )
        assert len(rows) == 1
        claim = rows[0]["c"]
        assert claim["subject_id"] == "be46-siemens" and claim["modality"] == "reported"
        assert doc.body[claim["evidence_start"] : claim["evidence_end"]] == doc.body[start:end]
        assert ctx.archive.get(claim["evidence_document_id"]) == raw.payload
        assert claim.get("valid_from") is None
        assert (
            ctx.driver.read("MATCH ()-[r:HEADQUARTERED_IN]->() RETURN count(r) AS n", {}, 30)[0][
                "n"
            ]
            == 0
        )
        # An old unqualified output cannot turn context into a factual edge or replace evidence.
        extractor.extract.return_value.assertions = [
            extracted.model_copy(update={"qualifiers": None})
        ]
        assert execute_run(RunSpec(source_id="wikipedia", mode="reextract"), ctx).errors == 1
        assert (
            ctx.driver.read(
                "MATCH (c:NewsClaim) WHERE c.retracted_at IS NULL RETURN count(c) AS n", {}, 30
            )[0]["n"]
            == 1
        )
        extractor.extract.return_value.assertions = []
        assert execute_run(RunSpec(source_id="wikipedia", mode="reextract"), ctx).errors == 0
        assert (
            ctx.driver.read(
                "MATCH (o:EnrichmentObservation {kind:'encyclopedia_revision'}) "
                "RETURN count(o) AS n",
                {},
                30,
            )[0]["n"]
            == 1
        )
    finally:
        ctx.driver.close()
        wipe_graph(neo4j_instance)
