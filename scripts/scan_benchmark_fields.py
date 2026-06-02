from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_SRC = ROOT_DIR / "src"
if str(PROJECT_SRC) not in os.sys.path:
    os.sys.path.insert(0, str(PROJECT_SRC))

from vizcompress.bench_precheck import scan_benchmark_fields


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Quick field-level scan for benchmark JSON files.")
    parser.add_argument("path", type=Path, nargs="?", help="Benchmark JSON file or directory.")
    parser.add_argument("--root", type=Path, default=None, help="Directory to scan (alias to path when path is dir).")
    parser.add_argument(
        "--pattern",
        default="*.json",
        help="Glob pattern when scanning directories (default: *.json).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write JSON report to this path. Defaults to stdout.",
    )
    return parser.parse_args()


def _print_or_write(report: dict, out: Path | None) -> None:
    if out is not None:
        print(f"wrote: {out}")
        return
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> int:
    args = parse_args()
    if args.path is None and args.root is None:
        raise ValueError("one of positional path or --root is required")
    root = args.root if args.root is not None else args.path
    report = scan_benchmark_fields(root, args.pattern, out=args.out)
    _print_or_write(report, args.out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
