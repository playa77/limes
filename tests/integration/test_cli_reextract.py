# tests/integration/test_cli_reextract.py | v1.0.0 | introduced by WP-28
"""Re-extraction CLI without a required budget envelope (D-75)."""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_reextract_help_does_not_require_budget():
    result = subprocess.run(
        [sys.executable, "-m", "limes.cli.main", "reextract", "--help"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert result.returncode == 0
    assert "Deprecated compatibility" in result.stdout



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
