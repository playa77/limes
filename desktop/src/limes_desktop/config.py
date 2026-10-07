# desktop/src/limes_desktop/config.py | v0.1.0 | profiles + JSON store (FR-DC-001/003)
import json
import os
from pathlib import Path

from pydantic import BaseModel


class ConnectionProfile(BaseModel):
    """A named API endpoint the desktop client can connect to (FR-DC-001)."""

    name: str
    base_url: str = "http://127.0.0.1:8000"
    # Legacy profile field, ignored by API-backed backup.
    compose_root: str | None = None


class ProfileStore:
    """Persists connection profiles as profiles.json + active in a config dir."""

    def __init__(self, config_dir: Path | None = None) -> None:
        self._dir = config_dir if config_dir is not None else Path(
            os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
        ) / "limes-desktop"

    @property
    def _profiles_file(self) -> Path:
        return self._dir / "profiles.json"

    @property
    def _active_file(self) -> Path:
        return self._dir / "active"

    def _ensure_dir(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)

    def _atomic_write(self, path: Path, text: str) -> None:
        self._ensure_dir()
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)

    def _read_profiles(self) -> dict[str, ConnectionProfile]:
        try:
            raw = json.loads(self._profiles_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(raw, dict):
            return {}
        profiles: dict[str, ConnectionProfile] = {}
        for key, value in raw.items():
            try:
                profiles[str(key)] = ConnectionProfile.model_validate(value)
            except ValueError:
                continue
        return profiles

    def _read_active(self) -> str | None:
        try:
            name = self._active_file.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return name or None

    def profiles(self) -> list[ConnectionProfile]:
        return list(self._read_profiles().values())

    def save(self, profile: ConnectionProfile) -> None:
        profiles = self._read_profiles()
        profiles[profile.name] = profile
        payload = {name: p.model_dump() for name, p in profiles.items()}
        self._atomic_write(self._profiles_file, json.dumps(payload, indent=2))

    def delete(self, name: str) -> None:
        profiles = self._read_profiles()
        profiles.pop(name, None)
        payload = {n: p.model_dump() for n, p in profiles.items()}
        self._atomic_write(self._profiles_file, json.dumps(payload, indent=2))
        if self._read_active() == name:
            self._active_file.unlink(missing_ok=True)

    def active(self) -> ConnectionProfile | None:
        name = self._read_active()
        if name is None:
            return None
        return self._read_profiles().get(name)

    def set_active(self, name: str) -> None:
        self._atomic_write(self._active_file, name)
