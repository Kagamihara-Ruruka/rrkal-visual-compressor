from __future__ import annotations

from _test_helpers import *  # re-export shared test helpers

from pathlib import Path
import sys

# Keep legacy import-time behavior: prefer local src on module search path.
ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_SRC = str(ROOT_DIR / "src")
if PROJECT_SRC not in sys.path:
    sys.path.insert(0, PROJECT_SRC)
