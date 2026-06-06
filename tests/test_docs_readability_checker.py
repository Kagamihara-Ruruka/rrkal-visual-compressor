from __future__ import annotations

import subprocess
import json
import sys
import os
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


def test_docs_readability_checkpoint_json_output_is_pure_json() -> None:
    script_path = ROOT_DIR / "scripts" / "docs_readability_checkpoint.py"
    run_env = os.environ.copy()
    run_env["DOCS_READABILITY_CHECKPOINT_TEST_MODE"] = "1"
    result = subprocess.run(
        [sys.executable, str(script_path), "--json"],
        text=True,
        capture_output=True,
        encoding="utf-8",
        env=run_env,
        check=False,
    )
    assert result.returncode == 0
    stdout = (result.stdout or "").strip()
    assert stdout, "stdout must not be empty"
    payload = json.loads(stdout)

    assert payload["checkpoint_passed"] is True
    assert payload["schema"] == "docs-readability-checkpoint/v1"
    assert payload["status"] == "pass"

    required_keys = [
        "clean_docs_scan_passed",
        "negative_fixture_detection_passed",
        "cli_help_passed",
        "no_manifest_schema_change",
        "readability_pytest_passed",
        "checkpoint_passed",
        "status",
        "schema",
        "boundary",
    ]
    for key in required_keys:
        assert key in payload

    boundary = payload["boundary"]
    assert boundary["no_manifest_schema_change_required"] is True
    assert boundary["cli_behavior_unchanged"] is True
    assert boundary["algorithm_unchanged"] is True
    assert boundary["cross_repo_integration_not_touched"] is True

    assert "Docs readability scan" not in stdout
    assert "usage:" not in stdout
    assert "clean_docs_scan_passed=true" not in stdout
    assert "... [100%]" not in stdout
