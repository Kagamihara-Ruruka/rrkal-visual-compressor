#!/usr/bin/env python3
"""Validate docs readability checkpoint JSON schema and guard against silent drift."""

from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT_SCRIPT = ROOT / "scripts" / "docs_readability_checkpoint.py"
SCHEMA = "docs-readability-checkpoint/v1"
CHECKPOINT_TEST_ENV = "DOCS_READABILITY_CHECKPOINT_TEST_MODE"
CHECKPOINT_RUNNER_ENV = "DOCS_READABILITY_CHECKPOINT_RUNNER"
PROCESS_FANOUT_WARNING_LIMIT = 20
SUBPROCESS_TIMEOUT_SECONDS = 30

REQUIRED_KEYS = (
    "clean_docs_scan_passed",
    "negative_fixture_detection_passed",
    "cli_help_passed",
    "no_manifest_schema_change",
    "readability_pytest_passed",
)

BOUNDARY_KEYS = (
    "no_manifest_schema_change_required",
    "cli_behavior_unchanged",
    "algorithm_unchanged",
    "cross_repo_integration_not_touched",
)


def _run_checkpoint_json() -> dict[str, Any]:
    env = dict(os.environ)
    env[CHECKPOINT_TEST_ENV] = "1"
    env[CHECKPOINT_RUNNER_ENV] = "1"
    result = subprocess.run(
        [sys.executable, str(CHECKPOINT_SCRIPT), "--json"],
        text=True,
        capture_output=True,
        encoding="utf-8",
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"checkpoint script failed: rc={result.returncode}, stderr={result.stderr!r}")
    payload_raw = (result.stdout or "").strip()
    if not payload_raw:
        raise RuntimeError("checkpoint script produced empty stdout")
    return json.loads(payload_raw)


def _is_true(value: Any) -> bool:
    return value is True


def _check_report(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if data.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    if data.get("status") != "pass":
        errors.append("status must be 'pass'")
    if data.get("checkpoint_passed") is not True:
        errors.append("checkpoint_passed must be true")

    for key in REQUIRED_KEYS:
        if key not in data:
            errors.append(f"missing required key: {key}")
            continue
        if not _is_true(data[key]):
            errors.append(f"required boolean must be true: {key}")

    boundary = data.get("boundary")
    if not isinstance(boundary, dict):
        errors.append("boundary must be an object")
        return errors

    for key in BOUNDARY_KEYS:
        if key not in boundary:
            errors.append(f"missing boundary key: {key}")
        elif not _is_true(boundary[key]):
            errors.append(f"boundary boolean must remain true: {key}")
    return errors


def _validate(data: dict[str, Any]) -> bool:
    return not _check_report(data)


def _check_process_fanout(data: dict[str, Any]) -> bool:
    if "c2_python_process_count" not in data:
        return False
    count = data["c2_python_process_count"]
    if not isinstance(count, int):
        return False
    if count < 0:
        return False
    return True


def _mutation_suite(report: dict[str, Any]) -> bool:
    # required booleans -> false should fail
    for key in REQUIRED_KEYS:
        mutated = copy.deepcopy(report)
        mutated[key] = False
        mutated["checkpoint_passed"] = True
        if _validate(mutated):
            return False

    # checkpoint_passed forced false while required booleans stay true should fail
    mutated = copy.deepcopy(report)
    mutated["checkpoint_passed"] = False
    if _validate(mutated):
        return False

    # status mismatch should fail
    mutated = copy.deepcopy(report)
    mutated["status"] = "pass"
    mutated["checkpoint_passed"] = False
    if _validate(mutated):
        return False

    # missing key should fail
    for key in REQUIRED_KEYS:
        mutated = copy.deepcopy(report)
        mutated.pop(key, None)
        if _validate(mutated):
            return False

    # boundary booleans flipped should fail
    for key in BOUNDARY_KEYS:
        mutated = copy.deepcopy(report)
        boundary = copy.deepcopy(mutated.get("boundary", {}))
        if not isinstance(boundary, dict):
            return False
        boundary[key] = False
        mutated["boundary"] = boundary
        if _validate(mutated):
            return False

    # boundary key removed should fail
    for key in BOUNDARY_KEYS:
        mutated = copy.deepcopy(report)
        boundary = copy.deepcopy(mutated.get("boundary", {}))
        if not isinstance(boundary, dict):
            return False
        boundary.pop(key, None)
        mutated["boundary"] = boundary
        if _validate(mutated):
            return False

    return True


def run_validation() -> bool:
    report = _run_checkpoint_json()
    if not _validate(report):
        return False
    return _check_process_fanout(report)


def run_self_test_negative() -> bool:
    report = _run_checkpoint_json()
    if not _validate(report):
        return False
    return _mutation_suite(report)


def run() -> int:
    parser = argparse.ArgumentParser(description="Validate docs readability checkpoint JSON output")
    parser.add_argument("--self-test-negative", action="store_true")
    args = parser.parse_args()

    ok = run_validation()
    try:
        report = _run_checkpoint_json()
        count = report.get("c2_python_process_count")
    except Exception as exc:
        count = None
        print(f"WARNING: failed to read process fan-out evidence: {exc}")
    if args.self_test_negative:
        ok = run_self_test_negative()
        print("self-test-negative: PASS" if ok else "self-test-negative: FAIL")
    else:
        print("validator: PASS" if ok else "validator: FAIL")
    if count is None:
        print("c2_python_process_count=none")
    else:
        print(f"c2_python_process_count={count}")
        if count > PROCESS_FANOUT_WARNING_LIMIT:
            print(f"warn: c2_python_process_count={count} > {PROCESS_FANOUT_WARNING_LIMIT}")
    return 0 if ok else 1


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
