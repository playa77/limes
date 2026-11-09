# desktop/tests/unit/test_webapp.py | v1.1.0 | launcher surfaces: SPA, proxy, profiles, session
"""Behavior coverage of `limes_desktop.webapp.create_launcher_app`.

Every proxied/upstream interaction uses respx mocks (no real network); the
spans of behavior are one per distinct failure/success path: verbatim
upstream error bodies, browser-credential stripping, bounded same-origin
redirect following, forbidden cross-origin redirects, the error envelope
shape, profile CRUD over the injected store, session-kind classification and
the token-never-appears-in-a-response rule, plus the static SPA's index
fallback and traversal guard.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from limes_desktop.config import ProfileStore
from limes_desktop.webapp import VERSION, create_launcher_app

BASE_URL = "https://api.example"
ACTIVE = {"name": "lab", "base_url": BASE_URL}

DIST_FILES = {
    "index.html": b"<!doctype html><title>index-fallback</title>",
    "assets/app.js": b"console.log('spa');",
}


@pytest.fixture()
def dist_dir(tmp_path: Path):
    root = tmp_path / "dist"
    for name, content in DIST_FILES.items():
        path = (root / name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return root


@pytest.fixture()
def store(tmp_path: Path):
    return ProfileStore(config_dir=tmp_path / "xdg")


def build(store: ProfileStore, dist_dir: Path, **kwargs: object) -> TestClient:
    app = create_launcher_app(dist_dir=dist_dir, store=store, **kwargs)
    return TestClient(app)


# -- static SPA host ----------------------------------------------------------


def test_index_served_and_deep_link_falls_back(store: ProfileStore, dist_dir) -> None:
    client = build(store, dist_dir)
    index = client.get("/")
    assert index.status_code == 200
    assert b"index-fallback" in index.content

    deep = client.get("/ops/offices")
    assert deep.status_code == 200
    assert b"index-fallback" in deep.content

    asset = client.get("/assets/app.js")
    assert asset.status_code == 200
    assert asset.content == DIST_FILES["assets/app.js"]


def test_dot_dot_outside_dist_is_never_served(store: ProfileStore, dist_dir, tmp_path) -> None:
    # A secret one level above the bundle root is never served: every
    # request path either resolves inside dist (assets), falls back to the
    # SPA index, or 404s — never the outsider's bytes. The raw "/../" forms
    # collapse in URL normalization, so percent-encoded variants probe the
    # launcher's own resolve-back-under-dist guard.
    secret = tmp_path / "secret.txt"
    secret.write_bytes(b"OUTSIDE-SECRET")

    client = build(store, dist_dir)
    for path in (
        "/%2e%2e/secret.txt",
        "/assets/%2E%2E/secret.txt",
        "/assets/..%2fsecret.txt",
        "/assets/../../secret.txt",
        "/assets/../../etc/passwd",
    ):
        shot = client.get(path)
        assert b"OUTSIDE-SECRET" not in shot.content, path
        if shot.status_code != 200:
            assert shot.status_code == 404
            assert shot.json() == {"detail": "not found"}


# -- bearer proxy --------------------------------------------------------------


def save_active(store: ProfileStore) -> None:
    from limes_desktop.config import ConnectionProfile

    store.save(ConnectionProfile(name=ACTIVE["name"], base_url=BASE_URL))
    store.set_active(ACTIVE["name"])


@respx.mock
def test_proxy_rewrites_paths_and_injects_browser_invisible_token(
    store: ProfileStore, dist_dir
) -> None:
    save_active(store)
    route = respx.get(f"{BASE_URL}/health").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    client = build(store, dist_dir, env_credential=("secret-token", "api"))

    response = client.get("/api/health", headers={"Authorization": "Bearer browser-evil"})
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    upstream_headers = route.calls.last.request.headers
    assert upstream_headers["Authorization"] == "Bearer secret-token"
    # The browser's own credential state never travels upstream.
    assert "cookie" not in upstream_headers


@respx.mock
def test_upstream_error_body_travels_verbatim(store: ProfileStore, dist_dir) -> None:
    save_active(store)
    respx.post(f"{BASE_URL}/query/nl").mock(
        return_value=httpx.Response(
            422,
            json={
                "error": {"code": "BAD_REQUEST", "message": "hop ceiling exceeded", "details": {}}
            },
        )
    )
    client = build(store, dist_dir)
    bob = client.post("/api/query/nl", json={"question": "?"})
    assert bob.status_code == 422
    assert bob.json()["error"]["message"] == "hop ceiling exceeded"


@respx.mock
def test_transport_unreachable_maps_to_503(store: ProfileStore, dist_dir) -> None:
    save_active(store)
    respx.get(f"{BASE_URL}/sources").mock(side_effect=httpx.ConnectError("no listener"))
    client = build(store, dist_dir)
    shot = client.get("/api/sources")
    assert shot.status_code == 503
    assert shot.json()["error"]["code"] == "API_UNREACHABLE"


@respx.mock
def test_same_origin_redirect_followed(store: ProfileStore, dist_dir) -> None:
    save_active(store)
    respx.get(f"{BASE_URL}/entity/x/neighbors").mock(
        side_effect=[
            httpx.Response(301, headers={"Location": f"{BASE_URL}/entity/x/neighbors2"}),
            httpx.Response(200, json={"nodes": []}),
        ]
    )
    respx.get(f"{BASE_URL}/entity/x/neighbors2").mock(
        return_value=httpx.Response(200, json={"nodes": []})
    )
    client = build(store, dist_dir)
    out = client.get("/api/entity/x/neighbors")
    assert out.status_code == 200
    assert out.json() == {"nodes": []}


@respx.mock
def test_cross_origin_redirect_is_forbidden(store: ProfileStore, dist_dir) -> None:
    save_active(store)
    respx.get(f"{BASE_URL}/entity/x").mock(
        return_value=httpx.Response(302, headers={"Location": "https://evil.example/x"}),
    )
    client = build(store, dist_dir)
    out = client.get("/api/entity/x")
    assert out.status_code == 502
    assert out.json()["error"]["code"] == "REDIRECT_BLOCKED"


@respx.mock
def test_redirect_hop_ceiling_block(store: ProfileStore, dist_dir) -> None:
    save_active(store)
    respx.get(f"{BASE_URL}/loop").mock(
        return_value=httpx.Response(301, headers={"Location": f"{BASE_URL}/loop"})
    )
    client = build(store, dist_dir)
    out = client.get("/api/loop")
    assert out.status_code == 502
    assert out.json()["error"]["code"] == "REDIRECT_BLOCKED"


@respx.mock
def test_no_active_profile_returns_503(store: ProfileStore, dist_dir) -> None:
    client = build(store, dist_dir)
    shot = client.get("/api/health")
    assert shot.status_code == 503
    assert shot.json()["error"]["code"] == "NO_ACTIVE_PROFILE"


# -- profiles -------------------------------------------------------------------
def test_profile_crud_membership(store: ProfileStore, dist_dir) -> None:
    client = build(store, dist_dir)

    made = client.put("/profiles", json={"name": "lab", "base_url": BASE_URL})
    assert made.status_code == 200
    assert made.json() == {"name": "lab", "base_url": BASE_URL}

    listing = client.get("/profiles")
    assert listing.json() == {"lab": {"name": "lab", "base_url": BASE_URL}}

    activated = client.put("/profiles/active", json={"active": "lab"})
    assert activated.status_code == 204
    assert client.get("/profiles/active").json() == {"active": "lab"}

    # Unknown activation targets and unknown deletions are precise.
    assert client.put("/profiles/active", json={"active": "ghost"}).status_code == 404
    assert client.delete("/profiles/ghost").status_code == 404

    gone = client.delete("/profiles/lab")
    assert gone.status_code == 204
    assert client.get("/profiles").json() == {}
    assert client.get("/profiles/active").json() == {"active": None}


def test_profile_requires_http_s(store: ProfileStore, dist_dir) -> None:
    client = build(store, dist_dir)
    bad = client.put("/profiles", json={"name": "x", "base_url": "ftp://nope"})
    assert bad.status_code == 400
    assert "http" in bad.json()["detail"]
    # Plain http to a remote host stays forbidden by the credential rule.
    remote_http = client.put("/profiles", json={"name": "x", "base_url": "http://api.example"})
    assert remote_http.status_code == 400


def test_clear_active_accepts_null(store: ProfileStore, dist_dir) -> None:
    save_active(store)
    client = build(store, dist_dir)
    shot = client.put("/profiles/active", json={"active": None})
    assert shot.status_code == 204
    assert client.get("/profiles/active").json() == {"active": None}


# -- session credential (memory only) ------------------------------------------


@respx.mock
def test_session_descriptor_reports_none_without_credential(
    store: ProfileStore, dist_dir
) -> None:
    save_active(store)
    client = build(store, dist_dir)
    shot = client.get("/session")
    assert shot.json()["token_kind"] == "none"
    assert shot.json()["profile"] == ACTIVE["name"]
    assert shot.json()["base_url"] == BASE_URL


@respx.mock
def test_submitted_token_classifies_and_never_echoes(store: ProfileStore, dist_dir) -> None:
    save_active(store)
    respx.get(f"{BASE_URL}/operations/capabilities").mock(
        return_value=httpx.Response(403, json={"detail": "operator credential required"})
    )
    client = build(store, dist_dir)

    typed = client.post("/session/token", json={"token": "typed-secret"})
    assert typed.status_code == 200
    # The value must not appear in the response at all.
    assert "typed-secret" not in typed.text
    assert typed.json()["token_kind"] == "api"

    respx.get(f"{BASE_URL}/operations/capabilities").mock(return_value=httpx.Response(200, json={}))
    promoted = client.post("/session/token", json={"token": "operator-secret"})
    assert promoted.json()["token_kind"] == "operator"
    assert "operator-secret" not in promoted.text


@respx.mock
def test_env_credential_is_operator_and_proxied(store: ProfileStore, dist_dir) -> None:
    save_active(store)
    route = respx.get(f"{BASE_URL}/health").mock(
        return_value=httpx.Response(200, json={"status": "ok"})
    )
    client = build(store, dist_dir, env_credential=("op-secret", "operator"))
    assert client.get("/session").json()["token_kind"] == "operator"
    client.get("/api/health")
    assert route.calls.last.request.headers["Authorization"] == "Bearer op-secret"


def test_empty_token_submission_rejected(store: ProfileStore, dist_dir) -> None:
    save_active(store)
    client = build(store, dist_dir)
    shot = client.post("/session/token", json={"token": "  "})
    assert shot.status_code == 400


# -- version identity -----------------------------------------------------------


def test_version_module_constant_matches_package() -> None:
    from importlib.metadata import PackageNotFoundError, version

    try:
        expect = version("limes-desktop")
    except PackageNotFoundError:
        pytest.skip("workspace package not installed")
    assert VERSION == expect
