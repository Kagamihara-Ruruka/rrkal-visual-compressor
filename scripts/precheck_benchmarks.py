from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]

PROJECT_SRC = ROOT_DIR / "src"
if str(PROJECT_SRC) not in os.sys.path:
    os.sys.path.insert(0, str(PROJECT_SRC))

from vizcompress.bench_precheck import precheck_benchmarks


def _print_failure_hints(root: Path, summary: dict[str, Any]) -> None:
    if summary.get("scan_ok") and summary.get("contract_ok"):
        return

    print("Precheck failed.", file=sys.stderr)
    if summary.get("failed_report"):
        print(f"failed_report: {summary['failed_report']}", file=sys.stderr)

    candidate_script = ROOT_DIR / "scripts" / "report_workspace_candidates.py"
    workspace_root = root if root != (ROOT_DIR / "docs" / "benchmarks") else ROOT_DIR
    if candidate_script.exists():
        print("If failures may be caused by stale output directories with ACL lock issues, run:", file=sys.stderr)
        print(
            f'  python "{candidate_script}" --root "{workspace_root}" --max-depth 4 --out "{workspace_root / "tmp" / "workspace_candidates.json"}"',
            file=sys.stderr,
        )
        print("Common candidates: tmp_*, tmp-*, smoke_*, *smoke*, *model.vizretain*", file=sys.stderr)
    else:
        print(f"candidate helper missing: {candidate_script}", file=sys.stderr)


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


def main() -> int:
    args = parse_args()
    root = args.root.expanduser().resolve()

    if not root.exists():
        print(f"benchmark root does not exist: {root}")
        return 2
    if not root.is_dir():
        print(f"benchmark root is not a directory: {root}")
        return 2

    if args.skip_scan and args.skip_contract:
        print("cannot skip both scan and contract validation")
        return 2

    rc, summary = precheck_benchmarks(
        root=root,
        pattern=args.pattern,
        scan_out=args.scan_out,
        contract_out=args.contract_out,
        skip_scan=args.skip_scan,
        skip_contract=args.skip_contract,
        fail_on_scan_warning=args.fail_on_scan_warning,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))

    if rc != 0:
        _print_failure_hints(root, summary)

    return rc


if __name__ == "__main__":
    raise SystemExit(main())