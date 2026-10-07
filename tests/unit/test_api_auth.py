# tests/unit/test_api_auth.py | v1.0.0 | every API surface authenticates
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from limes.api.main import create_app
from limes.config import Settings
from limes.errors import ConfigurationError
from tests.fixtures.graph_data import ONTOLOGY_PATH

TOKEN = "test-session-credential"


def settings(tmp_path, token=TOKEN):
    return Settings(
        _env_file=None,
        api_token=token,
        neo4j_uri="bolt://unused:7687",
        neo4j_user="unused",
        neo4j_password="unused",
        ontology_path=ONTOLOGY_PATH,
        feeds_config_path=ONTOLOGY_PATH.parent / "feeds.yaml",
        gold_set_path=tmp_path / "gold_set.jsonl",
        baseline_path=tmp_path / "baseline.json",
        archive_path=tmp_path / "archive",
    )


@pytest.fixture
def app(tmp_path, monkeypatch):
    driver = SimpleNamespace(read=lambda *args: [{"one": 1}], close=lambda: None)
    monkeypatch.setattr("limes.api.main.GraphDriver", lambda *args: driver)
    monkeypatch.setattr("limes.api.main.provision", lambda *args: None)
    return create_app(settings(tmp_path))


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/health"),
        ("GET", "/ontology"),
        ("GET", "/cost/ledger"),
        ("POST", "/query/nl"),
        ("POST", "/saved-queries"),
        ("GET", "/docs"),
        ("GET", "/openapi.json"),
    ],
)
@pytest.mark.parametrize("authorization", ["", "Bearer wrong", "Basic wrong"])
def test_missing_or_invalid_credentials_reject_every_surface(app, method, path, authorization):
    with TestClient(app) as client:
        response = client.request(method, path, headers={"Authorization": authorization})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert TOKEN not in response.text


@pytest.mark.parametrize("scheme", ["Bearer", "bearer", "BEARER"])
def test_authenticated_consumer_can_use_api_without_host_privileges(app, scheme):
    with TestClient(app, headers={"Authorization": f"{scheme} {TOKEN}"}) as client:
        response = client.get("/ontology")
    assert response.status_code == 200
    assert response.json()["version"] == "1.0.0"


def test_authentication_preserves_read_only_query_validation(app):
    with TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"}) as client:
        response = client.post("/query/cypher", json={"cypher": "CREATE (n)"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "CYPHER_VALIDATION_FAILED"


def test_api_refuses_to_start_without_a_credential(tmp_path):
    with pytest.raises(ConfigurationError, match="LIMES_API_TOKEN"):
        with TestClient(create_app(settings(tmp_path, token=""))):
            pass
