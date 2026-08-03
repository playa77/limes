# tests/acceptance/test_ac44_type_closure.py | v1.0.0 | introduced by WP-39
"""AC-44: every type named in a §8 signature is defined in §5.5 or §8.15,
verified by `tools/check_docs.py`.

The check tool is the project's own consistency validator (WP-01); the
acceptance test runs it across a real process boundary and requires a
clean exit — the mechanical form of the criterion.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_ac44_check_docs_passes():
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "check_docs.py"), str(REPO_ROOT / "docs")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
