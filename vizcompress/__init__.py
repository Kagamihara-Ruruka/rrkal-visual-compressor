"""RRKAL visual compression core (local workspace entry point)."""

from __future__ import annotations

from pathlib import Path
import sys

from typing import List

_ROOT_DIR = Path(__file__).resolve().parent
_SRC_PACKAGE = _ROOT_DIR.parent / "src" / "vizcompress"

# Make module discovery resolve shim entry points and source-tree submodules.
_PATHS: List[str] = []
for _path in (_ROOT_DIR, _SRC_PACKAGE):
    _text_path = str(_path)
    if _text_path not in _PATHS:
        _PATHS.append(_text_path)
__path__ = _PATHS  # type: ignore[name-defined]

# Keep package metadata parity with canonical source package.
__version__ = "0.1.0"
__all__ = ["__version__"]

if str(_SRC_PACKAGE.parent) not in sys.path:
    sys.path.insert(0, str(_SRC_PACKAGE.parent))