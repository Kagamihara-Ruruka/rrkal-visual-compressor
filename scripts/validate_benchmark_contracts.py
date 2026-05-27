from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_SRC = ROOT_DIR / "src"
if str(PROJECT_SRC) not in os.sys.path:
    os.sys.path.insert(0, str(PROJECT_SRC))

from vizcompress.benchmark_contracts import validate_benchmark_contract


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate benchmark payload contracts.")
    parser.add_argument("input", type=Path, help="Benchmark JSON output path.")
    parser.add_argument("--out", type=Path, default=None, help="Write JSON report to this path.")
    parser.add_argument("--tolerance", type=float, default=1e-12, help="Tolerance for monotonic R2 checks.")
    parser.add_argument(
        "--no-nondecreasing-r2",
        action="store_true",
        help="Disable nondecreasing Fourier R2 monotonicity check.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input.expanduser().resolve()
    payload = json.loads(input_path.read_text(encoding="utf-8"))

    passed, errors = validate_benchmark_contract(
        payload,
        nondecreasing_fourier_r2=not args.no_nondecreasing_r2,
        tolerance=args.tolerance,
    )

    report = {
        "input": str(input_path),
        "passed": passed,
        "error_count": len(errors),
        "errors": errors,
    }

    if args.out is not None:
        out = args.out.expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"report: {out}")

    print("PASS" if passed else "FAIL")
    if errors:
        for item in errors:
            print(f"- {item}")

    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())

