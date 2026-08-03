# tests/acceptance/test_ac00_meta_coverage.py | v1.0.0 | introduced by WP-39
"""Meta-test for the acceptance suite itself (WP-39's first acceptance
criterion): every AC-01…AC-44 from Doc 2 §14 has a mechanical test in this
directory.

The suite's own invariant is enforced mechanically: the test scans the
acceptance directory for `test_acNN_*` functions and fails if any of the
44 criteria lacks one. A criterion that stops being covered breaks this
test before it can break silently.
"""

from __future__ import annotations

import re
from pathlib import Path

ACCEPTANCE_DIR = Path(__file__).resolve().parent


def _covered_ac_ids() -> set[int]:
    covered: set[int] = set()
    for path in sorted(ACCEPTANCE_DIR.glob("test_ac*.py")):
        if path.name == "test_ac00_meta_coverage.py":
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"test_ac(\d+)(?:_|\b)", text):
            covered.add(int(match.group(1)))
    return covered


def test_every_acceptance_criterion_has_a_mechanical_test():
    covered = _covered_ac_ids()
    missing = [f"AC-{number:02d}" for number in range(1, 45) if number not in covered]
    assert not missing, f"no mechanical test for: {', '.join(missing)}"
    assert len(covered) >= 44
