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

from vizcompress.data import SYNTHETIC_KINDS, make_synthetic_dataset
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
    exploratory_r2_gate: float | None = None,
    demo_r2_gate: float | None = None,
    min_payload_ratio: float = 1.0,
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
        payload_ratio = _safe_ratio(raw_payload, payload_bytes)
        r2_pass = r2_gate is None or float(metrics["r2"]) >= float(r2_gate)
        payload_pass = payload_ratio >= float(min_payload_ratio)
        gate_reason = _frontier_gate_reason(r2_pass=r2_pass, payload_pass=payload_pass)
        tier = _frontier_tier(
            r2=float(metrics["r2"]),
            payload_ratio=payload_ratio,
            strict_gate=0.99 if r2_gate is None else float(r2_gate),
            exploratory_gate=0.95 if exploratory_r2_gate is None else float(exploratory_r2_gate),
            demo_gate=0.90 if demo_r2_gate is None else float(demo_r2_gate),
            min_payload_ratio=min_payload_ratio,
        )
        sweep.append(
            {
                "target_keep_ratio": float(target_keep_ratio),
                "actual_keep_ratio": float(model.metrics["keep_ratio_actual"]),
                "r2": float(metrics["r2"]),
                "rmse": float(metrics["rmse"]),
                "max_abs": float(metrics["max_abs"]),
                "kept_points": int(model.prefilter.parameter_count),
                "payload_bytes": float(payload_bytes),
                "payload_ratio": payload_ratio,
                "r2_gate_pass": bool(r2_pass),
                "payload_gate_pass": bool(payload_pass),
                "gate_reason": gate_reason,
                "frontier_tier": tier,
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
    # "best" here means highest quality tier with payload-efficient points.
    best_candidates = [item for item in sweep if item["payload_gate_pass"]]
    if best_candidates:
        best_point = max(
            best_candidates,
            key=lambda item: (
                _frontier_tier_score(item["frontier_tier"]),
                item["payload_ratio"],
                item["r2"],
                -item["actual_keep_ratio"],
            ),
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
        "best_point_gate_passes": bool(
            best_point is not None
            and best_point["frontier_tier"] in {"strict_pass", "exploratory_pass", "demo_pass"}
        ),
        "best_point_r2_gate_passes": bool(best_candidates and best_point["r2_gate_pass"]),
        "best_point_tier": best_point["frontier_tier"] if best_point else "reject",
        "min_payload_ratio": float(min_payload_ratio),
    }


def _frontier_gate_reason(*, r2_pass: bool, payload_pass: bool) -> str:
    # Keep frontier JSON self-explanatory for later agents and reports.
    if r2_pass and payload_pass:
        return "pass"
    if not r2_pass and not payload_pass:
        return "r2_and_payload_below_gate"
    if not r2_pass:
        return "r2_below_gate"
    return "payload_below_gate"


def _frontier_tier(
    r2: float,
    payload_ratio: float,
    strict_gate: float,
    exploratory_gate: float,
    demo_gate: float,
    min_payload_ratio: float,
) -> str:
    # Give each frontier point one of five buckets for reporting.
    # strict_pass -> exploratory -> demo -> reject.
    if payload_ratio < float(min_payload_ratio):
        return "payload_reject"
    if r2 >= float(strict_gate):
        return "strict_pass"
    if r2 >= float(exploratory_gate):
        return "exploratory_pass"
    if r2 >= float(demo_gate):
        return "demo_pass"
    return "reject"


def _frontier_tier_score(tier: str) -> int:
    # Stronger tiers have larger score for best-point selection.
    return {
        "strict_pass": 4,
        "exploratory_pass": 3,
        "demo_pass": 2,
        "reject": 1,
        "payload_reject": 0,
    }.get(tier, 0)


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


def _parse_gate_list(raw: str) -> list[float]:
    # Gate lists use normal float thresholds, usually around 0.90-0.99.
    values = _parse_float_list(raw, allow_zero=False)
    return sorted(values)


def _parse_string_list(raw: str) -> list[str]:
    # Parse comma-separated names while preserving order and removing duplicates.
    values: list[str] = []
    for item in raw.split(","):
        token = item.strip()
        if token and token not in values:
            values.append(token)
    if not values:
        raise ValueError(f"no valid value found in {raw!r}")
    return values


def _best_frontier_point_for_tier_config(
    sweep: list[dict[str, Any]],
    *,
    strict_gate: float,
    exploratory_gate: float,
    demo_gate: float,
    min_payload_ratio: float,
) -> dict[str, Any] | None:
    # Re-score an already computed sweep under another tier configuration.
    # This avoids rerunning model fitting just to ask "what if the gate changed?"
    candidates: list[dict[str, Any]] = []
    for item in sweep:
        rescored = dict(item)
        tier = _frontier_tier(
            r2=float(item["r2"]),
            payload_ratio=float(item["payload_ratio"]),
            strict_gate=strict_gate,
            exploratory_gate=exploratory_gate,
            demo_gate=demo_gate,
            min_payload_ratio=min_payload_ratio,
        )
        rescored["frontier_tier"] = tier
        rescored["r2_gate_pass"] = bool(float(item["r2"]) >= strict_gate)
        rescored["payload_gate_pass"] = bool(float(item["payload_ratio"]) >= min_payload_ratio)
        candidates.append(rescored)

    if not candidates:
        return None

    payload_candidates = [item for item in candidates if item["payload_gate_pass"]]
    if payload_candidates:
        return max(
            payload_candidates,
            key=lambda item: (
                _frontier_tier_score(str(item["frontier_tier"])),
                float(item["payload_ratio"]),
                float(item["r2"]),
                -float(item["actual_keep_ratio"]),
            ),
        )
    return max(candidates, key=lambda item: float(item["r2"]))


def _summarize_frontier_tier_matrix(
    rows: list[dict[str, Any]],
    *,
    strict_gate: float,
    exploratory_gates: list[float],
    demo_gates: list[float],
    min_payload_ratio: float,
) -> list[dict[str, Any]]:
    # Summarize how tier counts move as demo/exploratory gates change.
    matrix: list[dict[str, Any]] = []
    for exploratory_gate in exploratory_gates:
        for demo_gate in demo_gates:
            if demo_gate > exploratory_gate:
                continue
            counts = {
                "strict_pass": 0,
                "exploratory_pass": 0,
                "demo_pass": 0,
                "reject": 0,
                "payload_reject": 0,
            }
            best_payload_ratio = 0.0
            best_r2 = 0.0
            for row in rows:
                best = _best_frontier_point_for_tier_config(
                    row.get("sweep", []),
                    strict_gate=strict_gate,
                    exploratory_gate=exploratory_gate,
                    demo_gate=demo_gate,
                    min_payload_ratio=min_payload_ratio,
                )
                if best is None:
                    counts["reject"] += 1
                    continue
                tier = str(best["frontier_tier"])
                counts[tier] = counts.get(tier, 0) + 1
                best_payload_ratio = max(best_payload_ratio, float(best["payload_ratio"]))
                best_r2 = max(best_r2, float(best["r2"]))
            matrix.append(
                {
                    "strict_gate": float(strict_gate),
                    "exploratory_gate": float(exploratory_gate),
                    "demo_gate": float(demo_gate),
                    "row_count": len(rows),
                    "tier_counts": counts,
                    "best_payload_ratio": best_payload_ratio,
                    "best_r2": best_r2,
                }
            )
    return matrix


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
        "--frontier-min-payload-ratio",
        type=float,
        default=1.0,
        help="Minimum raw/model payload ratio required for a frontier candidate",
    )
    parser.add_argument(
        "--frontier-exploratory-r2-gate",
        type=float,
        default=0.95,
        help="R2 threshold for exploratory frontier tier",
    )
    parser.add_argument(
        "--frontier-demo-r2-gate",
        type=float,
        default=0.90,
        help="R2 threshold for demo-only frontier tier",
    )
    parser.add_argument(
        "--frontier-exploratory-r2-gates",
        default="0.94,0.95,0.96,0.97",
        help="Comma-separated exploratory R2 gates used by the optional tier matrix",
    )
    parser.add_argument(
        "--frontier-demo-r2-gates",
        default="0.88,0.90,0.92,0.94",
        help="Comma-separated demo R2 gates used by the optional tier matrix",
    )
    parser.add_argument(
        "--run-frontier-tier-matrix",
        action="store_true",
        default=False,
        help="Re-score existing frontier sweeps across demo/exploratory R2 gate pairs",
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
        "--noise-frontier-kinds",
        default="",
        help="Comma-separated synthetic base kinds used for noise frontier; overrides --noise-frontier-kind",
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


def _summarize_frontier_tiers_by_key(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    # Group frontier best-point quality tiers by a metadata field.
    # For noise scans, this makes degradation visible by sigma and by dataset kind.
    grouped: dict[str, dict[str, Any]] = {}
    tier_names = ["strict_pass", "exploratory_pass", "demo_pass", "reject", "payload_reject"]
    for row in rows:
        label = str(row.get(key, "unknown"))
        entry = grouped.setdefault(
            label,
            {
                "total": 0,
                "tier_counts": {name: 0 for name in tier_names},
                "best_payload_ratio": 0.0,
                "best_r2": 0.0,
            },
        )
        entry["total"] += 1
        best = row.get("best_point")
        tier = str(row.get("best_point_tier", "reject"))
        if tier not in entry["tier_counts"]:
            entry["tier_counts"][tier] = 0
        entry["tier_counts"][tier] += 1
        if best:
            entry["best_payload_ratio"] = max(entry["best_payload_ratio"], float(best["payload_ratio"]))
            entry["best_r2"] = max(entry["best_r2"], float(best["r2"]))
    return grouped


def _recommend_noise_frontier_strategy(
    tier_by_sigma: dict[str, dict[str, Any]],
    tier_by_kind: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    # Convert tier breakdowns into a concrete next research move.
    # This is intentionally conservative: it recommends where to investigate,
    # not that the current method is solved.
    high_sigma_rejects = 0
    high_sigma_total = 0
    for sigma_label, item in tier_by_sigma.items():
        sigma = float(sigma_label)
        if sigma < 0.05:
            continue
        counts = item.get("tier_counts", {})
        high_sigma_total += int(item.get("total", 0))
        high_sigma_rejects += int(counts.get("reject", 0)) + int(counts.get("payload_reject", 0))

    kind_rejects: dict[str, int] = {}
    for kind, item in tier_by_kind.items():
        counts = item.get("tier_counts", {})
        kind_rejects[str(kind)] = int(counts.get("reject", 0)) + int(counts.get("payload_reject", 0))

    worst_kind = max(kind_rejects, key=kind_rejects.get) if kind_rejects else "unknown"
    high_noise_reject_ratio = (
        float(high_sigma_rejects) / float(high_sigma_total) if high_sigma_total else 0.0
    )

    if high_noise_reject_ratio >= 0.25:
        strategy = "localized_basis_or_residual_layer"
        rationale = "high-sigma rows contain enough rejects that global/RDP fitting alone is not robust"
    elif kind_rejects.get("spikes", 0) > 0:
        strategy = "sparse_residual_layer"
        rationale = "spike-like data fails before smooth data, so sparse residual handling should be promoted"
    else:
        strategy = "gate_tuning_only"
        rationale = "current frontier has no strong reject cluster; tune tiers before adding model complexity"

    return {
        "recommended_strategy": strategy,
        "rationale": rationale,
        "worst_kind": worst_kind,
        "high_sigma_reject_ratio": high_noise_reject_ratio,
        "high_sigma_rejects": high_sigma_rejects,
        "high_sigma_total": high_sigma_total,
        "kind_rejects": kind_rejects,
    }


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
                        exploratory_r2_gate=args.frontier_exploratory_r2_gate,
                        demo_r2_gate=args.frontier_demo_r2_gate,
                        min_payload_ratio=args.frontier_min_payload_ratio,
                    )
                )
        frontier_tier_counts: dict[str, int] = {}
        for item in frontier_rows:
            key = str(item["best_point_tier"])
            frontier_tier_counts[key] = frontier_tier_counts.get(key, 0) + 1
        frontier_tier_matrix = (
            _summarize_frontier_tier_matrix(
                frontier_rows,
                strict_gate=args.r2_gate,
                exploratory_gates=_parse_gate_list(args.frontier_exploratory_r2_gates),
                demo_gates=_parse_gate_list(args.frontier_demo_r2_gates),
                min_payload_ratio=args.frontier_min_payload_ratio,
            )
            if args.run_frontier_tier_matrix
            else []
        )
        frontier = {
            "keep_ratios": keep_ratios,
            "min_keep": int(args.rdp_frontier_min_keep),
            "max_keep": None if args.rdp_frontier_max_keep <= 0 else int(args.rdp_frontier_max_keep),
            "r2_gate": args.r2_gate,
            "exploratory_r2_gate": args.frontier_exploratory_r2_gate,
            "demo_r2_gate": args.frontier_demo_r2_gate,
            "min_payload_ratio": args.frontier_min_payload_ratio,
            "rows": frontier_rows,
            "summary": {
                "frontier_rows": len(frontier_rows),
                "monotonic_count": sum(1 for row in frontier_rows if row["monotonic_keep"]),
                "best_points_with_gate": sum(1 for row in frontier_rows if row["best_point_r2_gate_passes"]),
                "best_point_tier_counts": frontier_tier_counts,
                "tier_matrix": frontier_tier_matrix,
            },
        }

    noise_frontier = None
    if args.run_noise_frontier:
        noise_sigmas = _parse_float_list(args.noise_frontier_sigmas, allow_zero=True)
        noise_kinds = (
            _parse_string_list(args.noise_frontier_kinds)
            if args.noise_frontier_kinds.strip()
            else [args.noise_frontier_kind]
        )
        unknown_kinds = [kind for kind in noise_kinds if kind not in SYNTHETIC_KINDS]
        if unknown_kinds:
            raise ValueError(f"unknown noise frontier synthetic kind(s): {', '.join(unknown_kinds)}")

        keep_ratios = _parse_float_list(args.rdp_frontier_ratios)
        noise_rows = []
        dataset_by_name = dict(datasets)
        for kind in noise_kinds:
            base_series = dataset_by_name.get(kind) or make_synthetic_dataset(4000, kind=kind)
            for sigma in noise_sigmas:
                noisy_series = _with_gaussian_noise(
                    base_series,
                    sigma=sigma,
                    seed=int(args.noise_frontier_seed + round(sigma * 100000) + len(kind)),
                )
                for term in terms:
                    row = _benchmark_rdp_frontier(
                        name=f"{kind}_noise_{sigma:g}",
                        series=noisy_series,
                        terms=term,
                        keep_ratio_list=keep_ratios,
                        min_keep=args.rdp_frontier_min_keep,
                        max_keep=args.rdp_frontier_max_keep or None,
                        r2_gate=args.r2_gate,
                        exploratory_r2_gate=args.frontier_exploratory_r2_gate,
                        demo_r2_gate=args.frontier_demo_r2_gate,
                        min_payload_ratio=args.frontier_min_payload_ratio,
                    )
                    row["noise_sigma"] = float(sigma)
                    row["base_kind"] = kind
                    noise_rows.append(row)

        noise_frontier = {
            "base_kinds": noise_kinds,
            "sigmas": noise_sigmas,
            "seed": int(args.noise_frontier_seed),
            "keep_ratios": keep_ratios,
            "min_payload_ratio": args.frontier_min_payload_ratio,
            "rows": noise_rows,
            "summary": {
                "noise_rows": len(noise_rows),
                "best_points_with_gate": sum(1 for row in noise_rows if row["best_point_r2_gate_passes"]),
                "monotonic_count": sum(1 for row in noise_rows if row["monotonic_keep"]),
                "best_point_tier_counts": {
                    "strict_pass": 0,
                    "exploratory_pass": 0,
                    "demo_pass": 0,
                    "reject": 0,
                    "payload_reject": 0,
                },
                "by_sigma": _summarize_frontier_by_key(noise_rows, "noise_sigma"),
                "by_kind": _summarize_frontier_by_key(noise_rows, "base_kind"),
                "tier_by_sigma": _summarize_frontier_tiers_by_key(noise_rows, "noise_sigma"),
                "tier_by_kind": _summarize_frontier_tiers_by_key(noise_rows, "base_kind"),
                "tier_matrix": (
                    _summarize_frontier_tier_matrix(
                        noise_rows,
                        strict_gate=args.r2_gate,
                        exploratory_gates=_parse_gate_list(args.frontier_exploratory_r2_gates),
                        demo_gates=_parse_gate_list(args.frontier_demo_r2_gates),
                        min_payload_ratio=args.frontier_min_payload_ratio,
                    )
                    if args.run_frontier_tier_matrix
                    else []
                ),
            },
        }
        for item in noise_rows:
            key = str(item["best_point_tier"])
            noise_frontier["summary"]["best_point_tier_counts"][key] = (
                noise_frontier["summary"]["best_point_tier_counts"][key] + 1
            )
        noise_frontier["summary"]["recommended_next_strategy"] = _recommend_noise_frontier_strategy(
            noise_frontier["summary"]["tier_by_sigma"],
            noise_frontier["summary"]["tier_by_kind"],
        )

    payload = {
        "terms": terms,
        "rows": rows,
        "summary": {
            "gate_config": {
                "r2_gate": args.r2_gate,
                "frontier_exploratory_r2_gate": args.frontier_exploratory_r2_gate,
                "frontier_demo_r2_gate": args.frontier_demo_r2_gate,
                "frontier_exploratory_r2_gates": _parse_gate_list(args.frontier_exploratory_r2_gates),
                "frontier_demo_r2_gates": _parse_gate_list(args.frontier_demo_r2_gates),
                "run_frontier_tier_matrix": args.run_frontier_tier_matrix,
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
                f"- frontier strict gate = {frontier['r2_gate']}",
                f"- frontier exploratory gate = {frontier['exploratory_r2_gate']}",
                f"- frontier demo gate = {frontier['demo_r2_gate']}",
                "- frontier best-point tiers:",
            ]
        )
        for tier_name, tier_count in sorted(frontier["summary"]["best_point_tier_counts"].items()):
            lines.append(f"  - {tier_name}: {tier_count}")
        if frontier["summary"]["tier_matrix"]:
            lines.extend(
                [
                    "",
                    "### RDP frontier tier matrix",
                    "",
                    "| exploratory gate | demo gate | strict | exploratory | demo | reject | payload reject | best R2 | best payload ratio |",
                    "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
                ]
            )
            for item in frontier["summary"]["tier_matrix"]:
                counts = item["tier_counts"]
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            _format_float(item["exploratory_gate"]),
                            _format_float(item["demo_gate"]),
                            _format_float(counts["strict_pass"]),
                            _format_float(counts["exploratory_pass"]),
                            _format_float(counts["demo_pass"]),
                            _format_float(counts["reject"]),
                            _format_float(counts["payload_reject"]),
                            _format_float(item["best_r2"]),
                            _format_float(item["best_payload_ratio"]),
                        ]
                    )
                    + " |"
                )
        lines.extend(
            [
                "",
                "## RDP frontier scan",
                "",
                "| dataset | terms | target keep ratio | actual keep | r2 | payload ratio | kept points | best gate reason | frontier tier | best under R2 gate? |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | ---: |",
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
                        str(best["frontier_tier"]) if best else "no_candidate",
                        "yes" if item["best_point_r2_gate_passes"] else "no",
                    ]
                )
                + " |"
            )

    if noise_frontier is not None:
        lines.extend(
            [
                "",
                "- noise frontier best-point tiers:",
            ]
        )
        for tier_name, tier_count in sorted(
            noise_frontier["summary"]["best_point_tier_counts"].items()
        ):
            lines.append(f"  - {tier_name}: {tier_count}")
        recommendation = noise_frontier["summary"].get("recommended_next_strategy", {})
        if recommendation:
            lines.extend(
                [
                    "",
                    "### Noise frontier recommendation",
                    "",
                    f"- recommended strategy: `{recommendation['recommended_strategy']}`",
                    f"- rationale: {recommendation['rationale']}",
                    f"- worst kind: `{recommendation['worst_kind']}`",
                    f"- high-sigma reject ratio: `{_format_float(recommendation['high_sigma_reject_ratio'])}`",
                ]
            )
        if noise_frontier["summary"]["tier_matrix"]:
            lines.extend(
                [
                    "",
                    "### Noise frontier tier matrix",
                    "",
                    "| exploratory gate | demo gate | strict | exploratory | demo | reject | payload reject | best R2 | best payload ratio |",
                    "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
                ]
            )
            for item in noise_frontier["summary"]["tier_matrix"]:
                counts = item["tier_counts"]
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            _format_float(item["exploratory_gate"]),
                            _format_float(item["demo_gate"]),
                            _format_float(counts["strict_pass"]),
                            _format_float(counts["exploratory_pass"]),
                            _format_float(counts["demo_pass"]),
                            _format_float(counts["reject"]),
                            _format_float(counts["payload_reject"]),
                            _format_float(item["best_r2"]),
                            _format_float(item["best_payload_ratio"]),
                        ]
                    )
                    + " |"
                )
        lines.extend(
            [
                "",
                "## Noise frontier scan",
                "",
                "| base kind | sigma | terms | target keep ratio | actual keep | r2 | payload ratio | gate reason | frontier tier |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
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
                        str(best["frontier_tier"]) if best else "no_candidate",
                    ]
                )
                + " |"
            )
        lines.extend(["", "### Noise frontier by sigma", ""])
        lines.extend(
            [
                "| sigma | rows | gate passes | strict | exploratory | demo | reject | payload reject | monotonic rows | best R2 | best payload ratio |",
                "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for sigma, item in sorted(noise_frontier["summary"]["by_sigma"].items(), key=lambda pair: float(pair[0])):
            tier_item = noise_frontier["summary"]["tier_by_sigma"].get(str(sigma), {})
            tier_counts = tier_item.get("tier_counts", {})
            lines.append(
                "| "
                + " | ".join(
                    [
                        _format_float(sigma),
                        _format_float(item["total"]),
                        _format_float(item["best_points_with_gate"]),
                        _format_float(tier_counts.get("strict_pass", 0)),
                        _format_float(tier_counts.get("exploratory_pass", 0)),
                        _format_float(tier_counts.get("demo_pass", 0)),
                        _format_float(tier_counts.get("reject", 0)),
                        _format_float(tier_counts.get("payload_reject", 0)),
                        _format_float(item["monotonic"]),
                        _format_float(item["best_r2"]),
                        _format_float(item["best_payload_ratio"]),
                    ]
                )
                + " |"
            )
        lines.extend(["", "### Noise frontier by kind", ""])
        lines.extend(
            [
                "| kind | rows | gate passes | strict | exploratory | demo | reject | payload reject | monotonic rows | best R2 | best payload ratio |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for kind, item in sorted(noise_frontier["summary"]["by_kind"].items()):
            tier_item = noise_frontier["summary"]["tier_by_kind"].get(str(kind), {})
            tier_counts = tier_item.get("tier_counts", {})
            lines.append(
                "| "
                + " | ".join(
                    [
                        kind,
                        _format_float(item["total"]),
                        _format_float(item["best_points_with_gate"]),
                        _format_float(tier_counts.get("strict_pass", 0)),
                        _format_float(tier_counts.get("exploratory_pass", 0)),
                        _format_float(tier_counts.get("demo_pass", 0)),
                        _format_float(tier_counts.get("reject", 0)),
                        _format_float(tier_counts.get("payload_reject", 0)),
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
