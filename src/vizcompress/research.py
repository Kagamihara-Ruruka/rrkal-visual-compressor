from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from vizcompress.compressors import compress_fourier, compress_rdp, rolling_std
from vizcompress.core import RDPModel, TimeSeries, FourierModel
from vizcompress.metrics import regression_metrics


@dataclass(frozen=True)
class HaarWaveletModel:
    reconstructed_y: np.ndarray
    metrics: dict[str, float]


@dataclass(frozen=True)
class PiecewiseModel:
    breakpoints: np.ndarray
    segment_models: list[FourierModel]
    reconstructed_y: np.ndarray
    metrics: dict[str, float]


@dataclass(frozen=True)
class PiecewisePolynomialModel:
    breakpoints: np.ndarray
    segment_coeffs: list[np.ndarray]
    segment_intervals: list[tuple[float, float]]
    reconstructed_y: np.ndarray
    metrics: dict[str, float]


@dataclass(frozen=True)
class DetrendedFourierModel:
    """Fourier model with explicit linear trend removed and re-added."""

    reconstructed_y: np.ndarray
    trend_coeffs: tuple[float, float]
    metrics: dict[str, float]
    raw_fourier: FourierModel


@dataclass(frozen=True)
class RDPPrefilteredFourierModel:
    """Fourier model after simplifying points with RDP first."""

    prefilter: RDPModel
    core_fourier: FourierModel
    reconstructed_y: np.ndarray
    metrics: dict[str, float]


def _count_for_rdp_epsilon(series: TimeSeries, epsilon: float) -> int:
    # Try one epsilon value and return how many points RDP keeps.
    # Bigger epsilon means stronger simplification.
    return int(compress_rdp(series, epsilon).parameter_count)


def _find_rdp_epsilon_for_target_count(
    series: TimeSeries,
    target_count: int,
    *,
    max_steps: int = 28,
) -> float:
    # Binary-search epsilon so we end up with roughly `target_count` points.
    # Bigger epsilon => fewer kept points.
    if target_count >= series.sample_count:
        return 0.0

    lo = 0.0
    hi = 1.0
    if _count_for_rdp_epsilon(series, hi) > target_count:
        while _count_for_rdp_epsilon(series, hi) > target_count and hi < 64.0:
            hi *= 2.0

    # Keep at least 2 points.
    for _ in range(max_steps):
        mid = (lo + hi) / 2.0
        count = _count_for_rdp_epsilon(series, mid)
        if count <= target_count:
            hi = mid
        else:
            lo = mid

    return hi


def _fit_linear_trend(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    # Fit y = a*x + b with least squares.
    # This isolates the long-term slope so Fourier focuses on wave shape.
    """Return coefficients (slope, intercept) for y ~= a*x + b."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.size < 2:
        raise ValueError("linear trend requires at least 2 samples")
    x0 = float(np.mean(x))
    x_n = x - x0
    A = np.column_stack([x_n, np.ones_like(x_n)])
    coeffs, *_ = np.linalg.lstsq(A, y, rcond=None)
    a, b = coeffs
    return float(a), float(b + np.mean(y) - a * x0)


def compress_fourier_with_linear_detrend(
    series: TimeSeries,
    terms: int,
) -> DetrendedFourierModel:
    # Step 1: remove a straight-line trend.
    # Step 2: compress the remaining signal with Fourier.
    # Step 3: add trend back to rebuild the original scale.
    """Remove linear trend then fit Fourier, then re-add trend."""
    if terms <= 0:
        raise ValueError("terms must be positive")
    a, b = _fit_linear_trend(series.x, series.y)
    trend = a * series.x + b
    residual = series.y - trend
    de_trended_series = TimeSeries(x=series.x, y=residual, source=series.source)
    core = compress_fourier(de_trended_series, terms=terms)
    reconstructed = core.reconstructed_y + trend
    metrics = dict(core.metrics)
    metrics.update(
        {
            "trend_slope": a,
            "trend_intercept": b,
            "trend_rmse": float(np.sqrt(np.mean((series.y - trend) ** 2))),
            "trend_removed_rmse": metrics["rmse"],
        }
    )
    return DetrendedFourierModel(
        reconstructed_y=reconstructed,
        trend_coeffs=(a, b),
        metrics=metrics,
        raw_fourier=core,
    )


def adaptive_residual_threshold(
    x: np.ndarray,
    residual: np.ndarray,
    *,
    window: int = 128,
    adaptive_factor: float = 3.0,
    min_threshold: float = 1e-8,
) -> dict[str, Any]:
    # Build one threshold for each sample.
    # In noisier windows we allow larger error, in smoother windows tighter error.
    """Build a per-sample threshold by fitting a trend on rolling residual volatility."""
    if len(x) != len(residual):
        raise ValueError("x and residual must have same length")
    if len(x) < 3:
        raise ValueError("at least 3 samples required")
    if adaptive_factor <= 0:
        raise ValueError("adaptive_factor must be > 0")
    if window < 2:
        raise ValueError("window must be >= 2")

    x = np.asarray(x, dtype=np.float64)
    residual = np.asarray(residual, dtype=np.float64)
    volatility = rolling_std(np.abs(residual), window=window)
    a, b = _fit_linear_trend(x, volatility)
    trend_volatility = a * x + b
    trend_volatility = np.maximum(trend_volatility, np.min(volatility))
    threshold = np.maximum(min_threshold, adaptive_factor * trend_volatility)
    keep_mask = np.abs(residual) > threshold
    return {
        "trend_coeffs": (float(a), float(b)),
        "volatility": volatility,
        "trend_volatility": trend_volatility,
        "threshold": threshold,
        "keep_indices": np.flatnonzero(keep_mask),
        "keep_count": int(keep_mask.sum()),
        "coverage_ratio": float(1.0 - keep_mask.mean()),
    }


def detect_jump_breakpoints(y: np.ndarray, *, jump_fraction: float = 0.05, max_breaks: int = 4) -> np.ndarray:
    # Detect likely jump points by large step changes between neighbors.
    """Detect large slope-change indices to split a series into local segments."""
    if y.size < 3:
        return np.empty(0, dtype=np.int64)

    slope = np.abs(np.diff(y))
    if np.all(slope == 0):
        return np.empty(0, dtype=np.int64)

    n_breaks = min(max_breaks, max(0, y.size // 500))
    if n_breaks <= 0:
        return np.empty(0, dtype=np.int64)
    threshold = np.quantile(slope, 1.0 - jump_fraction)
    candidate = np.flatnonzero(slope >= threshold) + 1
    if candidate.size <= n_breaks:
        return np.asarray(candidate, dtype=np.int64)

    selected = np.argpartition(slope, -n_breaks)[-n_breaks:]
    selected += 1
    return np.sort(selected.astype(np.int64))


def _piecewise_breakpoints_with_limits(
    series: TimeSeries,
    breakpoints: np.ndarray | None,
    *,
    jump_fraction: float,
    max_breaks: int,
) -> np.ndarray:
    # Pick split points and cap them to `max_breaks`.
    # Remove invalid points and keep the strongest jumps if too many exist.
    if breakpoints is None or breakpoints.size == 0:
        detected = detect_jump_breakpoints(series.y, jump_fraction=jump_fraction, max_breaks=max_breaks)
    else:
        detected = np.asarray(breakpoints, dtype=np.int64)
        detected = detected[(detected > 0) & (detected < series.sample_count - 1)]
        if detected.size == 0:
            return np.empty(0, dtype=np.int64)
        if detected.size > max_breaks:
            candidate_score = np.abs(np.diff(series.y)[detected - 1])
            keep = np.argpartition(candidate_score, -max_breaks)[-max_breaks:]
            detected = np.sort(detected[keep])
    return detected


def _piecewise_boundaries(sample_count: int, breakpoints: np.ndarray) -> np.ndarray:
    # Turn split points into segment boundaries.
    # Keep each segment at least 2 points so fitting is possible.
    raw_boundaries = np.array([0, *breakpoints.tolist(), sample_count], dtype=np.int64)
    raw_boundaries = np.unique(raw_boundaries)
    boundaries = [raw_boundaries[0]]
    for value in raw_boundaries[1:]:
        if value <= boundaries[-1]:
            continue
        if value - boundaries[-1] >= 2:
            boundaries.append(int(value))
    return np.array(boundaries, dtype=np.int64)


def _term_allocation(total_terms: int, segment_count: int) -> list[int]:
    # Split Fourier terms across segments as evenly as possible.
    # Any leftovers are given one by one in a round-robin loop.
    base = max(1, total_terms // max(segment_count, 1))
    allocation = [base for _ in range(segment_count)]
    extra = total_terms - base * segment_count
    idx = 0
    while extra > 0:
        allocation[idx % segment_count] += 1
        idx += 1
        extra -= 1
    return allocation


def compress_fourier_piecewise(
    series: TimeSeries,
    terms: int,
    *,
    breakpoints: np.ndarray | None = None,
    max_breaks: int = 4,
) -> PiecewiseModel:
    # Run one Fourier model for each local segment.
    # This limits global oversmoothing/spread from one local jump.
    """Compress with independent Fourier models per local segment."""
    if terms <= 0:
        raise ValueError("terms must be positive")
    breakpoints = _piecewise_breakpoints_with_limits(
        series,
        breakpoints,
        jump_fraction=0.05,
        max_breaks=max_breaks,
    )
    boundaries = _piecewise_boundaries(series.sample_count, breakpoints)

    if boundaries.size < 3:
        model = compress_fourier(series, terms=terms)
        return PiecewiseModel(
            breakpoints=np.empty(0, dtype=np.int64),
            segment_models=[model],
            reconstructed_y=model.reconstructed_y,
            metrics={
                "segment_count": 1,
                "terms_total": terms,
                "terms_by_segment": [terms],
                "global_max_jump": float(np.max(np.abs(np.diff(series.y)))) if series.sample_count >= 2 else 0.0,
            },
        )

    segment_count = boundaries.size - 1
    allocations = _term_allocation(terms, segment_count)
    reconstructed = np.empty_like(series.y, dtype=np.float64)
    segment_models: list[FourierModel] = []

    for start, stop, seg_terms in zip(boundaries[:-1], boundaries[1:], allocations, strict=False):
        seg_y = series.y[start:stop]
        if seg_y.size < 2:
            continue
        seg_x = np.linspace(0.0, 1.0, seg_y.size, dtype=np.float64)
        segment_series = TimeSeries(x=seg_x, y=seg_y, source=series.source)
        seg_model = compress_fourier(segment_series, terms=seg_terms)
        reconstructed[start:stop] = seg_model.reconstructed_y
        segment_models.append(seg_model)

    if not segment_models:
        model = compress_fourier(series, terms=terms)
        return PiecewiseModel(
            breakpoints=np.empty(0, dtype=np.int64),
            segment_models=[model],
            reconstructed_y=model.reconstructed_y,
            metrics={
                "segment_count": 1,
                "terms_total": terms,
                "terms_by_segment": [terms],
                "global_max_jump": float(np.max(np.abs(np.diff(series.y)))) if series.sample_count >= 2 else 0.0,
            },
        )

    max_jump = float(np.max(np.abs(np.diff(series.y)))) if series.sample_count >= 2 else 0.0
    return PiecewiseModel(
        breakpoints=breakpoints,
        segment_models=segment_models,
        reconstructed_y=reconstructed,
        metrics={
            "segment_count": len(segment_models),
            "terms_total": terms,
            "terms_by_segment": allocations[: len(segment_models)],
            "global_max_jump": max_jump,
        },
    )


def _fit_polynomial_segment(x: np.ndarray, y: np.ndarray, degree: int) -> np.ndarray:
    # Fit least-squares polynomial coefficients for one segment.
    # Normalize x first to avoid numeric issues.
    if x.size <= 1:
        raise ValueError("segment must contain at least two points")
    degree = int(degree)
    if degree < 0:
        raise ValueError("degree must be >= 0")
    degree = min(degree, max(0, x.size - 1))
    x0 = float(np.mean(x))
    x_scale = float(np.max(np.abs(x - x0)))
    if not np.isfinite(x_scale) or x_scale == 0.0:
        x_scale = 1.0
    x_n = (x - x0) / x_scale
    v = np.polynomial.polynomial.polyvander(x_n, degree)
    coeffs, *_ = np.linalg.lstsq(v, y, rcond=None)
    return np.asarray(coeffs, dtype=np.float64)


def _eval_polynomial_segment(x: np.ndarray, coeffs: np.ndarray, *, x0: float, x_scale: float) -> np.ndarray:
    # Evaluate the normalized polynomial back to original x coordinates.
    return np.polynomial.polynomial.polyval((x - x0) / x_scale, coeffs)


def compress_piecewise_polynomial(
    series: TimeSeries,
    degree: int = 3,
    *,
    breakpoints: np.ndarray | None = None,
    max_breaks: int = 4,
) -> PiecewisePolynomialModel:
    # Fit low-degree polynomials on short local blocks.
    # Useful for smooth curves with clear bend points.
    """Fit low-degree polynomials on local segments for locality-preserving baseline."""
    if degree < 0:
        raise ValueError("degree must be non-negative")
    breakpoints = _piecewise_breakpoints_with_limits(
        series,
        breakpoints,
        jump_fraction=0.05,
        max_breaks=max_breaks,
    )
    boundaries = _piecewise_boundaries(series.sample_count, breakpoints)
    min_len = max(2, degree + 1)

    reconstructed = np.empty_like(series.y, dtype=np.float64)
    segment_coeffs: list[np.ndarray] = []
    segment_intervals: list[tuple[float, float]] = []
    approximate_param_count = 0

    for start, stop in zip(boundaries[:-1], boundaries[1:], strict=False):
        seg_x = series.x[start:stop]
        seg_y = series.y[start:stop]
        if seg_y.size < min_len:
            reconstructed[start:stop] = np.interp(series.x[start:stop], seg_x, seg_y)
            seg_coeffs = np.array([0.0], dtype=np.float64)
            parameters = 2
        else:
            seg_coeffs = _fit_polynomial_segment(seg_x, seg_y, degree=degree)
            x0 = float(np.mean(seg_x))
            x_scale = float(np.max(np.abs(seg_x - x0)))
            if not np.isfinite(x_scale) or x_scale == 0.0:
                x_scale = 1.0
            reconstructed[start:stop] = _eval_polynomial_segment(seg_x, seg_coeffs, x0=x0, x_scale=x_scale)
            parameters = int(seg_coeffs.size) + 2
        segment_coeffs.append(seg_coeffs)
        segment_intervals.append((float(series.x[start]), float(series.x[stop - 1])))
        approximate_param_count += parameters

    return PiecewisePolynomialModel(
        breakpoints=breakpoints,
        segment_coeffs=segment_coeffs,
        segment_intervals=segment_intervals,
        reconstructed_y=reconstructed,
        metrics={
            "segment_count": len(segment_coeffs),
            "degree": int(degree),
            "approx_parameter_count": int(approximate_param_count),
        },
    )


def _largest_power_of_two_leq(value: int) -> int:
    # Haar helper needs input length as a power of two.
    if value < 2:
        raise ValueError("value must be >= 2")
    return 1 << (value.bit_length() - 1)


def _haar_decompose(signal: np.ndarray, level: int) -> tuple[np.ndarray, list[np.ndarray]]:
    # Repeatedly split signal into coarse average and detail parts.
    levels: list[np.ndarray] = []
    approx = np.asarray(signal, dtype=np.float64).copy()
    for _ in range(level):
        n = approx.size
        if n < 2 or (n & 1):
            break
        even = approx[::2]
        odd = approx[1::2]
        detail = (even - odd) / np.sqrt(2.0)
        approx = (even + odd) / np.sqrt(2.0)
        levels.append(detail)
    return approx, levels


def _haar_reconstruct(approx: np.ndarray, levels: list[np.ndarray]) -> np.ndarray:
    # Rebuild signal from coarse part + detail levels using inverse Haar formulas.
    signal = approx.astype(np.float64, copy=True)
    for detail in reversed(levels):
        if signal.size != detail.size:
            raise ValueError("invalid Haar detail hierarchy")
        combined = np.empty(detail.size * 2, dtype=np.float64)
        combined[0::2] = (signal + detail) / np.sqrt(2.0)
        combined[1::2] = (signal - detail) / np.sqrt(2.0)
        signal = combined
    return signal


def compress_haar_threshold(
    series: TimeSeries,
    *,
    level: int = 3,
    threshold: float | None = None,
) -> HaarWaveletModel:
    # Keep only large wavelet details; drop tiny ones.
    # Small details usually behave like noise or very fine texture.
    """Research baseline: Haar-thresholded wavelet compression."""
    if level <= 0:
        raise ValueError("level must be > 0")
    if series.sample_count < 2:
        raise ValueError("series must contain at least 2 samples")

    n = _largest_power_of_two_leq(series.sample_count)
    x_src = np.arange(n, dtype=np.float64)
    y_src = series.y[:n]

    approx, levels = _haar_decompose(y_src, level=level)
    if not levels:
        reconstructed = y_src.astype(np.float64, copy=True)
        return HaarWaveletModel(
            reconstructed_y=np.interp(np.arange(series.sample_count), x_src, reconstructed),
            metrics={
                "level": float(0),
                "threshold": float(0.0),
                "kept_coefficients": float(n),
                "total_coefficients": float(n),
                "residual_payload_ratio": 1.0,
            },
        )

    if threshold is None:
        all_detail = np.concatenate(levels)
        threshold = 0.5 * np.quantile(np.abs(all_detail), 0.90)
    if threshold < 0.0:
        raise ValueError("threshold must be non-negative")

    kept = 0
    sparse_levels: list[np.ndarray] = []
    for detail in levels:
        keep = np.abs(detail) >= threshold
        sparse_levels.append(detail * keep.astype(float))
        kept += int(keep.sum())

    reconstructed_n = _haar_reconstruct(approx, sparse_levels)
    reconstructed = np.interp(
        np.linspace(0.0, float(n - 1), series.sample_count, dtype=np.float64),
        x_src,
        reconstructed_n,
    )
    total_coeff = float(n)
    return HaarWaveletModel(
        reconstructed_y=reconstructed,
        metrics={
            "level": float(min(level, len(levels))),
            "threshold": float(threshold),
            "kept_coefficients": float(kept + approx.size),
            "total_coefficients": float(total_coeff),
            "residual_payload_ratio": float((kept + approx.size) / total_coeff) if total_coeff else 1.0,
        },
    )


def locality_leakage_metric(
    series: TimeSeries,
    reconstructed: np.ndarray,
    *,
    window: int = 64,
) -> dict[str, Any]:
    # Compare reconstruction error near jump points and in smooth areas.
    # Lower leakage means errors stay local instead of spread globally.
    """Return residual leakage ratio around sharp transitions and in smooth zones."""
    if series.sample_count != reconstructed.size:
        raise ValueError("reconstructed length must match series.sample_count")
    if window < 1:
        raise ValueError("window must be >= 1")

    residual = np.abs(series.y - reconstructed)
    if series.sample_count < 8:
        return {
            "global_rmse": float(np.sqrt(np.mean(residual * residual))),
            "global_max": float(np.max(residual)),
            "local_rmse": float(np.sqrt(np.mean(residual * residual))),
            "far_rmse": float(np.sqrt(np.mean(residual * residual))),
            "local_ratio": 1.0,
            "leakage_ratio": 1.0,
            "jump_count": 0,
        }

    jump_points = detect_jump_breakpoints(series.y, max_breaks=8)
    if jump_points.size == 0:
        jump_points = np.array([int(np.argmax(np.abs(np.diff(series.y))) + 1)], dtype=np.int64)

    mask = np.ones(series.sample_count, dtype=bool)
    for point in jump_points:
        lo = max(0, point - window)
        hi = min(series.sample_count, point + window + 1)
        mask[lo:hi] = False
    if not np.any(mask):
        mask[:] = True

    local_error = residual[~mask]
    far_error = residual[mask]
    local_rmse = float(np.sqrt(np.mean(local_error * local_error)))
    far_rmse = float(np.sqrt(np.mean(far_error * far_error)))
    global_rmse = float(np.sqrt(np.mean(residual * residual)))
    global_max = float(np.max(residual))
    local_ratio = local_rmse / global_rmse if global_rmse else 0.0
    leakage = far_rmse / global_rmse if global_rmse else 0.0
    return {
        "global_rmse": global_rmse,
        "global_max": global_max,
        "local_rmse": local_rmse,
        "far_rmse": far_rmse,
        "local_ratio": local_ratio,
        "leakage_ratio": leakage,
        "jump_count": int(jump_points.size),
    }


def compress_fourier_with_uniform_param(
    series: TimeSeries,
    terms: int,
    *,
    reparametrize_to_uniform: bool = True,
) -> FourierModel:
    # For irregular x, rebuild x as a uniform index [0,1].
    # y values are unchanged; only the index spacing is normalized.
    """Fit Fourier on a uniform index when x sampling is irregular."""
    if terms <= 0:
        raise ValueError("terms must be positive")
    if not reparametrize_to_uniform:
        return compress_fourier(series, terms=terms)
    uniform = TimeSeries(
        x=np.linspace(0.0, 1.0, series.sample_count, dtype=np.float64),
        y=series.y,
        source=f"uniform:{series.source}",
    )
    return compress_fourier(uniform, terms=terms)


def compress_fourier_with_rdp_budget(
    series: TimeSeries,
    terms: int,
    *,
    target_keep_ratio: float = 0.08,
    min_keep: int = 128,
    max_keep: int | None = None,
) -> RDPPrefilteredFourierModel:
    # Viewport-aware baseline:
    # 1) simplify points with RDP,
    # 2) fit Fourier on simplified points,
    # 3) interpolate back to original x positions.
    if terms <= 0:
        raise ValueError("terms must be positive")
    if target_keep_ratio <= 0 or target_keep_ratio > 1:
        raise ValueError("target_keep_ratio must be in (0, 1]")
    if min_keep < 2:
        raise ValueError("min_keep must be >= 2")
    if series.sample_count < 2:
        raise ValueError("series must contain at least 2 samples")

    min_keep = max(2, int(min_keep))
    base_target = int(series.sample_count * target_keep_ratio)
    target_keep = max(min_keep, min(base_target, series.sample_count))
    if max_keep is not None:
        # Clamp requested point budget between minimum and optional maximum cap.
        target_keep = max(min_keep, min(target_keep, int(max_keep)))

    if target_keep >= series.sample_count:
        # Degenerate case: no prefilter needed.
        core = compress_fourier(series, terms=terms)
        return RDPPrefilteredFourierModel(
            prefilter=compress_rdp(series, epsilon=0.0),
            core_fourier=core,
            reconstructed_y=core.reconstructed_y,
            metrics={
                "keep_ratio_actual": 1.0,
                "target_keep_ratio": float(target_keep_ratio),
                **core.metrics,
            },
        )

    epsilon = _find_rdp_epsilon_for_target_count(series, target_keep)
    prefilter = compress_rdp(series, epsilon=epsilon)
    keep = max(2, int(len(prefilter.kept_indices)))
    if keep >= series.sample_count:
        core = compress_fourier(series, terms=terms)
        reconstructed = core.reconstructed_y
        reconstructed_prefilter = prefilter
    else:
        simplified = TimeSeries(x=prefilter.x, y=prefilter.y, source=f"rdp_budget:{series.source}")
        core = compress_fourier(simplified, terms=terms)
        reconstructed = np.interp(series.x, simplified.x, core.reconstructed_y)
        reconstructed_prefilter = prefilter

    metrics = dict(regression_metrics(series.y, reconstructed))
    metrics.update(
        {
            "target_keep_ratio": float(target_keep_ratio),
            "keep_ratio_actual": float(reconstructed_prefilter.parameter_count / series.sample_count),
            "rdp_kept_points": float(reconstructed_prefilter.parameter_count),
            "rdp_epsilon": float(reconstructed_prefilter.epsilon),
        }
    )
    return RDPPrefilteredFourierModel(
        prefilter=reconstructed_prefilter,
        core_fourier=core,
        reconstructed_y=reconstructed,
        metrics=metrics,
    )


def compress_multichannel_fourier_pca(
    channels: np.ndarray,
    terms: int,
    *,
    rank: int,
) -> dict[str, Any]:
    # Compress channels together by extracting shared latent axes (PCA/SVD),
    # then compress each axis with Fourier.
    """Compress multi-channel signals with PCA basis + Fourier on latent coefficients."""
    if channels.ndim != 2:
        raise ValueError("channels must be 2D [samples, channels]")
    if channels.shape[0] < 2:
        raise ValueError("at least 2 samples required")
    if terms <= 0:
        raise ValueError("terms must be positive")
    if rank <= 0:
        raise ValueError("rank must be positive")

    n_samples, n_channels = channels.shape
    rank = int(min(rank, n_channels))
    mean = np.mean(channels, axis=0, keepdims=True)
    centered = channels - mean
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    basis = vt[:rank].T
    scores = centered @ basis
    score_models = [
        compress_fourier(TimeSeries(np.arange(n_samples), scores[:, axis], source=f"latent-{axis}"), terms=terms)
        for axis in range(rank)
    ]
    score_recon = np.column_stack([model.reconstructed_y for model in score_models])
    reconstructed = score_recon @ basis.T + mean

    residual = channels - reconstructed
    return {
        "rank": rank,
        "terms": int(terms),
        "basis": basis,
        "mean": mean,
        "score_models": score_models,
        "reconstructed": reconstructed,
        "metrics": {
            "rmse": float(np.sqrt(np.mean(residual * residual))),
            "mae": float(np.mean(np.abs(residual))),
            "max_abs": float(np.max(np.abs(residual))),
            "parameter_count": float(rank * terms + rank * n_channels + n_channels),
        },
    }
