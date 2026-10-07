# tests/unit/test_logging.py | v1.0.0 | introduced by WP-02
import json

from limes.config import Settings
from limes.logging_setup import REDACTED, SecretRedactor, configure_logging


def _settings(**overrides) -> Settings:
    base = dict(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="limes",
        neo4j_password="super-secret",
        ontology_path="/tmp/ontology.yaml",
        feeds_config_path="/tmp/feeds.yaml",
        gold_set_path="/tmp/gold_set.jsonl",
        baseline_path="/tmp/baseline.json",
        archive_path="/tmp/archive",
        log_level="INFO",
        log_format="json",
    )
    base.update(overrides)
    return Settings(**base)


def _emit(event: str, **kwargs) -> dict:
    """Configure logging, emit one event, and return the rendered JSON line."""
    import io
    import sys

    stream = io.StringIO()
    real_stdout = sys.stdout
    sys.stdout = stream
    try:
        configure_logging(_settings())
        from structlog import get_logger

        get_logger().info(event, **kwargs)
    finally:
        sys.stdout = real_stdout
    return json.loads(stream.getvalue())


def test_redactor_masks_secret_values():
    redactor = SecretRedactor(("LIMES_OPENROUTER_API_KEY", "LIMES_NEO4J_PASSWORD"))
    event = {
        "event": "x",
        "LIMES_OPENROUTER_API_KEY": "sk-live-123",
        "nested": {"LIMES_NEO4J_PASSWORD": "pw"},
    }
    out = redactor(None, "info", event)
    assert out["LIMES_OPENROUTER_API_KEY"] == REDACTED
    assert out["nested"]["LIMES_NEO4J_PASSWORD"] == REDACTED


def test_redactor_leaves_non_secret_values():
    redactor = SecretRedactor()
    out = redactor(None, "info", {"event": "x", "run_id": "r1"})
    assert out["run_id"] == "r1"
    assert out["event"] == "x"


def test_redactor_matches_lowercase_variants():
    redactor = SecretRedactor(("LIMES_NEO4J_PASSWORD",))
    out = redactor(None, "info", {"neo4j_password": "pw"})
    assert out["neo4j_password"] == REDACTED


def test_configure_logging_emits_json_with_event_and_context():
    line = _emit("hello_world", run_id="r1", source_id="gleif")
    assert line["event"] == "hello_world"
    assert line["run_id"] == "r1"
    assert line["source_id"] == "gleif"


def test_configure_logging_redacts_secret_in_output():
    line = _emit("started", LIMES_OPENROUTER_API_KEY="sk-secret")
    assert line["LIMES_OPENROUTER_API_KEY"] == REDACTED


def test_bearer_credentials_are_redacted_recursively():
    redactor = SecretRedactor()
    out = redactor(
        None, "info", {"LIMES_API_TOKEN": "private", "headers": {"Authorization": "Bearer private"}}
    )
    assert out["LIMES_API_TOKEN"] == REDACTED
    assert out["headers"]["Authorization"] == REDACTED
