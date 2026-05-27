from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np

# Byte sizes used by the payload estimate formulas (float64 / int64)
FLOAT64_BYTES = 8
INT64_BYTES = 8

ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_SRC = ROOT_DIR / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from vizcompress.data import make_synthetic_dataset
from vizcompress.metrics import regression_metrics
from vizcompress.research import (
    adaptive_residual_threshold,
    PiecewiseModel,
    PiecewisePolynomialModel,
    RDPPrefilteredFourierModel,
    compress_fourier_piecewise,
    compress_fourier_with_uniform_param,
    compress_fourier_with_rdp_budget,
    compress_fourier_with_linear_detrend,
    compress_haar_threshold,
    compress_piecewise_polynomial,
    compress_multichannel_fourier_pca,
    locality_leakage_metric,
)
from vizcompress.compressors import compress_fourier
from vizcompress.core import FourierModel, TimeSeries


def _benchmark_row(name: str, series: TimeSeries, terms: int, max_breaks: int = 4) -> dict[str, Any]:
    # Fit multiple representations for the same signal.
    # This keeps quality, locality, and payload comparisons fair.
    global_model = compress_fourier(series, terms=terms)
    piecewise = compress_fourier_piecewise(series, terms=terms, max_breaks=max_breaks)
    polynomial = compress_piecewise_polynomial(series, degree=3, max_breaks=max_breaks)
    uniform = compress_fourier_with_uniform_param(series, terms=terms, reparametrize_to_uniform=True)
    # Keep a small fraction of points for rendering-aware fitting.
    # This simulates a pixel/DPI budget before mathematical fitting.
    target_keep_ratio = min(0.25, 0.04 + terms / 1000.0)
    rdp_prefilter = compress_fourier_with_rdp_budget(
        series,
        terms=terms,
        target_keep_ratio=target_keep_ratio,
        min_keep=128,
    )
    detrended = compress_fourier_with_linear_detrend(series, terms=terms)
    haar_level = max(1, int(np.floor(np.log2(series.sample_count))) - 1)
    haar = compress_haar_threshold(series, level=min(3, haar_level))

    # Compute residuals against the detrended reconstruction.
    # If this residual is small, the core model already captured most structure.
    residual = series.y - detrended.reconstructed_y
    # Keep only "important" residual points by a dynamic threshold.
    # In this run, those points are the residual/second layer payload.
    adaptive = adaptive_residual_threshold(
        x=series.x,
        residual=residual,
        window=128,
        adaptive_factor=2.8,
        min_threshold=1e-10,
    )

    g_metrics = regression_metrics(series.y, global_model.reconstructed_y)
    p_metrics = regression_metrics(series.y, piecewise.reconstructed_y)
    poly_metrics = regression_metrics(series.y, polynomial.reconstructed_y)
    u_metrics = regression_metrics(series.y, uniform.reconstructed_y)
    rdp_metrics = regression_metrics(series.y, rdp_prefilter.reconstructed_y)
    d_metrics = regression_metrics(series.y, detrended.reconstructed_y)
    h_metrics = regression_metrics(series.y, haar.reconstructed_y)

    global_leak = locality_leakage_metric(series, global_model.reconstructed_y, window=64)["leakage_ratio"]
    piecewise_leak = locality_leakage_metric(series, piecewise.reconstructed_y, window=64)["leakage_ratio"]
    poly_leak = locality_leakage_metric(series, polynomial.reconstructed_y, window=64)["leakage_ratio"]
    detrended_leak = locality_leakage_metric(series, detrended.reconstructed_y, window=64)["leakage_ratio"]

    adaptive_threshold_ratio = float(np.mean(adaptive["threshold"]))
    adaptive_keep_ratio = float(adaptive["keep_count"]) / float(series.sample_count)
    threshold_floor = float(np.min(adaptive["threshold"]))
    threshold_ceiling = float(np.max(adaptive["threshold"]))

    # Baseline payload: raw x+y as float64 arrays at original length.
    raw_payload = float(series.sample_count) * 2.0 * FLOAT64_BYTES
    global_payload = _estimate_fourier_payload_bytes(global_model)
    piecewise_payload = _estimate_piecewise_fourier_payload_bytes(piecewise)
    poly_payload = _estimate_piecewise_polynomial_payload_bytes(polynomial)
    uniform_payload = _estimate_fourier_payload_bytes(uniform)
    rdp_payload = _estimate_rdp_prefilter_payload_bytes(rdp_prefilter)
    detrended_payload = _estimate_fourier_payload_bytes(detrended.raw_fourier) + 2 * FLOAT64_BYTES
    haar_payload = _estimate_haar_payload_bytes(haar)
    adaptive_payload = _estimate_sparse_residual_payload_bytes(adaptive["keep_indices"])

    return {
        "dataset": name,
        "samples": int(series.sample_count),
        "terms": int(terms),
        "raw_payload_bytes": raw_payload,
        "global": {
            "r2": float(g_metrics["r2"]),
            "rmse": float(g_metrics["rmse"]),
            "leakage_ratio": global_leak,
            "max_abs": float(g_metrics["max_abs"]),
            "payload_bytes": global_payload,
            "payload_ratio": _safe_ratio(raw_payload, global_payload),
        },
        "piecewise_fourier": {
            "r2": float(p_metrics["r2"]),
            "rmse": float(p_metrics["rmse"]),
            "leakage_ratio": piecewise_leak,
            "segment_count": int(piecewise.metrics["segment_count"]),
            "payload_bytes": piecewise_payload,
            "payload_ratio": _safe_ratio(raw_payload, piecewise_payload),
        },
        "piecewise_polynomial": {
            "r2": float(poly_metrics["r2"]),
            "rmse": float(poly_metrics["rmse"]),
            "leakage_ratio": poly_leak,
            "segment_count": int(polynomial.metrics["segment_count"]),
            "approx_parameter_count": int(polynomial.metrics["approx_parameter_count"]),
            "payload_bytes": poly_payload,
            "payload_ratio": _safe_ratio(raw_payload, poly_payload),
        },
        "uniform_param_fourier": {
            "r2": float(u_metrics["r2"]),
            "rmse": float(u_metrics["rmse"]),
            "max_abs": float(u_metrics["max_abs"]),
            "payload_bytes": uniform_payload,
            "payload_ratio": _safe_ratio(raw_payload, uniform_payload),
        },
        "rdp_prefilter_fourier": {
            "r2": float(rdp_metrics["r2"]),
            "rmse": float(rdp_metrics["rmse"]),
            "max_abs": float(rdp_metrics["max_abs"]),
            "target_keep_ratio": float(target_keep_ratio),
            "actual_keep_ratio": float(rdp_prefilter.metrics["keep_ratio_actual"]),
            "rdp_kept": int(rdp_prefilter.prefilter.parameter_count),
            "rdp_epsilon": float(rdp_prefilter.prefilter.epsilon),
            "payload_bytes": rdp_payload,
            "payload_ratio": _safe_ratio(raw_payload, rdp_payload),
        },
        "detrended_fourier": {
            "r2": float(d_metrics["r2"]),
            "rmse": float(d_metrics["rmse"]),
            "leakage_ratio": detrended_leak,
            "r2_delta_vs_global": float(d_metrics["r2"] - g_metrics["r2"]),
            "trend_slope": float(detrended.metrics["trend_slope"]),
            "trend_intercept": float(detrended.metrics["trend_intercept"]),
            "adaptive_keep_ratio": adaptive_keep_ratio,
            "adaptive_threshold_ratio": adaptive_threshold_ratio,
            "adaptive_threshold_min": threshold_floor,
            "adaptive_threshold_max": threshold_ceiling,
            "payload_bytes": detrended_payload,
            "payload_ratio": _safe_ratio(raw_payload, detrended_payload),
        },
        "haar_threshold": {
            "r2": float(h_metrics["r2"]),
            "rmse": float(h_metrics["rmse"]),
            "max_abs": float(h_metrics["max_abs"]),
            "residual_payload_ratio": float(haar.metrics["residual_payload_ratio"]),
            "payload_bytes": haar_payload,
            "payload_ratio": _safe_ratio(raw_payload, haar_payload),
        },
        "adaptive_residual": {
            "keep_count": int(adaptive["keep_count"]),
            "payload_bytes": adaptive_payload,
            "payload_ratio": _safe_ratio(raw_payload, adaptive_payload),
        },
    }


def _safe_ratio(numerator: float, denominator: float, *, eps: float = 1e-12) -> float:
    # Avoid divide-by-zero noise in reports.
    # If denominator is near zero, return 0 to keep the table stable.
    if denominator <= eps:
        return 0.0
    return float(numerator / denominator)


def _estimate_fourier_payload_bytes(model: FourierModel) -> int:
    # Rough payload proxy for one Fourier model:
    # selected frequencies + coefficients + one bias value.
    coeff_count = int(model.parameter_count)
    return int(24 * coeff_count + 8)


def _estimate_piecewise_fourier_payload_bytes(model: PiecewiseModel) -> float:
    # Sum each segment's Fourier payload and add split index bytes.
    segment_bytes = sum(24 * int(seg.parameter_count) for seg in model.segment_models)
    breakpoint_bytes = int(len(model.breakpoints)) * INT64_BYTES
    # each breakpoint is an int64 index.
    return float(segment_bytes + breakpoint_bytes)


def _estimate_piecewise_polynomial_payload_bytes(model: PiecewisePolynomialModel) -> float:
    # Payload = polynomial coefficients + interval endpoints + breakpoint indexes.
    coeff_bytes = float(model.metrics.get("approx_parameter_count", 0) * FLOAT64_BYTES)
    interval_bytes = float(len(model.segment_coeffs) * 2 * FLOAT64_BYTES)
    breakpoint_bytes = float(len(model.breakpoints) * INT64_BYTES)
    return coeff_bytes + interval_bytes + breakpoint_bytes


def _estimate_rdp_prefilter_payload_bytes(model: RDPPrefilteredFourierModel) -> float:
    # RDP kept (x,y) points plus Fourier payload of simplified points.
    # This often grows if kept points are too many.
    keep_bytes = float(model.prefilter.parameter_count * (2 * FLOAT64_BYTES + INT64_BYTES))
    return keep_bytes + _estimate_fourier_payload_bytes(model.core_fourier)


def _estimate_haar_payload_bytes(model) -> float:
    # Store kept Haar detail coefficients + small metadata header.
    kept = float(model.metrics["kept_coefficients"])
    return kept * FLOAT64_BYTES + 2 * FLOAT64_BYTES


def _estimate_sparse_residual_payload_bytes(keep_indices: np.ndarray) -> float:
    # Residual layer stores (index,value) for each kept correction point.
    return float(len(keep_indices) * (INT64_BYTES + FLOAT64_BYTES))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run defensible locality and x-domain research benchmark.")
    parser.add_argument("--terms", default="16,32,64")
    parser.add_argument("--out-json", default="docs/benchmarks/defensible_hardening_report.json")
    parser.add_argument("--out-md", default="docs/benchmarks/defensible_hardening_report.md")
    parser.add_argument("--r2-gate", type=float, default=0.99)
    parser.add_argument("--leakage-gate", type=float, default=0.25)
    parser.add_argument("--max-adaptive-keep-ratio", type=float, default=0.45)
    parser.add_argument(
        "--locality-mode",
        choices=["strict", "any"],
        default="strict",
        help="strict: all selected locality methods must pass; any: any selected method passes",
    )
    parser.add_argument(
        "--include-piecewise-polynomial",
        action="store_true",
        default=False,
        help="Include piecewise polynomial locality in locality gate checks",
    )
    return parser.parse_args()


def _format_float(v: Any) -> str:
    if isinstance(v, (int, float)):
        return f"{float(v):.6g}"
    return str(v)


def _locality_checks(row: dict[str, Any], *, leakage_gate: float, include_poly: bool, locality_mode: str) -> tuple[list[float], bool]:
    # Choose whether leakage must pass on all methods (strict), or any one method (any).
    candidates = [
        row["piecewise_fourier"]["leakage_ratio"],
        row["detrended_fourier"]["leakage_ratio"],
    ]
    if include_poly:
        candidates.append(row["piecewise_polynomial"]["leakage_ratio"])

    if locality_mode == "any":
        ok = any(value <= leakage_gate for value in candidates)
    else:
        ok = all(value <= leakage_gate for value in candidates)
    return candidates, bool(ok)


def _gate_row(
    row: dict[str, Any],
    *,
    r2_gate: float,
    leakage_gate: float,
    max_keep_ratio: float,
    locality_mode: str,
    include_poly: bool,
) -> dict[str, Any]:
    # Gate report rows so we can quickly filter "defensible for demo" configs.
    if "global" not in row:
        return {
            "r2_gate": False,
            "leakage_gate": False,
            "residual_gate": False,
            "locality_candidates": [],
            "locality_mode": locality_mode,
            "defensible": False,
            "include_piecewise_polynomial": include_poly,
        }

    r2_gate_ok = row["detrended_fourier"]["r2"] >= r2_gate
    candidates, leakage_gate_ok = _locality_checks(
        row,
        leakage_gate=leakage_gate,
        include_poly=include_poly,
        locality_mode=locality_mode,
    )
    residual_gate_ok = row["detrended_fourier"]["adaptive_keep_ratio"] <= max_keep_ratio

    return {
        "r2_gate": bool(r2_gate_ok),
        "leakage_gate": bool(leakage_gate_ok),
        "residual_gate": bool(residual_gate_ok),
        "locality_candidates": [float(v) for v in candidates],
        "locality_mode": locality_mode,
        "include_piecewise_polynomial": include_poly,
        "defensible": bool(r2_gate_ok and leakage_gate_ok and residual_gate_ok),
    }


def _grouped_pass_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    # Aggregate gate pass counts per dataset so trends are visible at a glance.
    per_dataset: dict[str, dict[str, int]] = {}
    for row in rows:
        dataset = str(row["dataset"])
        if "gates" not in row:
            continue
        entry = per_dataset.setdefault(dataset, {"total": 0, "pass": 0})
        entry["total"] += 1
        if row["gates"]["defensible"]:
            entry["pass"] += 1
    return per_dataset


def main() -> int:
    args = parse_args()
    # Build a small synthetic stress test set:
    # abrupt steps, spikes, irregular timestamps, multi-scale structures, and smooth signals.
    terms = [int(item.strip()) for item in args.terms.split(",") if item.strip()]
    datasets = [
        ("steps", make_synthetic_dataset(4000, kind="steps")),
        ("spikes", make_synthetic_dataset(4000, kind="spikes")),
        ("irregular", make_synthetic_dataset(4000, kind="irregular")),
        ("multiscale", make_synthetic_dataset(4000, kind="multiscale")),
        ("smooth", make_synthetic_dataset(4000, kind="smooth")),
    ]

    rows = [_benchmark_row(name, series, term) for name, series in datasets for term in terms]

    x = np.linspace(0.0, 1.0, 1500, dtype=np.float64)
    channels = np.column_stack(
        [
            np.sin(2 * np.pi * 7.0 * x),
            0.85 * np.sin(2 * np.pi * 7.0 * x + 0.2),
            0.15 * np.sin(2 * np.pi * 29.0 * x),
        ]
    )
    mc = compress_multichannel_fourier_pca(channels, terms=32, rank=2)
    rows.append(
        {
            "dataset": "channels_multiaxis",
            "samples": int(channels.shape[0]),
            "multichannel_rank": int(mc["rank"]),
            "multichannel_metrics": {
                "rmse": float(mc["metrics"]["rmse"]),
                "mae": float(mc["metrics"]["mae"]),
                "max_abs": float(mc["metrics"]["max_abs"]),
                "parameter_count": float(mc["metrics"]["parameter_count"]),
            },
        }
    )
    rows = [
        {
            **row,
            "gates": _gate_row(
                row,
                r2_gate=args.r2_gate,
                leakage_gate=args.leakage_gate,
                max_keep_ratio=args.max_adaptive_keep_ratio,
                locality_mode=args.locality_mode,
                include_poly=args.include_piecewise_polynomial,
            ),
        }
        for row in rows
    ]

    per_dataset = _grouped_pass_rows(rows)
    locality_mode_desc = f"{args.locality_mode}({ 'piecewise_polynomial' if args.include_piecewise_polynomial else 'piecewise_fourier+detrended'})"

    payload = {
        "terms": terms,
        "rows": rows,
        "summary": {
            "gate_config": {
                "r2_gate": args.r2_gate,
                "leakage_gate": args.leakage_gate,
                "max_adaptive_keep_ratio": args.max_adaptive_keep_ratio,
                "locality_mode": args.locality_mode,
                "include_piecewise_polynomial": args.include_piecewise_polynomial,
            },
            "best_global_r2": max(row["global"]["r2"] for row in rows if "global" in row),
            "best_piecewise_leakage": min(
                row["piecewise_fourier"]["leakage_ratio"] for row in rows if "piecewise_fourier" in row
            ),
            "best_poly_leakage": min(
                row["piecewise_polynomial"]["leakage_ratio"] for row in rows if "piecewise_polynomial" in row
            ),
            "best_detrended_delta_r2": max(
                row["detrended_fourier"]["r2_delta_vs_global"] for row in rows if "detrended_fourier" in row
            ),
            "defensible_rows": sum(1 for row in rows if row["gates"]["defensible"]),
            "defensible_rdp_rows": sum(
                1 for row in rows if row.get("rdp_prefilter_fourier", {}).get("r2", 0.0) > args.r2_gate
            ),
            "rows_with_gate_fields": sum(1 for row in rows if "gates" in row),
            "multichannel_rmse": mc["metrics"]["rmse"],
            "dataset_passes": per_dataset,
            "locality_mode_desc": locality_mode_desc,
        },
    }

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Save both machine-readable and human-readable outputs from the same payload.
    lines = [
        "# Defensible Compression Research Report",
        "",
        f"- Terms: `{terms}`",
        f"- Rows: `{len(rows)}`",
        f"- Gate config: `R2 >= {args.r2_gate}` `leakage <= {args.leakage_gate}` `adaptive_keep <= {args.max_adaptive_keep_ratio}` `locality_mode = {args.locality_mode}` `include_poly = {args.include_piecewise_polynomial}`",
        "",
        "| dataset | terms | global R2 | detrended R2 | piecewise R2 | poly R2 | global leak | detrended leak | piecewise leak | poly leak | r2-delta | adaptive keep | adaptive th mean | global CR | detrended CR | piecewise CR | poly CR | rdp-pre CR | locality candidates | defensible |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        if "global" not in row:
            continue
        locality_candidates = ", ".join(_format_float(v) for v in row["gates"]["locality_candidates"])
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["dataset"]),
                    _format_float(row["terms"]),
                    _format_float(row["global"]["r2"]),
                    _format_float(row["detrended_fourier"]["r2"]),
                    _format_float(row["piecewise_fourier"]["r2"]),
                    _format_float(row["piecewise_polynomial"]["r2"]),
                    _format_float(row["global"]["leakage_ratio"]),
                    _format_float(row["detrended_fourier"]["leakage_ratio"]),
                    _format_float(row["piecewise_fourier"]["leakage_ratio"]),
                    _format_float(row["piecewise_polynomial"]["leakage_ratio"]),
                    _format_float(row["detrended_fourier"]["r2_delta_vs_global"]),
                    _format_float(row["detrended_fourier"]["adaptive_keep_ratio"]),
                    _format_float(row["detrended_fourier"]["adaptive_threshold_ratio"]),
                    _format_float(row["global"]["payload_ratio"]),
                    _format_float(row["detrended_fourier"]["payload_ratio"]),
                    _format_float(row["piecewise_fourier"]["payload_ratio"]),
                    _format_float(row["piecewise_polynomial"]["payload_ratio"]),
                    _format_float(row["rdp_prefilter_fourier"]["payload_ratio"]),
                    locality_candidates,
                    "pass" if row["gates"]["defensible"] else "fail",
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Multichannel summary",
            "",
            f"- rank = {mc['rank']}",
            f"- rmse = {mc['metrics']['rmse']:.6g}",
            f"- defensible rows = {payload['summary']['defensible_rows']} / {payload['summary']['rows_with_gate_fields']}",
            "- dataset pass summary:",
        ]
    )
    for dataset, pass_stat in sorted(per_dataset.items()):
        lines.append(f"  - {dataset}: {pass_stat['pass']} / {pass_stat['total']}")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"wrote {out_json}")
    print(f"wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
