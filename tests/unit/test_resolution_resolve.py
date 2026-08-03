# tests/unit/test_resolution_resolve.py | v1.0.0 | introduced by WP-25
"""`resolve_assertions` unit tests per Doc 2 §8.8.3-§8.8.5.

The four resolution bands (deterministic key, auto-link, adjudication, mint)
are exercised with a fake driver, a fake inference client, and a fake
Wikidata adapter — no network, no graph. The mention-to-assertion conversion
runs through the production path (`resolve_assertions`), and every branch
that logs a skip (missing adapter, wrong adapter type, failed enrichment,
surface not found in the document) is executed and counted, never silenced.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from limes.archive.store import ArchiveStore
from limes.config import Settings
from limes.errors import ExtractionError, SourceFetchError
from limes.ontology.registry import load_ontology
from limes.resolution import blocking, resolve
from limes.resolution.resolve import RunContext, resolve_assertions
from limes.sources.registry import SourceRegistry
from limes.sources.wikidata import WikidataAdapter, WikidataMatch
from limes.types import DocumentPayload, ExtractedAssertion, Mention

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY = load_ontology(REPO_ROOT / "ontology" / "ontology.yaml")

# A 20-character uppercase surface: the deterministic LEI pattern of
# Corporation (keys.py), so the mention resolves without any paid call.
LEI = "ABCDEFGHIJ0123456789"
OTHER_LEI = "9876543210ABCDEFGHIJ"
LEI_ID = f"lei:{LEI}"

EMBED_MODEL = "test/embed"
ADJUDICATE_MODEL = "test/adjudicator"


def _settings(tmp_path, **overrides) -> Settings:
    base = dict(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="u",
        neo4j_password="p",
        ontology_path=REPO_ROOT / "ontology" / "ontology.yaml",
        feeds_config_path=REPO_ROOT / "ontology" / "feeds.yaml",
        gold_set_path=tmp_path / "gold_set.jsonl",
        baseline_path=tmp_path / "baseline.json",
        archive_path=tmp_path / "archive",
        embedding_model=EMBED_MODEL,
        adjudication_model=ADJUDICATE_MODEL,
        embedding_dimensions=1024,
        er_autolink_cosine=0.93,
        er_autolink_margin=0.05,
        er_adjudicate_cosine=0.82,
    )
    base.update(overrides)
    return Settings(**base)


class FakeDriver:
    """Records writes; `read` serves canned candidate rows."""

    def __init__(self, candidate_rows=None) -> None:
        self.candidate_rows = candidate_rows or []
        self.writes: list[tuple[str, dict]] = []
        self.reads: list[str] = []

    def read(self, cypher: str, params: dict, timeout_s: int) -> list[dict]:
        self.reads.append(cypher)
        return self.candidate_rows

    def write_batch(self, statements: list[tuple[str, dict]]) -> None:
        self.writes.extend(statements)


class FakeClient:
    """Canned embed vectors and adjudication verdicts; counts calls so a
    test can prove the deterministic band spent nothing."""

    def __init__(self, vectors=None, adjudication='{"same": true, "confidence": 0.8}') -> None:
        self.vectors = vectors if vectors is not None else [UNITY_VECTOR]
        self.adjudication = adjudication
        self.embed_calls = 0
        self.complete_calls = 0

    def embed(self, texts: list[str], model_id: str) -> list[list[float]]:
        self.embed_calls += 1
        return [self.vectors[i] for i in range(len(texts))]

    def complete(self, messages, model_id, purpose, json_schema=None):
        self.complete_calls += 1
        return self.adjudication, 10, 5


UNITY_VECTOR = [1.0] + [0.0] * 1023


def cosine_row(entity_id: str, label: str, cosine: float) -> dict:
    # The vector index reports (1 + cosine) / 2; blocking.candidates converts
    # back to cosine space, so the fake row carries the engine score.
    return {"entity_id": entity_id, "label": label, "score": (1.0 + cosine) / 2.0}


class FakeWikidata(WikidataAdapter):
    """Enrichment-only adapter with canned matches; no network."""

    def __init__(self, matches=None, error: str | None = None) -> None:
        self.matches = matches or {}
        self.error = error
        self.calls = 0

    def enrich(self, entity_type: str, label: str) -> WikidataMatch | None:
        self.calls += 1
        if self.error is not None:
            raise SourceFetchError(self.error)
        return self.matches.get((entity_type, label.casefold()))


class NotAWikidataAdapter:
    """Registered under the wikidata id but not a WikidataAdapter."""

    source_id = "wikidata"
    name = "Not Wikidata"
    kind = "structured"
    trust_rank = 0.5
    supports_backfill = False
    supports_incremental = False


def _mention(surface: str, type_: str = "Corporation") -> Mention:
    return Mention(surface=surface, type=type_)


def _extracted(
    subject: Mention,
    object_: Mention,
    relation: str = "SUBSIDIARY_OF",
    evidence_start: int = 0,
    evidence_end: int = 40,
) -> ExtractedAssertion:
    return ExtractedAssertion(
        passage_index=0,
        subject=subject,
        relation=relation,
        object=object_,
        evidence_start=evidence_start,
        evidence_end=evidence_end,
        confidence=0.9,
    )


def _doc(body: str = "Alpha owns Beta. Gamma holds Delta.") -> DocumentPayload:
    return DocumentPayload(
        content_hash="doc-1",
        title="Test",
        body=body,
        language="de",
        published_at=datetime(2026, 7, 1, tzinfo=UTC),
    )


def _ctx(tmp_path, driver, registry, settings, client=None, with_client=True) -> RunContext:
    return RunContext(
        settings=settings,
        ontology=ONTOLOGY,
        driver=driver,
        registry=registry,
        archive=ArchiveStore(tmp_path / "archive"),
        client=client if with_client else None,
    )


@pytest.fixture(autouse=True)
def _clear_process_caches():
    # The enrichment and embed caches are process-global by design; tests
    # must not observe each other's entries.
    blocking._EMBED_CACHE.clear()
    resolve._ENRICH_CACHE.clear()
    yield
    blocking._EMBED_CACHE.clear()
    resolve._ENRICH_CACHE.clear()


def test_resolve_requires_an_inference_client(tmp_path):
    ctx = _ctx(
        tmp_path,
        FakeDriver(),
        SourceRegistry(),
        _settings(tmp_path),
        with_client=False,
    )
    with pytest.raises(ExtractionError, match="requires an inference client"):
        resolve_assertions([], ctx, _doc())


def test_resolve_requires_an_embedding_model(tmp_path):
    settings = _settings(tmp_path, embedding_model="")
    ctx = _ctx(tmp_path, FakeDriver(), SourceRegistry(), settings, client=FakeClient())
    with pytest.raises(ExtractionError, match="no embedding model pinned"):
        resolve_assertions([], ctx, _doc())


def test_resolve_requires_an_adjudication_model(tmp_path):
    settings = _settings(tmp_path, adjudication_model="")
    ctx = _ctx(tmp_path, FakeDriver(), SourceRegistry(), settings, client=FakeClient())
    with pytest.raises(ExtractionError, match="no adjudication model pinned"):
        resolve_assertions([], ctx, _doc())


def test_deterministic_key_band_costs_nothing(tmp_path):
    client = FakeClient()
    driver = FakeDriver()
    ctx = _ctx(tmp_path, driver, SourceRegistry(), _settings(tmp_path), client=client)
    item = _extracted(
        _mention(LEI), _mention(OTHER_LEI), evidence_end=len(f"{LEI} owns {OTHER_LEI}.")
    )
    assertions, stats = resolve_assertions([item], ctx, _doc(body=f"{LEI} owns {OTHER_LEI}."))

    assert stats.deterministic == 2
    assert assertions[0].subject.entity_id == LEI_ID
    assert assertions[0].provenance.ontology_version == ONTOLOGY.version
    # No embedding, no candidates read, no adjudication: the band is free.
    assert client.embed_calls == 0
    assert client.complete_calls == 0
    assert driver.reads == []
    # The mention node and the SAME_AS link are written.
    assert any("Mention" in cypher for cypher, _ in driver.writes)
    assert any("SAME_AS" in cypher for cypher, _ in driver.writes)


def test_repeated_mention_is_resolved_once(tmp_path):
    # Two assertions naming the same (type, surface): the second occurrence
    # reuses the first's resolution instead of re-routing it.
    client = FakeClient()
    driver = FakeDriver()
    ctx = _ctx(tmp_path, driver, SourceRegistry(), _settings(tmp_path), client=client)
    subject = _mention(LEI)
    item_a = _extracted(subject, _mention(OTHER_LEI), evidence_end=len(f"{LEI} owns {OTHER_LEI}."))
    item_b = _extracted(subject, _mention(OTHER_LEI), evidence_end=len(f"{LEI} owns {OTHER_LEI}."))
    assertions, stats = resolve_assertions(
        [item_a, item_b], ctx, _doc(body=f"{LEI} owns {OTHER_LEI}.")
    )

    # Four endpoints, all deterministic; the subject was routed exactly once.
    assert stats.deterministic == 4
    assert driver.reads == []
    assert {a.subject.entity_id for a in assertions} == {LEI_ID}


def test_auto_link_band_above_thresholds(tmp_path):
    driver = FakeDriver(
        [
            cosine_row("lei:VW", "Volkswagen AG", 0.95),
            cosine_row("lei:VWP", "VW AG", 0.85),
        ]
    )
    ctx = _ctx(tmp_path, driver, SourceRegistry(), _settings(tmp_path), client=FakeClient())
    item = _extracted(_mention("Volkswagen AG"), _mention(LEI))
    assertions, stats = resolve_assertions([item], ctx, _doc(body="Volkswagen AG owns X."))

    assert stats.auto_linked == 1
    assert assertions[0].subject.entity_id == "lei:VW"
    assert driver.reads, "the candidate query must have run"
    assert any("SAME_AS" in cypher for cypher, _ in driver.writes)


def test_adjudicated_band_when_margin_is_thin(tmp_path):
    # Top cosine 0.90 is above the adjudication floor but below the auto-link
    # ceiling with an insufficient margin: one adjudication call decides.
    driver = FakeDriver(
        [
            cosine_row("lei:VW", "Volkswagen AG", 0.90),
            cosine_row("lei:VWP", "VW AG", 0.89),
        ]
    )
    client = FakeClient()
    ctx = _ctx(tmp_path, driver, SourceRegistry(), _settings(tmp_path), client=client)
    item = _extracted(_mention("Volkswagen AG"), _mention(LEI))
    assertions, stats = resolve_assertions([item], ctx, _doc(body="Volkswagen AG owns X."))

    assert stats.adjudicated == 1
    assert client.complete_calls == 1
    assert assertions[0].subject.entity_id == "lei:VW"


def test_mint_when_no_candidates_exist(tmp_path):
    driver = FakeDriver([])
    ctx = _ctx(tmp_path, driver, SourceRegistry(), _settings(tmp_path), client=FakeClient())
    item = _extracted(_mention("Volkswagen AG"), _mention(LEI))
    assertions, stats = resolve_assertions([item], ctx, _doc(body="Volkswagen AG owns X."))

    assert stats.minted == 1
    minted_id = assertions[0].subject.entity_id
    assert minted_id.startswith("corporation:")
    # A minted mention is never linked — no entity node exists to link to.
    same_as_writes = [params for cypher, params in driver.writes if "SAME_AS" in cypher]
    assert all(params["entity_id"] != minted_id for params in same_as_writes)


def test_mint_when_adjudicator_says_different_entity(tmp_path):
    driver = FakeDriver(
        [
            cosine_row("lei:VW", "Volkswagen AG", 0.90),
            cosine_row("lei:VWP", "VW AG", 0.89),
        ]
    )
    client = FakeClient(adjudication='{"same": false, "confidence": 0.9}')
    ctx = _ctx(tmp_path, driver, SourceRegistry(), _settings(tmp_path), client=client)
    item = _extracted(_mention("Volkswagen AG"), _mention(LEI))
    assertions, stats = resolve_assertions([item], ctx, _doc(body="Volkswagen AG owns X."))

    assert stats.minted == 1
    assert client.complete_calls == 1


def test_surface_absent_from_document_zeroes_offsets(tmp_path):
    # The evidence-span check (AC-13) guarantees the surface is in the
    # document; a surface that is not is a counted, logged warning, and the
    # mention is created at zeroed offsets rather than dropped.
    driver = FakeDriver([])
    ctx = _ctx(tmp_path, driver, SourceRegistry(), _settings(tmp_path), client=FakeClient())
    item = _extracted(_mention("Zed"), _mention(LEI), evidence_end=20)
    assertions, _ = resolve_assertions([item], ctx, _doc(body="Alpha owns Beta."))

    assert assertions[0].subject.entity_id.startswith("corporation:")
    mention_writes = [params for cypher, params in driver.writes if "Mention" in cypher]
    zed = [params for params in mention_writes if params.get("surface") == "Zed"]
    assert zed and zed[0]["start"] == 0 and zed[0]["end"] == 0


def test_enrichment_cache_hit_skips_the_adapter(tmp_path):
    # The (type, surface) enrichment result is cached per process; the second
    # mention of the same surface never touches the adapter again.
    match = WikidataMatch(qid="Q5678", label="Angela Merkel")
    fake = FakeWikidata({("Person", "angela merkel"): match})
    registry = SourceRegistry()
    registry.register(fake)
    ctx = _ctx(tmp_path, FakeDriver([]), registry, _settings(tmp_path), client=FakeClient())
    item = _extracted(_mention("Angela Merkel", "Person"), _mention(LEI), evidence_end=40)
    first, _ = resolve_assertions([item], ctx, _doc(body="Angela Merkel owns X."))
    second, _ = resolve_assertions([item], ctx, _doc(body="Angela Merkel owns X."))

    assert first[0].subject.entity_id == "wikidata_qid:Q5678"
    assert second[0].subject.entity_id == "wikidata_qid:Q5678"
    assert fake.calls == 1  # a second resolve hit the cache, not the adapter


def test_enrichment_skipped_when_wikidata_absent_from_registry(tmp_path):
    # A registry without the wikidata adapter: enrichment is skipped with a
    # logged warning and the mention routes through the paid bands.
    ctx = _ctx(tmp_path, FakeDriver([]), SourceRegistry(), _settings(tmp_path), client=FakeClient())
    item = _extracted(_mention("Angela Merkel", "Person"), _mention(LEI), evidence_end=40)
    assertions, stats = resolve_assertions([item], ctx, _doc(body="Angela Merkel owns X."))

    assert stats.minted == 1
    assert assertions[0].subject.entity_id.startswith("person:")


def test_enrichment_skipped_when_adapter_has_wrong_type(tmp_path):
    registry = SourceRegistry()
    registry.register(NotAWikidataAdapter())
    ctx = _ctx(tmp_path, FakeDriver([]), registry, _settings(tmp_path), client=FakeClient())
    item = _extracted(_mention("Angela Merkel", "Person"), _mention(LEI), evidence_end=40)
    assertions, stats = resolve_assertions([item], ctx, _doc(body="Angela Merkel owns X."))

    assert stats.minted == 1
    assert assertions[0].subject.entity_id.startswith("person:")


def test_enrichment_failure_is_treated_as_a_miss(tmp_path):
    fake = FakeWikidata(error="wikidata is down")
    registry = SourceRegistry()
    registry.register(fake)
    ctx = _ctx(tmp_path, FakeDriver([]), registry, _settings(tmp_path), client=FakeClient())
    item = _extracted(_mention("Angela Merkel", "Person"), _mention(LEI), evidence_end=40)
    assertions, stats = resolve_assertions([item], ctx, _doc(body="Angela Merkel owns X."))

    assert stats.minted == 1
    assert assertions[0].subject.entity_id.startswith("person:")
