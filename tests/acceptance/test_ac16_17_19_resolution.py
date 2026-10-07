# tests/acceptance/test_ac16_17_19_resolution.py | v1.0.0 | introduced by WP-39
"""AC-16, AC-17, AC-19: entity resolution.

AC-16: deterministic keys short-circuit resolution — no embedding, no
vector query (a counting driver proves zero graph reads), no paid call
(respx active with no routes: any HTTP attempt fails the test loudly).

AC-17: resolution routes across all four §8.8.3 bands, and the mint
branch writes no node directly — entity counts are unchanged by the
resolve call.

AC-19: `unlink` retracts a `SAME_AS` by setting `retracted_at` without
deleting any node; the loader-written assertion stays attributed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
import respx
from httpx import Response

from limes.graph.driver import GraphDriver
from limes.graph.loader import load
from limes.graph.schema import provision
from limes.ontology.registry import load_ontology
from limes.resolution import link, resolve
from limes.resolution.resolve import resolve_assertions
from limes.types import Mention
from tests.acceptance import _resolution_support as support
from tests.acceptance._resolution_support import (
    CATALOGUE_URL,
    COMPLETIONS_URL,
    EMBED_URL,
    FakeWikidata,
    adjudication_handler,
    clear_process_caches,
    counting_from,
    doc,
    embed_handler,
    extracted,
    loaded_assertion,
    registry_with,
    run_context,
    settings_for,
)
from tests.fixtures.embeddings import (
    expected_vector,
    fake_embedder,
    vector_with_cosines,
)
from tests.fixtures.graph_data import wipe_graph
from tests.integration.conftest import Neo4jInstance

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"

SUBJECT_LEI = "529900T8BM49AURSDO55"
OBJECT_LEI = "549300BEQ1B5L7Z2WE72"


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


def test_ac16_deterministic_keys_short_circuit(driver: GraphDriver, tmp_path: Path):
    counting = counting_from(driver)
    body = f"{SUBJECT_LEI} holds {OBJECT_LEI}."
    extracted_items = [
        extracted(
            Mention(surface=SUBJECT_LEI, type="Corporation"),
            "SUBSIDIARY_OF",
            Mention(surface=OBJECT_LEI, type="Corporation"),
            0,
            len(body),
        )
    ]
    ctx, governor = run_context(
        counting, registry_with(FakeWikidata({})), settings_for(tmp_path), tmp_path
    )

    # No respx routes are registered: any HTTP attempt fails the test.
    with respx.mock:
        assertions, stats = resolve_assertions(extracted_items, ctx, doc(body, "ac16-doc"))

    assert stats.deterministic == 2
    assert stats.auto_linked == stats.adjudicated == stats.minted == 0
    assert counting.read_calls == 0  # no vector query was issued
    assert governor.checks == []  # no paid call was made
    assert assertions[0].subject.entity_id == f"lei:{SUBJECT_LEI}"
    assert assertions[0].object.entity_id == f"lei:{OBJECT_LEI}"


def test_ac17_routes_across_all_four_bands(driver: GraphDriver, tmp_path: Path):
    """The index is populated through the production load path with the
    fake embedder; query vectors are rotations of the entity embeddings
    into the target §8.8.3 bands."""
    ontology = load_ontology(ONTOLOGY_PATH)
    load(
        driver,
        [
            loaded_assertion("ac17-vw", "Rheinwerk Konzern AG"),
            loaded_assertion("ac17-parent", "Rheinwerk Beteiligung GmbH"),
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
        "Die Firma closes. "
        f"{SUBJECT_LEI} leads them."
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
    extracted_items = [
        extracted(
            Mention(surface="Volkswagen", type="Corporation"),
            "SUBSIDIARY_OF",
            Mention(surface="VW", type="Corporation"),
            *spans["Volkswagen"],
        ),
        extracted(
            Mention(surface="VAG", type="Corporation"),
            "SUBSIDIARY_OF",
            Mention(surface="Die Firma", type="Corporation"),
            *spans["VAG"],
        ),
        extracted(
            Mention(surface=SUBJECT_LEI, type="Corporation"),
            "SUBSIDIARY_OF",
            Mention(surface="Volkswagen", type="Corporation"),
            *spans["Volkswagen"],
        ),
    ]

    def text_for(surface: str, item) -> str:
        return f"{surface} (Corporation) — {body[item.evidence_start : item.evidence_end]}"

    vectors = {
        text_for("Volkswagen", extracted_items[0]): vector_with_cosines([(e_vw, 0.95)]),
        text_for("VW", extracted_items[0]): vector_with_cosines([(e_vw, 0.88)]),
        text_for("VAG", extracted_items[1]): vector_with_cosines([(e_vw, 0.50)]),
        text_for("Die Firma", extracted_items[1]): vector_with_cosines([(e_vw, 0.50)]),
    }
    counting = counting_from(driver)
    ctx, governor = run_context(
        counting, registry_with(FakeWikidata({})), settings_for(tmp_path), tmp_path
    )

    before = driver.read("MATCH (n:Entity) RETURN count(n) AS c", {}, 10)[0]["c"]

    with respx.mock:
        respx.get(CATALOGUE_URL).mock(return_value=Response(200, json=support.CATALOGUE))
        respx.post(EMBED_URL).mock(side_effect=embed_handler(vectors))
        respx.post(COMPLETIONS_URL).mock(
            side_effect=adjudication_handler({"Mention A: VW": {"same": True, "confidence": 0.85}})
        )
        assertions, stats = resolve_assertions(extracted_items, ctx, doc(body, "ac17-doc"))

    # Bands, per endpoint occurrence: deterministic (LEI), auto (Volkswagen
    # twice — subject of A1 and object of A3, one resolution), adjudicated
    # (VW), mint (VAG, Die Firma).
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
    assert by_surface["VW"]["entity_id"] == "ac17-vw"
    assert by_surface["VW"]["method"] == "adjudicated"
    assert "VAG" not in by_surface  # minted: no link
    assert "Die Firma" not in by_surface

    assert assertions[0].subject.entity_id == "ac17-vw"
    assert assertions[0].object.entity_id == "ac17-vw"
    assert len(governor.commits) == 2  # one embed call, one adjudication call
    assert assertions[1].subject.entity_id == resolve.hash_entity_id("corporation", "vag")


def test_ac19_unlink_retracts_without_deleting(driver: GraphDriver, tmp_path: Path):
    """AC-19: unlink sets retracted_at on SAME_AS; no node is deleted and
    the loader-written assertion stays attributed."""
    ontology = load_ontology(ONTOLOGY_PATH)
    load(driver, [loaded_assertion("ac19-1", "Volkswagen AG")], ontology)
    mention_id = link.create_mention(
        driver, Mention(surface="Volkswagen", type="Corporation"), "ac19-doc", 10, 20
    )
    link.link(driver, mention_id, "ac19-1", "auto", 0.95, datetime(2026, 8, 1, 12, 30, tzinfo=UTC))
    link.unlink(driver, mention_id, "ac19-1", datetime(2026, 8, 1, 13, 0, tzinfo=UTC))

    rows = driver.read(
        "MATCH (m:Mention {mention_id: $id})-[r:SAME_AS]->(e:Entity {entity_id: 'ac19-1'}) "
        "RETURN r.retracted_at AS retracted_at, e.label AS label",
        {"id": mention_id},
        10,
    )
    assert rows[0]["retracted_at"] is not None
    assert rows[0]["label"] == "Volkswagen AG"  # the entity node still exists

    # Prior assertions remain attributed: the loader-written edge survives
    # the unlink untouched.
    assertion_rows = driver.read(
        "MATCH ()-[r:SUBSIDIARY_OF {assertion_id: 'res-ac19-1'}]->() "
        "RETURN r.source_id AS source_id, r.confidence AS confidence",
        {},
        10,
    )
    assert assertion_rows[0]["source_id"] == "s1"
    assert assertion_rows[0]["confidence"] == 0.9

    # Re-linking after an unlink re-activates the same relationship.
    link.link(driver, mention_id, "ac19-1", "auto", 0.96, datetime(2026, 8, 1, 13, 30, tzinfo=UTC))
    rows = driver.read(
        "MATCH (m:Mention {mention_id: $id})-[r:SAME_AS]->(e) RETURN r.retracted_at AS at",
        {"id": mention_id},
        10,
    )
    assert rows[0]["at"] is None
