from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run benchmark prechecks: field scan + contract validation.")
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT_DIR / "docs" / "benchmarks",
        help="Benchmark directory.",
    )
    parser.add_argument(
        "--pattern",
        default="*.json",
        help="File glob pattern for benchmark JSON inputs.",
    )
    parser.add_argument(
        "--scan-out",
        type=Path,
        default=None,
        help="Path to write scan JSON report.",
    )
    parser.add_argument(
        "--contract-out",
        type=Path,
        default=None,
        help="Path to write contract validation summary JSON.",
    )
    parser.add_argument(
        "--skip-scan",
        action="store_true",
        help="Skip structural field scan.",
    )
    parser.add_argument(
        "--skip-contract",
        action="store_true",
        help="Skip strict contract validation.",
    )
    parser.add_argument(
        "--fail-on-scan-warning",
        action="store_true",
        help="Fail precheck if scan detects missing/invalid fields.",
    )
    return parser.parse_args()


def _run_command(cmd: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)


def _has_scan_violations(scan_report: dict) -> bool:
    if scan_report.get("summary", {}).get("invalid_json", 0) > 0:
        return True

    for item in scan_report.get("files", []):
        if not item.get("valid_json", True):
            return True
        rows = item.get("rows")
        if isinstance(rows, dict):
            if rows.get("rows_missing_any_required", 0) > 0:
                return True
        sweep = item.get("sweep")
        if isinstance(sweep, dict):
            if sweep.get("buckets_missing_any_required", 0) > 0:
                return True
    return False


def main() -> int:
    args = parse_args()
    root = args.root.expanduser().resolve()

    if args.skip_scan and args.skip_contract:
        print("cannot skip both scan and contract validation")
        return 2

    scan_report_path = args.scan_out or (root / "scan_report.json")
    contract_report_path = args.contract_out or (root / "contract_matrix_precheck.json")
    scan_script = ROOT_DIR / "scripts" / "scan_benchmark_fields.py"
    validate_all_script = ROOT_DIR / "scripts" / "validate_benchmark_contracts_all.py"

    scan_ok = True
    contract_ok = True
    scan_payload: dict | None = None
    contract_payload: dict | None = None

    if not args.skip_scan:
        scan_cmd = [
            sys.executable,
            str(scan_script),
            "--root",
            str(root),
            "--pattern",
            args.pattern,
            "--out",
            str(scan_report_path),
        ]
        scan_result = _run_command(scan_cmd)
        if scan_result.returncode != 0:
            scan_ok = False
            print(f"scan command failed rc={scan_result.returncode}")
            print(scan_result.stdout.strip())
            print(scan_result.stderr.strip())
        try:
            scan_payload = json.loads(scan_report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            scan_payload = None
            scan_ok = False

        if scan_payload is not None:
            if args.fail_on_scan_warning and _has_scan_violations(scan_payload):
                scan_ok = False

    contract_failed = False
    if not args.skip_contract:
        env = os.environ.copy()
        existing_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = os.pathsep.join(p for p in (str(ROOT_DIR / "src"), existing_path) if p)
        contract_cmd = [
            sys.executable,
            str(validate_all_script),
            "--root",
            str(root),
            "--pattern",
            args.pattern,
            "--out",
            str(contract_report_path),
            "--exclude",
            str(scan_report_path),
            "--exclude",
            str(contract_report_path),
        ]
        contract_result = _run_command(contract_cmd, env=env)
        contract_failed = contract_result.returncode != 0
        if contract_result.returncode != 0:
            contract_ok = False
            print(f"contract validation command failed rc={contract_result.returncode}")
            print(contract_result.stdout.strip())
            print(contract_result.stderr.strip())

        try:
            contract_payload = json.loads(contract_report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            contract_payload = None
            contract_ok = False
            contract_failed = True

    summary = {
        "root": str(root),
        "pattern": args.pattern,
        "scan_ok": scan_ok,
        "contract_ok": contract_ok,
        "scan_report": str(scan_report_path),
        "contract_report": str(contract_report_path),
        "skip_scan": args.skip_scan,
        "skip_contract": args.skip_contract,
        "failed_report": None,
        "scan": {},
        "contract": {
            "status": "not_run",
            "failed": 0,
            "passed": 0,
            "total": 0,
        },
        "status_counts": {},
        "skipped": 0,
        "skip_reasons": {},
        "total_inputs": 0,
    }

    if scan_payload is not None:
        summary["scan"] = scan_payload.get("summary", {})
    if contract_payload is not None:
        failed = contract_payload.get("failed", 0)
        summary["contract"] = {
            "failed": failed,
            "passed": contract_payload.get("passed", 0),
            "total": contract_payload.get("total", 0),
            "status": "fail" if failed else "ok",
        }
        summary["status_counts"] = contract_payload.get("status_counts", {})
        summary["skipped"] = contract_payload.get("skipped", 0)
        summary["skip_reasons"] = contract_payload.get("skip_reasons", {})
        summary["total_inputs"] = contract_payload.get("total_inputs", summary["contract"]["total"])
        if (failed > 0 or contract_failed) and args.skip_contract is False:
            summary["failed_report"] = str(contract_report_path)
    else:
        summary["total_inputs"] = scan_payload.get("summary", {}).get("total", 0) if scan_payload is not None else 0
        if contract_failed and args.skip_contract is False:
            summary["failed_report"] = str(contract_report_path)

    print(json.dumps(summary, ensure_ascii=False))

    if not scan_ok or not contract_ok:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
