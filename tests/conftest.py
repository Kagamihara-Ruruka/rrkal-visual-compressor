from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_SRC = str(ROOT_DIR / "src")
if PROJECT_SRC not in sys.path:
    sys.path.insert(0, PROJECT_SRC)

