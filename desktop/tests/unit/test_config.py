# desktop/tests/unit/test_config.py | v1.1.0 | Profile store + URL seam (FR-DC-001/003)
from pathlib import Path

import pytest
from limes_desktop.config import ConnectionProfile, ProfileStore, restrict_base_url


def test_store_roundtrip(tmp_path: Path) -> None:
    store = ProfileStore(config_dir=tmp_path)
    p = ConnectionProfile(name="local", base_url="http://127.0.0.1:8000")
    store.save(p)
    assert store.profiles() == [p]


def test_active_profile_roundtrip(tmp_path: Path) -> None:
    store = ProfileStore(config_dir=tmp_path)
    store.save(ConnectionProfile(name="local"))
    store.set_active("local")
    assert store.active() is not None and store.active().name == "local"


def test_set_active_none_clears(tmp_path: Path) -> None:
    store = ProfileStore(config_dir=tmp_path)
    store.save(ConnectionProfile(name="local"))
    store.set_active("local")
    store.set_active(None)
    assert store.active() is None


def test_delete_removes_active_selection(tmp_path: Path) -> None:
    store = ProfileStore(config_dir=tmp_path)
    store.save(ConnectionProfile(name="local"))
    store.set_active("local")
    store.delete("local")
    assert store.profiles() == []
    assert store.active() is None


def test_defaults_match_fr_dc_001() -> None:
    p = ConnectionProfile(name="x")
    assert p.base_url == "http://127.0.0.1:8000"


def test_corrupt_file_yields_empty(tmp_path: Path) -> None:
    (tmp_path / "profiles.json").write_text("{not json")
    assert ProfileStore(config_dir=tmp_path).profiles() == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("http://127.0.0.1:8000", "http://127.0.0.1:8000"),
        ("https://limes.example.org/", "https://limes.example.org"),
    ],
)
def test_restrict_base_url_accepts(raw: str, expected: str) -> None:
    assert restrict_base_url(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "ftp://x", "http://", "notaurl", "http://limes.example.org"],
)
def test_restrict_base_url_rejects(raw: str) -> None:
    with pytest.raises(ValueError):
        restrict_base_url(raw)
