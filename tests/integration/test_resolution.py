# tests/integration/test_resolution.py | v1.0.0 | introduced by WP-25
"""Entity resolution integration tests per Doc 2 §8.8 (AC-16, AC-17,
AC-19, AC-43), against the real Neo4j container.

The resume gate of the WP-25 seam resolution holds here: the vector index is
populated through the production `load` path with the injected fake embedder
(WP-25a) — no test hand-builds embeddings, and no test observes an empty
index. The OpenRouter client is real but respx-mocked; no live service is
hit, and the governor records prove which bands were paid.
"""

import json
import math
import random
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
import respx
from httpx import Response

from limes.config import Settings
from limes.graph.driver import GraphDriver
from limes.graph.embeddings import normalize_embedding
from limes.graph.loader import load as graph_load
from limes.graph.schema import provision
from limes.ontology.registry import load_ontology
from limes.resolution import blocking, link, resolve
from limes.resolution.resolve import ResolutionStats, RunContext, resolve_assertions
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
from tests.fixtures.embeddings import (
    TEST_EMBEDDING_DIMENSIONS,
    expected_vector,
    fake_embedder,
    vector_with_cosines,
)
from tests.integration.conftest import Neo4jInstance

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"

BASE_URL = "https://openrouter.test/api/v1"
CATALOGUE_URL = f"{BASE_URL}/models"
EMBED_URL = f"{BASE_URL}/embeddings"
COMPLETIONS_URL = f"{BASE_URL}/chat/completions"

EMBED_MODEL = "test/embed"
ADJUDICATE_MODEL = "test/adjudicator"

NOW = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)

CATALOGUE = {
    "data": [
        {"id": EMBED_MODEL, "pricing": {"prompt": "0.000000100", "completion": "0.000000100"}},
        {
            "id": ADJUDICATE_MODEL,
            "pricing": {"prompt": "0.000000100", "completion": "0.000000100"},
        },
    ]
}
USAGE = {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70}


@pytest.fixture(scope="module")
def driver(neo4j_instance: Neo4jInstance) -> GraphDriver:
    d = GraphDriver(
        neo4j_instance.uri,
        neo4j_instance.user,
        neo4j_instance.password,
        neo4j_instance.database,
    )
    yield d
    d.close()


@pytest.fixture(scope="module")
def ontology():
    return load_ontology(ONTOLOGY_PATH)


@pytest.fixture(scope="module", autouse=True)
def _provisioned(driver: GraphDriver, ontology) -> None:
    provision(driver, ontology, embedding_dimensions=TEST_EMBEDDING_DIMENSIONS)


@pytest.fixture(autouse=True)
def _clear_process_caches():
    """The embed and enrichment caches are process-global by design; tests
    must not observe each other's entries."""
    blocking._EMBED_CACHE.clear()
    resolve._ENRICH_CACHE.clear()
    yield
    blocking._EMBED_CACHE.clear()
    resolve._ENRICH_CACHE.clear()


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
        openrouter_base_url=BASE_URL,
        embedding_model=EMBED_MODEL,
        adjudication_model=ADJUDICATE_MODEL,
        embedding_dimensions=TEST_EMBEDDING_DIMENSIONS,
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


class FakeWikidata(WikidataAdapter):
    """Enrichment-only adapter with canned matches; no network."""

    def __init__(self, matches: dict[tuple[str, str], WikidataMatch]) -> None:
        self.matches = matches

    def enrich(self, entity_type: str, label: str) -> WikidataMatch | None:
        return self.matches.get((entity_type, label.casefold()))


def _registry(fake: FakeWikidata) -> SourceRegistry:
    registry = SourceRegistry()
    registry.register(fake)
    return registry


def _doc(body: str, content_hash: str = "doc-1") -> DocumentPayload:
    return DocumentPayload(
        content_hash=content_hash,
        title="Test",
        body=body,
        language="de",
        published_at=datetime(2026, 7, 1, tzinfo=UTC),
    )


def _extracted(
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


def _entity(entity_id: str, label: str) -> EntityEndpoint:
    return EntityEndpoint(entity_id=entity_id, type="Corporation", label=label)


def _loaded_assertion(entity_id: str, label: str) -> Assertion:
    return Assertion(
        assertion_id=f"res-{entity_id}",
        subject=_entity(entity_id, label),
        relation="SUBSIDIARY_OF",
        object=_entity("shared-parent", "Rheinwerk Beteiligung GmbH"),
        validity=Validity(valid_from=datetime(2020, 1, 1, tzinfo=UTC), recorded_at=NOW),
        provenance=Provenance(
            source_id="s1",
            source_trust=1.0,
            confidence=0.9,
            ontology_version="1.0.0",
        ),
    )


def _embed_handler(vectors_by_text: dict[str, list[float]]):
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


def _adjudication_handler(by_surface: dict[str, dict]):
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


def _context(driver: GraphDriver, registry: SourceRegistry, settings: Settings, tmp_path):
    from limes.archive.store import ArchiveStore
    from limes.extraction.openrouter_client import OpenRouterClient

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


def test_ac16_deterministic_keys_short_circuit(driver: GraphDriver, ontology, tmp_path):
    # AC-16: LEI-carrying mentions resolve with no embedding, no vector
    # query, no paid call — respx is active with no routes, so any HTTP
    # attempt fails the test loudly, and the counting driver proves the
    # index was never queried.
    counting = _counting_from(driver)

    body = "529900T8BM49AURSDO55 holds 549300BEQ1B5L7Z2WE72."
    doc = _doc(body, "ac16-doc")
    extracted = [
        _extracted(
            Mention(surface="529900T8BM49AURSDO55", type="Corporation"),
            "SUBSIDIARY_OF",
            Mention(surface="549300BEQ1B5L7Z2WE72", type="Corporation"),
            0,
            len(body),
        )
    ]
    registry = _registry(FakeWikidata({}))
    settings = _settings()
    ctx, governor = _context(counting, registry, settings, tmp_path)

    with respx.mock:
        assertions, stats = resolve_assertions(extracted, ctx, doc)

    assert stats.deterministic == 2
    assert stats.auto_linked == stats.adjudicated == stats.minted == 0
    assert counting.read_calls == 0
    assert governor.checks == []
    assert assertions[0].subject.entity_id == "lei:529900T8BM49AURSDO55"
    assert assertions[0].object.entity_id == "lei:549300BEQ1B5L7Z2WE72"


def _counting_from(driver: GraphDriver) -> CountingDriver:
    """Wrap the module fixture in a counting subclass without reconnecting."""
    counting = CountingDriver.__new__(CountingDriver)
    counting._driver = driver._driver
    counting._database = driver._database
    counting.read_calls = 0
    return counting


def test_ac17_routes_across_all_four_bands(driver: GraphDriver, ontology, tmp_path):
    # The index is populated through the production load path with the fake
    # embedder; query vectors are rotations of the entity embeddings into
    # the target §8.8.3 bands.
    graph_load(
        driver,
        [
            _loaded_assertion("ac17-vw", "Rheinwerk Konzern AG"),
            _loaded_assertion("ac17-parent", "Rheinwerk Beteiligung GmbH"),
        ],
        ontology,
        embedder=fake_embedder(),
    )
    e_vw = expected_vector("Rheinwerk Konzern AG")

    body = (
        "The company Volkswagen is expanding. "
        "VW grows. "
        "VAG shrinks. "
        "Die Firma closes. "
        "529900T8BM49AURSDO55 leads them."
    )
    spans = {
        "Volkswagen": (
            body.index("Volkswagen is expanding") - len("The company "),
            body.index("Volkswagen is expanding") + len("Volkswagen is expanding"),
        ),
        "VW": (body.index("VW grows"), body.index("VW grows") + len("VW grows")),
        "VAG": (body.index("VAG shrinks"), body.index("VAG shrinks") + len("VAG shrinks")),
        "Die Firma": (
            body.index("Die Firma closes"),
            body.index("Die Firma closes") + len("Die Firma closes"),
        ),
    }
    extracted = [
        _extracted(
            Mention(surface="Volkswagen", type="Corporation"),
            "SUBSIDIARY_OF",
            Mention(surface="VW", type="Corporation"),
            *spans["Volkswagen"],
        ),
        _extracted(
            Mention(surface="VAG", type="Corporation"),
            "SUBSIDIARY_OF",
            Mention(surface="Die Firma", type="Corporation"),
            *spans["VAG"],
        ),
        _extracted(
            Mention(surface="529900T8BM49AURSDO55", type="Corporation"),
            "SUBSIDIARY_OF",
            Mention(surface="Volkswagen", type="Corporation"),
            *spans["Volkswagen"],
        ),
    ]
    # The embed text is surface + type + the assertion's evidence sentence
    # (shared by both endpoints of an assertion) — exactly what the resolver
    # builds, so the mocked vectors key on the same strings.
    def text_for(surface: str, item: ExtractedAssertion) -> str:
        return f"{surface} (Corporation) — {body[item.evidence_start:item.evidence_end]}"

    vectors = {
        text_for("Volkswagen", extracted[0]): vector_with_cosines([(e_vw, 0.95)]),
        text_for("VW", extracted[0]): vector_with_cosines([(e_vw, 0.88)]),
        text_for("VAG", extracted[1]): vector_with_cosines([(e_vw, 0.50)]),
        text_for("Die Firma", extracted[1]): vector_with_cosines([(e_vw, 0.50)]),
    }
    registry = _registry(FakeWikidata({}))
    counting = _counting_from(driver)
    settings = _settings()
    ctx, governor = _context(counting, registry, settings, tmp_path)

    before = driver.read("MATCH (n:Entity) RETURN count(n) AS c", {}, 10)[0]["c"]

    with respx.mock:
        respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=CATALOGUE))
        respx.post(EMBED_URL).mock(side_effect=_embed_handler(vectors))
        respx.post(COMPLETIONS_URL).mock(
            side_effect=_adjudication_handler(
                {
                    "Mention A: VW": {"same": True, "confidence": 0.85},
                }
            )
        )
        assertions, stats = resolve_assertions(extracted, ctx, _doc(body, "ac17-doc"))

    # Bands, per endpoint occurrence: deterministic (LEI), auto (Volkswagen
    # twice — subject of A1 and object of A3, one resolution, two
    # occurrences), adjudicated (VW), mint (VAG, Die Firma).
    assert stats.deterministic == 1
    assert stats.auto_linked == 2
    assert stats.adjudicated == 1
    assert stats.minted == 2

    after = driver.read("MATCH (n:Entity) RETURN count(n) AS c", {}, 10)[0]["c"]
    assert after == before  # AC-17: the mint branch writes no entity node

    links = driver.read(
        "MATCH (m:Mention {document_id: 'ac17-doc'})-[r:SAME_AS]->(e:Entity) "
        "RETURN m.surface AS surface, e.entity_id AS entity_id, "
        "r.method AS method, r.score AS score",
        {},
        10,
    )
    by_surface = {row["surface"]: row for row in links}
    assert by_surface["Volkswagen"]["entity_id"] == "ac17-vw"
    assert by_surface["Volkswagen"]["method"] == "auto"
    assert by_surface["Volkswagen"]["score"] == pytest.approx(0.95, abs=1e-3)
    assert by_surface["VW"]["entity_id"] == "ac17-vw"
    assert by_surface["VW"]["method"] == "adjudicated"
    assert by_surface["VW"]["score"] == pytest.approx(0.85)
    assert "VAG" not in by_surface  # minted, no link
    assert "Die Firma" not in by_surface

    assert assertions[0].subject.entity_id == "ac17-vw"
    assert assertions[0].object.entity_id == "ac17-vw"
    assert len(governor.checks) == 2  # one embed call, one adjudication call
    assert assertions[1].subject.entity_id == resolve.hash_entity_id("corporation", "vag")
    assert assertions[1].object.entity_id == resolve.hash_entity_id("corporation", "die firma")


def test_ac17_margin_below_threshold_adjudicates(driver: GraphDriver, ontology, tmp_path):
    # The second adjudication trigger: cosine ≥ 0.93 with margin < 0.05.
    # Two entities with near-parallel embeddings (g = 0.995, via a designed
    # embedder through the production load path) make the margin band
    # reachable with exact geometry: cos(q, e1) = 0.95 and the achievable
    # cos(q, e2) = 0.95·g − sqrt((1−0.95²)(1−g²)) ≈ 0.914 → margin ≈ 0.036.
    rng = random.Random("margin-seed")
    raw = [rng.uniform(-1.0, 1.0) for _ in range(TEST_EMBEDDING_DIMENSIONS)]
    e1 = normalize_embedding(raw, TEST_EMBEDDING_DIMENSIONS)
    p_raw = [rng.uniform(-1.0, 1.0) for _ in range(TEST_EMBEDDING_DIMENSIONS)]
    p_dot = sum(a * b for a, b in zip(p_raw, e1, strict=True))
    p = normalize_embedding(
        [v - p_dot * ei for v, ei in zip(p_raw, e1, strict=True)],
        TEST_EMBEDDING_DIMENSIONS,
    )
    e2 = [0.995 * x + math.sqrt(1.0 - 0.995**2) * y for x, y in zip(e1, p, strict=True)]

    graph_load(
        driver,
        [
            _loaded_assertion("margin-1", "Margin AG"),
            _loaded_assertion("margin-2", "Margin Holding"),
        ],
        ontology,
        embedder=lambda texts: [{"Margin AG": e1, "Margin Holding": e2}[t] for t in texts],
    )
    q = vector_with_cosines([(e1, 0.95), (e2, 0.90)])

    body = "Margin Co expands. Margin Co2 follows."
    span = (0, len(body))
    extracted = [
        _extracted(
            Mention(surface="Margin Co", type="Corporation"),
            "SUBSIDIARY_OF",
            Mention(surface="Margin Co2", type="Corporation"),
            *span,
        )
    ]
    vectors = {
        "Margin Co (Corporation) — " + body: q,
        "Margin Co2 (Corporation) — " + body: vector_with_cosines([(e1, 0.50)]),
    }
    registry = _registry(FakeWikidata({}))
    settings = _settings()
    ctx, governor = _context(driver, registry, settings, tmp_path)

    with respx.mock:
        respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=CATALOGUE))
        respx.post(EMBED_URL).mock(side_effect=_embed_handler(vectors))
        respx.post(COMPLETIONS_URL).mock(
            side_effect=_adjudication_handler(
                {"Mention A: Margin Co": {"same": True, "confidence": 0.8}}
            )
        )
        _assertions, stats = resolve_assertions(extracted, ctx, _doc(body, "margin-doc"))

    assert stats.adjudicated == 1
    assert stats.minted == 1
    assert stats.auto_linked == 0
    rows = driver.read(
        "MATCH (m:Mention {surface: 'Margin Co'})-[r:SAME_AS]->(e:Entity) "
        "RETURN e.entity_id AS entity_id, r.method AS method",
        {},
        10,
    )
    assert rows[0]["entity_id"] == "margin-1"
    assert rows[0]["method"] == "adjudicated"


def test_ac19_unlink_retracts_without_deleting(driver: GraphDriver, ontology, tmp_path):
    # AC-19: unlink sets retracted_at on SAME_AS; no node is deleted and the
    # loader-written assertion stays attributed.
    graph_load(
        driver,
        [_loaded_assertion("ac19-1", "Volkswagen AG")],
        ontology,
    )
    mention_id = link.create_mention(
        driver, Mention(surface="Volkswagen", type="Corporation"), "ac19-doc", 10, 20
    )
    link.link(driver, mention_id, "ac19-1", "auto", 0.95, NOW)
    link.unlink(driver, mention_id, "ac19-1", datetime(2026, 8, 1, 13, 0, tzinfo=UTC))

    rows = driver.read(
        "MATCH (m:Mention {mention_id: $id})-[r:SAME_AS]->(e:Entity {entity_id: 'ac19-1'}) "
        "RETURN r.retracted_at AS retracted_at, e.label AS label",
        {"id": mention_id},
        10,
    )
    assert rows[0]["retracted_at"] is not None
    assert rows[0]["label"] == "Volkswagen AG"

    assertion_rows = driver.read(
        "MATCH ()-[r:SUBSIDIARY_OF {assertion_id: 'res-ac19-1'}]->() "
        "RETURN r.source_id AS source_id, r.confidence AS confidence",
        {},
        10,
    )
    assert assertion_rows[0]["source_id"] == "s1"

    # Re-linking after an unlink re-activates the same relationship.
    link.link(driver, mention_id, "ac19-1", "auto", 0.96, NOW)
    rows = driver.read(
        "MATCH (m:Mention {mention_id: $id})-[r:SAME_AS]->(e) RETURN r.retracted_at AS at",
        {"id": mention_id},
        10,
    )
    assert rows[0]["at"] is None


def test_ac43_conversion_mentions_and_stats(driver: GraphDriver, ontology, tmp_path):
    # AC-43: resolve_assertions converts ExtractedAssertion to Assertion,
    # creates one :Mention per endpoint, and returns stats matching the four
    # resolution bands — including the enrichment path (Wikidata QID).
    graph_load(
        driver,
        [
            _loaded_assertion("ac43-vw", "Alpenwerk Holding AG"),
            _loaded_assertion("ac43-vwag", "Alpenwerk Vertrieb GmbH"),
        ],
        ontology,
        embedder=fake_embedder(),
    )
    e_vw = expected_vector("Alpenwerk Holding AG")

    body = (
        "Olaf Scholz runs the Volkswagen group. "
        "529900T8BM49AURSDO55 is its parent. "
        "Volkswagen grew. "
        "VW invested. "
        "Die Firma lost. "
        "VAG merged."
    )
    spans = {}
    for surface, sentence in [
        ("Olaf Scholz", "Olaf Scholz runs the Volkswagen group."),
        ("LEI", "529900T8BM49AURSDO55 is its parent."),
        ("Volkswagen", "Volkswagen grew."),
        ("VW", "VW invested."),
        ("Die Firma", "Die Firma lost."),
        ("VAG", "VAG merged."),
    ]:
        start = body.index(sentence)
        spans[surface] = (start, start + len(sentence))

    extracted = [
        _extracted(
            Mention(surface="Olaf Scholz", type="Person"),
            "DIRECTOR_OF",
            Mention(surface="529900T8BM49AURSDO55", type="Corporation"),
            *spans["Olaf Scholz"],
        ),
        _extracted(
            Mention(surface="Volkswagen", type="Corporation"),
            "SUBSIDIARY_OF",
            Mention(surface="VW", type="Corporation"),
            *spans["Volkswagen"],
        ),
        _extracted(
            Mention(surface="Die Firma", type="Corporation"),
            "SUBSIDIARY_OF",
            Mention(surface="VAG", type="Corporation"),
            *spans["Die Firma"],
        ),
    ]

    def text_for(surface: str, item: ExtractedAssertion) -> str:
        return f"{surface} (Corporation) — {body[item.evidence_start:item.evidence_end]}"

    vectors = {
        text_for("Volkswagen", extracted[1]): vector_with_cosines([(e_vw, 0.95)]),
        text_for("VW", extracted[1]): vector_with_cosines([(e_vw, 0.88)]),
        text_for("Die Firma", extracted[2]): vector_with_cosines([(e_vw, 0.50)]),
        text_for("VAG", extracted[2]): vector_with_cosines([(e_vw, 0.50)]),
    }
    registry = _registry(
        FakeWikidata(
            {
                ("Person", "olaf scholz"): WikidataMatch(
                    qid="Q2041974", label="Olaf Scholz", aliases=["Olaf Scholz"]
                )
            }
        )
    )
    settings = _settings()
    ctx, governor = _context(driver, registry, settings, tmp_path)

    with respx.mock:
        respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=CATALOGUE))
        respx.post(EMBED_URL).mock(side_effect=_embed_handler(vectors))
        respx.post(COMPLETIONS_URL).mock(
            side_effect=_adjudication_handler(
                {
                    "Mention A: VW": {"same": True, "confidence": 0.85},
                }
            )
        )
        assertions, stats = resolve_assertions(extracted, ctx, _doc(body, "ac43-doc"))

    assert stats == ResolutionStats(deterministic=2, auto_linked=1, adjudicated=1, minted=2)

    mentions = driver.read(
        "MATCH (m:Mention {document_id: 'ac43-doc'}) RETURN m.surface AS surface, m.type AS type",
        {},
        10,
    )
    assert len(mentions) == 6  # one per extracted endpoint

    endpoint_ids = {
        e.entity_id for a in assertions for e in (a.subject, a.object)
    }
    assert "wikidata_qid:Q2041974" in endpoint_ids  # enrichment -> deterministic
    assert "lei:529900T8BM49AURSDO55" in endpoint_ids
    assert "ac43-vw" in endpoint_ids
    assert resolve.hash_entity_id("corporation", "die firma") in endpoint_ids
    assert resolve.hash_entity_id("corporation", "vag") in endpoint_ids

    first = assertions[0]
    assert first.relation == "DIRECTOR_OF"
    assert first.provenance.ontology_version == ontology.version
    assert first.provenance.confidence == 0.9  # extraction confidence carried through
    assert first.provenance.evidence_document_id == "ac43-doc"
    assert first.provenance.evidence_start == spans["Olaf Scholz"][0]
    assert first.provenance.evidence_end == spans["Olaf Scholz"][1]
    assert first.validity.valid_from is not None
    assert first.validity.recorded_at is not None

    scholz_mention = driver.read(
        "MATCH (m:Mention {document_id: 'ac43-doc', surface: 'Olaf Scholz'}) "
        "RETURN m.start AS start, m.end AS end",
        {},
        10,
    )
    assert scholz_mention[0]["start"] == spans["Olaf Scholz"][0]
    assert scholz_mention[0]["end"] == spans["Olaf Scholz"][0] + len("Olaf Scholz")
    assert len(governor.commits) == 2  # one embed + one adjudication call, both ledgered
