# tests/integration/test_api_health.py | v1.0.0 | introduced by WP-32
"""`GET /health` per Doc 2 §6: liveness with Neo4j reachability and the
ontology version; 503 while the database is unreachable."""

from pathlib import Path

from tests.fixtures.graph_data import make_api_client
from tests.integration.conftest import Neo4jInstance

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_health_returns_200_with_ontology_version(neo4j_instance: Neo4jInstance, tmp_path: Path):
    with make_api_client(neo4j_instance, tmp_path) as client:
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["neo4j"] is True
        assert body["ontology_version"] == "1.2.0"
        assert response.headers["X-LIMES-Ontology-Version"] == "1.2.0"


def test_health_returns_503_when_neo4j_unreachable(tmp_path: Path):
    from fastapi.testclient import TestClient

    from limes.api.main import create_app
    from limes.config import Settings
    from tests.fixtures.graph_data import ONTOLOGY_PATH

    settings = Settings(
        api_token="test-api-token",
        neo4j_uri="bolt://127.0.0.1:1",
        neo4j_user="u",
        neo4j_password="p",
        ontology_path=ONTOLOGY_PATH,
        feeds_config_path=ONTOLOGY_PATH.parent / "feeds.yaml",
        gold_set_path=tmp_path / "gold_set.jsonl",
        baseline_path=tmp_path / "baseline.json",
        archive_path=tmp_path / "archive",
    )
    with TestClient(
        create_app(settings), headers={"Authorization": "Bearer test-api-token"}
    ) as client:
        response = client.get("/health")
        assert response.status_code == 503
        body = response.json()
        assert body["error"]["code"] == "NEO4J_UNREACHABLE"
