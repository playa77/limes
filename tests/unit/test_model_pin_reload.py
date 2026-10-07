"""Operational pin updates take effect without host restart or credential reload."""

from types import SimpleNamespace

import pytest
from fastapi import Request

from limes.api.deps import get_nlq_context
from limes.config import reload_model_pins
from limes.config_files import update_model_pins
from limes.errors import ConfigurationError
from tests.unit.test_api_auth import settings


def test_new_pins_refresh_cached_query_context(tmp_path, monkeypatch):
    pins = tmp_path / "models.env"
    loaded = settings(tmp_path).model_copy(update={"model_pins_path": pins})
    state = SimpleNamespace(settings=loaded, ontology=object(), driver=object())
    request = Request({"type": "http", "app": SimpleNamespace(state=state)})
    builds = []

    def build(current, ontology, driver):
        context = SimpleNamespace(settings=current)
        builds.append(context)
        return context

    monkeypatch.setattr("limes.api.deps.build_nlq_context", build)
    first = get_nlq_context(request)
    assert get_nlq_context(request) is first
    update_model_pins(pins, {"LIMES_NL2CYPHER_MODEL": "provider/changed-model"})
    second = get_nlq_context(request)
    assert second is not first
    assert second.settings.nl2cypher_model == "provider/changed-model"
    assert second.settings.api_token == loaded.api_token
    assert second.settings.neo4j_password == loaded.neo4j_password
    assert len(builds) == 2


def test_overlay_cannot_replace_secrets(tmp_path):
    pins = tmp_path / "models.env"
    pins.write_text("LIMES_API_TOKEN=changed\n")
    loaded = settings(tmp_path).model_copy(update={"model_pins_path": pins})
    with pytest.raises(ConfigurationError, match="non-model"):
        reload_model_pins(loaded)


def test_environment_override_survives_pin_reload(tmp_path, monkeypatch):
    pins = tmp_path / "models.env"
    pins.write_text("LIMES_NL2CYPHER_MODEL=provider/file-model\n")
    loaded = settings(tmp_path).model_copy(
        update={
            "model_pins_path": pins,
            "nl2cypher_model": "provider/environment-model",
        }
    )
    monkeypatch.setenv("LIMES_NL2CYPHER_MODEL", "provider/environment-model")
    assert reload_model_pins(loaded).nl2cypher_model == "provider/environment-model"
