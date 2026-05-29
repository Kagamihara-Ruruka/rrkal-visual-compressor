from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def _as_int(value: Any) -> int | None:
    parsed = _to_float(value)
    if parsed is None or not parsed.is_integer():
        return None
    return int(parsed)


def _rows_to_contract(payload: dict[str, Any]) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for row in payload.get("rows", []):
        if not isinstance(row, dict):
            continue

        synthetic_kind = row.get("dataset") or row.get("synthetic_kind")
        if not isinstance(synthetic_kind, str):
            continue

        samples = _as_int(row.get("samples"))
        if samples is None or samples <= 0:
            continue

        fourier_terms = _as_int(row.get("terms")) or _as_int(row.get("fourier_terms"))
        if fourier_terms is None or fourier_terms <= 0:
            continue

        global_metrics = row.get("global", {})
        if isinstance(global_metrics, dict):
            r2 = _to_float(global_metrics.get("r2"))
            leakage = _to_float(global_metrics.get("leakage_ratio"))
        else:
            r2 = None
            leakage = None

        if r2 is None:
            fallback_candidates = (
                row.get("piecewise_fourier", {}),
                row.get("detrended_fourier", {}),
                row.get("uniform_param_fourier", {}),
            )
            for candidate in fallback_candidates:
                if isinstance(candidate, dict):
                    r2 = _to_float(candidate.get("r2")) or r2
                    leakage = _to_float(candidate.get("leakage_ratio")) or leakage
                    if r2 is not None:
                        break
        if r2 is None:
            continue

        payload_ratio = _to_float(global_metrics.get("payload_ratio")) if isinstance(global_metrics, dict) else None
        if payload_ratio is None or payload_ratio <= 0:
            payload_ratio = _to_float(row.get("payload_ratio"))
        if payload_ratio is None or payload_ratio <= 0:
            payload_ratio = 1.0

        gates = row.get("gates", {})
        defensible = False
        if isinstance(gates, dict):
            defensible = bool(gates.get("defensible"))

        converted.append(
            {
                "synthetic_kind": synthetic_kind,
                "samples": samples,
                "fourier_terms": fourier_terms,
                "channel_k": 1.0,
                "fourier_r2": r2,
                "channel_coverage_ratio": leakage if leakage is not None else 1.0,
                "direct_svg_to_package_ratio": payload_ratio,
                "direct_svg_gzip_to_package_ratio": payload_ratio,
                "source_csv_gzip_to_package_ratio": payload_ratio,
                "source_csv_to_package_ratio": payload_ratio,
                "_legacy_source": True,
                "_legacy_defensible": defensible,
            }
        )

    return converted


def _build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "high_fidelity_rows_count": 0,
            "defensible_rows_count": 0,
            "defensible_rows_ratio": 0.0,
            "defensible_channel_coverage_threshold": 1.0,
        }

    defensible_count = 0
    for row in rows:
        if bool(row.get("_legacy_defensible")):
            defensible_count += 1

    high_fidelity = sum(1 for row in rows if _to_float(row.get("fourier_r2", 0.0)) and row.get("fourier_r2", 0.0) >= 0.99)
    return {
        "high_fidelity_rows_count": int(high_fidelity),
        "defensible_rows_count": int(defensible_count),
        "defensible_rows_ratio": 0.0 if high_fidelity == 0 else defensible_count / float(high_fidelity),
        "defensible_channel_coverage_threshold": 1.0,
    }


def _convert_file(path: Path, dry_run: bool) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = _rows_to_contract(payload) if isinstance(payload, dict) else []
    result = {
        "benchmark": path.stem.replace("defensible_hardening_report", "legacy_hardening_contract").strip("_"),
        "rows": rows,
        "summary": _build_summary(rows),
        "source_file": str(path),
        "converted_from": "legacy_hardening_report",
    }

    if dry_run:
        return {
            "source": str(path),
            "output_rows": len(rows),
            "high_fidelity_rows_count": result["summary"]["high_fidelity_rows_count"],
            "defensible_rows_count": result["summary"]["defensible_rows_count"],
        }

    target = path.with_name(f"{path.stem}_contract.json")
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"source": str(path), "output": str(target), "output_rows": len(rows)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert legacy hardening benchmark reports to contract-shaped fixtures."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Explicit legacy report files to convert. If omitted, scan docs/benchmarks/*.json.",
    )
    parser.add_argument("--root", type=Path, default=None, help="Root directory containing legacy reports.")
    parser.add_argument("--dry-run", action="store_true", help="Only report conversion counts.")
    parser.add_argument(
        "--include",
        nargs="*",
        default=[
            "defensible_hardening_report.json",
            "defensible_hardening_report_any.json",
            "defensible_hardening_report_frontier.json",
            "defensible_hardening_report_terms64.json",
        ],
        help="File names to convert (default is hardening legacy set).",
    )
    return parser.parse_args()


def _collect_inputs(args: argparse.Namespace) -> list[Path]:
    if args.paths:
        return [path for path in args.paths if path.exists()]
    root = args.root or Path("docs/benchmarks")
    if isinstance(root, Path):
        root = root
    files: list[Path] = []
    include = set(args.include or [])
    if root.is_dir():
        for name in include:
            candidate = root / name
            if candidate.is_file():
                files.append(candidate)
    return files


def main() -> int:
    args = parse_args()
    inputs = _collect_inputs(args)
    if not inputs:
        print("no legacy files found")
        return 1

    output = []
    for path in inputs:
        report = _convert_file(path, args.dry_run)
        output.append(report)
    print(json.dumps({"count": len(output), "files": output}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
