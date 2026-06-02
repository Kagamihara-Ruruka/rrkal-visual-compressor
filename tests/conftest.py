from __future__ import annotations

from pathlib import Path
import sys
import os

from _test_helpers import cli_env

for _path in reversed([p for p in cli_env().get("PYTHONPATH", "").split(os.pathsep) if p]):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from _test_helpers import *  # re-export shared test helpers
