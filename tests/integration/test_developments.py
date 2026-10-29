"""BE-44: proposal→denial→agreement→official award, both time axes and reviews.

Expectations are authored independently from the query implementation. Source
artifacts are loaded by production archive/document/claim/assertion writers.
No provider or paid model calls occur.
"""

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import SecretStr

from limes.archive.store import ArchiveStore
from limes.graph.loader import load, save_claims, save_document
from limes.news.models import ClaimQualifiers, TrackingRequest
from limes.news.store import TrackingStore
from limes.types import Assertion, DocumentPayload, Provenance, Validity
from tests.fixtures.graph_data import (
    endpoint,
    load_ontology_artifact,
    make_api_client,
    provisioned_driver,
    wipe_graph,
)


def instant(day):
    return datetime(2026, 10, day, tzinfo=UTC)


def test_developments_cross_source_history_and_operator_review(neo4j_instance, tmp_path):
    wipe_graph(neo4j_instance)
    driver = provisioned_driver(neo4j_instance)
    ontology = load_ontology_artifact()
    archive = ArchiveStore(tmp_path / "archive")
    subject = endpoint(
        "contract-investigation", "Contract", "Public contract", ("ted_notice_id", "T1")
    )
    company = endpoint("company-investigation", "Corporation", "Alpha", ("lei", "BE44-TEST-LEI"))
    tracking = TrackingStore(tmp_path / "jobs.db")
    tracking.save(
        TrackingRequest(investigation_id="award", title="Award", entity_ids=[company.entity_id])
    )
    load(driver, [], ontology, standalone_entities=[subject, company])
    for index, (modality, status, text) in enumerate(
        [
            ("proposed", "proposed", "Alpha proposes bidding for the public contract."),
            ("denied", "denied", "Alpha denies an agreement about the public contract."),
            ("reported", "completed", "Alpha reports agreement about the public contract."),
        ]
    ):
        key = archive.put("news", text.encode(), "text/plain")
        doc = DocumentPayload(
            content_hash=key,
            title=text,
            body=text,
            language="en",
            published_at=instant(index + 1),
            url=f"https://example.test/{index}",
            news_metadata={
                "investigation_id": "award",
                "publisher": "wire",
                "dispatch_id": str(index),
                "publication_known": True,
            },
        )
        save_document(driver, doc, ontology)
        claim = Assertion(
            assertion_id=f"news-{index}",
            subject=subject,
            relation="AWARDED_TO",
            object=company,
            validity=Validity(valid_from=instant(index + 1), recorded_at=instant(index + 2)),
            provenance=Provenance(
                source_id="news",
                source_trust=0.5,
                confidence=0.9,
                ontology_version=ontology.version,
                evidence_document_id=key,
                evidence_start=0,
                evidence_end=len(text),
            ),
            qualifiers=ClaimQualifiers(
                modality=modality,
                event_status=status,
                time_precision="day",
                event_candidate="Public contract award",
                attribution="Alpha",
            ),
        )
        save_claims(driver, [claim], doc, ontology)
        if index == 0:
            # Same report reused in another investigation, not independent confirmation.
            duplicate = doc.model_copy(
                update={"content_hash": archive.put("news", b"duplicate", "text/plain")}
            )
            save_document(driver, duplicate, ontology)
            save_claims(driver, [claim], duplicate, ontology)
    official_key = archive.put("ted", b'{"notice":"T1","award":"Alpha"}', "application/json")
    official = Assertion(
        assertion_id="official-award",
        subject=subject,
        relation="AWARDED_TO",
        object=company,
        validity=Validity(valid_from=instant(4), recorded_at=instant(6)),
        provenance=Provenance(
            source_id="ted",
            source_trust=0.95,
            confidence=1.0,
            ontology_version=ontology.version,
            evidence_document_id=official_key,
        ),
    )
    load(driver, [official], ontology)
    tracking.save(
        TrackingRequest(
            investigation_id="relation-case",
            title="Relation targets",
            assertion_ids=["official-award"],
        )
    )
    event = endpoint("coded-event", "Event", "Coded report")
    coded = Assertion(
        assertion_id="coded-actor",
        subject=company,
        relation="ACTOR_IN",
        object=event,
        validity=Validity(valid_from=instant(2), recorded_at=instant(3)),
        provenance=Provenance(
            source_id="gdelt",
            source_trust=0.5,
            confidence=1.0,
            ontology_version=ontology.version,
            evidence_channel="coded",
            source_event_id="123",
            evidence_document_id=archive.put("gdelt", b"coded export row", "text/plain"),
            evidence_member="export.CSV",
            evidence_row=3,
            article_text_available=False,
        ),
    )
    load(driver, [coded], ontology)
    try:
        with make_api_client(
            neo4j_instance,
            tmp_path,
            jobs_path=tmp_path / "jobs.db",
            operator_token=SecretStr("operator-test"),
        ) as client:
            path = "/news/investigations/award/developments"
            response = client.get(path)
            assert response.status_code == 200, response.text
            view = response.json()
            assert view["coverage"] == {
                "claim": 4,
                "assertion": 1,
                "coded_observation": 1,
                "entity_targets_requested": 1,
                "entity_targets_found": 1,
                "relation_targets_requested": 0,
                "relation_targets_found": 0,
            }
            assert not view["truncated"]
            empty = client.get(path, params={"as_of": "2025-01-01T00:00:00Z"}).json()
            assert empty["evidence"] == [] and empty["candidates"] == []
            assert any("No evidence matches" in note for note in empty["diagnosis"])
            relation_case = client.get("/news/investigations/relation-case/developments").json()
            assert relation_case["coverage"]["relation_targets_found"] == 1
            assert len(relation_case["evidence"]) == 6

            assert {
                e["properties"].get("modality") for e in view["evidence"] if e["kind"] == "claim"
            } == {"proposed", "denied", "reported"}
            assert all(c["decision"] == "unresolved" for c in view["candidates"])
            assert any(c["independence"] == "dependent" for c in view["candidates"])
            historical = client.get(path, params={"believed": instant(5).isoformat()}).json()
            assert historical["coverage"]["assertion"] == 0
            early = client.get(path, params={"as_of": instant(1).isoformat()}).json()
            assert early["coverage"]["claim"] == 2 and early["coverage"]["assertion"] == 0
            proposal = next(
                e for e in view["evidence"] if e["properties"].get("modality") == "proposed"
            )
            factual = next(e for e in view["evidence"] if e["kind"] == "assertion")
            payload = {
                "request_id": str(uuid4()),
                "left": proposal["evidence_id"],
                "right": factual["evidence_id"],
                "decision": "same_event",
                "assessment": "context",
                "independence": "unknown",
                "rationale": "Same notice identity; proposal is not award.",
            }
            reviews = "/news/investigations/award/event-match-reviews"
            assert client.post(reviews, json=payload).status_code == 403
            op = {"Authorization": "Bearer operator-test"}
            first = client.post(reviews, json=payload, headers=op)
            assert first.status_code == 200, first.text
            assert client.post(reviews, json=payload, headers=op).json() == first.json()
            assert (
                client.post(
                    reviews, json=payload | {"decision": "different_event"}, headers=op
                ).status_code
                == 409
            )
            revised = payload | {
                "request_id": str(uuid4()),
                "decision": "unresolved",
                "rationale": "Needs review",
            }
            assert client.post(reviews, json=revised, headers=op).status_code == 200
            now = client.get(path).json()
            assert len(now["reviews"]) == 2
            assert client.get(path, params={"believed": first.json()["recorded_at"]}).json()[
                "reviews"
            ] == [first.json()]
            dependent = next(c for c in view["candidates"] if c["independence"] == "dependent")
            rejected = payload | {
                "request_id": str(uuid4()),
                "left": dependent["left"],
                "right": dependent["right"],
                "independence": "independent",
            }
            assert client.post(reviews, json=rejected, headers=op).status_code == 422
            assert client.get(path, params={"limit": 1}).json()["truncated"]
            assert client.get(path, params={"as_of": "2026-10-01"}).status_code == 422
            assert client.get(path, params={"limit": 101}).status_code == 422
            assert client.get("/news/investigations/missing/developments").status_code == 404
            # No automatic merges or positive edges from qualified reports/reviews.
            assert (
                driver.read("MATCH ()-[r:AWARDED_TO]->() RETURN count(r) AS n", {}, 30)[0]["n"] == 1
            )
            archived = client.get("/news/assertions/official-award/evidence").json()
            assert archived["archive_status"] == "available"
            assert archived["preview"] == '{"notice":"T1","award":"Alpha"}'
            coded_view = next(e for e in view["evidence"] if e["kind"] == "coded_observation")
            assert coded_view["properties"]["evidence_row"] == 3
            assert not coded_view["properties"]["article_text_available"]
            # Real API → client mirrors → analyst network/timeline and evidence inspection.
            from limes_desktop.api.client import ApiClient
            from limes_desktop.views.developments import DevelopmentPanel
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance() or QApplication([])
            desktop_client = ApiClient("http://localhost")
            desktop_client.close()
            desktop_client._client = client
            panel = DevelopmentPanel(lambda: desktop_client, lambda action, done: done(action()))
            panel.set_case("award")
            panel.load()
            assert len(panel.rows) == 6
            assert panel.timeline.rowCount() == 12
            assert panel.scene.items()
            official_index = next(
                i for i, row in enumerate(panel.rows) if row["kind"] == "assertion"
            )
            panel.evidence_list.setCurrentRow(official_index)
            assert '"notice"' in panel.detail.toPlainText()
            assert "causation" in panel.detail.toPlainText()
            panel.valid.setText(instant(1).isoformat())
            assert panel.rows == []
            panel.load()
            assert len(panel.rows) == 2
            panel.close()
            app.processEvents()
            assert archive.get(official_key).startswith(b'{"notice"')
    finally:
        driver.close()
        wipe_graph(neo4j_instance)
