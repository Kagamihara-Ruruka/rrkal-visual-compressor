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


def _benchmark_rdp_frontier(
    name: str,
    series: TimeSeries,
    terms: int,
    keep_ratio_list: list[float],
    *,
    min_keep: int = 128,
    max_keep: int | None = None,
    r2_gate: float | None = None,
) -> dict[str, Any]:
    # Try several RDP budgets and report where each one lands.
    # This is a "sweet-spot" table: too many points no longer saves much,
    # too few points ruins accuracy.
    raw_payload = float(series.sample_count) * 2.0 * FLOAT64_BYTES
    sweep = []

    for target_keep_ratio in keep_ratio_list:
        if target_keep_ratio <= 0.0 or target_keep_ratio > 1.0:
            continue
        model = compress_fourier_with_rdp_budget(
            series,
            terms=terms,
            target_keep_ratio=target_keep_ratio,
            min_keep=min_keep,
            max_keep=max_keep,
        )
        metrics = regression_metrics(series.y, model.reconstructed_y)
        payload_bytes = _estimate_rdp_prefilter_payload_bytes(model)
        r2_pass = r2_gate is None or float(metrics["r2"]) >= float(r2_gate)
        sweep.append(
            {
                "target_keep_ratio": float(target_keep_ratio),
                "actual_keep_ratio": float(model.metrics["keep_ratio_actual"]),
                "r2": float(metrics["r2"]),
                "rmse": float(metrics["rmse"]),
                "max_abs": float(metrics["max_abs"]),
                "kept_points": int(model.prefilter.parameter_count),
                "payload_bytes": float(payload_bytes),
                "payload_ratio": _safe_ratio(raw_payload, payload_bytes),
                "r2_gate_pass": bool(r2_pass),
                "gate_reason": "pass" if r2_pass else "r2_below_gate",
            }
        )

    if not sweep:
        return {
            "dataset": name,
            "terms": int(terms),
            "samples": int(series.sample_count),
            "sweep": [],
            "best_point": None,
        }

    sweep = sorted(sweep, key=lambda item: item["target_keep_ratio"])
    # "best" here means highest payload compression among points with enough fidelity.
    best_candidates = [
        item for item in sweep if item["r2_gate_pass"]
    ]
    if best_candidates:
        best_point = max(
            best_candidates,
            key=lambda item: (item["payload_ratio"], item["r2"], -item["actual_keep_ratio"]),
        )
    else:
        best_point = max(sweep, key=lambda item: item["r2"])

    # Check that target budgets behave logically: larger target ratio should keep
    # more points than smaller target ratio.
    monotonic_keep = True
    for left, right in zip(sweep[:-1], sweep[1:]):
        if right["actual_keep_ratio"] + 1e-12 < left["actual_keep_ratio"]:
            monotonic_keep = False
            break

    return {
        "dataset": name,
        "terms": int(terms),
        "samples": int(series.sample_count),
        "target_keep_ratios": [float(item["target_keep_ratio"]) for item in sweep],
        "sweep": sweep,
        "monotonic_keep": bool(monotonic_keep),
        "best_point": best_point,
        "best_point_r2_gate_passes": bool(r2_gate is None) or bool(best_candidates),
    }


def _with_gaussian_noise(series: TimeSeries, *, sigma: float, seed: int) -> TimeSeries:
    # Keep the same x-domain and add controlled Gaussian noise to y.
    # This lets us test whether a compression setting survives noisier data.
    if sigma < 0.0:
        raise ValueError("sigma must be >= 0")
    rng = np.random.default_rng(seed)
    if sigma == 0.0:
        y = series.y.copy()
    else:
        y = series.y + rng.normal(0.0, sigma, size=series.y.size)
    return TimeSeries(
        x=series.x.copy(),
        y=np.asarray(y, dtype=np.float64),
        source=f"{series.source}:noise_sigma={sigma}",
    )


def _safe_ratio(numerator: float, denominator: float, *, eps: float = 1e-12) -> float:
    # Avoid divide-by-zero noise in reports.
    # If denominator is near zero, return 0 to keep the table stable.
    if denominator <= eps:
        return 0.0
    return float(numerator / denominator)


def _parse_float_list(raw: str, *, allow_zero: bool = False) -> list[float]:
    # Parse a user string like "0.02,0.05,0.1,0.2".
    # Invalid tokens are ignored, then duplicates are removed.
    values: list[float] = []
    for item in raw.split(","):
        token = item.strip()
        if not token:
            continue
        value = float(token)
        if value < 0.0 or value > 1.0 or (value == 0.0 and not allow_zero):
            interval = "[0,1]" if allow_zero else "(0,1]"
            raise ValueError(f"value must be in {interval}, got {value}")
        if value not in values:
            values.append(value)
    if not values:
        raise ValueError(f"no valid ratio found in {raw!r}")
    return values


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
    parser.add_argument(
        "--run-rdp-frontier",
        action="store_true",
        default=False,
        help="Run extra RDP frontier scan rows for multiple keep ratios",
    )
    parser.add_argument(
        "--rdp-frontier-ratios",
        default="0.02,0.04,0.08,0.12,0.16,0.2,0.3",
        help="Comma-separated RDP target keep ratios for frontier scan",
    )
    parser.add_argument(
        "--rdp-frontier-min-keep",
        type=int,
        default=128,
        help="Minimum RDP points kept during frontier scan",
    )
    parser.add_argument(
        "--rdp-frontier-max-keep",
        type=int,
        default=0,
        help="Optional maximum RDP keep count (0 means no max limit)",
    )
    parser.add_argument(
        "--run-noise-frontier",
        action="store_true",
        default=False,
        help="Run RDP frontier against fixed Gaussian noise levels",
    )
    parser.add_argument(
        "--noise-frontier-kind",
        default="smooth",
        help="Synthetic base kind used for noise frontier",
    )
    parser.add_argument(
        "--noise-frontier-sigmas",
        default="0,0.02,0.05,0.10",
        help="Comma-separated Gaussian noise sigma values",
    )
    parser.add_argument(
        "--noise-frontier-seed",
        type=int,
        default=20260528,
        help="Random seed for reproducible noise frontier",
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


def _summarize_frontier_by_key(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    # Small report helper: group frontier rows by one metadata field, such as
    # noise sigma, and count which rows met the R2 gate.
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        label = str(row.get(key, "unknown"))
        entry = grouped.setdefault(
            label,
            {
                "total": 0,
                "best_points_with_gate": 0,
                "monotonic": 0,
                "best_payload_ratio": 0.0,
                "best_r2": 0.0,
            },
        )
        entry["total"] += 1
        if row["best_point_r2_gate_passes"]:
            entry["best_points_with_gate"] += 1
        if row["monotonic_keep"]:
            entry["monotonic"] += 1
        best = row.get("best_point")
        if best:
            entry["best_payload_ratio"] = max(entry["best_payload_ratio"], float(best["payload_ratio"]))
            entry["best_r2"] = max(entry["best_r2"], float(best["r2"]))
    return grouped


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

    frontier = None
    if args.run_rdp_frontier:
        keep_ratios = _parse_float_list(args.rdp_frontier_ratios)
        frontier_rows = []
        for name, series in datasets:
            for term in terms:
                frontier_rows.append(
                    _benchmark_rdp_frontier(
                        name=name,
                        series=series,
                        terms=term,
                        keep_ratio_list=keep_ratios,
                        min_keep=args.rdp_frontier_min_keep,
                        max_keep=args.rdp_frontier_max_keep or None,
                        r2_gate=args.r2_gate,
                    )
                )
        frontier = {
            "keep_ratios": keep_ratios,
            "min_keep": int(args.rdp_frontier_min_keep),
            "max_keep": None if args.rdp_frontier_max_keep <= 0 else int(args.rdp_frontier_max_keep),
            "r2_gate": args.r2_gate,
            "rows": frontier_rows,
            "summary": {
                "frontier_rows": len(frontier_rows),
                "monotonic_count": sum(1 for row in frontier_rows if row["monotonic_keep"]),
                "best_points_with_gate": sum(1 for row in frontier_rows if row["best_point_r2_gate_passes"]),
            },
        }

    noise_frontier = None
    if args.run_noise_frontier:
        noise_sigmas = _parse_float_list(args.noise_frontier_sigmas, allow_zero=True)
        if args.noise_frontier_kind not in {name for name, _ in datasets}:
            base_series = make_synthetic_dataset(4000, kind=args.noise_frontier_kind)
        else:
            base_series = dict(datasets)[args.noise_frontier_kind]

        keep_ratios = _parse_float_list(args.rdp_frontier_ratios)
        noise_rows = []
        for sigma in noise_sigmas:
            noisy_series = _with_gaussian_noise(
                base_series,
                sigma=sigma,
                seed=int(args.noise_frontier_seed + round(sigma * 100000)),
            )
            for term in terms:
                row = _benchmark_rdp_frontier(
                    name=f"{args.noise_frontier_kind}_noise_{sigma:g}",
                    series=noisy_series,
                    terms=term,
                    keep_ratio_list=keep_ratios,
                    min_keep=args.rdp_frontier_min_keep,
                    max_keep=args.rdp_frontier_max_keep or None,
                    r2_gate=args.r2_gate,
                )
                row["noise_sigma"] = float(sigma)
                row["base_kind"] = args.noise_frontier_kind
                noise_rows.append(row)

        noise_frontier = {
            "base_kind": args.noise_frontier_kind,
            "sigmas": noise_sigmas,
            "seed": int(args.noise_frontier_seed),
            "keep_ratios": keep_ratios,
            "rows": noise_rows,
            "summary": {
                "noise_rows": len(noise_rows),
                "best_points_with_gate": sum(1 for row in noise_rows if row["best_point_r2_gate_passes"]),
                "monotonic_count": sum(1 for row in noise_rows if row["monotonic_keep"]),
                "by_sigma": _summarize_frontier_by_key(noise_rows, "noise_sigma"),
            },
        }

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
        "run_rdp_frontier": bool(args.run_rdp_frontier),
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
        "rdp_frontier": frontier,
        "noise_frontier": noise_frontier,
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

    if frontier is not None:
        lines.extend(
            [
                "",
                "## RDP frontier scan",
                "",
                "| dataset | terms | target keep ratio | actual keep | r2 | payload ratio | kept points | best gate reason | best under R2 gate? |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |",
            ]
        )
        for item in frontier["rows"]:
            best = item["best_point"]
            best_keep = float(best["target_keep_ratio"]) if best else 0.0
            best_ratio = float(best["actual_keep_ratio"]) if best else 0.0
            best_r2 = float(best["r2"]) if best else 0.0
            best_payload = float(best["payload_ratio"]) if best else 0.0
            best_points = int(best["kept_points"]) if best else 0
            best_reason = str(best["gate_reason"]) if best else "no_candidate"
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(item["dataset"]),
                        _format_float(item["terms"]),
                        _format_float(best_keep),
                        _format_float(best_ratio),
                        _format_float(best_r2),
                        _format_float(best_payload),
                        _format_float(best_points),
                        best_reason,
                        "yes" if item["best_point_r2_gate_passes"] else "no",
                    ]
                )
                + " |"
            )

    if noise_frontier is not None:
        lines.extend(
            [
                "",
                "## Noise frontier scan",
                "",
                "| base kind | sigma | terms | target keep ratio | actual keep | r2 | payload ratio | gate reason |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
            ]
        )
        for item in noise_frontier["rows"]:
            best = item["best_point"]
            best_keep = float(best["target_keep_ratio"]) if best else 0.0
            best_ratio = float(best["actual_keep_ratio"]) if best else 0.0
            best_r2 = float(best["r2"]) if best else 0.0
            best_payload = float(best["payload_ratio"]) if best else 0.0
            best_reason = str(best["gate_reason"]) if best else "no_candidate"
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(item["base_kind"]),
                        _format_float(item["noise_sigma"]),
                        _format_float(item["terms"]),
                        _format_float(best_keep),
                        _format_float(best_ratio),
                        _format_float(best_r2),
                        _format_float(best_payload),
                        best_reason,
                    ]
                )
                + " |"
            )
        lines.extend(["", "### Noise frontier by sigma", ""])
        lines.extend(
            [
                "| sigma | rows | gate passes | monotonic rows | best R2 | best payload ratio |",
                "| ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for sigma, item in sorted(noise_frontier["summary"]["by_sigma"].items(), key=lambda pair: float(pair[0])):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _format_float(sigma),
                        _format_float(item["total"]),
                        _format_float(item["best_points_with_gate"]),
                        _format_float(item["monotonic"]),
                        _format_float(item["best_r2"]),
                        _format_float(item["best_payload_ratio"]),
                    ]
                )
                + " |"
            )

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"wrote {out_json}")
    print(f"wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
