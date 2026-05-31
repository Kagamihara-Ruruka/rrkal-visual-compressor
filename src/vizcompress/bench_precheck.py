from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from vizcompress.benchmark_contracts import validate_benchmark_contract

PRECHECK_SUMMARY_SCHEMA_VERSION = "1.0"
SCAN_REPORT_SCHEMA_VERSION = "1.0"
CONTRACT_REPORT_SCHEMA_VERSION = "1.0"

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

_BENCHMARK_EXCLUDED_NAMES = {
    "terms_channel_benchmark_parity_report.json",
    "defensible_hardening_report.json",
    "defensible_hardening_report_any.json",
    "defensible_hardening_report_frontier.json",
    "defensible_hardening_report_terms64.json",
}


def _is_generated_report_name(name: str) -> bool:
    name_l = name.lower()
    return name_l.startswith("scan_report") or name_l.startswith("contract_matrix")


def _collect_payloads(target: Path, pattern: str, excluded_names: set[str] | None = None) -> list[Path]:
    excluded = {name.lower() for name in (excluded_names or set())}
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
        and path.name.lower() not in excluded
        and path.name not in _BENCHMARK_EXCLUDED_NAMES
        and not _is_generated_report_name(path.name)
    ]


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
        if not set(_CONTRACT_SWEEP_REQUIRED_FIELDS).issubset(keys):
            missing_any += 1
            for field in _CONTRACT_SWEEP_REQUIRED_FIELDS:
                if field not in keys:
                    missing[field] += 1
        for key in keys - set(_CONTRACT_SWEEP_REQUIRED_FIELDS):
            unexpected[key] += 1

    return {
        "count": len(sweep),
        "sweep_total": len(sweep),
        "non_dict_buckets": non_dict_rows,
        "buckets_missing_any_required": missing_any,
        "missing_required": _sorted_counts(missing),
        "unexpected_fields": _sorted_counts(unexpected),
    }


def _is_contract_row(row: object) -> bool:
    return isinstance(row, dict) and all(key in row for key in ("synthetic_kind", "samples", "fourier_terms", "fourier_r2"))


def _is_contract_sweep_bucket(bucket: object) -> bool:
    return isinstance(bucket, dict) and all(key in bucket for key in _CONTRACT_SWEEP_REQUIRED_FIELDS)


def scan_benchmark_fields(root: Path, pattern: str, out: Path | None = None) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": SCAN_REPORT_SCHEMA_VERSION,
        "root": str(root.resolve()),
        "pattern": pattern,
        "files": [],
    }

    paths = _collect_payloads(root, pattern)
    invalid_json = 0
    for path in paths:
        item: dict[str, Any] = {
            "path": str(path),
            "valid_json": True,
            "mode": "unknown",
            "summary_fields": {},
            "errors": [],
        }
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
            item["valid_json"] = False
            item["errors"] = [f"unreadable_json: {exc}"]
            invalid_json += 1
            report["files"].append(item)
            continue

        if not isinstance(payload, dict):
            item["valid_json"] = False
            item["errors"] = ["invalid_root: payload is not object"]
            invalid_json += 1
            report["files"].append(item)
            continue

        rows = payload.get("rows")
        sweep = payload.get("sweep")
        has_rows = isinstance(rows, list)
        has_sweep = isinstance(sweep, list)
        if has_rows:
            item["rows"] = _scan_row_bucket(rows)
        if has_sweep:
            item["sweep"] = _scan_sweep_bucket(sweep)

        has_contract_rows = any(_is_contract_row(row) for row in rows) if has_rows else False
        has_contract_sweep = any(_is_contract_sweep_bucket(bucket) for bucket in sweep) if has_sweep else False

        if has_rows and has_sweep:
            item["mode"] = "mixed" if (has_contract_rows and has_contract_sweep) else "legacy"
        elif has_rows:
            item["mode"] = "rows" if has_contract_rows else "legacy"
        elif has_sweep:
            item["mode"] = "sweep" if has_contract_sweep else "legacy"
        else:
            item["mode"] = "legacy"

        if item["mode"] == "legacy":
            item["errors"] = ["not_a_contract_payload: non_contract_rows_or_sweep_schema"]

        summary = payload.get("summary")
        if isinstance(summary, dict):
            item["summary_fields"] = {
                field: field in summary
                for field in (
                    "high_fidelity_rows_count",
                    "defensible_rows_count",
                    "defensible_rows_ratio",
                    "defensible_channel_coverage_threshold",
                )
            }
        report["files"].append(item)

    mode_counter = Counter[str]()
    for item in report["files"]:
        mode_counter[item.get("mode", "unknown")] += 1
    report["summary"] = {
        "total": len(report["files"]),
        "invalid_json": invalid_json,
        "mode_breakdown": _sorted_counts(mode_counter),
    }

    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return report


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


def _prefixed_errors(path: str, errors: list[str]) -> list[str]:
    return [f"{path}: {item}" for item in errors]


def _is_contract_row_payload(rows: list[object]) -> bool:
    return any(
        isinstance(row, dict) and all(field in row for field in ("synthetic_kind", "samples", "fourier_terms", "fourier_r2"))
        for row in rows
    )


def _is_contract_sweep_payload(sweep: list[object]) -> bool:
    return any(isinstance(bucket, dict) and all(field in bucket for field in _CONTRACT_SWEEP_REQUIRED_FIELDS) for bucket in sweep)


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


def validate_benchmark_contracts_all(
    root: Path,
    pattern: str,
    out: Path | None = None,
    excluded_names: set[str] | None = None,
    fail_fast: bool = False,
) -> dict[str, Any]:
    excluded = {Path(item).name for item in (excluded_names or set())}
    paths = _collect_payloads(root, pattern, excluded_names=excluded)

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
        if fail_fast and status == "FAIL":
            break

    summary: dict[str, Any] = {
        "schema_version": CONTRACT_REPORT_SCHEMA_VERSION,
        "root": str(root),
        "pattern": pattern,
        "total": len(by_status["PASS"]) + len(by_status["FAIL"]),
        "total_inputs": len(paths),
        "passed": len(by_status["PASS"]),
        "failed": len(by_status["FAIL"]),
        "skipped": len(by_status["SKIP"]),
        "skip_reasons": dict(by_skip_reason),
        "status_counts": {key: len(value) for key, value in sorted(by_status.items())},
        "rows": rows,
    }

    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def _has_scan_violations(scan_report: dict[str, Any]) -> bool:
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


def precheck_benchmarks(
    *,
    root: Path,
    pattern: str = "*.json",
    scan_out: Path | None = None,
    contract_out: Path | None = None,
    skip_scan: bool = False,
    skip_contract: bool = False,
    fail_on_scan_warning: bool = False,
    fail_fast: bool = False,
) -> tuple[int, dict[str, Any]]:
    if skip_scan and skip_contract:
        return 2, {"error": "cannot skip both scan and contract validation"}

    scan_report_path = scan_out or (root / "scan_report.json")
    contract_report_path = contract_out or (root / "contract_matrix_precheck.json")

    scan_ok = True
    contract_ok = True
    scan_payload: dict[str, Any] | None = None
    contract_payload: dict[str, Any] | None = None

    if not skip_scan:
        scan_payload = scan_benchmark_fields(root, pattern, out=scan_report_path)
        if fail_on_scan_warning and _has_scan_violations(scan_payload):
            scan_ok = False

    contract_failed = False
    if not skip_contract:
        excluded = {scan_report_path.name, contract_report_path.name}
        try:
            contract_payload = validate_benchmark_contracts_all(
                root,
                pattern,
                out=contract_report_path,
                excluded_names=excluded,
                fail_fast=fail_fast,
            )
        except Exception:
            contract_payload = None
            contract_ok = False
            contract_failed = True
        else:
            contract_failed = contract_payload.get("failed", 0) > 0
            if contract_failed:
                contract_ok = False

    summary: dict[str, Any] = {
        "schema_version": PRECHECK_SUMMARY_SCHEMA_VERSION,
        "root": str(root),
        "pattern": pattern,
        "scan_ok": scan_ok,
        "contract_ok": contract_ok,
        "scan_report": str(scan_report_path),
        "contract_report": str(contract_report_path),
        "skip_scan": skip_scan,
        "skip_contract": skip_contract,
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
        failed = int(contract_payload.get("failed", 0))
        summary["contract"] = {
            "failed": failed,
            "passed": int(contract_payload.get("passed", 0)),
            "total": int(contract_payload.get("total", 0)),
            "status": "fail" if failed else "ok",
        }
        summary["status_counts"] = contract_payload.get("status_counts", {})
        summary["skipped"] = int(contract_payload.get("skipped", 0))
        summary["skip_reasons"] = contract_payload.get("skip_reasons", {})
        summary["total_inputs"] = int(contract_payload.get("total_inputs", summary["contract"]["total"]))
        if (failed > 0 or contract_failed) and not skip_contract:
            summary["failed_report"] = str(contract_report_path)
    else:
        summary["total_inputs"] = (
            int(scan_payload.get("summary", {}).get("total", 0)) if scan_payload is not None else 0
        )
        if contract_failed and not skip_contract:
            summary["failed_report"] = str(contract_report_path)

    rc = 0 if (scan_ok and contract_ok) else 2
    return rc, summary

