# tests/acceptance/_resolution_support.py | v1.0.0 | introduced by WP-39
"""Shared resolution harness for the acceptance suite (AC-16, AC-17,
AC-19, AC-43): the counting driver, the mock governor, the fake
enrichment adapter, and the RunContext builder the four-band tests
exercise `resolve_assertions` with. Mirrors the integration suite's
harness so the acceptance tests assert the same properties at the same
seam.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from httpx import Response

from limes.archive.store import ArchiveStore
from limes.config import Settings
from limes.extraction.openrouter_client import OpenRouterClient
from limes.graph.driver import GraphDriver
from limes.ontology.registry import load_ontology
from limes.resolution import resolve
from limes.resolution.resolve import RunContext
from limes.sources.registry import SourceRegistry
from limes.sources.wikidata import WikidataAdapter, WikidataMatch
from limes.types import (
    Assertion,
    DocumentPayload,
    EntityEndpoint,
    ExtractedAssertion,
    Mention,
    Provenance,
    Validity,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"

BASE_URL = "https://openrouter.test/api/v1"
CATALOGUE_URL = f"{BASE_URL}/models"
EMBED_URL = f"{BASE_URL}/embeddings"
COMPLETIONS_URL = f"{BASE_URL}/chat/completions"

EMBED_MODEL = "test/embed"
ADJUDICATE_MODEL = "test/adjudicator"

NOW = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)

USAGE = {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70}

CATALOGUE = {
    "data": [
        {"id": EMBED_MODEL, "pricing": {"prompt": "0.000000100", "completion": "0.000000100"}},
        {
            "id": ADJUDICATE_MODEL,
            "pricing": {"prompt": "0.000000100", "completion": "0.000000100"},
        },
    ]
}


def settings_for(tmp_path: Path, **overrides) -> Settings:
    base = dict(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="limes",
        neo4j_password="pw",
        ontology_path=ONTOLOGY_PATH,
        feeds_config_path=REPO_ROOT / "ontology" / "feeds.yaml",
        gold_set_path=tmp_path / "gold_set.jsonl",
        baseline_path=tmp_path / "baseline.json",
        archive_path=tmp_path / "archive",
        openrouter_api_key="sk-test",
        openrouter_base_url=BASE_URL,
        embedding_model=EMBED_MODEL,
        adjudication_model=ADJUDICATE_MODEL,
        embedding_dimensions=1024,
        http_timeout_seconds=10,
    )
    base.update(overrides)
    return Settings(**base)


class MockGovernor:
    """Records check/commit calls like the unit-test governor."""

    def __init__(self) -> None:
        self.checks: list[Decimal] = []
        self.commits: list = []

    @property
    def usd_eur_rate(self) -> float:
        return 0.92

    def check(self, estimated_cost_eur: Decimal) -> None:
        self.checks.append(estimated_cost_eur)

    def commit(self, actual) -> None:
        self.commits.append(actual)

    def remaining(self) -> Decimal:
        return Decimal("1")


class CountingDriver(GraphDriver):
    """Counts `read` calls so a test can prove no vector query was issued."""

    def __init__(self, *args) -> None:
        super().__init__(*args)
        self.read_calls = 0

    def read(self, cypher: str, params: dict, timeout_s: int) -> list[dict]:
        self.read_calls += 1
        return super().read(cypher, params, timeout_s)


def counting_from(driver: GraphDriver) -> CountingDriver:
    """Wrap the module fixture in a counting subclass without reconnecting."""
    counting = CountingDriver.__new__(CountingDriver)
    counting._driver = driver._driver
    counting._database = driver._database
    counting.read_calls = 0
    return counting


class FakeWikidata(WikidataAdapter):
    """Enrichment-only adapter with canned matches; no network."""

    def __init__(self, matches: dict[tuple[str, str], WikidataMatch]) -> None:
        self.matches = matches

    def enrich(self, entity_type: str, label: str) -> WikidataMatch | None:
        return self.matches.get((entity_type, label.casefold()))


def registry_with(fake: FakeWikidata) -> SourceRegistry:
    registry = SourceRegistry()
    registry.register(fake)
    return registry


def doc(body: str, content_hash: str = "doc-1") -> DocumentPayload:
    return DocumentPayload(
        content_hash=content_hash,
        title="Test",
        body=body,
        language="de",
        published_at=datetime(2026, 7, 1, tzinfo=UTC),
    )


def extracted(
    subject: Mention,
    relation: str,
    object_: Mention,
    evidence_start: int,
    evidence_end: int,
    confidence: float = 0.9,
) -> ExtractedAssertion:
    return ExtractedAssertion(
        passage_index=0,
        subject=subject,
        relation=relation,
        object=object_,
        confidence=confidence,
        evidence_start=evidence_start,
        evidence_end=evidence_end,
    )


def entity(entity_id: str, label: str) -> EntityEndpoint:
    return EntityEndpoint(entity_id=entity_id, type="Corporation", label=label)


def loaded_assertion(entity_id: str, label: str, relation: str = "SUBSIDIARY_OF") -> Assertion:
    return Assertion(
        assertion_id=f"res-{entity_id}",
        subject=entity(entity_id, label),
        relation=relation,
        object=entity("shared-parent", "Rheinwerk Beteiligung GmbH"),
        validity=Validity(valid_from=datetime(2020, 1, 1, tzinfo=UTC), recorded_at=NOW),
        provenance=Provenance(
            source_id="s1",
            source_trust=1.0,
            confidence=0.9,
            ontology_version="1.0.0",
        ),
    )


def embed_handler(vectors_by_text: dict[str, list[float]]):
    def handler(request):
        body = json.loads(request.content)
        texts = body["input"]
        return Response(
            200,
            json={
                "data": [{"embedding": vectors_by_text[text]} for text in texts],
                "usage": USAGE,
            },
        )

    return handler


def adjudication_handler(by_surface: dict[str, dict]):
    def handler(request):
        body = json.loads(request.content)
        content = body["messages"][0]["content"]
        for surface, verdict in by_surface.items():
            if surface in content:
                return Response(
                    200,
                    json={
                        "choices": [{"message": {"content": json.dumps(verdict)}}],
                        "usage": USAGE,
                    },
                )
        raise AssertionError(f"unexpected adjudication call: {content[:600]}")

    return handler


def run_context(
    driver: GraphDriver,
    registry: SourceRegistry,
    settings: Settings,
    tmp_path: Path,
):
    governor = MockGovernor()
    client = OpenRouterClient(settings, governor)
    return (
        RunContext(
            settings=settings,
            ontology=load_ontology(ONTOLOGY_PATH),
            driver=driver,
            registry=registry,
            archive=ArchiveStore(tmp_path / "archive"),
            client=client,
        ),
        governor,
    )


def clear_process_caches() -> None:
    """The embed and enrichment caches are process-global by design; tests
    must not observe each other's entries."""
    from limes.resolution import blocking

    blocking._EMBED_CACHE.clear()
    resolve._ENRICH_CACHE.clear()
