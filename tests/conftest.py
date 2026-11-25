"""pytest configuration: isolate every test run from your real data (see tests/_isolation.py)."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import tests._isolation  # noqa: E402,F401  (must run before any backend import)
