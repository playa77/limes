"""Investigation → dynamic feeds → shared extraction/resolver → claim graph → API.

The independent behavioral expectations are proposal/denial, unknown dates,
idempotent replay, retained versions, source evidence and absence of factual edges.
All provider/model transports are mocked. Neo4j is disposable.
"""

import json
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace

import respx
from httpx import Response
from pydantic import SecretStr

from limes.composition import build_run_context
from limes.extraction.base import ExtractionResult
from limes.graph.loader import load
from limes.news.models import TrackingRequest
from limes.news.store import TrackingStore
from limes.news.targets import queries_for
from limes.pipeline.run import RunSpec, execute_run
from limes.types import EntityEndpoint, RawRecord
from tests.fixtures.graph_data import make_api_client, wipe_graph
from tests.integration.test_pipeline_run_unstructured import (
    CATALOGUE,
    CATALOGUE_URL,
    COMPLETIONS_URL,
    OBJECT_LEI,
    SUBJECT_LEI,
    USAGE,
    _FakeNer,
    _settings,
)


def test_dynamic_news_qualified_roundtrip_and_retry(neo4j_instance, tmp_path, monkeypatch):
    wipe_graph(neo4j_instance)
    monkeypatch.setattr("limes.composition.spacy.load", lambda _: _FakeNer())
    settings = _settings(
        neo4j_instance,
        tmp_path,
        extraction_prompt_version="2.0.0",
        extraction_schema_version="2.0.0",
        jobs_path=tmp_path / "jobs.db",
    )
    ctx = build_run_context(settings, needs_inference=True)
    subject = EntityEndpoint(
        entity_id=f"lei:{SUBJECT_LEI}",
        type="Corporation",
        label=SUBJECT_LEI,
        deterministic_key=("lei", SUBJECT_LEI),
    )
    object_ = EntityEndpoint(
        entity_id=f"lei:{OBJECT_LEI}",
        type="Corporation",
        label=OBJECT_LEI,
        deterministic_key=("lei", OBJECT_LEI),
    )
    load(ctx.driver, [], ctx.ontology, standalone_entities=[subject, object_])
    tracking = TrackingStore(settings.jobs_path)
    request = TrackingRequest(
        investigation_id="case", title="Supply investigation", entity_ids=[subject.entity_id]
    )
    tracking.save(request)
    adapter = ctx.registry.get("news")
    adapter.configure("case", 1, queries_for(ctx.driver, request))
    phase = ["proposes"]

    def fetch(url, **kwargs):
        return (
            f'<rss version="2.0"><channel><title>Test wire</title><link>https://example.org</link>'
            f"<description>Independent test feed</description><item><guid>dispatch-1</guid>"
            f"<title>{SUBJECT_LEI} {phase[0]} to supply {OBJECT_LEI}.</title>"
            '<link>https://example.org/report</link><source url="https://example.org">'
            "Test wire</source></item></channel></rss>"
        ).encode()

    monkeypatch.setattr("limes.sources.news.fetch_bytes", fetch)

    def completion(request):
        body = json.loads(request.content)
        message = body["messages"][0]["content"]
        verb = "proposes" if "proposes to supply" in message else "denies"
        text = f"{SUBJECT_LEI} {verb} to supply {OBJECT_LEI}."
        result = [
            {
                "passage_index": 0,
                "subject": {
                    "surface": SUBJECT_LEI,
                    "type": "Corporation",
                    "deterministic_key": ["lei", SUBJECT_LEI],
                },
                "object": {
                    "surface": OBJECT_LEI,
                    "type": "Corporation",
                    "deterministic_key": ["lei", OBJECT_LEI],
                },
                "relation": "SUPPLIES",
                "confidence": 0.91,
                "evidence_start": 0,
                "evidence_end": len(text),
                "qualifiers": {
                    "modality": "proposed" if verb == "proposes" else "denied",
                    "attribution": SUBJECT_LEI,
                    "assessment": "unassessed",
                    "event_status": "completed",
                    "time_precision": "unknown",
                },
            }
        ]
        return Response(
            200, json={"choices": [{"message": {"content": json.dumps(result)}}], "usage": USAGE}
        )

    spec = RunSpec(source_id="news", mode="ingest")
    try:
        with respx.mock(assert_all_called=False) as mock:
            mock.get(CATALOGUE_URL).respond(200, json=CATALOGUE)
            calls = mock.post(COMPLETIONS_URL).mock(side_effect=completion)
            first = execute_run(spec, ctx)
            assert first.errors == 0 and first.assertions_written == 2
            # DE/EN feed identities stay separate while their shared dispatch stays dependent.
            assert calls.call_count == 2
            execute_run(spec, ctx)
            assert calls.call_count == 2  # Shared extraction cache prevents repeat paid calls.
            phase[0] = "denies"
            second = execute_run(spec, ctx)
            assert second.errors == 0 and second.assertions_written == 2
        assert (
            ctx.driver.read("MATCH ()-[r:SUPPLIES]->() RETURN count(r) AS n", {}, 30)[0]["n"] == 0
        )
        claims = ctx.driver.read("MATCH (c:NewsClaim) RETURN properties(c) AS c", {}, 30)
        assert {r["c"]["modality"] for r in claims} == {"proposed", "denied"}
        assert {r["c"]["event_status"] for r in claims} == {"proposed", "denied"}
        assert all(r["c"].get("valid_from") is None for r in claims)
        assert len({r["c"]["syndication_key"] for r in claims}) == 1
        docs = ctx.driver.read("MATCH (d:NewsDocument) RETURN properties(d) AS d", {}, 30)
        assert len(docs) == 4
        assert sum(bool(r["d"].get("previous_document_id")) for r in docs) >= 2
        for row in docs:
            doc = row["d"]
            archived = json.loads(ctx.archive.get(doc["document_id"]))
            assert archived["dispatch_id"] == "dispatch-1"
            assert ctx.archive.get(doc["feed_hash"]).startswith(b"<rss")
            assert doc.get("published_at") is None
        # Failed/unqualified re-extraction cannot retract valid prior claims.
        bad = SimpleNamespace(
            model_id="test/extractor",
            extract=lambda *a: ExtractionResult(
                assertions=[],
                input_tokens=0,
                output_tokens=0,
                raw_response="",
                parse_errors=["SCHEMA"],
            ),
        )
        bad_ctx = replace(ctx, extractor=bad)
        failed = execute_run(RunSpec(source_id="news", mode="reextract"), bad_ctx)
        assert failed.errors > 0
        assert (
            ctx.driver.read(
                "MATCH (c:NewsClaim) WHERE c.retracted_at IS NULL RETURN count(c) AS n", {}, 30
            )[0]["n"]
            == 4
        )
        # API surfaces include auth, strict filtering, evaluation pool and exact evidence.
        with make_api_client(
            neo4j_instance,
            tmp_path,
            jobs_path=settings.jobs_path,
            operator_token=SecretStr("operator-test"),
        ) as client:
            response = client.get("/news/claims?investigation_id=case&modality=denied")
            assert response.status_code == 200 and len(response.json()) == 2
            claim = response.json()[0]
            evidence = client.get("/news/documents/" + claim["evidence_document_id"]).json()
            assert "denies" in evidence["body"][claim["evidence_start"] : claim["evidence_end"]]
            assert evidence["article_text_available"] is False
            assert len(client.get("/news/evaluation").json()) == 4
            payload = request.model_dump(mode="json")
            assert client.put("/news/investigations/case", json=payload).status_code == 403
            op = {"Authorization": "Bearer operator-test"}
            assert (
                client.put("/news/investigations/case", json=payload, headers=op).status_code == 200
            )
            assert (
                client.put(
                    "/news/documents/" + claim["evidence_document_id"] + "/review",
                    headers=op,
                    json={
                        "expected_modality": "denied",
                        "expected_event_status": "denied",
                        "expected_time_precision": "unknown",
                        "notes": "Verified denial against supplied sentence.",
                    },
                ).status_code
                == 200
            )
            # Archived successful empty replacement retracts only that document's
            # extracted claims, preserving other dispatch versions and sources.
            archived_doc = docs[0]["d"]
            adapter.replay_records = [
                RawRecord(
                    payload=ctx.archive.get(archived_doc["document_id"]),
                    content_type="application/json",
                    fetched_at=datetime.now(UTC),
                    acquisition_context=json.loads(archived_doc["metadata"]),
                )
            ]
            empty = SimpleNamespace(
                model_id="test/extractor",
                extract=lambda *a: ExtractionResult(
                    assertions=[],
                    input_tokens=0,
                    output_tokens=0,
                    raw_response="[]",
                    parse_errors=[],
                ),
            )
            replacement = execute_run(
                RunSpec(source_id="news", mode="reextract"), replace(ctx, extractor=empty)
            )
            assert replacement.errors == 0
            assert (
                ctx.driver.read(
                    "MATCH (c:NewsClaim) WHERE c.retracted_at IS NULL RETURN count(c) AS n", {}, 30
                )[0]["n"]
                == 3
            )
    finally:
        ctx.driver.close()
