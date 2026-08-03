# tests/acceptance/test_ac24_builder.py | v1.0.0 | introduced by WP-39
"""AC-24: the builder cannot construct a query violating domain or range;
every rejection is precise.

`translate_spec` is the builder's translation seam: a spec that would
violate a domain or range (or name an unknown type, relation, or malformed
property) is rejected with a precise message naming the hop. The API
maps the rejection to 400.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from limes.api.builder import BuilderSpecRejected, translate_spec
from limes.api.models import BuilderHop, BuilderSpec
from limes.config import Settings
from limes.ontology.registry import load_ontology
from tests.fixtures.graph_data import make_api_client, wipe_graph
from tests.integration.conftest import Neo4jInstance

REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "ontology.yaml"


def _settings() -> Settings:
    return Settings(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="limes",
        neo4j_password="pw",
        ontology_path=ONTOLOGY_PATH,
        feeds_config_path=REPO_ROOT / "ontology" / "feeds.yaml",
        gold_set_path=REPO_ROOT / "gold_set" / "gold_set.jsonl",
        baseline_path=REPO_ROOT / "gold_set" / "baseline.json",
        archive_path=REPO_ROOT / "archive",
        openrouter_api_key="sk-test",
        query_default_limit=500,
    )


def _spec(start_type: str = "Corporation", hops: list[BuilderHop] | None = None) -> BuilderSpec:
    return BuilderSpec(start_type=start_type, hops=hops or [])


def test_ac24_valid_spec_translates():
    ontology = load_ontology(ONTOLOGY_PATH)
    spec = _spec(
        hops=[
            BuilderHop(
                relation="SUBSIDIARY_OF",
                direction="out",
                target_type="Corporation",
            )
        ]
    )
    cypher, _params = translate_spec(spec, ontology, _settings())
    assert "(n0:Corporation)" in cypher
    assert "-[:SUBSIDIARY_OF]->(n1:Corporation)" in cypher
    assert cypher.endswith("LIMIT 500")


@pytest.mark.parametrize(
    "spec,message",
    [
        (_spec(start_type="NotAType"), "unknown start type"),
        (
            _spec(
                hops=[
                    BuilderHop(relation="NotARelation", direction="out", target_type="Corporation")
                ]
            ),
            "hop 1: unknown relation",
        ),
        (
            _spec(
                hops=[BuilderHop(relation="SUBSIDIARY_OF", direction="out", target_type="NotAType")]
            ),
            "hop 1: unknown target type",
        ),
        # SUBSIDIARY_OF domain is Corporation: a Person subject violates it.
        (
            _spec(
                hops=[BuilderHop(relation="SUBSIDIARY_OF", direction="in", target_type="Person")]
            ),
            "does not admit 'Person' as subject",
        ),
        # HEADQUARTERED_IN range is Location: a Person object violates it.
        (
            _spec(
                hops=[
                    BuilderHop(relation="HEADQUARTERED_IN", direction="out", target_type="Person")
                ]
            ),
            "does not admit 'Person' as object",
        ),
        # AMENDS is non-temporal: a temporal qualifier on it is refused.
        (
            _spec(
                hops=[
                    BuilderHop(
                        relation="AMENDS",
                        direction="out",
                        target_type="LegalAct",
                        temporal_qualifier="current",
                    )
                ]
            ),
            "non-temporal",
        ),
        # A property name that is not a valid Cypher identifier.
        (
            _spec(
                hops=[
                    BuilderHop(
                        relation="SUBSIDIARY_OF",
                        direction="out",
                        target_type="Corporation",
                        filters={"bad name!": 1},
                    )
                ]
            ),
            "not a valid Cypher identifier",
        ),
    ],
)
def test_ac24_every_invalid_spec_is_rejected_precisely(spec: BuilderSpec, message: str):
    ontology = load_ontology(ONTOLOGY_PATH)
    with pytest.raises(BuilderSpecRejected, match=message):
        translate_spec(spec, ontology, _settings())


def test_ac24_api_refuses_an_invalid_spec_with_400(
    neo4j_instance: Neo4jInstance,
    tmp_path: Path,
):
    wipe_graph(neo4j_instance)
    with make_api_client(neo4j_instance, tmp_path) as client:
        body = {
            "start_type": "Person",
            "hops": [
                {"relation": "SUBSIDIARY_OF", "direction": "out", "target_type": "Corporation"}
            ],
        }
        response = client.post("/query/builder", json=body)
        assert response.status_code == 400, response.text
        assert "does not admit 'Person' as subject" in response.text
