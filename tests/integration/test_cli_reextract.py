# tests/integration/test_cli_reextract.py | v1.0.0 | introduced by WP-28
"""CLI reextract tests per Doc 2 §8.14 (Doc 1 §9.4).

The `--budget` refusal is exercised across a real process boundary (G2) —
a typer usage error at parse time, before any context is built. The
re-extraction semantics themselves (cache miss under a new prompt version,
superseded retraction, never deletion) are proven by WP-27's
`test_reextract_retracts_superseded_and_relinks` at the `execute_run`
level; the CLI layer here adds the version flow (settings copy) and the
default source selection, which are unit-tested in-process.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_reextract_refuses_without_budget():
    # G2 — the refusal is a typer usage error: non-zero exit, the missing
    # option named, no context built, no network.
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "limes.cli.main",
            "reextract",
            "--prompt-version",
            "1.0.1",
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode != 0
    assert "--budget" in result.stderr


def test_reextract_defaults_to_unstructured_sources():
    # D-45: without --source, reextract covers exactly the
    # document-producing (unstructured) sources; an explicit source is
    # honored verbatim.
    from limes.cli.reextract import _reextract_sources
    from limes.sources.registry import build_default_registry

    registry = build_default_registry()
    expected = {
        source_id
        for source_id in registry.source_ids()
        if registry.get(source_id).kind == "unstructured"
    }
    assert set(_reextract_sources(None)) == expected
    assert _reextract_sources("feeds") == ["feeds"]
