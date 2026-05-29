from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_SRC = ROOT_DIR / "src"
if str(PROJECT_SRC) not in os.sys.path:
    os.sys.path.insert(0, str(PROJECT_SRC))

from vizcompress.benchmark_contracts import validate_benchmark_contract


_BENCHMARK_EXCLUDED_EXACT = {
    "terms_channel_benchmark_parity_report.json",
}

_CONTRACT_SUMMARY_COUNTERS = (
    "high_fidelity_rows_count",
    "defensible_rows_count",
    "defensible_rows_ratio",
)

_CONTRACT_SWEEP_REQUIRED_FIELDS = (
    "high_fidelity_rows_count",
    "defensible_rows_count",
    "defensible_rows_ratio",
    "best_ratio",
)


def _is_generated_report_name(name: str) -> bool:
    return name.startswith("scan_report") or name.startswith("contract_matrix")


def _iter_inputs(root: Path, pattern: str) -> list[Path]:
    inputs = sorted(root.glob(pattern))
    return [
        path
        for path in inputs
        if path.is_file()
        and not path.name.endswith("_contract.json")
        and path.name not in _BENCHMARK_EXCLUDED_EXACT
        and not _is_generated_report_name(path.name)
    ]


def _prefixed_errors(path: str, errors: list[str]) -> list[str]:
    return [f"{path}: {item}" for item in errors]


def _is_contract_row_payload(rows: list[object]) -> bool:
    return any(
        isinstance(row, dict) and all(field in row for field in ("synthetic_kind", "samples", "fourier_terms", "fourier_r2"))
        for row in rows
    )


def _is_contract_sweep_payload(sweep: list[object]) -> bool:
    return any(
        isinstance(bucket, dict) and all(field in bucket for field in _CONTRACT_SWEEP_REQUIRED_FIELDS)
        for bucket in sweep
    )


def _is_contract_payload(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    rows = payload.get("rows")
    sweep = payload.get("sweep")
    if isinstance(rows, list) and _is_contract_row_payload(rows):
        summary = payload.get("summary")
        if not isinstance(summary, dict):
            return False
        return all(field in summary for field in _CONTRACT_SUMMARY_COUNTERS)
    if isinstance(sweep, list) and _is_contract_sweep_payload(sweep):
        return True
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate all benchmark JSON contracts in a directory.")
    parser.add_argument("--root", type=Path, default=ROOT_DIR / "docs" / "benchmarks", help="Benchmark directory.")
    parser.add_argument(
        "--pattern",
        default="*.json",
        help="Glob pattern for JSON candidates inside root.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write JSON summary report to this path.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first failure.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.expanduser().resolve()
    paths = _iter_inputs(root, args.pattern)

    if not paths:
        print(f"no benchmark files found: root={root}, pattern={args.pattern}")
        return 0

    by_status: dict[str, list[str]] = defaultdict(list)
    by_skip_reason: dict[str, int] = defaultdict(int)
    rows: list[dict[str, object]] = []

    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            by_status["FAIL"].append(str(path))
            rows.append(
                {
                    "input": str(path),
                    "status": "FAIL",
                    "passed": False,
                    "error_count": 1,
                    "errors": [f"{path}: invalid_json: {exc}"],
                }
            )
            print(f"FAIL {path}: invalid_json")
            if args.fail_fast:
                break
            continue

        if not _is_contract_payload(payload):
            by_status["SKIP"].append(str(path))
            by_skip_reason["legacy_or_non_contract_payload"] += 1
            rows.append(
                {
                    "input": str(path),
                    "status": "SKIP",
                    "passed": None,
                    "error_count": 0,
                    "skip_reason": "legacy_or_non_contract_payload",
                    "errors": [],
                }
            )
            print(f"SKIP {path}")
            continue

        ok, errors = validate_benchmark_contract(payload)
        status = "PASS" if ok else "FAIL"
        by_status[status].append(str(path))
        rows.append(
            {
                "input": str(path),
                "status": status,
                "passed": ok,
                "error_count": len(errors),
                "errors": _prefixed_errors(str(path), errors),
            }
        )
        if ok:
            print(f"PASS {path}")
        else:
            print(f"FAIL {path}")
            for item in errors[:3]:
                print(f"  - {item}")
        if args.fail_fast and not ok:
            break

    passed = len(by_status["PASS"])
    failed = len(by_status["FAIL"])
    skipped = len(by_status["SKIP"])
    summary = {
        "root": str(root),
        "pattern": args.pattern,
        "total": passed + failed,
        "total_inputs": len(paths),
        "skipped": skipped,
        "skip_reasons": dict(by_skip_reason),
        "passed": passed,
        "failed": failed,
        "status_counts": {key: len(value) for key, value in sorted(by_status.items())},
        "rows": rows,
    }

    if args.out is not None:
        out = args.out.expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"summary: {out}")
        if summary["failed"] > 0:
            print(f"failed_report: {out}")

    print(f"SUMMARY passed={summary['passed']} failed={summary['failed']} total={summary['total']} skipped={summary['skipped']}")
    return 0 if summary["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
