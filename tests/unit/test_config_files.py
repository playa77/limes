# tests/unit/test_config_files.py | v1.0.0 | safe model pin updates
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from dotenv import dotenv_values

from limes.config_files import update_model_pins
from limes.errors import ConfigurationError


def test_secret_files_and_non_model_keys_are_never_modified(tmp_path: Path):
    secrets = tmp_path / "secrets.env"
    secrets.write_text("LIMES_OPENROUTER_API_KEY=private\n")
    with pytest.raises(ConfigurationError):
        update_model_pins(secrets, {"LIMES_EXTRACTION_MODEL": "test/model"})
    with pytest.raises(ConfigurationError):
        update_model_pins(tmp_path / "models.env", {"LIMES_OPENROUTER_API_KEY": "private"})
    assert secrets.read_text() == "LIMES_OPENROUTER_API_KEY=private\n"
    assert not (tmp_path / "models.env").exists()


def test_repeated_pin_update_is_idempotent(tmp_path: Path):
    path = tmp_path / "models.env"
    values = {"LIMES_EXTRACTION_MODEL": "test/model"}
    update_model_pins(path, values)
    modified = path.stat().st_mtime_ns
    update_model_pins(path, values)
    assert path.stat().st_mtime_ns == modified


def test_failed_replace_preserves_previous_pins(tmp_path: Path, monkeypatch):
    path = tmp_path / "models.env"
    update_model_pins(path, {"LIMES_EXTRACTION_MODEL": "test/previous"})

    def fail(*args):
        raise OSError("disk failure")

    monkeypatch.setattr("limes.config_files.os.replace", fail)
    with pytest.raises(OSError):
        update_model_pins(path, {"LIMES_EXTRACTION_MODEL": "test/new"})
    assert dotenv_values(path)["LIMES_EXTRACTION_MODEL"] == "test/previous"
    assert not list(tmp_path.glob(".models-*"))


def test_concurrent_writers_preserve_both_roles(tmp_path: Path):
    path = tmp_path / "models.env"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            pool.submit(update_model_pins, path, values)
            for values in (
                {"LIMES_EXTRACTION_MODEL": "test/extraction"},
                {"LIMES_NL2CYPHER_MODEL": "test/query"},
            )
        ]
        for result in results:
            result.result()
    values = dotenv_values(path)
    assert values["LIMES_EXTRACTION_MODEL"] == "test/extraction"
    assert values["LIMES_NL2CYPHER_MODEL"] == "test/query"


@pytest.mark.parametrize("value", ["", "test/model\nKEY=oops", "test model", "test/model#comment"])
def test_pin_values_cannot_inject_configuration(tmp_path: Path, value: str):
    with pytest.raises(ConfigurationError):
        update_model_pins(tmp_path / "models.env", {"LIMES_EXTRACTION_MODEL": value})


def test_existing_model_file_cannot_interpolate_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMES_OPENROUTER_API_KEY", "private")
    path = tmp_path / "models.env"
    text = "LIMES_EXTRACTION_MODEL=${LIMES_OPENROUTER_API_KEY}\n"
    path.write_text(text)
    with pytest.raises(ConfigurationError):
        update_model_pins(path, {"LIMES_NL2CYPHER_MODEL": "test/query"})
    assert path.read_text() == text
    assert "private" not in path.read_text()


def test_model_file_symlink_is_rejected(tmp_path):
    secret = tmp_path / "secrets.env"
    secret.write_text("private")
    path = tmp_path / "models.env"
    path.symlink_to(secret)
    with pytest.raises(ConfigurationError, match="symbolic link"):
        update_model_pins(path, {"LIMES_NL2CYPHER_MODEL": "test/query"})
    assert secret.read_text() == "private"
