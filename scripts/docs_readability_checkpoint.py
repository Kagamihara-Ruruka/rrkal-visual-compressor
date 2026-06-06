#!/usr/bin/env python3
"""c_2 docs readability checkpoint runner."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


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


def _is_docs_scan_ok(*, verbose: bool) -> bool:
    cmd = [
        sys.executable,
        str(CHECKER),
        str(CHECKER),
        *map(str, DOCS),
    ]
    rc, output = _run(cmd, cwd=ROOT)
    if verbose:
        print(output.rstrip())
    return rc == 0 and "PASS: no decode errors, no marker risks detected" in output


def _is_negative_fixture_ok(*, verbose: bool) -> bool:
    cmd = [
        sys.executable,
        str(CHECKER),
        "--strict",
        str(FFFD_FIXTURE),
        str(PUA_FIXTURE),
    ]
    rc, output = _run(cmd, cwd=ROOT)
    if verbose:
        print(output.rstrip())
    return (
        rc == 2
        and "WARN: soft-readability concerns" in output
        and "U+FFFD present" in output
        and "PUA chars found" in output
    )


def _is_cli_help_ok(*, verbose: bool) -> bool:
    rc_mod = 0
    for target in ("vizcompress", "vizcompress.cli"):
        rc, output = _run([sys.executable, "-m", target, "--help"], cwd=ROOT)
        if verbose:
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
    if not changed:
        return True
    blocked_keywords = {"manifest", "schema"}
    blocked_prefixes = {"src/vizcompress", "src/vizcompress/"}
    for path in changed:
        low = path.lower()
        if low in blocked_prefixes or any(keyword in low for keyword in blocked_keywords):
            return False
    return True


def _run_pytest() -> tuple[bool, str]:
    pytest_cmd = PYTEST_CMD[:] if PYTEST_CMD else [sys.executable, "-m", "pytest", "tests/test_docs_readability_checker.py", "-q"]
    if os.environ.get("DOCS_READABILITY_CHECKPOINT_TEST_MODE", "") == "1":
        pytest_cmd.extend(["-k", "not test_docs_readability_checkpoint_json_output_is_pure_json"])
    rc, output = _run(pytest_cmd, cwd=ROOT)
    return rc == 0, output


def _collect_report(
    *,
    clean_scan: bool,
    fixture: bool,
    cli_help: bool,
    no_manifest: bool,
    pytest_ok: bool,
    schema_version: str,
) -> dict[str, object]:
    checkpoint_passed = all([clean_scan, fixture, cli_help, no_manifest, pytest_ok])
    return {
        "schema": schema_version,
        "status": "pass" if checkpoint_passed else "fail",
        "clean_docs_scan_passed": clean_scan,
        "negative_fixture_detection_passed": fixture,
        "cli_help_passed": cli_help,
        "no_manifest_schema_change": no_manifest,
        "readability_pytest_passed": pytest_ok,
        "checkpoint_passed": checkpoint_passed,
        "boundary": {
            "no_manifest_schema_change_required": True,
            "cli_behavior_unchanged": True,
            "algorithm_unchanged": True,
            "cross_repo_integration_not_touched": True,
        },
    }


def _print_report(report: dict[str, object]) -> None:
    print(f"clean_docs_scan_passed={'true' if report['clean_docs_scan_passed'] else 'false'}")
    print(f"negative_fixture_detection_passed={'true' if report['negative_fixture_detection_passed'] else 'false'}")
    print(f"cli_help_passed={'true' if report['cli_help_passed'] else 'false'}")
    print(f"no_manifest_schema_change={'true' if report['no_manifest_schema_change'] else 'false'}")
    print(f"readability_pytest_passed={'true' if report['readability_pytest_passed'] else 'false'}")
    print(f"checkpoint_passed={'true' if report['checkpoint_passed'] else 'false'}")
    print(f"status={report['status']}")
    print(f"schema={report['schema']}")


def _print_json_report(report: dict[str, object], *, indent: int = 2) -> None:
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=indent))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run docs readability checkpoint")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON report",
    )
    args = parser.parse_args()

    clean_scan = _is_docs_scan_ok(verbose=not args.json)
    fixture = _is_negative_fixture_ok(verbose=not args.json)
    cli_help = _is_cli_help_ok(verbose=not args.json)
    no_manifest = _is_no_manifest_schema_change()
    pytest_ok, pytest_output = _run_pytest()
    if not args.json:
        print(pytest_output.rstrip())

    report = _collect_report(
        clean_scan=clean_scan,
        fixture=fixture,
        cli_help=cli_help,
        no_manifest=no_manifest,
        pytest_ok=pytest_ok,
        schema_version="docs-readability-checkpoint/v1",
    )

    if args.json:
        _print_json_report(report)
    else:
        _print_report(report)

    return 0 if report["checkpoint_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
