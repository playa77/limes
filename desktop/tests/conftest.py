# desktop/tests/conftest.py | v0.1.0 | Headless-safe Qt: offscreen platform before any Qt import
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
