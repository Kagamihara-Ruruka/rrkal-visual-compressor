from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import os

ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_SRC = ROOT_DIR / "src"
if str(PROJECT_SRC) not in os.sys.path:
    os.sys.path.insert(0, str(PROJECT_SRC))

from vizcompress.benchmark_contracts import validate_benchmark_contract


def _iter_inputs(root: Path, pattern: str) -> list[Path]:
    inputs = sorted(root.glob(pattern))
    filtered = [
        path for path in inputs
        if path.is_file()
        and not path.name.endswith("_contract.json")
        and path.name != "terms_channel_benchmark_parity_report.json"
    ]
    return filtered


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
    rows: list[dict[str, object]] = []

    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        ok, errors = validate_benchmark_contract(payload)
        status = "PASS" if ok else "FAIL"
        by_status[status].append(str(path))
        rows.append(
            {
                "input": str(path),
                "passed": ok,
                "error_count": len(errors),
                "errors": errors,
            }
        )
        if ok:
            print(f"PASS {path}")
        else:
            print(f"FAIL {path}")
            if errors:
                for item in errors[:3]:
                    print(f"  - {item}")
        if args.fail_fast and not ok:
            break

    summary = {
        "root": str(root),
        "pattern": args.pattern,
        "total": len(paths),
        "passed": len(by_status["PASS"]),
        "failed": len(by_status["FAIL"]),
        "rows": rows,
    }

    if args.out is not None:
        out = args.out.expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"summary: {out}")

    print(f"SUMMARY passed={summary['passed']} failed={summary['failed']} total={summary['total']}")
    return 0 if summary["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

