# LIMES

LIMES is an ontology-driven research knowledge graph for German and European
policy analysis. It combines official registries with German and English text
extraction, preserves source provenance and bitemporal assertions, and exposes
network, geographic and temporal views through a PySide6 desktop client.

LIMES is a **personal research artifact**. Source coverage is uneven and extracted
claims can be wrong; inspect provenance and hop-level coverage before interpreting
a result. Information about public office holders and registered representatives
has no automated retention or pseudonymization policy.

## Current runtime

<!-- limes-runtime: {"services":["api","neo4j","worker"],"api_publication":"127.0.0.1:8000:8000","database_published":false,"api_authentication":"bearer","desktop_credentials":"session-only","budget_enforcement":false} -->

| Runtime fact | Current contract |
|---|---|
| Shipped services | api, neo4j, worker |
| API publication | `127.0.0.1:8000:8000` |
| Database publication | None |
| API authentication | Bearer token |
| Desktop credentials | Session memory only |
| Spending enforcement | None |


Compose ships Neo4j, the authenticated API, and the existing operational worker.
The desktop replaces Dash; the Dash service is removed from both Compose files.
Legacy Dash code is retained for compatibility tests and is not a shipped service.
The API publishes `127.0.0.1:8000`; Neo4j has no published port.
`docs/TESTING_PHASE.md` is the current contract for redesigned behavior and remaining
work. The original specifications retain the graph/type/coverage contracts.

Starting or changing the stack requires its administrator. Using the API or desktop
requires the API credential, without Docker-group membership or host root access.
The worker and physical backup privilege redesign is still outstanding; operational
CLI commands currently run inside that worker. This is not yet a rootless stack.

## Configure and run

Copy these templates, keeping actual configuration untracked:

```bash
cp config/settings.env.example config/settings.env
cp config/models.env.example config/models.env
cp config/secrets.env.example config/secrets.env
```

Set Neo4j credentials and the OpenRouter key in `config/secrets.env`. Generate a
bearer token with `python -c 'import secrets; print(secrets.token_urlsafe(32))'` and
set `LIMES_API_TOKEN` in that file. Supply the same Neo4j password to Compose
interpolation with `docker compose --env-file config/secrets.env up -d --build`.
Settings and model pins contain no secrets. The API refuses startup without a token.

Defaults in `config/settings.env.example` use container paths. Host-side development
can override paths and Neo4j connection settings. Empty environment values are
unset, so an empty exported model variable cannot hide a file pin. Environment
values override file values; split files override legacy host `.env` settings.
Model selection writes only `config/models.env`, via serialized atomic replacement.

For local use, choose `http://127.0.0.1:8000` in the desktop. It asks for the token
once per endpoint and keeps it only in memory; profiles.json contains no credential.
`LIMES_API_TOKEN` may supply the initial endpoint's session credential. The token
is sent in the `Authorization: Bearer …` header, including for `/health` and `/docs`.

For a remote server, use HTTPS termination or a loopback tunnel:

```bash
ssh -N -L 8000:127.0.0.1:8000 account@server
```

The SSH account need not belong to the Docker group. Keep the desktop URL on
loopback for that tunnel. Authenticated remote plain HTTP is rejected by the client.
For direct HTTPS, forward a server's TLS proxy to its loopback API; do not publish
Neo4j. Removing the development override is not a server-promotion procedure.

## Operations and inference

| Command | Behavior |
|---|---|
| `make up` / `make down` | Administrator starts/stops the three services |
| `make ingest SOURCE=<id>` / `make ingest-all` | Operational worker commands |
| `make backfill SOURCE=<id> DAYS=<n>` | Historical ingestion; no budget gate |
| `make reextract PROMPT_VERSION=<v>` | Re-extract archived text with a cache/provenance version |
| `make select-models ARGS="--provisional"` | Catalogue-ranked model pins, no confirmation ceremony |
| `make select-models ARGS="--provisional --confirm"` | Optional interactive confirmation |
| `make select-models ARGS="--measured"` | Evaluate all roles, record scores and measured pins |
| `make evaluate ARGS="--resolution"` | Evaluate the gold/calibration sets |
| `make migrate ONTOLOGY_VERSION=<v>` | Apply an ontology migration |
| `make backup` | Existing administrator-only offline dump; replacement pending |
| `make stamp-embeddings` | Fill missing embeddings after the structured backbone |
| `make desktop-run MODE=ui` | Launch the desktop client |

Operational Make targets currently need the worker's Docker access. Paid data runs
are explicit operator actions. Bootstrap structured sources before unstructured
backfill, with embedding stamping between them, to avoid duplicated extraction.

There is no spending enforcement. `/cost/ledger` reports period spend and per-call
model/token accounting; it has no remaining-budget field. Old `--budget` options
are accepted and ignored. Run costs are calculated from the process's recorded
costs, rather than a monthly allowance shared with other processes.

Chat parameters `LIMES_INFERENCE_TEMPERATURE`, `LIMES_INFERENCE_MAX_TOKENS`, and
`LIMES_INFERENCE_REASONING_EFFORT` control requests. Empty values omit the provider
parameter. Each successful chat call logs the exact configured parameter payload
alongside purpose, model and token usage, without prompts or credentials.

Provisional pins are validated against the fetched catalogue and dated automatically.
Measured pins require finite scores and winners for all four roles, and create
`config/models.evaluation.json` with scores, winners, dataset hash, date and inference
settings. Changing extraction/embedding models reports affected data without
triggering re-extraction. Real model measurement is still an operator data run;
implementation tests exercise the flow with mocked inference.

## Development and verification

Python 3.12 and uv are required. Use one canonical environment:

```bash
UV_PROJECT_ENVIRONMENT=venv uv sync --frozen --all-packages
venv/bin/ruff check src tests desktop/src desktop/tests
venv/bin/mypy
venv/bin/python tools/check_docs.py docs/
venv/bin/python -m pytest tests/unit -q
venv/bin/python -m pytest desktop/tests/unit desktop/tests/contract -q
venv/bin/python -m pytest tests/integration -q
venv/bin/python -m pytest tests/acceptance -q
venv/bin/python -m pytest desktop/tests/integration -q
```

Graph suites create and destroy only their disposable Neo4j containers. Use
`LIMES_TEST_NEO4J_URI` for a dedicated existing test database when Docker publishing
is unavailable. Run acceptance separately. Tests never make real paid model calls.
GitHub Actions runs lint, types, docs, unit, desktop contract, integration,
acceptance and desktop integration checks, retaining JUnit evidence as artifacts.

Read `AGENTS.md`, `DECISIONS.md`, and `OPEN_ISSUES.md` for constraints and evidence.
Authentication and deployment are now in scope; worker privileges, remote operational
commands, backup orchestration and version-stamped deployments remain redesign work.
