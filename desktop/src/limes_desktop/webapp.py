# desktop/src/limes_desktop/webapp.py | v1.1.0 | DC-17 loopback launcher
"""The launcher for the ReUI web desktop (DC-17 / A11).

One FastAPI app on a loopback-only bind that:

- serves the built SPA (`desktop/web/dist`, `LIMES_DESKTOP_DIST`, or the
  packaged `resources/web/dist`) with an index fallback for deep links,
- proxies `/api/*` to the active profile's base URL while injecting the
  session bearer token the browser never sees — the response body travels
  verbatim, same-origin redirects are re-dispatched (bounded), cross-origin
  redirects are refused, and transport failures surface as the §11 503 shape,
- exposes the connection-profile CRUD (`/profiles`) over the XDG store.

Tokens live in process memory only, keyed by endpoint. They arrive from
`LIMES_OPERATOR_TOKEN` / `LIMES_API_TOKEN` or the session dialog — never from
the profile store — and never appear in a response, a log, or on disk.
The session descriptor reports which credential *kind* the proxy would
inject, by proving the operator credential against the API's capabilities
endpoint; the credential value itself is never served.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, cast

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from limes_desktop.config import ConnectionProfile, ProfileStore, restrict_base_url

VERSION = "1.1.0"

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_PORT = 8747
MAX_REDIRECT_HOPS = 5
PROXY_TIMEOUT_S = 30.0

_CREDENTIAL_KIND = Literal["operator", "api", "none"]
_CAPABILITIES_PATH = "/operations/capabilities"

# Forwarded to the API: exactly what the proxy decides, never the browser's
# ambient state (no cookies, no forwarded chains, no client authorization).
_FORWARD_HEADERS = ("accept", "content-type")


def _envelope(status: int, code: str, message: str) -> JSONResponse:
    """Launcher-internal failures in the §6 error shape the web client reads."""
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": {}}},
    )


def resolve_dist_dir() -> Path:
    """Locate the built SPA: env override, packaged copy, then the workspace
    checkout. Deployment (.deb / packaged bundle) stays deferred in the
    roadmap, so the checkout layout is the supported base."""

    env = os.environ.get("LIMES_DESKTOP_DIST", "")
    candidates = (
        [Path(env)] if env
        else [
            Path(__file__).resolve().parent / "resources" / "web" / "dist",
            Path(__file__).resolve().parents[2] / "web" / "dist",
        ]
    )
    for candidate in candidates:
        if (candidate / "index.html").is_file():
            return candidate
    searched = ", ".join(str(c) for c in candidates) or "LIMES_DESKTOP_DIST (unset)"
    raise RuntimeError(
        "the web desktop bundle is missing; build it with `pnpm build` inside "
        f"desktop/web/ or point LIMES_DESKTOP_DIST at it — searched: {searched}"
    )


class TokenBody(BaseModel):
    token: str


class ProfileBody(BaseModel):
    name: str
    base_url: str


class ActiveBody(BaseModel):
    active: str | None


class SessionDescriptor(BaseModel):
    token_kind: _CREDENTIAL_KIND
    profile: str | None
    base_url: str


def create_launcher_app(
    dist_dir: Path | None = None,
    store: ProfileStore | None = None,
    http: httpx.AsyncClient | None = None,
    env_credential: tuple[str, str] | None = None,
) -> FastAPI:
    """Build the launcher. `store` and `http` are injectable for tests; the
    entry point passes None (XDG store default client, fresh async HTTP client)."""

    profile_store = store if store is not None else ProfileStore()
    transport = http if http is not None else httpx.AsyncClient(
        timeout=httpx.Timeout(PROXY_TIMEOUT_S), follow_redirects=False
    )
    if dist_dir is not None:
        dist = dist_dir.resolve()
    else:
        dist = resolve_dist_dir().resolve()

    # Session credential memory: endpoint → (token, kind). Seeded base URLs
    # inherit the env credential; dialog tokens are endpoint-specific.
    tokens: dict[str, tuple[str, str]] = {}

    def active_profile() -> ConnectionProfile | None:
        return profile_store.active()

    def credential_for(base_url: str) -> tuple[str, str] | None:
        if base_url in tokens:
            return tokens[base_url]
        if env_credential is not None:
            return env_credential
        return None

    async def classify_token(base_url: str, token: str) -> Literal["operator", "api"]:
        """One bounded capabilities probe; 200 proves the operator credential.
        Anything else (including transport failure) reads as the plain API
        kind — capabilities are re-proven by the client session anyway."""

        headers = {"Authorization": f"Bearer {token}"}
        try:
            probe = await transport.request(
                "GET", f"{base_url}{_CAPABILITIES_PATH}", headers=headers
            )
            return "operator" if probe.status_code == 200 else "api"
        except httpx.RequestError:
            return "api"

    def descriptor() -> SessionDescriptor:
        active = active_profile()
        base_url = active.base_url if active is not None else DEFAULT_BASE_URL
        credential = credential_for(base_url)
        kind = (
            credential[1]
            if credential is not None and credential[1] in ("operator", "api")
            else "none"
        )
        assert kind in ("operator", "api", "none")
        return SessionDescriptor(
            token_kind=cast(_CREDENTIAL_KIND, kind),
            profile=active.name if active is not None else None,
            base_url=base_url,
        )

    app = FastAPI(title="LIMES web desktop launcher", docs_url=None, redoc_url=None)

    # -- launcher session (session memory only, descriptor without secrets) ---

    @app.get("/session")
    def launcher_session() -> SessionDescriptor:
        return descriptor()

    @app.post("/session/token")
    async def set_session_token(body: TokenBody) -> SessionDescriptor:
        token = body.token.strip()
        active = active_profile()
        base_url = active.base_url if active is not None else DEFAULT_BASE_URL
        if not token:
            raise HTTPException(status_code=400, detail="an empty token cannot be submitted")
        tokens[base_url] = (token, await classify_token(base_url, token))
        return descriptor()

    # -- connection profiles (FR-DC-001/003) ---------------------------------

    @app.put("/profiles")
    def save_profile(body: ProfileBody) -> dict[str, str]:
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="profile name required")
        try:
            base_url = restrict_base_url(body.base_url)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        profile_store.save(ConnectionProfile(name=name, base_url=base_url))
        return {"name": name, "base_url": base_url}

    @app.get("/profiles")
    def list_profiles() -> dict[str, dict[str, str]]:
        return {
            profile.name: {"name": profile.name, "base_url": profile.base_url}
            for profile in profile_store.profiles()
        }

    @app.get("/profiles/active")
    def active_profile_name() -> dict[str, str | None]:
        active = active_profile()
        return {"active": active.name if active is not None else None}

    @app.put("/profiles/active")
    def set_active_profile(body: ActiveBody) -> Response:
        if body.active is not None and body.active not in {
            profile.name for profile in profile_store.profiles()
        }:
            raise HTTPException(status_code=404, detail=f"unknown profile: {body.active}")
        profile_store.set_active(body.active)
        return Response(status_code=204)

    @app.delete("/profiles/{name}")
    def delete_profile(name: str) -> Response:
        existing = {profile.name: profile for profile in profile_store.profiles()}
        if name not in existing:
            raise HTTPException(status_code=404, detail=f"unknown profile: {name}")
        active = active_profile()
        if active is not None and active.name == name:
            tokens.pop(active.base_url, None)
        profile_store.delete(name)
        return Response(status_code=204)

    # -- /api bearer proxy -----------------------------------------------------

    def _origin(url: httpx.URL) -> tuple[str | None, str | None, int | None]:
        return (url.scheme, url.host, url.port)

    async def _forward(
        method: str,
        path: str,
        query: str,
        body: bytes,
        forward_headers: dict[str, str],
    ) -> Response:
        active = active_profile()
        if active is None:
            return _envelope(503, "NO_ACTIVE_PROFILE", "no active connection profile")
        base_url = active.base_url
        target = f"{base_url}{path}"
        if query:
            target = f"{target}?{query}"
        credential = credential_for(base_url)
        headers = dict(forward_headers)
        if credential is not None:
            headers["Authorization"] = f"Bearer {credential[0]}"
        try:
            response = await transport.request(method, target, headers=headers, content=body)
        except httpx.RequestError:
            return _envelope(503, "API_UNREACHABLE", "API transport unavailable")
        origin = _origin(response.request.url)
        hops = 0
        while 300 <= response.status_code < 400:
            following = response.next_request
            if following is None or hops >= MAX_REDIRECT_HOPS:
                return _envelope(
                    502,
                    "REDIRECT_BLOCKED",
                    "API redirect limit reached or redirect target missing",
                )
            if _origin(following.url) != origin:
                return _envelope(
                    502,
                    "REDIRECT_BLOCKED",
                    "API redirect outside the configured origin is forbidden",
                )
            try:
                response = await transport.send(following, follow_redirects=False)
            except httpx.RequestError:
                return _envelope(503, "API_UNREACHABLE", "API transport unavailable")
            hops += 1
        relayed = {
            name: value
            for name, value in response.headers.items()
            if name.lower() in ("content-type", "x-limes-ontology-version")
        }
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=relayed,
            media_type=None,
        )

    @app.api_route(
        "/api/{rest:path}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
    )
    async def proxy(request: Request, rest: str) -> Response:
        body = await request.body()
        forward_headers = {
            name: value
            for name, value in request.headers.items()
            if name.lower() in _FORWARD_HEADERS and (name.lower() != "content-type" or body)
        }
        return await _forward(
            request.method,
            f"/{rest}",
            request.url.query,
            body,
            forward_headers,
        )

    # -- built SPA (index fallback for deep links; /api is registered above) --

    @app.get("/{asset:path}", include_in_schema=False)
    def spa_asset(asset: str) -> Response:
        relative = asset or "index.html"
        candidate = (dist / relative).resolve()
        try:
            candidate.relative_to(dist)
        except ValueError:
            raise HTTPException(status_code=404, detail="not found") from None
        if candidate.is_file():
            return FileResponse(candidate)
        index = dist / "index.html"
        return FileResponse(index)

    return app
