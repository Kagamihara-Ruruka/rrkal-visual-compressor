from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT_DIR / "scripts" / "check_docs_readability.py"
FIXTURE_DIR = ROOT_DIR / "tests" / "fixtures" / "docs_readability"


def _run_checker(target: Path, strict: bool = False) -> tuple[int, str]:
    cmd = [sys.executable, str(SCRIPT_PATH)]
    if strict:
        cmd.append("--strict")
    cmd.append(str(target))
    result = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def test_readability_checker_accepts_clean_fixture() -> None:
    fixture = FIXTURE_DIR / "clean.md"
    rc, output = _run_checker(fixture)
    assert rc == 0
    assert "PASS: no decode errors, no marker risks detected" in output


def test_readability_checker_warns_on_fffd_marker() -> None:
    fixture = FIXTURE_DIR / "contains_fffd.md"
    rc, output = _run_checker(fixture, strict=True)
    assert rc == 2
    assert "U+FFFD present" in output


def test_readability_checker_warns_on_pua_marker() -> None:
    fixture = FIXTURE_DIR / "contains_pua.md"
    rc, output = _run_checker(fixture, strict=True)
    assert rc == 2
    assert "PUA chars found" in output
