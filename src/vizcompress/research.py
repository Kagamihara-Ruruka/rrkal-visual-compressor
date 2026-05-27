from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from vizcompress.compressors import compress_fourier
from vizcompress.core import TimeSeries, FourierModel


@dataclass(frozen=True)
class PiecewiseModel:
    breakpoints: np.ndarray
    segment_models: list[FourierModel]
    reconstructed_y: np.ndarray
    metrics: dict[str, float]


def detect_jump_breakpoints(y: np.ndarray, *, jump_fraction: float = 0.05, max_breaks: int = 4) -> np.ndarray:
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


def _term_allocation(total_terms: int, segment_count: int) -> list[int]:
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
    """Compress with independent Fourier models per local segment."""
    if terms <= 0:
        raise ValueError("terms must be positive")
    if breakpoints is None or breakpoints.size == 0:
        breakpoints = detect_jump_breakpoints(series.y, max_breaks=max_breaks)
    else:
        breakpoints = np.asarray(breakpoints, dtype=np.int64)
        if breakpoints.size:
            breakpoints = breakpoints[(breakpoints > 0) & (breakpoints < series.sample_count - 1)]

    # Keep boundaries unique and enforce minimum segment length.
    raw_boundaries = np.array([0, *breakpoints.tolist(), series.sample_count], dtype=np.int64)
    raw_boundaries = np.unique(raw_boundaries)
    boundaries = [raw_boundaries[0]]
    for value in raw_boundaries[1:]:
        if value - boundaries[-1] >= 2:
            boundaries.append(int(value))
        elif value == raw_boundaries[-1]:
            continue
    boundaries = np.array(boundaries, dtype=np.int64)

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


def locality_leakage_metric(
    series: TimeSeries,
    reconstructed: np.ndarray,
    *,
    window: int = 64,
) -> dict[str, Any]:
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
            "local_to_global_ratio": 1.0,
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
