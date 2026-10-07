# tests/unit/test_config.py | v1.0.1 | introduced by WP-02, env-file isolation by WP-40
from pathlib import Path

import pytest

from limes import config as config_module
from limes.config import load_settings
from limes.errors import ConfigurationError

REQUIRED = {
    "LIMES_NEO4J_URI": "bolt://localhost:7687",
    "LIMES_NEO4J_USER": "limes",
    "LIMES_NEO4J_PASSWORD": "secret",
    "LIMES_ONTOLOGY_PATH": "/tmp/ontology.yaml",
    "LIMES_FEEDS_CONFIG_PATH": "/tmp/feeds.yaml",
    "LIMES_GOLD_SET_PATH": "/tmp/gold_set.jsonl",
    "LIMES_BASELINE_PATH": "/tmp/baseline.json",
    "LIMES_ARCHIVE_PATH": "/tmp/archive",
}


@pytest.fixture(autouse=True)
def no_env_file(monkeypatch):
    """The tests assert on the environment alone: a `.env` next to the CWD
    would leak values (e.g. LIMES_NEO4J_PASSWORD) into the settings and
    silently invalidate the missing-key cases. `_env_file=None` disables the
    file source entirely, so the suite passes regardless of the host."""
    real_settings = config_module.Settings
    monkeypatch.setattr(
        config_module,
        "Settings",
        lambda **kwargs: real_settings(**{"_env_file": None, **kwargs}),
    )


@pytest.fixture
def env(monkeypatch):
    """Populate every required key; individual tests remove what they test."""
    for key, value in REQUIRED.items():
        monkeypatch.setenv(key, value)
    yield
    for key in REQUIRED:
        monkeypatch.delenv(key, raising=False)


def test_load_settings_all_keys_present(env):
    settings = load_settings()
    assert settings.neo4j_uri == "bolt://localhost:7687"
    assert settings.embedding_dimensions == 1024
    assert settings.model_pin_stage == "provisional"
    assert settings.archive_path == Path("/tmp/archive")


def test_load_settings_missing_required_key_names_it(env, monkeypatch):
    monkeypatch.delenv("LIMES_NEO4J_PASSWORD")
    with pytest.raises(ConfigurationError, match="neo4j_password"):
        load_settings()


def test_load_settings_empty_required_key_names_it(env, monkeypatch):
    monkeypatch.setenv("LIMES_NEO4J_USER", "")
    with pytest.raises(ConfigurationError, match="neo4j_user"):
        load_settings()


def test_load_settings_measured_stage_requires_pinned_models(env, monkeypatch):
    monkeypatch.setenv("LIMES_MODEL_PIN_STAGE", "measured")
    with pytest.raises(ConfigurationError, match="extraction_model"):
        load_settings()


def test_load_settings_measured_stage_with_pins_passes(env, monkeypatch):
    monkeypatch.setenv("LIMES_MODEL_PIN_STAGE", "measured")
    monkeypatch.setenv("LIMES_EXTRACTION_MODEL", "some-model")
    monkeypatch.setenv("LIMES_ADJUDICATION_MODEL", "some-model")
    monkeypatch.setenv("LIMES_EMBEDDING_MODEL", "some-model")
    monkeypatch.setenv("LIMES_NL2CYPHER_MODEL", "some-model")
    settings = load_settings()
    assert settings.model_pin_stage == "measured"


def test_settings_ignores_unknown_env_keys(env, monkeypatch):
    monkeypatch.setenv("LIMES_TYPO_KEY", "boom")
    settings = load_settings()
    assert not hasattr(settings, "typo_key")


def test_empty_environment_does_not_shadow_pin_file(tmp_path, monkeypatch):
    from limes.config import Settings

    pin_file = tmp_path / "models.env"
    pin_file.write_text("LIMES_EXTRACTION_MODEL=test/pinned\n")
    monkeypatch.setenv("LIMES_EXTRACTION_MODEL", "")
    settings = Settings(
        _env_file=pin_file, **{k.removeprefix("LIMES_").lower(): v for k, v in REQUIRED.items()}
    )
    assert settings.extraction_model == "test/pinned"


@pytest.mark.parametrize(
    "field,value",
    [
        ("inference_temperature", -1),
        ("inference_temperature", 3),
        ("inference_max_tokens", 0),
        ("inference_reasoning_effort", "typo"),
    ],
)
def test_invalid_inference_parameters_fail_configuration(field, value):
    from pydantic import ValidationError

    from limes.config import Settings

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            **{k.removeprefix("LIMES_").lower(): v for k, v in REQUIRED.items()},
            **{field: value},
        )


def test_pin_file_precedence_and_nonempty_environment_override(tmp_path, monkeypatch):
    from limes.config import Settings

    legacy = tmp_path / "legacy.env"
    models = tmp_path / "models.env"
    legacy.write_text("LIMES_EXTRACTION_MODEL=test/old\n")
    models.write_text("LIMES_EXTRACTION_MODEL=test/new\n")
    monkeypatch.delenv("LIMES_EXTRACTION_MODEL", raising=False)
    values = {key.removeprefix("LIMES_").lower(): value for key, value in REQUIRED.items()}
    assert Settings(_env_file=(legacy, models), **values).extraction_model == "test/new"
    monkeypatch.setenv("LIMES_EXTRACTION_MODEL", "test/environment")
    assert Settings(_env_file=(legacy, models), **values).extraction_model == "test/environment"
