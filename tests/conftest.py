# tests/conftest.py | v1.0.0 | introduced by WP-01
# Makes `limes` importable from the src layout when pytest runs without the
# package installed (e.g. a bare `python3 -m pytest` outside the venv).
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# PA-1 R5: keep the per-host netiquette slot locks inside a session-local dir
# so tests never touch the operator volume; per-test cases override it again.
import os
import tempfile

_SESSION_SLOT_DIR = tempfile.mkdtemp(prefix="limes-host-slots-")
os.environ.setdefault("LIMES_HOST_SLOT_DIR", _SESSION_SLOT_DIR)
