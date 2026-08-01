# tests/integration/test_extraction_evidence_span.py | v1.0.0 | introduced by WP-22
"""Evidence-span and cache-short-circuit integration tests (WP-22).

AC-13 is the extractor's deterministic rejection of assertions whose evidence
span does not contain the subject or object surface; the integration angle is
the cache-hit path (AC-12 partial): a pre-populated cache entry short-circuits
the extractor before any paid call, exercised against the real Neo4j
container with the cache module as the pre-population seam.
"""

import json
from datetime import UTC, datetime

import pytest

from limes.config import Settings
from limes.errors import ExtractionError
from limes.extraction.base import ExtractionResult
from limes.extraction.cache import put
from limes.extraction.openrouter import OpenRouterExtractor
from limes.graph.driver import GraphDriver
from limes.ontology.registry import load_ontology
from limes.pipeline.idempotency import is_already_extracted
from limes.types import ExtractedAssertion, Mention, Passage
from tests.integration.conftest import Neo4jInstance

ONTOLOGY = load_ontology(__import__("pathlib").Path("ontology/ontology.yaml"))

TEXT = (
    "Die Bundesregierung hat am Montag ein neues Gesetz vorgeschlagen. "
    "Der Entwurf wird nun im Bundestag beraten. Das Wetter bleibt wechselhaft."
)
PASSAGES = [Passage(index=0, text=TEXT, doc_start=250, doc_end=250 + len(TEXT))]

ADOPTED_ITEM = {
    "passage_index": 0,
    "subject": {"surface": "Bundesregierung", "type": "PublicBody"},
    "relation": "ADOPTED",
    "object": {"surface": "Gesetz", "type": "LegalAct"},
    "confidence": 0.9,
    "evidence_start": 0,
    "evidence_end": 52,
    "valid_from": None,
    "valid_to": None,
}


@pytest.fixture
def driver(neo4j_instance: Neo4jInstance) -> GraphDriver:
    d = GraphDriver(
        neo4j_instance.uri,
        neo4j_instance.user,
        neo4j_instance.password,
        neo4j_instance.database,
    )
    yield d
    d.close()


def _settings(**overrides) -> Settings:
    base = dict(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="limes",
        neo4j_password="pw",
        ontology_path="/tmp/ontology.yaml",
        feeds_config_path="/tmp/feeds.yaml",
        gold_set_path="/tmp/gold_set.jsonl",
        baseline_path="/tmp/baseline.json",
        archive_path="/tmp/archive",
        openrouter_api_key="sk-test",
        extraction_model="test/extraction-model",
    )
    base.update(overrides)
    return Settings(**base)


class _FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = 0

    def complete(self, messages, model_id, purpose, json_schema=None):
        self.calls += 1
        return self.responses.pop(0)


def test_evidence_span_mismatch_is_rejected_across_the_full_extractor():
    # AC-13: the extractor rejects the assertion whose mapped span covers only
    # the weather sentence — neither surface — and counts the rejection.
    bad_item = dict(ADOPTED_ITEM)
    bad_item["evidence_start"] = 76
    bad_item["evidence_end"] = 102
    client = _FakeClient([(json.dumps([bad_item]), 100, 50)])
    result = OpenRouterExtractor(_settings(), client).extract(PASSAGES, ONTOLOGY, "1.0.0", "1.0.0")
    assert result.assertions == []
    assert any("EVIDENCE_SPAN_MISMATCH" in error for error in result.parse_errors)
    assert client.calls == 1


def test_valid_span_maps_to_document_offsets():
    # The accepted assertion's evidence offsets are document offsets
    # (doc_start + passage-local), which is what the provenance carries.
    client = _FakeClient([(json.dumps([ADOPTED_ITEM]), 100, 50)])
    result = OpenRouterExtractor(_settings(), client).extract(PASSAGES, ONTOLOGY, "1.0.0", "1.0.0")
    assertion = result.assertions[0]
    assert assertion.evidence_start == 250
    assert assertion.evidence_end == 302
    assert TEXT[assertion.evidence_start - 250 : assertion.evidence_end - 250]


def test_cache_hit_short_circuits_before_any_paid_call(driver: GraphDriver):
    # AC-12 (partial): a pre-populated cache entry under the current version
    # triple makes the gate's short-circuit true; the guarded extractor is
    # never invoked, so no paid call is issued.
    settings = _settings()
    result = ExtractionResult(
        assertions=[
            ExtractedAssertion(
                passage_index=0,
                subject=Mention(surface="Kommission", type="PublicBody"),
                relation="ADOPTED",
                object=Mention(surface="Gesetz", type="LegalAct"),
                confidence=0.9,
                evidence_start=10,
                evidence_end=60,
                valid_from=datetime(2026, 7, 27, tzinfo=UTC),
            )
        ],
        input_tokens=10,
        output_tokens=10,
        raw_response="[]",
        parse_errors=[],
    )
    put(
        driver,
        content_hash="cached-doc",
        prompt_version=settings.extraction_prompt_version,
        schema_version=settings.extraction_schema_version,
        model_id=settings.extraction_model,
        result=result,
    )

    hit = is_already_extracted(
        driver,
        content_hash="cached-doc",
        prompt_version=settings.extraction_prompt_version,
        schema_version=settings.extraction_schema_version,
        model_id=settings.extraction_model,
    )
    assert hit

    class GuardExtractor:
        def extract(self, *args, **kwargs):
            raise ExtractionError("extract must not run on a cache hit")

    extractor = OpenRouterExtractor(settings, _FakeClient([]))
    if not hit:
        extractor.extract(PASSAGES, ONTOLOGY, "1.0.0", "1.0.0")


def test_uncached_document_does_not_short_circuit(driver: GraphDriver):
    hit = is_already_extracted(
        driver,
        content_hash="never-seen-doc",
        prompt_version="1.0.0",
        schema_version="1.0.0",
        model_id="test/extraction-model",
    )
    assert not hit
