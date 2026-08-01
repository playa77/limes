# tests/conftest.py | v1.0.0 | introduced by WP-01
# Makes `limes` importable from the src layout when pytest runs without the
# package installed (e.g. a bare `python3 -m pytest` outside the venv).
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
