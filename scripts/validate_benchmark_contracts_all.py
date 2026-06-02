from __future__ import annotations

import argparse
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_SRC = ROOT_DIR / "src"
if str(PROJECT_SRC) not in os.sys.path:
    os.sys.path.insert(0, str(PROJECT_SRC))

from vizcompress.bench_precheck import validate_benchmark_contracts_all


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

    report = validate_benchmark_contracts_all(
        root,
        args.pattern,
        out=args.out,
        excluded_names={Path(item).name for item in args.exclude},
        fail_fast=args.fail_fast,
    )
    rows = report["rows"]
    if not rows and report["total_inputs"] == 0:
        print(f"no benchmark files found: root={root}, pattern={args.pattern}")
        return 0

    for row in rows:
        status = row["status"]
        print(f"{status} {row['input']}")
        if status == "FAIL":
            for item in row.get("errors", [])[:3]:
                print(f"  - {item}")

    print(
        f"SUMMARY passed={report['passed']} failed={report['failed']} total={report['total']} "
        f"skipped={report['skipped']}"
    )

    if args.out is not None:
        out = args.out.expanduser().resolve()
        print(f"summary: {out}")
        if report["failed"] > 0:
            print(f"failed_report: {out}")

    return 0 if report["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
