# limes-desktop

PySide6 (Qt 6) desktop client for the LIMES knowledge graph. It fully replaces
the Dash UI: search, entity detail with provenance, three query surfaces
(natural language, query builder, Cypher console), network/map/timeline
visualization, read-only operational monitoring, and backup orchestration.

The client is a strict API consumer. Every graph fact comes from the FastAPI
service over HTTP; the single exception is backup, which shells out to
`limes backup` inside the worker container. It holds no Neo4j driver, no
ontology literals, and no extraction code, so it degrades explicitly
(connection banner, per-view states) when the stack is down.

## Install and run

```bash
make desktop-install        # uv sync --project desktop
make desktop-run            # MODE=ui for the real GUI; default prints the version
```

The entry point is `limes-desktop` (`limes_desktop.__main__:main`, declared in
`desktop/pyproject.toml`); `limes-desktop --version` prints the version and
exits.

## Test and lint

```bash
make desktop-test           # pytest desktop/tests/unit desktop/tests/contract
make desktop-lint           # ruff check desktop/src desktop/tests
```

The unit and contract suites are offline (Qt runs on the `offscreen` platform;
API interactions are `respx`-mocked). The integration suite needs the shared
test Neo4j container and is invoked separately, like the root suites
(AGENTS.md, D-63):

```bash
./venv/bin/python -m pytest desktop/tests/integration -q
```

## Docs

- Requirements: `docs/LIMES_Desktop_Client_Requirements_v1.0.0.md`
- Architecture: `docs/LIMES_Desktop_Client_Architecture_v1.0.0.md`
