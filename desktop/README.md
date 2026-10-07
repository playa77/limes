# LIMES desktop

The PySide6 desktop is a typed, authenticated HTTP consumer. Profiles contain names
and URLs, never tokens. Credentials stay in session memory. Use HTTPS remotely or
a loopback tunnel; Docker membership is unnecessary.

Backup submits an operator-only durable job over the same HTTP connection and
follows output asynchronously. It requires an operator credential, never Docker,
a Compose root or host shell access. Neo4j is unavailable during physical backup.

Install with `UV_PROJECT_ENVIRONMENT=venv uv sync --frozen --all-packages` at the
repository root, then `venv/bin/limes-desktop`. On headless verification hosts set
`QT_QPA_PLATFORM=offscreen`. Current design/configuration and release procedures
are generated in [ARCHITECTURE](../docs/ARCHITECTURE.md) and
[OPERATIONS](../docs/OPERATIONS.md). Tests never call paid inference.
