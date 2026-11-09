# desktop/tests/contract/test_openapi_surface.py | v1.1.0 | AC-DC-7 via the generated schema
"""Contract: the web client consumes the API's real OpenAPI surface.

Supersedes the retired Python model-mirror parity (`test_model_parity.py`
over `limes_desktop.api.models`): the DC-17 client is the TypeScript SPA, so
its parity evidence is generated. Three invariants:

1. The committed `desktop/web/src/api/openapi.json` equals the schema the
   API's `create_app()` produces right now — regenerate with
   `pnpm -C desktop/web gen:api` after any API surface change.
2. Every endpoint call the TS client makes exists in that schema.
3. Every schema path/method is mirrored by exactly one client call — the
   desktop mirrors the whole query surface; an API route without a client
   entry point is a hole, not a convenience.

No node is required: the committed files are plain text checked here.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
EXPORTER = REPO_ROOT / "tools" / "export_openapi.py"
OPENAPI_JSON = REPO_ROOT / "desktop" / "web" / "src" / "api" / "openapi.json"
SCHEMA_TS = REPO_ROOT / "desktop" / "web" / "src" / "api" / "schema.ts"
CLIENT_TS = REPO_ROOT / "desktop" / "web" / "src" / "api" / "client.ts"

_VERBS = ("get", "post", "put", "delete", "patch")


def _exporter() -> Any:
    spec = importlib.util.spec_from_file_location("limes_export_openapi", EXPORTER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _openapi_surface(current: dict[str, Any]) -> set[tuple[str, str]]:
    surface: set[tuple[str, str]] = set()
    for path, operations in current["paths"].items():
        shape = re.sub(r"\{[^/{}]+\}", "{}", path)
        for method in operations:
            if method in _VERBS:
                surface.add((method.upper(), shape))
    return surface


def _client_surface() -> set[tuple[str, str]]:
    text = CLIENT_TS.read_text(encoding="utf-8")
    calls: set[tuple[str, str]] = set()
    # Path templates are shown either with their method directly on the seam
    # (this.get(`/api/...`)) or via the `queryOutcome` helper whose first
    # argument is a POST path, so both shapes contribute.
    pattern = re.compile(
        r'this\.(get|post|put|delete|queryOutcome)\(\s*(?:["\'`])(/api/[^"\'`]+)'
    )
    for method, raw in pattern.findall(text):
        verb = "POST" if method == "queryOutcome" else method.upper()
        template = raw[len("/api") :]
        template = template.split("?", 1)[0]  # literal queries are not part of the shape
        # Seam convention in client.ts: path parameters are always
        # `${encodeURIComponent(...)}`; a bare `${var}` ending the template
        # is the query-suffix builder (`/cost/ledger${suffix}`), so the URL
        # path ends before it.
        end = re.search(r"\$\{([^{}]*)\}$", template)
        if end is not None and "(" not in end.group(1):
            template = template[: end.start()]
        template = re.sub(r"\$\{[^{}]*\}", "{}", template)
        if not template.startswith("/"):
            template = f"/{template}"
        calls.add((verb, template))
    return calls


# Surfaces the desktop contract names — every one must have a client entry
# point (same curation policy as the retired test_model_parity MIRRORED list).
_REQUIRED_MIRROR = frozenset(
    {
        ("GET", "/health"),
        ("GET", "/ontology"),
        ("GET", "/ontology/versions"),
        ("GET", "/builder/schema"),
        ("POST", "/query/nl"),
        ("POST", "/query/builder"),
        ("POST", "/query/cypher"),
        ("GET", "/entity/{}"),
        ("GET", "/entity/{}/enrichment"),
        ("GET", "/entity/{}/neighbors"),
        ("GET", "/public-offices"),
        ("GET", "/search"),
        ("POST", "/coverage"),
        ("GET", "/saved-queries"),
        ("POST", "/saved-queries"),
        ("DELETE", "/saved-queries/{}"),
        ("GET", "/sources"),
        ("GET", "/cost/ledger"),
        ("GET", "/ingest/status"),
        ("GET", "/operations/capabilities"),
        ("POST", "/operations/jobs"),
        ("GET", "/operations/jobs/{}"),
        ("GET", "/news/investigations"),
        ("PUT", "/news/investigations/{}"),
        ("POST", "/news/investigations/{}/replay"),
        ("POST", "/news/investigations/{}/event-match-reviews"),
        ("GET", "/news/investigations/{}/developments"),
        ("GET", "/news/claims"),
        ("GET", "/news/documents/{}"),
        ("GET", "/news/assertions/{}/evidence"),
    }
)

# API surfaces intentionally outside the desktop contract (checked against
# LIMES_Desktop_Client_Requirements: the requirements name only GET /health
# for the API version, and the claims/investigations/developments/documents
# set for news; evaluation-pool reads, document review writes and operator
# job cancellation have no desktop resource). Anything else left unmirrored
# by a future API addition fails the parity test until it is either mirrored
# or consciously added here with its requirement-level reason.
_ALLOWED_UNMIRRORED = frozenset(
    {
        ("GET", "/version"),
        ("GET", "/news/evaluation"),
        ("PUT", "/news/documents/{}/review"),
        ("POST", "/operations/jobs/{}/cancel"),
    }
)


def test_committed_openapi_is_current() -> None:
    exporter = _exporter()
    current = exporter.current_schema()
    committed = json.loads(OPENAPI_JSON.read_text(encoding="utf-8"))
    assert committed == current, (
        "desktop/web/src/api/openapi.json drifted from the API surface; "
        "run `pnpm -C desktop/web gen:api` and commit both generated files"
    )


def test_generated_schema_covers_every_path() -> None:
    """schema.ts is the openapi-typescript product of the committed JSON:
    every OpenAPI path appears as a key in its generated `paths` object."""
    committed = json.loads(OPENAPI_JSON.read_text(encoding="utf-8"))
    schema_text = SCHEMA_TS.read_text(encoding="utf-8")
    for path in committed["paths"]:
        assert f'"{path}":' in schema_text, f"schema.ts is missing path {path!r}"


def test_ts_client_calls_match_openapi_surface() -> None:
    current = _exporter().current_schema()
    api_surface = _openapi_surface(current)
    client_surface = _client_surface()
    assert client_surface, f"no /api calls recognized in {CLIENT_TS}"

    invented = client_surface - api_surface
    unmirrored = api_surface - client_surface
    unexpected = sorted(unmirrored - _ALLOWED_UNMIRRORED)
    unrequired = sorted(_REQUIRED_MIRROR - client_surface)
    assert not invented, f"client endpoint(s) absent from the API: {sorted(invented)}"
    assert not unexpected, (
        "API endpoint(s) without a TS client mirror outside the allowed "
        f"residual set: {unexpected}"
    )
    assert not unrequired, (
        "Requirement-named surface(s) without a TS client mirror: "
        f"{sorted(_REQUIRED_MIRROR - client_surface)}"
    )
