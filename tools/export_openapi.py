# tools/export_openapi.py | v1.0.0 | DC-17 A12: committed OpenAPI schema for the web client
"""Export the LIMES API's current OpenAPI schema for the web client.

The SPA's generated TypeScript schema (`desktop/web/src/api/schema.ts`,
openapi-typescript) is built from this file, and the desktop contract test
(`desktop/tests/contract/test_openapi_surface.py`) re-computes the schema and
rejects drift against the committed `desktop/web/src/api/openapi.json`.
Regenerate with `venv/bin/python tools/export_openapi.py` after any API
surface change, then run `pnpm -C desktop/web gen:api`.

No server is started: FastAPI builds the route schema from the router
declarations alone.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from limes.api.main import create_app
from limes.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPO_ROOT / "desktop" / "web" / "src" / "api" / "openapi.json"


def export_settings() -> Settings:
    """Settings that satisfy construction without a reachable deployment.

    The schema generator never opens network connections; local paths point
    at a disposable temporary directory, the ontology at the repo artifact.
    """

    temp = Path(tempfile.gettempdir()) / "limes-openapi-export" / "scratch"
    temp.mkdir(parents=True, exist_ok=True)
    return Settings(
        api_token="test-api-token",
        operator_token="test-operator",
        neo4j_uri="bolt://127.0.0.1:7687",
        neo4j_user="unused",
        neo4j_password="unused",
        neo4j_database="neo4j",
        ontology_path=REPO_ROOT / "ontology" / "ontology.yaml",
        feeds_config_path=REPO_ROOT / "ontology" / "feeds.yaml",
        gold_set_path=temp / "gold_set.jsonl",
        baseline_path=temp / "baseline.json",
        archive_path=temp / "archive",
    )


def current_schema() -> dict[str, Any]:
    app = create_app(export_settings())
    return app.openapi()


def main() -> None:
    OUTPUT_PATH.write_text(json.dumps(current_schema(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
