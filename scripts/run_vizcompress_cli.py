from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from _test_helpers import cli_env


def main() -> int:
    return subprocess.call(
        [sys.executable, "-m", "vizcompress.cli", *sys.argv[1:]],
        env=cli_env(),
    )


if __name__ == "__main__":
    raise SystemExit(main())
