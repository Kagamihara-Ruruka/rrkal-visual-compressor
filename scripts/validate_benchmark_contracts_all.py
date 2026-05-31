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

CONTRACT_REPORT_SCHEMA_VERSION = "1.0"


_BENCHMARK_EXCLUDED_EXACT = {"terms_channel_benchmark_parity_report.json"}
_CONTRACT_SWEEP_REQUIRED_FIELDS = (
    "high_fidelity_rows_count",
    "defensible_rows_count",
    "defensible_rows_ratio",
    "best_ratio",
)
_CONTRACT_ROW_SUMMARY_REQUIRED_FIELDS = (
    "high_fidelity_rows_count",
    "defensible_rows_count",
)


def _is_generated_report_name(name: str) -> bool:
    name_l = name.lower()
    return name_l.startswith("scan_report") or name_l.startswith("contract_matrix")


def _safe_load_json(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"benchmark JSON not found: {path}")
    if not path.is_file():
        raise ValueError(f"benchmark JSON is not a file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"invalid benchmark JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise TypeError(f"benchmark payload must be a JSON object: {path}")
    return payload


def _iter_inputs(root: Path, pattern: str, excluded: set[str] | None = None) -> list[Path]:
    excluded_set = {name.lower() for name in (excluded or set())}
    inputs = sorted(root.glob(pattern))
    return [
        path
        for path in inputs
        if path.is_file()
        and not path.name.endswith("_contract.json")
        and path.name.lower() not in _BENCHMARK_EXCLUDED_EXACT
        and path.name.lower() not in excluded_set
        and not _is_generated_report_name(path.name)
    ]


def _prefixed_errors(path: str, errors: list[str]) -> list[str]:
    return [f"{path}: {item}" for item in errors]


def _is_contract_row_payload(rows: list[object]) -> bool:
    return any(
        isinstance(row, dict)
        and all(field in row for field in ("synthetic_kind", "samples", "fourier_terms", "fourier_r2"))
        for row in rows
    )


def _is_contract_sweep_payload(sweep: list[object]) -> bool:
    return any(
        isinstance(bucket, dict)
        and all(field in bucket for field in _CONTRACT_SWEEP_REQUIRED_FIELDS)
        for bucket in sweep
    )


def _has_contract_row_summary(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    return all(field in payload for field in _CONTRACT_ROW_SUMMARY_REQUIRED_FIELDS)


def _is_contract_payload(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    rows = payload.get("rows")
    sweep = payload.get("sweep")
    if isinstance(rows, list) and _is_contract_row_payload(rows) and _has_contract_row_summary(payload.get("summary")):
        return True
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
        "--exclude",
        action="append",
        default=[],
        help="File names to exclude from validation input discovery.",
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
    if not root.exists():
        print(f"benchmark root does not exist: {root}")
        return 2
    if not root.is_dir():
        print(f"benchmark root is not a directory: {root}")
        return 2

    excluded_names = {Path(item).name for item in args.exclude}
    paths = _iter_inputs(root, args.pattern, excluded_names)

    if not paths:
        print(f"no benchmark files found: root={root}, pattern={args.pattern}")
        return 0

    by_status: dict[str, list[str]] = defaultdict(list)
    by_skip_reason: dict[str, int] = defaultdict(int)
    rows: list[dict[str, object]] = []

    for path in paths:
        try:
            payload = _safe_load_json(path)
        except (FileNotFoundError, OSError, ValueError, TypeError) as exc:
            ok = False
            errors = [str(exc)]
            status = "FAIL"
        else:
            if not _is_contract_payload(payload):
                status = "SKIP"
                by_status[status].append(str(path))
                by_skip_reason["legacy_or_non_contract_payload"] += 1
                rows.append(
                    {
                        "input": str(path),
                        "status": status,
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
                "passed": ok if status != "SKIP" else None,
                "error_count": len(errors),
                "errors": _prefixed_errors(str(path), errors),
            }
        )
        if status == "PASS":
            print(f"PASS {path}")
        elif status == "FAIL":
            print(f"FAIL {path}")
            for item in errors[:3]:
                print(f"  - {item}")

        if args.fail_fast and status == "FAIL":
            break

    summary = {
        "schema_version": CONTRACT_REPORT_SCHEMA_VERSION,
        "root": str(root),
        "pattern": args.pattern,
        "total": len(by_status["PASS"]) + len(by_status["FAIL"]),
        "total_inputs": len(paths),
        "passed": len(by_status["PASS"]),
        "failed": len(by_status["FAIL"]),
        "skipped": len(by_status["SKIP"]),
        "skip_reasons": dict(by_skip_reason),
        "status_counts": {key: len(value) for key, value in sorted(by_status.items())},
        "rows": rows,
    }

    if args.out is not None:
        out = args.out.expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        print(f"summary: {out}")
        if summary["failed"] > 0:
            print(f"failed_report: {out}")

    print(
        f"SUMMARY passed={summary['passed']} failed={summary['failed']} total={summary['total']} "
        f"skipped={summary['skipped']}"
    )
    return 0 if summary["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
