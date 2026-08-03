# tests/acceptance/conftest.py | v1.0.0 | introduced by WP-39
"""Shared fixtures for the acceptance suite (WP-39, Doc 2 §12.4).

Inherits the session-scoped disposable Neo4j container from
`tests/integration/conftest.py` through pytest_plugins, so the tree has
exactly one container boot path. The acceptance suite exercises the same
production seams as the integration suite, against the same lifecycle.

`populated_graph` builds a realistic populated graph through the
production ingestion path — `execute_run` over the recorded GISCO, GLEIF,
and feed fixtures, with only the network boundary stubbed (fixture
fetches, respx-mocked paid endpoints, injected fake spaCy models) — the
same seam Trace 1/2 tests use. Graph state is produced exactly as the
pipeline produces it (Doc 2 §12.2 rule 1); no test writes state directly.

`acceptance_settings` is the shared Settings factory for the suite: all
keys, test models, and the disposable container's coordinates.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import respx
from httpx import Response

from limes.config import Settings
from limes.pipeline.run import RunSpec, execute_run
from limes.sources import feeds as feeds_module
from limes.sources.feeds import FeedsAdapter
from limes.sources.gisco_nuts import GiscoNutsAdapter
from limes.sources.gleif import GleifAdapter
from limes.types import RawRecord
from tests.fixtures.embeddings import fake_embedder
from tests.integration.conftest import Neo4jInstance

pytest_plugins = ["tests.integration.conftest"]

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"
FIXTURES = REPO_ROOT / "tests" / "fixtures"

BASE_URL = "https://openrouter.test/api/v1"
CATALOGUE_URL = f"{BASE_URL}/models"
COMPLETIONS_URL = f"{BASE_URL}/chat/completions"
EMBEDDINGS_URL = f"{BASE_URL}/embeddings"

EXTRACTION_MODEL = "test/extractor"
EMBED_MODEL = "test/embed"
ADJUDICATE_MODEL = "test/adjudicator"
NL2CYPHER_MODEL = "test/nl2cypher"

FETCHED_AT = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)

USAGE = {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70}

# The two LEIs the feed sample's document carries; the fake NER finds them
# and the resolution pattern table resolves them deterministically (AC-16).
SUBJECT_LEI = "529900T8BM49AURSDO55"
OBJECT_LEI = "549300BEQ1B5L7Z2WE72"
FEED_URL = "https://example.com/rss"

CATALOGUE = {
    "data": [
        {
            "id": EXTRACTION_MODEL,
            "pricing": {"prompt": "0.000000500", "completion": "0.000001500", "request": "0"},
        },
        {
            "id": EMBED_MODEL,
            "pricing": {"prompt": "0.000000100", "completion": "0", "request": "0"},
        },
        {
            "id": ADJUDICATE_MODEL,
            "pricing": {"prompt": "0.000000500", "completion": "0.000001500", "request": "0"},
        },
        {
            "id": NL2CYPHER_MODEL,
            "pricing": {"prompt": "0.000000500", "completion": "0.000001500", "request": "0"},
        },
    ]
}


class _FakeEnt:
    """One fake spaCy span: the two LEIs, labeled ORG so the gate's
    non-entity filter keeps them."""

    def __init__(self, text: str, label: str, start: int, end: int) -> None:
        self.text = text
        self.label_ = label
        self.start_char = start
        self.end_char = end


class FakeNer:
    """The injected spaCy model: finds the two LEIs anywhere in the text.
    `enabled=False` yields no spans — the gate's below-threshold path."""

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled

    def __call__(self, text: str) -> SimpleNamespace:
        if not self._enabled:
            return SimpleNamespace(ents=[])
        spans = []
        for surface in (SUBJECT_LEI, OBJECT_LEI):
            start = text.find(surface)
            if start >= 0:
                spans.append(_FakeEnt(surface, "ORG", start, start + len(surface)))
        return SimpleNamespace(ents=spans)


def acceptance_settings(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
    **overrides: Any,
) -> Settings:
    """The suite's Settings factory: container coordinates, repo artifacts,
    test models, and the mock transport base URL."""
    base: dict[str, Any] = {
        "neo4j_uri": neo4j_instance.uri,
        "neo4j_user": neo4j_instance.user,
        "neo4j_password": neo4j_instance.password,
        "neo4j_database": neo4j_instance.database,
        "ontology_path": ONTOLOGY_PATH,
        "feeds_config_path": REPO_ROOT / "ontology" / "feeds.yaml",
        "gold_set_path": tmp_path / "gold_set.jsonl",
        "baseline_path": tmp_path / "baseline.json",
        "archive_path": tmp_path / "archive",
        "openrouter_api_key": "sk-test",
        "openrouter_base_url": BASE_URL,
        "extraction_model": EXTRACTION_MODEL,
        "embedding_model": EMBED_MODEL,
        "adjudication_model": ADJUDICATE_MODEL,
        "nl2cypher_model": NL2CYPHER_MODEL,
        "http_timeout_seconds": 10,
    }
    base.update(overrides)
    return Settings(**base)


def fake_embedder_vectors(request) -> Response:
    """The embeddings endpoint's canned response: deterministic vectors via
    the test embedder, honoring the request's `input` list."""
    payload = json.loads(request.content.decode("utf-8"))
    texts = [str(item) for item in (payload or {}).get("input", [])]
    return Response(
        200,
        json={
            "data": [{"embedding": vector} for vector in fake_embedder()(texts)],
            "usage": {"prompt_tokens": 40, "total_tokens": 40},
        },
    )


def mock_paid_transport(extraction_items: list[dict[str, Any]] | None = None) -> None:
    """respx routes for the catalogue, chat completions, and embeddings —
    the entire paid boundary of the pipeline. The chat response carries
    `extraction_items` (default: the LEI-carrying SUBSIDIARY_OF item the
    feed sample's document extracts to); embeddings return deterministic
    vectors via the test embedder."""
    if extraction_items is None:
        gate_text = f"Holding announcement\n\n{SUBJECT_LEI} holds {OBJECT_LEI}."
        extraction_items = [
            {
                "passage_index": 0,
                "subject": {"surface": SUBJECT_LEI, "type": "Corporation"},
                "relation": "SUBSIDIARY_OF",
                "object": {"surface": OBJECT_LEI, "type": "Corporation"},
                "valid_from": "2026-07-01",
                "confidence": 0.95,
                "evidence_start": 0,
                "evidence_end": len(gate_text),
            }
        ]
    respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=CATALOGUE))
    respx.post(COMPLETIONS_URL).mock(
        return_value=Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(extraction_items)}}],
                "usage": USAGE,
            },
        )
    )
    respx.post(EMBEDDINGS_URL).mock(side_effect=fake_embedder_vectors)


def gisco_fixture_records() -> list[RawRecord]:
    """The recorded GISCO files as raw records (Trace 1's fetch output)."""

    def record(name: str, url: str) -> RawRecord:
        return RawRecord(
            payload=(FIXTURES / "gisco_nuts" / name).read_bytes(),
            content_type="text/csv",
            source_url=url,
            fetched_at=FETCHED_AT,
        )

    return [
        record("nuts_hierarchy.csv", "https://example.test/nuts.csv"),
        record("postcode_correspondence.csv", "https://example.test/postcodes.csv"),
    ]


def _gleif_zip(name: str) -> bytes:
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, (FIXTURES / "gleif" / name).read_text(encoding="utf-8"))
    return buffer.getvalue()


def gleif_fixture_records() -> list[RawRecord]:
    """The recorded GLEIF CSVs, wrapped in the zip the adapter fetches."""

    def record(name: str, url: str) -> RawRecord:
        return RawRecord(
            payload=_gleif_zip(name),
            content_type="application/zip",
            source_url=url,
            fetched_at=FETCHED_AT,
        )

    return [
        record("entities.csv", "https://example.test/entities.zip"),
        record("relationships.csv", "https://example.test/relationships.zip"),
    ]


def feed_sample_record() -> RawRecord:
    """One curated-feed entry envelope — the feed sample the populated
    graph's document path ingests (D-19's deterministic envelope)."""
    envelope = {
        "feed": {"url": FEED_URL, "name": "Test feed", "language": "en"},
        "entry_id": "entry-1",
        "title": "Holding announcement",
        "link": "https://example.com/entries/1",
        "summary": "",
        "content": f"<p>{SUBJECT_LEI} holds {OBJECT_LEI}.</p>",
        "published": "2026-07-31T09:30:00+00:00",
    }
    return RawRecord(
        payload=json.dumps(envelope, sort_keys=True).encode("utf-8"),
        content_type="application/vnd.limes.feed-entry+json",
        source_url=FEED_URL,
        fetched_at=FETCHED_AT,
    )


def _feeds_config(tmp_path: Path) -> Path:
    """A one-feed config at 0.70 trust, matching the sample record's URL —
    the D-20 per-feed override the pipeline run stamps from."""
    path = tmp_path / "feeds.yaml"
    path.write_text(
        f'version: "1.0.0"\nfeeds:\n'
        f"  - url: {FEED_URL}\n"
        f"    name: Test feed\n"
        f"    language: en\n"
        f"    trust_rank: 0.70\n"
    )
    return path


@pytest.fixture(scope="module")
def populated_graph(
    neo4j_instance: Neo4jInstance,
    tmp_path_factory: pytest.TempPathFactory,
) -> dict[str, Any]:
    """A graph populated through the production ingestion path: the GISCO
    geography and postal correspondence, the GLEIF entity backbone, and one
    news-extracted feed document with evidence fields. The paid boundary is
    respx-mocked and the spaCy models are injected fakes — the graph state
    itself is produced by `execute_run` (Trace 1 and Trace 2).

    Module-scoped: each module that asks for it gets its own fresh graph.
    """
    tmp = tmp_path_factory.mktemp("acceptance-graph")
    settings = acceptance_settings(neo4j_instance, tmp)

    from limes import composition as composition_module
    from tests.fixtures.graph_data import wipe_graph

    wipe_graph(neo4j_instance)

    real_load = feeds_module._load_feed_config
    feeds_config_path = _feeds_config(tmp)
    fetch_gisco = GiscoNutsAdapter.fetch
    fetch_gleif = GleifAdapter.fetch
    fetch_feeds = FeedsAdapter.fetch
    spacy_load = composition_module.spacy.load
    fake_de = FakeNer()
    fake_en = FakeNer()

    try:
        feeds_module._load_feed_config = lambda _path: real_load(feeds_config_path)
        GiscoNutsAdapter.fetch = lambda self, since, until: iter(gisco_fixture_records())
        GleifAdapter.fetch = lambda self, since, until: iter(gleif_fixture_records())
        FeedsAdapter.fetch = lambda self, since, until: iter([feed_sample_record()])
        composition_module.spacy.load = lambda name: fake_de if name.endswith("de") else fake_en

        from limes.composition import build_run_context

        with respx.mock:
            mock_paid_transport()
            ctx = build_run_context(
                settings,
                needs_inference=True,
                budget_eur=Decimal("3.00"),
            )
            try:
                gisco = execute_run(RunSpec(source_id="gisco_nuts", mode="ingest"), ctx)
                gleif = execute_run(RunSpec(source_id="gleif", mode="ingest"), ctx)
                feeds = execute_run(RunSpec(source_id="feeds", mode="ingest"), ctx)
            finally:
                ctx.driver.close()

        return {
            "settings": settings,
            "runs": {"gisco": gisco, "gleif": gleif, "feeds": feeds},
            "content_hash": feeds_module.payload_hash(feed_sample_record().payload),
        }
    finally:
        feeds_module._load_feed_config = real_load
        GiscoNutsAdapter.fetch = fetch_gisco
        GleifAdapter.fetch = fetch_gleif
        FeedsAdapter.fetch = fetch_feeds
        composition_module.spacy.load = spacy_load
