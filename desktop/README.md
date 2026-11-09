# LIMES desktop (DC-17 / D-99)

The desktop is a browser SPA (`desktop/web/`, React 19 + Tailwind v4 on the
ReUI/shadcn radix-nova system) served by a local FastAPI launcher
(`desktop/src/limes_desktop/`). The launcher binds loopback only, serves the
built bundle, injects the session bearer token into `/api/*` (the browser
never holds a credential), and stores connection profiles — names and URLs
only — in the XDG config store. Single-instance is a process-level advisory
lock; a second launcher exits quietly.

Run it:

```bash
UV_PROJECT_ENVIRONMENT=venv uv sync --frozen --all-packages
pnpm -C desktop/web install --frozen-lockfile
pnpm -C desktop/web build          # produces dist/ the launcher serves
venv/bin/limes-desktop            # serve on http://127.0.0.1:8747 (loopback)
```

Headless sanity: `venv/bin/limes-desktop --version`. The dist directory is
overridable via `LIMES_DESKTOP_DIST`. Connection profiles point at
`http://127.0.0.1:8000` locally, HTTPS remotely, or a loopback SSH tunnel;
credentials arrive from `LIMES_OPERATOR_TOKEN`/`LIMES_API_TOKEN` or the
session dialog and live in launcher memory for one session only.

Backup submits an operator-only durable job over the same proxied connection
and follows output asynchronously; it requires an operator credential, never
Docker or host shell access, and never auto-retries.

Tests never call paid inference. Python lanes: `make desktop-test`,
`make desktop-integration`, `make desktop-lint`. Web lane:
`make web-check` (typecheck, vitest, eslint, build). Contract guards:
`desktop/tests/contract/` (generated OpenAPI parity + ontology-literal scan
of both client halves). Generated runtime docs live in
[ARCHITECTURE](../docs/ARCHITECTURE.md) and
[OPERATIONS](../docs/OPERATIONS.md).
