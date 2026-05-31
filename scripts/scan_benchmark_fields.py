from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

SCAN_REPORT_SCHEMA_VERSION = "1.0"

REQUIRED_ROW_FIELDS = (
    "synthetic_kind",
    "samples",
    "fourier_terms",
    "fourier_r2",
    "source_csv_gzip_to_package_ratio",
)

OPTIONAL_RATIO_FIELDS = (
    "direct_svg_to_package_ratio",
    "direct_svg_gzip_to_package_ratio",
)

OPTIONAL_ROW_FIELDS = (
    "channel_k",
    "channel_coverage_ratio",
    "source_csv_to_package_ratio",
) + OPTIONAL_RATIO_FIELDS

REQUIRED_SWEEP_FIELDS = (
    "high_fidelity_rows_count",
    "defensible_rows_count",
    "defensible_rows_ratio",
    "best_ratio",
)

_BENCHMARK_EXCLUDED_NAMES = {
    "terms_channel_benchmark_parity_report.json",
    "defensible_hardening_report.json",
    "defensible_hardening_report_any.json",
    "defensible_hardening_report_frontier.json",
    "defensible_hardening_report_terms64.json",
}


def _is_generated_report_name(name: str) -> bool:
    return name.startswith("scan_report") or name.startswith("contract_matrix")


def _is_contract_row(row: object) -> bool:
    return isinstance(row, dict) and all(key in row for key in ("synthetic_kind", "samples", "fourier_terms", "fourier_r2"))


def _is_contract_sweep_bucket(bucket: object) -> bool:
    return isinstance(bucket, dict) and all(key in bucket for key in REQUIRED_SWEEP_FIELDS)


def _has_contract_shape(payload: dict[str, Any]) -> bool:
    rows = payload.get("rows")
    sweep = payload.get("sweep")
    if isinstance(rows, list):
        return bool(rows) and any(_is_contract_row(item) for item in rows)
    if isinstance(sweep, list):
        return bool(sweep) and any(_is_contract_sweep_bucket(item) for item in sweep)
    return False


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


def _sorted_counts(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _scan_row_bucket(rows: list[Any]) -> dict[str, Any]:
    required_fields = set(REQUIRED_ROW_FIELDS)
    optional_fields = set(OPTIONAL_ROW_FIELDS)
    missing = Counter[str]()
    unexpected = Counter[str]()
    non_dict_rows = 0
    missing_any = 0

    for row in rows:
        if not isinstance(row, dict):
            non_dict_rows += 1
            continue
        keys = set(row.keys())
        row_missing_any = False
        present = keys.intersection(required_fields)
        if len(present) != len(required_fields):
            row_missing_any = True
            for field in required_fields:
                if field not in row:
                    missing[field] += 1

        if not any(field in keys for field in OPTIONAL_RATIO_FIELDS):
            row_missing_any = True
            missing["direct_svg_ratio"] += 1

        if row_missing_any:
            missing_any += 1

        for key in keys - required_fields - optional_fields:
            unexpected[key] += 1

    return {
        "count": len(rows),
        "rows_total": len(rows),
        "non_dict_rows": non_dict_rows,
        "rows_missing_any_required": missing_any,
        "missing_required": _sorted_counts(missing),
        "unexpected_fields": _sorted_counts(unexpected),
    }


def _scan_sweep_bucket(sweep: list[Any]) -> dict[str, Any]:
    missing = Counter[str]()
    unexpected = Counter[str]()
    non_dict_rows = 0
    missing_any = 0

    for bucket in sweep:
        if not isinstance(bucket, dict):
            non_dict_rows += 1
            continue
        keys = set(bucket.keys())
        if not set(REQUIRED_SWEEP_FIELDS).issubset(keys):
            missing_any += 1
            for field in REQUIRED_SWEEP_FIELDS:
                if field not in keys:
                    missing[field] += 1
        for key in keys - set(REQUIRED_SWEEP_FIELDS):
            unexpected[key] += 1

    return {
        "count": len(sweep),
        "sweep_total": len(sweep),
        "non_dict_buckets": non_dict_rows,
        "buckets_missing_any_required": missing_any,
        "missing_required": _sorted_counts(missing),
        "unexpected_fields": _sorted_counts(unexpected),
    }


def _scan_payload(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(path),
        "valid_json": True,
        "mode": "unknown",
        "summary_fields": {},
        "errors": [],
    }

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        result["valid_json"] = False
        result["errors"] = [f"unreadable_json: {exc}"]
        return result

    if not isinstance(payload, dict):
        result["errors"] = ["invalid_root: payload is not object"]
        return result

    rows = payload.get("rows")
    sweep = payload.get("sweep")
    has_rows = isinstance(rows, list)
    has_sweep = isinstance(sweep, list)

    if has_rows:
        result["rows"] = _scan_row_bucket(rows)
    if has_sweep:
        result["sweep"] = _scan_sweep_bucket(sweep)

    has_contract_rows = any(_is_contract_row(item) for item in rows) if has_rows else False
    has_contract_sweep = any(_is_contract_sweep_bucket(item) for item in sweep) if has_sweep else False

    if has_rows and has_sweep:
        result["mode"] = "mixed" if (has_contract_rows and has_contract_sweep) else "legacy"
    elif has_rows:
        result["mode"] = "rows" if has_contract_rows else "legacy"
    elif has_sweep:
        result["mode"] = "sweep" if has_contract_sweep else "legacy"
    else:
        result["mode"] = "legacy"

    if result["mode"] == "legacy":
        result["errors"] = ["not_a_contract_payload: non_contract_rows_or_sweep_schema"]

    summary = payload.get("summary")
    if isinstance(summary, dict):
        result["summary_fields"] = {
            field: field in summary for field in (
                "high_fidelity_rows_count",
                "defensible_rows_count",
                "defensible_rows_ratio",
                "defensible_channel_coverage_threshold",
            )
        }

    return result


def _collect_payloads(target: Path, pattern: str) -> list[Path]:
    if target.is_file():
        return [target]
    if not target.is_dir():
        raise FileNotFoundError(f"path not found: {target}")
    inputs = sorted(target.glob(pattern))
    return [
        path
        for path in inputs
        if path.is_file()
        and not path.name.endswith("_contract.json")
        and path.name not in _BENCHMARK_EXCLUDED_NAMES
        and not _is_generated_report_name(path.name)
    ]


def main() -> int:
    args = parse_args()
    if args.path is None and args.root is None:
        raise ValueError("one of positional path or --root is required")
    root = args.root if args.root is not None else args.path
    report = {
        "schema_version": SCAN_REPORT_SCHEMA_VERSION,
        "root": str(root.resolve()),
        "pattern": args.pattern,
        "files": [],
    }

    paths = _collect_payloads(root, args.pattern)
    invalid_json = 0
    for path in paths:
        item = _scan_payload(path)
        if not item.get("valid_json", False):
            invalid_json += 1
        report["files"].append(item)

    mode_counter = Counter[str]()
    for item in report["files"]:
        mode_counter[item.get("mode", "unknown")] += 1
    report["summary"] = {
        "total": len(report["files"]),
        "invalid_json": invalid_json,
        "mode_breakdown": _sorted_counts(mode_counter),
    }

    json_payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json_payload, encoding="utf-8")
        print(f"wrote: {args.out}")
    else:
        print(json_payload)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
