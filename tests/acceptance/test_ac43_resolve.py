# tests/acceptance/test_ac43_resolve.py | v1.0.0 | introduced by WP-39
"""AC-43: `resolve_assertions` converts `ExtractedAssertion` to
`Assertion`, creates a `:Mention` per endpoint, and returns stats matching
the four resolution bands — exercised end-to-end through the production
resolver, with the enrichment (Wikidata) path included.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import respx
from httpx import Response

from limes.graph.driver import GraphDriver
from limes.graph.loader import load
from limes.graph.schema import provision
from limes.ontology.registry import load_ontology
from limes.resolution import resolve
from limes.resolution.resolve import ResolutionStats, resolve_assertions
from limes.sources.wikidata import WikidataMatch
from limes.types import Mention
from tests.acceptance import _resolution_support as support
from tests.acceptance._resolution_support import (
    CATALOGUE_URL,
    COMPLETIONS_URL,
    EMBED_URL,
    FakeWikidata,
    adjudication_handler,
    clear_process_caches,
    doc,
    embed_handler,
    extracted,
    loaded_assertion,
    registry_with,
    run_context,
    settings_for,
)
from tests.fixtures.embeddings import expected_vector, fake_embedder, vector_with_cosines
from tests.fixtures.graph_data import wipe_graph
from tests.integration.conftest import Neo4jInstance

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"


@pytest.fixture(scope="module")
def driver(neo4j_instance: Neo4jInstance) -> GraphDriver:
    d = GraphDriver(
        neo4j_instance.uri,
        neo4j_instance.user,
        neo4j_instance.password,
        neo4j_instance.database,
    )
    wipe_graph(neo4j_instance)
    provision(d, load_ontology(ONTOLOGY_PATH), embedding_dimensions=1024)
    yield d
    d.close()


@pytest.fixture(autouse=True)
def _clear_caches():
    clear_process_caches()
    yield
    clear_process_caches()


def test_ac43_conversion_mentions_and_stats(driver: GraphDriver, tmp_path: Path):
    ontology = load_ontology(ONTOLOGY_PATH)
    load(
        driver,
        [
            loaded_assertion("ac43-vw", "Alpenwerk Holding AG"),
            loaded_assertion("ac43-vwag", "Alpenwerk Vertrieb GmbH"),
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
    spans: dict[str, tuple[int, int]] = {}
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

    extracted_items = [
        extracted(
            Mention(surface="Olaf Scholz", type="Person"),
            "DIRECTOR_OF",
            Mention(surface="529900T8BM49AURSDO55", type="Corporation"),
            *spans["Olaf Scholz"],
        ),
        extracted(
            Mention(surface="Volkswagen", type="Corporation"),
            "SUBSIDIARY_OF",
            Mention(surface="VW", type="Corporation"),
            *spans["Volkswagen"],
        ),
        extracted(
            Mention(surface="Die Firma", type="Corporation"),
            "SUBSIDIARY_OF",
            Mention(surface="VAG", type="Corporation"),
            *spans["Die Firma"],
        ),
    ]

    def text_for(surface: str, item) -> str:
        return f"{surface} (Corporation) — {body[item.evidence_start : item.evidence_end]}"

    vectors = {
        text_for("Volkswagen", extracted_items[1]): vector_with_cosines([(e_vw, 0.95)]),
        text_for("VW", extracted_items[1]): vector_with_cosines([(e_vw, 0.88)]),
        text_for("Die Firma", extracted_items[2]): vector_with_cosines([(e_vw, 0.50)]),
        text_for("VAG", extracted_items[2]): vector_with_cosines([(e_vw, 0.50)]),
    }
    registry = registry_with(
        FakeWikidata(
            {
                ("Person", "olaf scholz"): WikidataMatch(
                    qid="Q2041974", label="Olaf Scholz", aliases=["Olaf Scholz"]
                )
            }
        )
    )
    ctx, governor = run_context(driver, registry, settings_for(tmp_path), tmp_path)

    with respx.mock:
        respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=support.CATALOGUE))
        respx.post(EMBED_URL).mock(side_effect=embed_handler(vectors))
        respx.post(COMPLETIONS_URL).mock(
            side_effect=adjudication_handler({"Mention A: VW": {"same": True, "confidence": 0.85}})
        )
        assertions, stats = resolve_assertions(extracted_items, ctx, doc(body, "ac43-doc"))

    # The four bands, by endpoint occurrence: enrichment (Olaf Scholz) and
    # the LEI are deterministic; Volkswagen auto-links; VW adjudicates; the
    # two unknown surfaces mint.
    assert stats == ResolutionStats(deterministic=2, auto_linked=1, adjudicated=1, minted=2)

    mentions = driver.read(
        "MATCH (m:Mention {document_id: 'ac43-doc'}) RETURN m.surface AS surface, m.type AS type",
        {},
        10,
    )
    assert len(mentions) == 6  # one :Mention per extracted endpoint

    endpoint_ids = {e.entity_id for a in assertions for e in (a.subject, a.object)}
    assert "wikidata_qid:Q2041974" in endpoint_ids  # enrichment -> deterministic
    assert "lei:529900T8BM49AURSDO55" in endpoint_ids
    assert "ac43-vw" in endpoint_ids
    assert resolve.hash_entity_id("corporation", "die firma") in endpoint_ids
    assert resolve.hash_entity_id("corporation", "vag") in endpoint_ids

    first = assertions[0]
    from limes.types import Assertion

    assert isinstance(first, Assertion)  # ExtractedAssertion -> Assertion conversion
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
