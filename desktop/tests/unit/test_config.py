# desktop/tests/unit/test_config.py | v0.1.0 | ProfileStore behavior (FR-DC-001)
from pathlib import Path

from limes_desktop.config import ConnectionProfile, ProfileStore


def test_store_roundtrip(tmp_path: Path) -> None:
    store = ProfileStore(config_dir=tmp_path)
    p = ConnectionProfile(name="local", base_url="http://127.0.0.1:8000",
                          compose_root="/home/daniel/projects/limes")
    store.save(p)
    assert store.profiles() == [p]


def test_active_profile_roundtrip(tmp_path: Path) -> None:
    store = ProfileStore(config_dir=tmp_path)
    store.save(ConnectionProfile(name="local"))
    store.set_active("local")
    assert store.active() is not None and store.active().name == "local"


def test_defaults_match_fr_dc_001(tmp_path: Path) -> None:
    p = ConnectionProfile(name="x")
    assert p.base_url == "http://127.0.0.1:8000"
    assert p.compose_root is None


def test_corrupt_file_yields_empty(tmp_path: Path) -> None:
    (tmp_path / "profiles.json").write_text("{not json")
    assert ProfileStore(config_dir=tmp_path).profiles() == []
