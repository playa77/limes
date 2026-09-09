# desktop/tests/conftest.py | v0.1.0 | Headless-safe Qt: offscreen platform before any Qt import
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# test modules import shared stubs (test_main_window_support) by bare name
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "unit"))
