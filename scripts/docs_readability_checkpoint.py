#!/usr/bin/env python3
"""c_2 docs readability checkpoint runner."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check_docs_readability.py"
DOCS = [
    ROOT / "docs" / "AGENT_START_HERE.zh-TW.md",
    ROOT / "docs" / "AGENT_HANDOFF.md",
    ROOT / "docs" / "C2_QUICK_STARTUP_DELIVERY_SOP.md",
]
FFFD_FIXTURE = ROOT / "tests" / "fixtures" / "docs_readability" / "contains_fffd.md"
PUA_FIXTURE = ROOT / "tests" / "fixtures" / "docs_readability" / "contains_pua.md"
PYTEST_CMD = [sys.executable, "-m", "pytest", "tests/test_docs_readability_checker.py", "-q"]


def _run(cmd: list[str], *, cwd: Path | None = None) -> tuple[int, str]:
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode, output


def _is_docs_scan_ok() -> bool:
    cmd = [
        sys.executable,
        str(CHECKER),
        str(CHECKER),
        *map(str, DOCS),
    ]
    rc, output = _run(cmd, cwd=ROOT)
    print(output.rstrip())
    return rc == 0 and "PASS: no decode errors, no marker risks detected" in output


def _is_negative_fixture_ok() -> bool:
    cmd = [
        sys.executable,
        str(CHECKER),
        "--strict",
        str(FFFD_FIXTURE),
        str(PUA_FIXTURE),
    ]
    rc, output = _run(cmd, cwd=ROOT)
    print(output.rstrip())
    return (
        rc == 2
        and "WARN: soft-readability concerns" in output
        and "U+FFFD present" in output
        and "PUA chars found" in output
    )


def _is_cli_help_ok() -> bool:
    rc_mod = 0
    for target in ("vizcompress", "vizcompress.cli"):
        rc, output = _run([sys.executable, "-m", target, "--help"], cwd=ROOT)
        print(output.rstrip())
        if rc != 0 or "usage:" not in output:
            rc_mod += 1
    return rc_mod == 0


def _is_no_manifest_schema_change() -> bool:
    changed = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        check=False,
        text=True,
        encoding="utf-8",
        capture_output=True,
    ).stdout.splitlines()
    no_diff = changed + []
    if not no_diff:
        return True
    blocked_keywords = {"manifest", "schema"}
    blocked_dirs = {"src/vizcompress", "src/vizcompress/"}
    for p in changed:
        low = p.lower()
        if low in blocked_dirs or any(k in low for k in blocked_keywords):
            return False
    return True


def _run_pytest() -> tuple[bool, str]:
    rc, output = _run(PYTEST_CMD, cwd=ROOT)
    return rc == 0, output


def _print_report(
    clean_scan: bool,
    fixture: bool,
    cli_help: bool,
    no_manifest: bool,
    pytest_ok: bool,
) -> None:
    print(f"clean_docs_scan_passed={'true' if clean_scan else 'false'}")
    print(f"negative_fixture_detection_passed={'true' if fixture else 'false'}")
    print(f"cli_help_passed={'true' if cli_help else 'false'}")
    print(f"no_manifest_schema_change={'true' if no_manifest else 'false'}")
    print(f"readability_pytest_passed={'true' if pytest_ok else 'false'}")


def main() -> int:
    clean_scan = _is_docs_scan_ok()
    fixture = _is_negative_fixture_ok()
    cli_help = _is_cli_help_ok()
    no_manifest = _is_no_manifest_schema_change()
    pytest_ok, pytest_output = _run_pytest()
    print(pytest_output.rstrip())

    _print_report(
        clean_scan=clean_scan,
        fixture=fixture,
        cli_help=cli_help,
        no_manifest=no_manifest,
        pytest_ok=pytest_ok,
    )

    return 0 if all([clean_scan, fixture, cli_help, no_manifest, pytest_ok]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
