#!/usr/bin/env python3
"""c_2 docs readability checkpoint runner."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check_docs_readability.py"
CHECKPOINT_TEST_MODE_ENV = "DOCS_READABILITY_CHECKPOINT_TEST_MODE"
DOCS = [
    ROOT / "docs" / "AGENT_START_HERE.zh-TW.md",
    ROOT / "docs" / "AGENT_HANDOFF.md",
    ROOT / "docs" / "C2_QUICK_STARTUP_DELIVERY_SOP.md",
]
FFFD_FIXTURE = ROOT / "tests" / "fixtures" / "docs_readability" / "contains_fffd.md"
PUA_FIXTURE = ROOT / "tests" / "fixtures" / "docs_readability" / "contains_pua.md"
LEAF_PYTEST_PATTERN = "test_leaf_"
PYTEST_CMD = [sys.executable, "-m", "pytest", "tests/test_docs_readability_checker.py", "-q"]
PROCESS_TIMEOUT_SECONDS = 30
PROCESS_FANOUT_WARNING_LIMIT = 20


def _run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = PROCESS_TIMEOUT_SECONDS,
    env: dict[str, str] | None = None,
) -> tuple[int, str]:
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            text=True,
            capture_output=True,
            encoding="utf-8",
            env=run_env,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return 124, (exc.stdout or "") + (exc.stderr or "")
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
    rc, output = _run(["git", "diff", "--name-only", "HEAD"])
    if rc != 0:
        return False
    changed = output.splitlines()
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
    pytest_cmd.extend(["-k", LEAF_PYTEST_PATTERN, "--maxfail=1"])
    rc, output = _run(
        pytest_cmd,
        cwd=ROOT,
        env={CHECKPOINT_TEST_MODE_ENV: "1"},
    )
    return rc == 0, output


def _snapshot_python_processes() -> list[str]:
    sample_cmds: list[str] = []
    if os.name == "nt":
        rc, output = _run(
            ["tasklist", "/V", "/FO", "CSV", "/NH", "/FI", "IMAGENAME eq python.exe"],
            cwd=ROOT,
            timeout=10,
            env={},
        )
        if rc != 0:
            return sample_cmds
        reader = csv.reader(io.StringIO(output))
        for row in reader:
            if not row:
                continue
            # CSV format: ["python.exe","1234","Console","1","...","No",...,"cmdline"]
            if len(row) >= 9:
                sample_cmds.append(f"PID={row[1]} CMD={row[8]}")
            elif len(row) >= 2:
                sample_cmds.append(f"PID={row[1]} IMG={row[0]}")
    else:
        try:
            import psutil

            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                name = (proc.info.get("name") or "").lower()
                if "python" in name:
                    cmd = proc.info.get("cmdline") or []
                    sample_cmds.append(f"PID={proc.pid} CMD={' '.join(cmd)}")
        except Exception:
            return sample_cmds
    return sample_cmds


def _collect_report(
    *,
    clean_scan: bool,
    fixture: bool,
    cli_help: bool,
    no_manifest: bool,
    pytest_ok: bool,
    schema_version: str,
    python_process_count: int,
    python_process_samples: list[str],
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
        "c2_python_process_count": python_process_count,
        "boundary": {
            "no_manifest_schema_change_required": True,
            "cli_behavior_unchanged": True,
            "algorithm_unchanged": True,
            "cross_repo_integration_not_touched": True,
            "leaf_tests_only": True,
            "recursion_guard_set": True,
        },
        "c2_python_process_samples": python_process_samples[:5],
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
    print(f"c2_python_process_count={report['c2_python_process_count']}")
    if report["c2_python_process_count"] > PROCESS_FANOUT_WARNING_LIMIT:
        print("WARN: process fan-out high", report["c2_python_process_count"])


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
    process_snapshot = _snapshot_python_processes()

    report = _collect_report(
        clean_scan=clean_scan,
        fixture=fixture,
        cli_help=cli_help,
        no_manifest=no_manifest,
        pytest_ok=pytest_ok,
        schema_version="docs-readability-checkpoint/v1",
        python_process_count=len(process_snapshot),
        python_process_samples=process_snapshot,
    )

    if args.json:
        _print_json_report(report)
    else:
        _print_report(report)

    return 0 if report["checkpoint_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
